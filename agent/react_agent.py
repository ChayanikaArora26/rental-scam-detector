"""
agent/react_agent.py — ReAct-style agent using the Anthropic tool-use API.

Pattern: Reason → Act (tool call) → Observe (tool result) → repeat → Answer

Tools:
  search_analyses   — search past rental analyses in the DB
  summarise_records — ask Claude to summarise a list of records
  send_alert_email  — send an email alert (admin use)
  flag_document     — mark a past analysis for manual review

All user input is anonymised BEFORE reaching this module.
Full tool trace is logged to agent_logs (anonymised only).
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import anthropic
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database.models import AgentLog

log = logging.getLogger(__name__)
settings = get_settings()

MODEL = "claude-sonnet-4-20250514"
MAX_TURNS = 6   # safety limit on ReAct iterations

# ── Tool definitions ────────────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "search_analyses",
        "description": (
            "Search past rental document analyses in the database. "
            "Returns matching analyses ordered by recency."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "verdict":    {"type": "string", "description": "Filter by verdict substring e.g. 'HIGH RISK'"},
                "limit":      {"type": "integer", "description": "Max results (default 5, max 20)"},
            },
            "required": [],
        },
    },
    {
        "name": "summarise_records",
        "description": "Ask Claude to produce a short natural-language summary of a list of records.",
        "input_schema": {
            "type": "object",
            "properties": {
                "records":    {"type": "array",  "description": "List of record dicts to summarise"},
                "focus":      {"type": "string", "description": "What to focus on in the summary"},
            },
            "required": ["records"],
        },
    },
    {
        "name": "send_alert_email",
        "description": "Send a plain-text alert email. Admin-only action.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to":      {"type": "string", "description": "Recipient email"},
                "subject": {"type": "string"},
                "body":    {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "flag_document",
        "description": "Flag a past analysis for manual review.",
        "input_schema": {
            "type": "object",
            "properties": {
                "analysis_id": {"type": "string", "description": "UUID of the agent_log to flag"},
                "reason":      {"type": "string"},
            },
            "required": ["analysis_id", "reason"],
        },
    },
]

SYSTEM_PROMPT = """You are RentalGuard AI — a specialist assistant that helps users understand
rental document analysis results and Australian tenancy law.

You have tools to search past analyses and send administrative alerts.

Rules:
1. Only discuss rental documents and tenancy matters.
2. Never reveal raw PII — all inputs are pre-anonymised.
3. When uncertain, say so. Do not fabricate legal advice.
4. Recommend NSW Fair Trading or a tenancy advocate for formal legal questions.
5. Be concise and direct.
"""


# ── Tool execution ──────────────────────────────────────────────────────────

async def _execute_tool(
    name: str,
    inputs: dict,
    db: AsyncSession,
    client: anthropic.AsyncAnthropic,
) -> Any:
    if name == "search_analyses":
        verdict_filter = inputs.get("verdict", "")
        limit = min(int(inputs.get("limit", 5)), 20)
        q = select(AgentLog).order_by(AgentLog.created_at.desc()).limit(limit)
        if verdict_filter:
            # Safe parameterised filter on JSONB/text
            q = q.where(AgentLog.agent_response.ilike(f"%{verdict_filter}%"))
        rows = (await db.execute(q)).scalars().all()
        return [
            {
                "id":       r.id,
                "input":    r.anonymised_input[:200],
                "response": (r.agent_response or "")[:200],
                "created":  r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    elif name == "summarise_records":
        records = inputs.get("records", [])
        focus   = inputs.get("focus", "key patterns and risk signals")
        if not records:
            return "No records to summarise."
        prompt = f"Summarise these records focusing on {focus}:\n\n{json.dumps(records, indent=2)}"
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    elif name == "send_alert_email":
        from email_service.service import _send
        await _send(inputs["to"], inputs["subject"], f"<pre>{inputs['body']}</pre>")
        return f"Alert email sent to {inputs['to']}"

    elif name == "flag_document":
        analysis_id = inputs["analysis_id"]
        reason      = inputs["reason"]
        # Add a flag note to tool_calls_json
        result = await db.execute(select(AgentLog).where(AgentLog.id == analysis_id))
        log_row = result.scalar_one_or_none()
        if not log_row:
            return f"Analysis {analysis_id} not found"
        existing = log_row.tool_calls_json or {}
        existing["flagged"] = {"reason": reason, "at": datetime.now(timezone.utc).isoformat()}
        log_row.tool_calls_json = existing
        return f"Analysis {analysis_id} flagged: {reason}"

    return f"Unknown tool: {name}"


# ── ReAct loop ──────────────────────────────────────────────────────────────

async def run_agent(
    message: str,
    db: AsyncSession,
    user_id: str | None = None,
) -> dict:
    """
    Run the ReAct agent.

    Args:
        message:  Already-anonymised user message
        db:       DB session (for tool use + logging)
        user_id:  Optional authenticated user

    Returns:
        {
          "response":   str,
          "tools_used": list[str],
          "tokens":     int,
        }
    """
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    messages = [{"role": "user", "content": message}]
    tools_used: list[str] = []
    tool_trace: list[dict] = []
    total_tokens = 0

    for turn in range(MAX_TURNS):
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        total_tokens += resp.usage.input_tokens + resp.usage.output_tokens

        # Append assistant turn
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason == "end_turn":
            # Final text response
            final_text = next(
                (b.text for b in resp.content if hasattr(b, "text")), ""
            )
            break

        if resp.stop_reason != "tool_use":
            break

        # Execute all tool calls in this turn
        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            tools_used.append(block.name)
            log.info("Agent calling tool: %s(%s)", block.name, block.input)
            result = await _execute_tool(block.name, block.input, db, client)
            tool_trace.append({"tool": block.name, "input": block.input, "output": result})
            tool_results.append({
                "type":        "tool_result",
                "tool_use_id": block.id,
                "content":     json.dumps(result) if not isinstance(result, str) else result,
            })

        messages.append({"role": "user", "content": tool_results})

    else:
        # Exhausted turns
        final_text = "I've reached the maximum reasoning steps. Please refine your question."

    # ── Log to DB (anonymised input only) ─────────────────────────
    agent_log = AgentLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        anonymised_input=message[:4000],
        agent_response=final_text[:4000],
        tool_calls_json={"turns": tool_trace, "total_tokens": total_tokens},
        tokens_used=total_tokens,
    )
    db.add(agent_log)

    return {
        "response":   final_text,
        "tools_used": list(dict.fromkeys(tools_used)),  # deduplicated
        "tokens":     total_tokens,
    }
