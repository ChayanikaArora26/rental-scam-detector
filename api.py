"""
api.py — FastAPI backend for the Rental Scam Detector.

Run:
    uvicorn api:app --reload --port 8000

Endpoints:
    GET  /                      → serves static/index.html
    POST /api/analyse           → multipart: file?, text?, name, email
    POST /api/chat              → JSON: {messages, context?} → chatbot reply
    GET  /api/history/{email}   → list of past analyses for that email
    GET  /api/status            → server health + LLM provider info
"""

import asyncio
import os
import pathlib
import tempfile
from contextlib import asynccontextmanager
from typing import Any

import requests as _requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database
import download_data
import llm_analyser
from rental_scam_detector import (
    RentalScamDetector,
    load_cuad,
    load_document,
    load_forms_and_chunk,
    FORMS_DIR,
    EMBED_CACHE,
)

# ── Paths ────────────────────────────────────────────────────────
BASE_DIR   = pathlib.Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)


# ── Startup: load detector once ──────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    download_data.run()   # no-op if data already present
    print("Initialising database …")
    database.init_db()

    print("Loading detector …")
    au_texts = [r["text"] for r in load_forms_and_chunk(FORMS_DIR)]
    if EMBED_CACHE.exists():
        # Embedding cache baked into image — skip loading CUAD to stay under 512MB RAM
        print("  Embedding cache found — skipping CUAD load.")
        app.state.detector = RentalScamDetector(au_texts)
    else:
        print("  No cache — loading CUAD to build embeddings (first run only)…")
        _, cuad_texts = load_cuad()
        app.state.detector = RentalScamDetector(au_texts + cuad_texts)
    print(f"Ready  |  LLM provider: {llm_analyser.PROVIDER}")
    yield


app = FastAPI(title="Rental Scam Detector API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (CSS, JS assets if any)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Pydantic models ───────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str      # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context: dict[str, Any] | None = None

class ScrapeRequest(BaseModel):
    url: str


# ── Routes ───────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serve the single-page HTML app."""
    index = STATIC_DIR / "index.html"
    if not index.exists():
        return JSONResponse({"error": "Frontend not found. Place index.html in static/"}, status_code=404)
    return FileResponse(str(index))


@app.get("/api/status")
def status():
    return {
        "ok": True,
        "llm_provider": llm_analyser.PROVIDER,
        "llm_enabled":  llm_analyser.ENABLED,
    }


@app.post("/api/analyse")
async def analyse(
    file:  UploadFile | None = File(default=None),
    text:  str               = Form(default=""),
    name:  str               = Form(default=""),
    email: str               = Form(default=""),
):
    """
    Analyse a rental document or pasted text for scam signals.

    Accepts multipart/form-data with either:
      - `file`  — a PDF or DOCX upload
      - `text`  — plain text (listing / agreement body)
    Plus optional `name` and `email` to save history.
    """
    raw_text = ""
    filename = ""

    # Extract text from uploaded file
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

    # Fall back to pasted text
    if not raw_text.strip():
        raw_text = text.strip()

    if not raw_text:
        raise HTTPException(400, "Provide a file or paste some text.")

    # Run detection
    detector = app.state.detector
    result   = detector.analyse(raw_text)
    llm_out  = llm_analyser.explain(result)

    # Persist if user supplied email
    if email.strip():
        uid = database.get_or_create_user(name or email.split("@")[0], email)
        database.save_analysis(uid, result, llm_out, filename)

    # Serialise (DataFrame → list of dicts)
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
    """
    Multi-turn chatbot for Australian tenancy law questions.

    Body (JSON):
      messages — list of {role: "user"|"assistant", content: str}
      context  — optional analysis result to inject as document context
    """
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    reply = llm_analyser.chat(messages, req.context)
    return {"reply": reply, "provider": llm_analyser.PROVIDER}


@app.post("/api/scrape")
async def scrape_url(req: ScrapeRequest):
    """
    Fetch a rental listing URL and extract readable text for analysis.
    Supports Gumtree, Domain, RealEstate.com.au, and any public page.
    """
    url = req.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    def _fetch(u: str) -> str:
        r = _requests.get(
            u, timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (compatible; RentalScamDetector/1.0)"},
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
            raise HTTPException(422, "Page returned too little text — it may require a login or block bots.")
        return {"text": text, "chars": len(text), "url": url}
    except _requests.RequestException as e:
        raise HTTPException(422, f"Could not fetch URL: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error processing page: {e}")


@app.get("/api/history/{email}")
def history(email: str):
    """Return all past analyses for this email address."""
    rows = database.get_user_history(email)
    return {"email": email, "count": len(rows), "analyses": rows}
