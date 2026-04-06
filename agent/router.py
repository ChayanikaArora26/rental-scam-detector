"""
agent/router.py — POST /agent/run

Accepts a user message, anonymises it, runs the ReAct agent, returns response.
Requires authentication (verified user).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent.react_agent import run_agent
from anonymiser.pipeline import anonymise
from auth.dependencies import get_current_verified_user
from database.models import User
from database.session import get_db

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentRequest(BaseModel):
    message: str


class AgentResponse(BaseModel):
    response: str
    tools_used: list[str]
    tokens: int
    pii_redacted: bool


@router.post("/run", response_model=AgentResponse)
async def agent_run(
    body: AgentRequest,
    user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(body.message) > 8000:
        raise HTTPException(status_code=400, detail="Message too long (max 8000 chars)")

    # ── Anonymise before LLM ──────────────────────────────────────
    clean_text, pii_map = anonymise(body.message)
    pii_redacted = bool(pii_map)

    result = await run_agent(clean_text, db, user_id=user.id)

    return AgentResponse(
        response=result["response"],
        tools_used=result["tools_used"],
        tokens=result["tokens"],
        pii_redacted=pii_redacted,
    )
