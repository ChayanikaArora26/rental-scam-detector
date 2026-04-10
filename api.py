"""
api.py — RentalGuard FastAPI backend (full-stack).

Endpoints:
  Auth:    /auth/*         — register, login, refresh, logout, verify, reset
  Agent:   /agent/run      — ReAct LLM agent (authenticated)
  API:     /api/analyse    — rental document analysis (public)
           /api/chat       — legacy chatbot
           /api/history/*  — analysis history
           /api/status     — health check
           /api/scrape     — URL scraper
"""

import asyncio
import logging
import os
import pathlib
import tempfile
from contextlib import asynccontextmanager
from typing import Any

import requests as _requests
from bs4 import BeautifulSoup
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# ── Internal modules ──────────────────────────────────────────────
import sqlite_database as sqlite_db    # existing SQLite layer (legacy)
import download_data
import llm_analyser
from auth.router import router as auth_router
from agent.router import router as agent_router
from config import get_settings
from database.session import engine, get_db
from database.models import Base
from security.rate_limiter import limiter
from email_service.service import send_analysis_report
from rental_scam_detector import (
    RentalScamDetector,
    load_cuad,
    load_document,
    load_forms_and_chunk,
    FORMS_DIR,
    EMBED_CACHE,
)

log = logging.getLogger(__name__)
settings = get_settings()

BASE_DIR   = pathlib.Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)


# ── Startup / shutdown ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Download reference data
    download_data.run()

    # 2. Bootstrap legacy SQLite DB
    sqlite_db.init_db()

    # 3. Create Postgres tables (create-if-not-exists for dev convenience)
    #    In production use: alembic upgrade head
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("PostgreSQL tables ready")
    except Exception as e:
        log.warning("PostgreSQL not available — auth/agent disabled: %s", e)

    # 4. Load ML detector
    log.info("Loading rental scam detector…")
    au_texts = [r["text"] for r in load_forms_and_chunk(FORMS_DIR)]
    if EMBED_CACHE.exists():
        app.state.detector = RentalScamDetector(au_texts)
    else:
        _, cuad_texts = load_cuad()
        app.state.detector = RentalScamDetector(au_texts + cuad_texts)

    log.info("Ready | LLM: %s", llm_analyser.PROVIDER)
    yield

    await engine.dispose()


# ── App ───────────────────────────────────────────────────────────
app = FastAPI(title="RentalGuard API", version="2.0.0", lifespan=lifespan)

# Rate limiter state
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda req, exc: JSONResponse(
        {"detail": "Too many requests — please slow down"},
        status_code=429,
    ),
)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        settings.APP_URL,
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Routers ───────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(agent_router)


# ── Pydantic models ───────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context: dict[str, Any] | None = None

class ScrapeRequest(BaseModel):
    url: str


# ── Existing API routes ───────────────────────────────────────────

@app.get("/", include_in_schema=False)
def serve_frontend():
    index = STATIC_DIR / "index.html"
    if not index.exists():
        return JSONResponse({"detail": "Frontend not deployed"}, 404)
    return FileResponse(str(index))


@app.get("/api/status")
def status():
    return {
        "ok":           True,
        "llm_provider": llm_analyser.PROVIDER,
        "llm_enabled":  llm_analyser.ENABLED,
        "version":      "2.0.0",
    }


@app.post("/api/analyse")
async def analyse(
    request: Request,
    file:    UploadFile | None = File(default=None),
    text:    str               = Form(default=""),
    name:    str               = Form(default=""),
    email:   str               = Form(default=""),
    db:      Any               = Depends(get_db),
):
    raw_text = ""
    filename = ""

    if file and file.filename:
        filename = file.filename
        suffix   = pathlib.Path(filename).suffix.lower()
        if suffix not in {".pdf", ".docx"}:
            raise HTTPException(400, "Only PDF and DOCX files are supported.")
        content = await file.read()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            raw_text = load_document(tmp_path)
        finally:
            os.unlink(tmp_path)

    if not raw_text.strip():
        raw_text = text.strip()

    if not raw_text:
        raise HTTPException(400, "Provide a file or paste some text.")

    detector = app.state.detector
    result   = detector.analyse(raw_text)
    llm_out  = llm_analyser.explain(result)

    # Save to SQLite history for anonymous/email users
    if email.strip():
        uid = sqlite_db.get_or_create_user(name or email.split("@")[0], email)
        sqlite_db.save_analysis(uid, result, llm_out, filename)

    # If a verified registered user is logged in, send them the report email
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from auth.service import decode_access_token, get_user_by_id
            payload = decode_access_token(auth_header.split(" ", 1)[1])
            user_id = payload.get("sub")
            if user_id:
                reg_user = await get_user_by_id(db, user_id)
                if reg_user and reg_user.is_verified:
                    asyncio.create_task(
                        send_analysis_report(reg_user.email, result, llm_out, filename)
                    )
        except Exception:
            pass  # token issues never block analysis

    details = (
        result["details"].to_dict(orient="records")
        if result["details"] is not None and not result["details"].empty
        else []
    )

    return {
        "verdict":       result["verdict"],
        "combined_risk": result["combined_risk"],
        "flag_score":    result["flag_score"],
        "n_flags":       result["n_flags"],
        "n_anomalous":   result["n_anomalous"],
        "total_chunks":  result["total_chunks"],
        "anomaly_pct":   result["anomaly_pct"],
        "red_flags":     result["red_flags"],
        "llm":           llm_out,
        "details":       details,
        "filename":      filename,
    }


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    reply = llm_analyser.chat(messages, req.context)
    return {"reply": reply, "provider": llm_analyser.PROVIDER}


@app.post("/api/scrape")
async def scrape_url(req: ScrapeRequest):
    url = req.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    def _fetch(u: str) -> str:
        r = _requests.get(
            u, timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (compatible; RentalGuard/2.0)"},
            allow_redirects=True,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe", "noscript"]):
            tag.decompose()
        lines = [l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()]
        return "\n".join(lines)[:40000]

    try:
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, _fetch, url)
        if len(text) < 100:
            raise HTTPException(422, "Page returned too little text.")
        return {"text": text, "chars": len(text), "url": url}
    except _requests.RequestException as e:
        raise HTTPException(422, f"Could not fetch URL: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error processing page: {e}")


@app.get("/api/history/{email}")
def history(email: str):
    rows = sqlite_db.get_user_history(email)
    return {"email": email, "count": len(rows), "analyses": rows}
