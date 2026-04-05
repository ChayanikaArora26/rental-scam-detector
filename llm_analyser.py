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

# ── Provider selection ───────────────────────────────────────────
_ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
_HF_TOKEN      = os.environ.get("HF_TOKEN", "")

_claude_client = None
_hf_client     = None

if _ANTHROPIC_KEY:
    try:
        import anthropic
        _claude_client = anthropic.Anthropic(api_key=_ANTHROPIC_KEY)
    except ImportError:
        pass

if not _claude_client and _HF_TOKEN:
    try:
        from huggingface_hub import InferenceClient
        _hf_client = InferenceClient(token=_HF_TOKEN)
    except ImportError:
        pass

PROVIDER = (
    "claude"       if _claude_client else
    "huggingface"  if _hf_client     else
    "rule-based"
)
ENABLED = PROVIDER != "rule-based"

CLAUDE_MODEL = "claude-haiku-4-5-20251001"
HF_MODEL     = "mistralai/Mistral-7B-Instruct-v0.3"

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
    if _claude_client:
        return _explain_claude(result)
    if _hf_client:
        return _explain_hf(result)
    return _fallback(result)


# ── Claude implementation ────────────────────────────────────────
def _explain_claude(result: dict) -> dict:
    try:
        msg = _claude_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": _build_prompt(result)}],
        )
        parsed = json.loads(msg.content[0].text.strip())
        return {**parsed, "powered_by_ai": True, "provider": "claude"}
    except Exception as e:
        return {**_fallback(result), "error": str(e)}


# ── HuggingFace implementation ───────────────────────────────────
def _explain_hf(result: dict) -> dict:
    prompt = _build_prompt(result)
    # Mistral instruct format
    formatted = f"[INST] {prompt} [/INST]"
    try:
        raw = _hf_client.text_generation(
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
    if _claude_client:
        return _chat_claude(messages, context)
    if _hf_client:
        return _chat_hf(messages, context)
    return _chat_fallback(messages, context)


def _chat_claude(messages: list, context: dict | None) -> str:
    try:
        system = _build_chat_system(context)
        msg = _claude_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=800,
            system=system,
            messages=messages,
        )
        return msg.content[0].text.strip()
    except Exception as e:
        return f"Sorry, I hit an error talking to Claude: {e}"


def _chat_hf(messages: list, context: dict | None) -> str:
    try:
        system = _build_chat_system(context)
        full_messages = [{"role": "system", "content": system}] + list(messages)
        response = _hf_client.chat_completion(
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
    """Keyword-based fallback that tracks recent conversation context."""
    last = messages[-1]["content"].lower() if messages else ""
    # Scan the last 5 messages (including current) for topic context
    recent = " ".join(m["content"].lower() for m in messages[-5:])

    # ── Topic detectors (recent context, not just last message) ──
    _repair_ctx  = any(w in recent for w in ["repair", "maintenance", "fix", "broken", "mould", "mold", "hot water", "heater", "plumb"])
    _bond_ctx    = any(w in recent for w in ["bond", "deposit", "security deposit"])
    _evict_ctx   = any(w in recent for w in ["evict", "notice", "terminate", "end lease", "vacate"])
    _entry_ctx   = any(w in recent for w in ["inspect", "entry", "enter", "access"])
    _rent_ctx    = any(w in recent for w in ["rent increase", "rent rise", "raise rent", "increase rent"])
    _scam_ctx    = any(w in recent for w in ["scam", "fraud", "fake", "western union", "crypto", "suspicious"])

    # Follow-up words that need context to answer
    _followup    = any(w in last for w in ["pay", "cost", "charge", "who", "responsible", "liable",
                                            "law", "legal", "right", "can they", "allowed", "have to",
                                            "must", "need to", "yes", "no", "really", "how long",
                                            "what if", "refuse", "won't", "wont", "ignored"])

    # ── Repair questions (including follow-ups) ───────────────────
    if any(w in last for w in ["repair", "maintenance", "fix", "broken", "mould", "mold", "hot water", "heater"]) \
       or (_followup and _repair_ctx):
        pay_q = any(w in last for w in ["pay", "cost", "charge", "who", "responsible", "liable", "law", "legal", "have to", "must"])
        refuse_q = any(w in last for w in ["refuse", "won't", "wont", "ignor", "not fix"])
        if pay_q:
            return (
                "**Yes** — under the Residential Tenancies Act, landlords are legally required to keep the property in a reasonable state of repair. "
                "They must cover repair costs unless the damage was caused by the tenant's negligence.\n\n"
                "If your landlord refuses, you can:\n"
                "• Send a written repair request (keeps a paper trail)\n"
                "• Apply to **NCAT** for a repair order (NSW) or your state's tribunal\n"
                "• For urgent repairs, arrange them yourself (up to 2 weeks rent) and claim costs back"
            )
        if refuse_q:
            return (
                "If your landlord refuses to repair:\n"
                "• Send a **written request** via email/letter — this is your evidence\n"
                "• Give a reasonable timeframe (e.g. 7 days for non-urgent, immediate for urgent)\n"
                "• If ignored, apply to **NCAT** (NSW) for a repair order — it's free and binding\n"
                "• For urgent issues (no hot water, gas leak), you can arrange repairs yourself and reclaim costs"
            )
        return (
            "Landlords must keep the property in reasonable repair under the Residential Tenancies Act. "
            "For **urgent repairs** (burst pipe, no hot water, broken heater), you may arrange them yourself "
            "(up to 2 weeks rent cost) if the landlord doesn't respond promptly. "
            "Always document everything in writing and keep receipts."
        )

    # ── Bond questions ────────────────────────────────────────────
    if any(w in last for w in ["bond", "deposit", "security deposit"]) \
       or (_followup and _bond_ctx):
        return (
            "In NSW, the maximum bond is **4 weeks rent**. Key rules:\n"
            "• Landlord must lodge it with **NSW Fair Trading** within 10 days\n"
            "• You get it back when you leave, minus any legitimate deductions\n"
            "• Never pay bond via cash, crypto, or wire transfer — use the official rental bond portal\n"
            "• Disputes go to the **Rental Bond Board** or NCAT"
        )

    # ── Scam questions ────────────────────────────────────────────
    if any(w in last for w in ["scam", "fraud", "fake", "suspicious", "western union", "crypto", "bitcoin"]) \
       or (_followup and _scam_ctx):
        return (
            "Common Australian rental scams:\n"
            "• Wire-transfer bond requests before inspection\n"
            "• Overseas landlord claiming to mail keys after payment\n"
            "• Gumtree/Facebook listings at well below market rent\n"
            "• WhatsApp-only contact, refusing video calls\n"
            "• Pressure to pay immediately ('multiple applicants')\n\n"
            "Report to NSW Fair Trading: **13 32 20** or your state equivalent."
        )

    # ── Eviction / notice questions ───────────────────────────────
    if any(w in last for w in ["evict", "eviction", "notice", "terminate", "end lease", "vacate"]) \
       or (_followup and _evict_ctx):
        return (
            "In NSW, a landlord must give written notice before terminating a tenancy:\n"
            "• **No grounds** (end of fixed term): 90 days\n"
            "• **Selling the property**: 30 days\n"
            "• **Breach of agreement**: 14 days\n\n"
            "You cannot be evicted without a tribunal order if you dispute it. "
            "Contact the **Tenants' Union of NSW** (02 8117 3700) for free advice."
        )

    # ── Rent increase questions ───────────────────────────────────
    if any(w in last for w in ["rent increase", "rent rise", "raise rent", "increase rent", "put up rent"]) \
       or (_followup and _rent_ctx):
        return (
            "In NSW, rent can only be increased **once every 12 months** with **60 days written notice**.\n\n"
            "You can challenge an excessive increase at **NCAT** within 30 days of receiving the notice. "
            "The tribunal will consider local market rents to decide if it's fair."
        )

    # ── Entry / inspection questions ──────────────────────────────
    if any(w in last for w in ["inspect", "entry", "enter", "access", "landlord come"]) \
       or (_followup and _entry_ctx):
        return (
            "In NSW, landlords must give **at least 24 hours written notice** before entering. "
            "Routine inspections are limited to **4 times per year**. "
            "You have the right to be present. Entry without notice (except emergencies) is illegal — "
            "you can report it to NSW Fair Trading."
        )

    # ── Dispute / tribunal questions ──────────────────────────────
    if any(w in last for w in ["fair trading", "ncat", "tribunal", "complaint", "dispute", "help", "who do i call"]):
        return (
            "For tenancy disputes in NSW:\n"
            "• **NSW Fair Trading** (13 32 20) — free mediation\n"
            "• **NCAT** — binding tribunal decisions (apply at ncat.nsw.gov.au)\n"
            "• **Tenants' Union of NSW** (02 8117 3700) — free legal advice\n\n"
            "Other states: Consumer Affairs VIC (1300 55 81 81) · RTA QLD (1300 366 311)"
        )

    # ── Context-aware generic follow-up ──────────────────────────
    if _followup and context:
        risk = context.get("combined_risk", 0)
        n = context.get("n_flags", 0)
        return (
            f"Based on the document analysis (risk **{risk}%**, {n} red flag(s)), "
            "I'd recommend getting proper legal advice for this specific situation.\n\n"
            "For AI-powered answers, set a free HuggingFace token:\n"
            "`export HF_TOKEN=hf_...` (free at huggingface.co → Settings → Access Tokens)"
        )

    return (
        "I can answer questions about:\n"
        "• **Bond** limits and lodgement\n"
        "• **Repairs** — who pays, what to do if landlord refuses\n"
        "• **Eviction** notices and your rights\n"
        "• **Rent increases** — limits and how to dispute\n"
        "• **Entry** notice requirements\n"
        "• **Scam** patterns to watch for\n\n"
        "For full AI answers on any question, set a free HuggingFace token:\n"
        "`export HF_TOKEN=hf_...` — get one at **huggingface.co → Settings → Access Tokens**"
    )
