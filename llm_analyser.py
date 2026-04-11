"""
llm_analyser.py — LLM layer for the Rental Scam Detector.

Priority chain (first available wins):
  1. ANTHROPIC_API_KEY  → Claude Haiku  (best quality)
  2. HF_TOKEN          → Mistral-7B via HuggingFace Inference API (free)
  3. neither           → rule-based fallback (always works)

To activate Claude:
    export ANTHROPIC_API_KEY=sk-ant-...

To activate HuggingFace (free):
    export HF_TOKEN=hf_...
    (Get a free token at huggingface.co → Settings → Access Tokens)

Then restart the server.

Public functions:
  explain(result)           → structured analysis dict
  chat(messages, context)   → str reply for multi-turn chatbot
"""

import os
import json
from pathlib import Path

# Load .env so ANTHROPIC_API_KEY is available even without shell export
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path, override=False)
    except ImportError:
        pass

# ── Provider selection (lazy — checked at call time, not import time) ───────
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
HF_MODEL     = "mistralai/Mistral-7B-Instruct-v0.3"

def _make_claude_client():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=key)
    except ImportError:
        return None

def _make_hf_client():
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        return None
    try:
        from huggingface_hub import InferenceClient
        return InferenceClient(token=token)
    except ImportError:
        return None

def _get_provider() -> tuple:
    """Return (claude_client, hf_client, provider_name) — always re-reads env vars."""
    claude = _make_claude_client()
    if claude:
        return claude, None, "claude"
    hf = _make_hf_client()
    if hf:
        return None, hf, "huggingface"
    return None, None, "rule-based"

# Module-level names kept for /api/status — refreshed on each call below
_claude_client, _hf_client, PROVIDER = _get_provider()
ENABLED = PROVIDER != "rule-based"

# ── Shared prompt builder ────────────────────────────────────────
def _build_prompt(result: dict) -> str:
    flags_text = "\n".join(
        f"- [{rf.get('severity_label','?')}] {rf['flag']}\n  Exact text found: «{rf['snippet']}»"
        for rf in result.get("red_flags", [])
    ) or "None"

    anomalous_section = ""
    details = result.get("details")
    if details is not None and not details.empty:
        bad = details[details["anomalous"]]["chunk"].tolist()[:5]
        if bad:
            bullet_chunks = "\n".join("- " + c[:200] for c in bad)
            anomalous_section = "Top anomalous clauses:\n" + bullet_chunks

    doc_excerpt = result.get("doc_text", "")[:3000]
    verdict     = result['verdict']
    risk        = result['combined_risk']
    n_flags     = result['n_flags']
    n_anomalous = result['n_anomalous']
    total       = result['total_chunks']

    return f"""You are an expert Australian tenancy lawyer reviewing a rental document for a student renter.

DOCUMENT EXCERPT (first 3000 chars):
\"\"\"
{doc_excerpt}
\"\"\"

AUTOMATED SCAN RESULTS:
- Overall verdict: {verdict}
- Risk score: {risk}%
- Red flags found ({n_flags}):
{flags_text}
- Anomalous clauses (not found in any real AU lease): {n_anomalous} of {total} chunks
{anomalous_section}

Using BOTH the document text and the scan results above, respond in exactly this JSON format (no markdown fences, no extra text):
{{
  "summary": "<2-3 sentences: what is this document, what is the overall risk, and the single most important thing the renter needs to know>",
  "clause_advice": ["<for each red flag: explain in plain English WHY it is suspicious and what harm it could cause the renter>"],
  "user_action": "<exactly 3 bullet points starting with bullet character of concrete next steps the renter should take>"
}}

Rules:
- Be specific and reference the actual flagged text, not generic advice
- Each clause_advice item must explain the real-world risk to the renter
- If no red flags, say so clearly and note any other concerns from the document
- Assume the reader has never rented before and does not know Australian law"""


# ── Main public function ─────────────────────────────────────────
def explain(result: dict) -> dict:
    """
    Produce a plain-English risk report using the best available LLM.

    Parameters
    ──────────
    result — dict returned by RentalScamDetector.analyse()

    Returns
    ───────
    {
        "summary":       str        — 2-3 sentence overall risk explanation
        "clause_advice": list[str]  — one sentence per red flag
        "user_action":   str        — 3 bullet-point action items
        "powered_by_ai": bool       — False if rule-based fallback used
        "provider":      str        — "claude" | "huggingface" | "rule-based"
    }
    """
    claude, hf, _ = _get_provider()
    if claude:
        return _explain_claude(result, claude)
    if hf:
        return _explain_hf(result, hf)
    return _fallback(result)


# ── Claude implementation ────────────────────────────────────────
def _explain_claude(result: dict, client=None) -> dict:
    if client is None:
        client = _claude_client
    try:
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": _build_prompt(result)}],
        )
        parsed = json.loads(msg.content[0].text.strip())
        return {**parsed, "powered_by_ai": True, "provider": "claude"}
    except Exception as e:
        return {**_fallback(result), "error": str(e)}


# ── HuggingFace implementation ───────────────────────────────────
def _explain_hf(result: dict, client=None) -> dict:
    if client is None:
        client = _hf_client
    prompt = _build_prompt(result)
    # Mistral instruct format
    formatted = f"[INST] {prompt} [/INST]"
    try:
        raw = client.text_generation(
            formatted,
            model=HF_MODEL,
            max_new_tokens=500,
            temperature=0.3,
            do_sample=True,
        )
        # Strip any accidental leading/trailing whitespace or markdown
        raw = raw.strip().lstrip("```json").rstrip("```").strip()
        parsed = json.loads(raw)
        return {**parsed, "powered_by_ai": True, "provider": "huggingface"}
    except Exception as e:
        return {**_fallback(result), "error": str(e), "provider": "huggingface"}


# ── Rule-based fallback ──────────────────────────────────────────
def _fallback(result: dict) -> dict:
    risk = result["combined_risk"]
    n    = result["n_flags"]

    if risk >= 40:
        summary = (
            f"This listing has {n} serious warning sign(s) and a risk score of {risk}%. "
            "It shows multiple patterns strongly associated with rental fraud in Australia."
        )
    elif risk >= 20:
        summary = (
            f"This listing has {n} warning sign(s) and a risk score of {risk}%. "
            "Proceed with caution and verify the landlord's identity before paying anything."
        )
    else:
        summary = (
            f"Risk score is {risk}%. No major red flags detected. "
            "This looks broadly consistent with a standard Australian tenancy agreement."
        )

    advice = [
        f"{rf['flag']} — verify this before signing."
        for rf in result.get("red_flags", [])
    ]

    action = (
        "• Never pay a bond via Western Union, gift cards, or cryptocurrency.\n"
        "• Always inspect the property in person before signing or paying.\n"
        "• Check the landlord or agent on the NSW Fair Trading register (or your state equivalent)."
    )

    return {
        "summary":       summary,
        "clause_advice": advice,
        "user_action":   action,
        "powered_by_ai": False,
        "provider":      "rule-based",
    }


# ═══════════════════════════════════════════════════════════════
# CHATBOT
# ═══════════════════════════════════════════════════════════════

_CHAT_SYSTEM = (
    "You are a knowledgeable and friendly Australian tenancy law assistant. "
    "You help renters understand their rights, spot rental scam patterns, and "
    "navigate rental agreements in Australia. Be concise, practical, and empathetic. "
    "When relevant, cite specific Australian laws such as the Residential Tenancies "
    "Act 2010 (NSW), Residential Tenancies Act 1997 (VIC), or the relevant state "
    "authority (NSW Fair Trading, Consumer Affairs Victoria, etc.). "
    "If you don't know something, say so clearly and point to the right authority."
)


def _build_chat_system(context: dict | None) -> str:
    """Build system prompt, optionally injecting last analysis context."""
    sys = _CHAT_SYSTEM
    if context:
        flags_text = "\n".join(
            f"  - {rf['flag']}: «{rf['snippet']}»"
            for rf in context.get("red_flags", [])
        ) or "  None"
        sys += (
            "\n\nDOCUMENT CONTEXT — the user has just analysed a rental document:\n"
            f"  Verdict: {context.get('verdict', 'N/A')}\n"
            f"  Risk Score: {context.get('combined_risk', 0)}%\n"
            f"  Red Flags Triggered ({context.get('n_flags', 0)}):\n{flags_text}\n"
            f"  Anomalous Chunks: {context.get('n_anomalous', 0)} of {context.get('total_chunks', 0)}\n"
            "Use this context when answering questions about 'this document' or 'this listing'."
        )
    return sys


def chat(messages: list, context: dict | None = None) -> str:
    """
    Multi-turn chatbot for Australian tenancy law questions.

    Parameters
    ──────────
    messages : list of {role: "user"|"assistant", content: str}
    context  : optional result dict from RentalScamDetector.analyse()

    Returns
    ───────
    str — the assistant's reply
    """
    claude, hf, _ = _get_provider()
    if claude:
        return _chat_claude(messages, context, claude)
    if hf:
        return _chat_hf(messages, context, hf)
    return _chat_fallback(messages, context)


def _chat_claude(messages: list, context: dict | None, client=None) -> str:
    if client is None:
        client = _claude_client
    try:
        system = _build_chat_system(context)
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=800,
            system=system,
            messages=messages,
        )
        return msg.content[0].text.strip()
    except Exception as e:
        return f"Sorry, I hit an error talking to Claude: {e}"


def _chat_hf(messages: list, context: dict | None, client=None) -> str:
    if client is None:
        client = _hf_client
    try:
        system = _build_chat_system(context)
        full_messages = [{"role": "system", "content": system}] + list(messages)
        response = client.chat_completion(
            model=HF_MODEL,
            messages=full_messages,
            max_tokens=600,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        # fall through to keyword fallback
        return _chat_fallback(messages, context)


def _chat_fallback(messages: list, context: dict | None) -> str:
    """Keyword-based fallback for when no LLM provider is configured."""
    last = messages[-1]["content"].lower() if messages else ""

    # Only scan USER messages for context (bot replies pollute keyword detection)
    user_recent = " ".join(
        m["content"].lower() for m in messages[-6:] if m.get("role") == "user"
    )

    def _has(*words) -> bool:
        return any(w in last for w in words)

    def _ctx(*words) -> bool:
        return any(w in user_recent for w in words)

    # ── Entry / inspection — check FIRST (before eviction/notice overlap) ──
    if _has("entry", "enter", "entering", "access", "come in", "landlord come",
            "inspect", "inspection", "notice to enter", "right to enter",
            "without notice", "any time", "anytime", "turn up"):
        return (
            "In NSW, landlords must give **at least 24 hours written notice** before entering. "
            "They can only enter for specific reasons (routine inspection, repairs, showing to buyers). "
            "Routine inspections are limited to **4 times per year**. "
            "You have the right to be present. Entry without notice — except genuine emergencies — "
            "is illegal and can be reported to **NSW Fair Trading (13 32 20)**."
        )

    # ── Repairs ───────────────────────────────────────────────────
    if _has("repair", "maintenance", "maintain", "fix", "broken", "mould", "mold",
            "hot water", "heater", "plumb", "leak", "pest", "rodent") \
       or (_ctx("repair", "maintenance", "fix", "broken") and _has("who", "pay", "cost", "responsible", "liable", "have to", "must", "refuse", "won't", "wont")):
        if _has("refuse", "won't", "wont", "ignor", "not fix", "not respond"):
            return (
                "If your landlord refuses to repair:\n"
                "• Send a **written request** via email/letter — this is your evidence\n"
                "• Give a reasonable timeframe (7 days non-urgent, immediate for urgent)\n"
                "• If ignored, apply to **NCAT** (NSW) for a repair order — free and binding\n"
                "• For urgent issues (no hot water, gas leak), you can arrange repairs yourself and reclaim costs up to 2 weeks rent"
            )
        return (
            "Landlords must keep the property in reasonable repair under the Residential Tenancies Act. "
            "They pay for repairs unless you caused the damage.\n\n"
            "For **urgent repairs** (burst pipe, no hot water, broken heater in winter):\n"
            "• Contact landlord immediately in writing\n"
            "• If no response, arrange the repair yourself (up to 2 weeks rent cost) and claim it back\n"
            "• Always keep receipts and document everything in writing."
        )

    # ── Bond / deposit ────────────────────────────────────────────
    if _has("bond", "deposit", "security deposit"):
        return (
            "In NSW, the maximum bond is **4 weeks rent**. Key rules:\n"
            "• Landlord must lodge it with **NSW Fair Trading** within 10 working days\n"
            "• You get it back when you leave, minus any legitimate deductions\n"
            "• Never pay bond via cash, crypto, or wire transfer — use the official rental bond portal\n"
            "• Disputes about deductions go to the **Rental Bond Board** or **NCAT**"
        )

    # ── Scams ─────────────────────────────────────────────────────
    if _has("scam", "fraud", "fake", "suspicious", "western union", "crypto", "bitcoin",
            "gift card", "wire transfer", "overseas landlord", "keys by post"):
        return (
            "Common Australian rental scams to watch for:\n"
            "• Bond or rent requested before you've inspected the property\n"
            "• Overseas landlord who can't meet — keys sent by post after payment\n"
            "• Payment via Western Union, gift cards, crypto, or wire transfer\n"
            "• Listings well below market rent with pressure to act fast\n"
            "• WhatsApp-only contact, refusing video calls or in-person viewing\n\n"
            "If you suspect a scam: **do not pay anything** and report to "
            "**NSW Fair Trading (13 32 20)** or **Scamwatch (scamwatch.gov.au)**."
        )

    # ── Eviction / termination ────────────────────────────────────
    if _has("evict", "eviction", "terminate", "end lease", "vacate", "kicked out",
            "end tenancy", "leave the property"):
        return (
            "In NSW, a landlord must give written notice before ending a tenancy:\n"
            "• **End of fixed term (no grounds)**: 90 days\n"
            "• **Selling the property**: 30 days\n"
            "• **Breach of agreement**: 14 days\n\n"
            "You cannot be physically removed without a **NCAT order** if you dispute it. "
            "Contact the **Tenants' Union of NSW (02 8117 3700)** for free advice."
        )

    # ── Rent increases ────────────────────────────────────────────
    if _has("rent increase", "rent rise", "raise rent", "increase rent", "put up rent",
            "rent going up", "higher rent", "rent hike"):
        return (
            "In NSW, rent can only be increased **once every 12 months** and requires "
            "**60 days written notice**.\n\n"
            "If the increase seems excessive:\n"
            "• Apply to **NCAT within 30 days** of receiving the notice\n"
            "• The tribunal will compare your rent to local market rates\n"
            "• You don't have to move out while disputing it"
        )

    # ── Tribunal / dispute ────────────────────────────────────────
    if _has("fair trading", "ncat", "tribunal", "complaint", "dispute", "help",
            "who do i call", "who should i contact", "where do i go"):
        return (
            "For tenancy disputes in NSW:\n"
            "• **NSW Fair Trading (13 32 20)** — free mediation, first step\n"
            "• **NCAT (ncat.nsw.gov.au)** — binding tribunal decisions, low-cost\n"
            "• **Tenants' Union of NSW (02 8117 3700)** — free legal advice\n\n"
            "Other states:\n"
            "• VIC: Consumer Affairs Victoria — 1300 55 81 81\n"
            "• QLD: Residential Tenancies Authority — 1300 366 311\n"
            "• WA: Department of Mines, Industry Regulation and Safety — 1300 304 054"
        )

    # ── Rights / what can landlord do ────────────────────────────
    if _has("right", "rights", "allowed", "can they", "can landlord", "is it legal",
            "illegal", "law", "legal"):
        return (
            "As a tenant in Australia, your key rights include:\n"
            "• **Quiet enjoyment** — landlord cannot enter without proper notice\n"
            "• **Habitable property** — landlord must maintain it in good repair\n"
            "• **Bond protection** — must be lodged with the government, not kept by landlord\n"
            "• **Rent increase limits** — once per 12 months with 60 days notice (NSW)\n"
            "• **No illegal eviction** — landlord needs a tribunal order to remove you\n\n"
            "For your specific situation, contact **Tenants' Union of NSW (02 8117 3700)**."
        )

    # ── Generic follow-up with document context ───────────────────
    if context and any(w in last for w in ["this", "document", "agreement", "lease", "listing", "it"]):
        risk = context.get("combined_risk", 0)
        flags = context.get("red_flags", [])
        flag_list = "\n".join(f"• {rf['flag']}" for rf in flags[:5]) or "• None detected"
        return (
            f"Based on the analysed document (risk score: **{risk}%**):\n\n"
            f"Red flags found:\n{flag_list}\n\n"
            "For detailed legal advice on this specific document, consult the "
            "**Tenants' Union of NSW (02 8117 3700)** — they offer free advice."
        )

    return (
        "I can help with Australian tenancy questions. Try asking about:\n"
        "• **Bond** — limits, lodgement, getting it back\n"
        "• **Repairs** — who pays, what to do if landlord refuses\n"
        "• **Entry** — notice requirements, how many inspections are allowed\n"
        "• **Eviction** — notice periods and your rights\n"
        "• **Rent increases** — limits and how to challenge them\n"
        "• **Scams** — how to spot and report rental fraud\n"
        "• **Your rights** as a tenant under Australian law"
    )
