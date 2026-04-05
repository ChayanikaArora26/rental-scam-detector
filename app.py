"""
app.py — Streamlit frontend for the Rental Scam Detector.

Run:
    streamlit run app.py
"""

import io
import os
import pathlib
import tempfile

import pandas as pd
import streamlit as st

# ── Core modules ────────────────────────────────────────────────
import download_data
from rental_scam_detector import (
    RentalScamDetector,
    load_cuad,
    load_forms_and_chunk,
    load_document,
    normalize_text,
    FORMS_DIR,
)
import llm_analyser
import database

# ── Page config ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Rental Scam Detector",
    page_icon="🏠",
    layout="wide",
)

# ── Bootstrap data files + DB ───────────────────────────────────
@st.cache_resource(show_spinner="Downloading reference data (one-time setup)…")
def bootstrap_data():
    download_data.run()
    database.init_db()

bootstrap_data()


# ── Load detector once (cached so CUAD isn't re-parsed every run) ──
@st.cache_resource(show_spinner="Loading reference corpus (one-time setup)…")
def get_detector() -> RentalScamDetector:
    _, cuad_texts = load_cuad()
    au_chunks     = load_forms_and_chunk(FORMS_DIR)
    au_texts      = [r["text"] for r in au_chunks]
    return RentalScamDetector(au_texts + cuad_texts)


# ── Helpers ──────────────────────────────────────────────────────
RISK_COLORS = {
    "HIGH":   ("#c0392b", "🔴"),
    "MEDIUM": ("#d68910", "🟡"),
    "LOW":    ("#1e8449", "🟢"),
}

def risk_level(verdict: str) -> str:
    v = verdict.upper()
    if "HIGH"   in v: return "HIGH"
    if "MEDIUM" in v: return "MEDIUM"
    return "LOW"


def render_verdict_card(result: dict):
    level = risk_level(result["verdict"])
    color, icon = RISK_COLORS[level]
    risk  = result["combined_risk"]

    st.markdown(
        f"""
        <div style="
            background:{color}22;border-left:6px solid {color};
            border-radius:8px;padding:16px 20px;margin-bottom:16px">
          <h2 style="margin:0;color:{color}">{icon} {result['verdict']}</h2>
          <p style="margin:4px 0 0;font-size:0.95em">
            Risk score: <strong>{risk}%</strong> &nbsp;|&nbsp;
            Red flags: <strong>{result['n_flags']}</strong> &nbsp;|&nbsp;
            Anomalous clauses: <strong>{result['n_anomalous']}/{result['total_chunks']}</strong>
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(min(risk, 100) / 100)


def render_red_flags(red_flags: list[dict]):
    if not red_flags:
        st.success("No red-flag patterns detected.")
        return
    st.subheader(f"⚠ {len(red_flags)} Red Flag(s) Detected")
    for rf in red_flags:
        with st.expander(rf["flag"]):
            st.code(rf["snippet"], language=None)


def render_llm_card(llm: dict):
    ai_badge = "✨ AI-powered" if llm.get("powered_by_ai") else "📋 Rule-based"
    st.subheader(f"Analysis ({ai_badge})")
    st.info(llm["summary"])

    if llm.get("clause_advice"):
        st.markdown("**Clause-by-clause notes:**")
        for line in llm["clause_advice"]:
            st.markdown(f"- {line}")

    st.markdown("**What you should do:**")
    for bullet in llm["user_action"].split("\n"):
        if bullet.strip():
            st.markdown(bullet.strip())

    if not llm.get("powered_by_ai"):
        st.caption(
            "💡 Set `ANTHROPIC_API_KEY` to unlock Claude AI explanations."
        )


def render_chunk_table(details: pd.DataFrame):
    if details.empty:
        return
    with st.expander("Detailed chunk scores"):
        styled = details.style.background_gradient(
            subset=["best_score"], cmap="RdYlGn", vmin=0, vmax=0.5
        ).format({"best_score": "{:.3f}"})
        st.dataframe(styled, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
# Sidebar — user identity + navigation
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("🏠 Rental Scam Detector")
    st.caption("Powered by CUAD + AU Tenancy Baseline")
    st.divider()

    with st.form("user_form"):
        name  = st.text_input("Your name",  placeholder="Jane Smith")
        email = st.text_input("Your email", placeholder="jane@email.com")
        st.form_submit_button("Save", use_container_width=True)

    st.divider()
    page = st.radio(
        "Navigate",
        ["Analyse Document", "My History", "About"],
        label_visibility="collapsed",
    )


# ═══════════════════════════════════════════════════════════════
# Page 1 — Analyse Document
# ═══════════════════════════════════════════════════════════════
if page == "Analyse Document":
    st.title("Analyse a Rental Listing or Agreement")

    input_method = st.radio(
        "Input method",
        ["Upload a file (PDF or DOCX)", "Paste text"],
        horizontal=True,
    )

    raw_text = ""
    filename = ""

    if input_method == "Upload a file (PDF or DOCX)":
        uploaded = st.file_uploader(
            "Drop your rental agreement here",
            type=["pdf", "docx"],
            label_visibility="collapsed",
        )
        if uploaded:
            filename = uploaded.name
            suffix   = pathlib.Path(filename).suffix
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            try:
                raw_text = load_document(tmp_path)
            finally:
                os.unlink(tmp_path)
    else:
        raw_text = st.text_area(
            "Paste the listing or agreement text here",
            height=220,
            placeholder="e.g. 'Send $2000 via Western Union to secure this property...'",
        )

    analyse_btn = st.button("🔍 Analyse", type="primary", use_container_width=True)

    if analyse_btn:
        if not raw_text.strip():
            st.warning("Please provide some text or upload a file first.")
            st.stop()

        detector = get_detector()

        with st.spinner("Analysing…"):
            result  = detector.analyse(raw_text)
            llm_out = llm_analyser.explain(result)

        # Save to DB if user supplied email
        if email.strip():
            uid = database.get_or_create_user(
                name or email.split("@")[0], email
            )
            database.save_analysis(uid, result, llm_out, filename)

        # Render results
        render_verdict_card(result)

        col1, col2 = st.columns([1, 1])
        with col1:
            render_red_flags(result["red_flags"])
        with col2:
            render_llm_card(llm_out)

        render_chunk_table(result["details"])

        if not email.strip():
            st.info(
                "Enter your email in the sidebar to save this result to your history."
            )


# ═══════════════════════════════════════════════════════════════
# Page 2 — My History
# ═══════════════════════════════════════════════════════════════
elif page == "My History":
    st.title("My Past Analyses")

    lookup_email = email.strip() if email.strip() else ""
    if not lookup_email:
        lookup_email = st.text_input(
            "Enter your email to load history",
            placeholder="jane@email.com",
        )

    if lookup_email:
        history = database.get_user_history(lookup_email)
        if not history:
            st.info("No analyses found for this email yet.")
        else:
            st.success(f"{len(history)} past analysis/analyses found.")

            # Summary table
            rows = []
            for h in history:
                level = risk_level(h["verdict"])
                _, icon = RISK_COLORS[level]
                rows.append({
                    "Date (UTC)":  h["created_at"][:16].replace("T", " "),
                    "File":        h["filename"] or "pasted text",
                    "Verdict":     f"{icon} {h['verdict']}",
                    "Risk %":      h["combined_risk"],
                    "Red Flags":   h["n_flags"],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            # Expandable detail for each run
            for h in history:
                label = (
                    f"{h['created_at'][:16].replace('T', ' ')} — "
                    f"{h['filename'] or 'pasted text'}"
                )
                with st.expander(label):
                    st.markdown(f"**Verdict:** {h['verdict']}")
                    if h.get("llm_summary"):
                        st.info(h["llm_summary"])
                    if h["red_flags"]:
                        st.markdown("**Red flags:**")
                        for rf in h["red_flags"]:
                            st.markdown(f"- **{rf['flag']}** — `{rf['snippet']}`")
                    else:
                        st.success("No red flags in this analysis.")


# ═══════════════════════════════════════════════════════════════
# Page 3 — About
# ═══════════════════════════════════════════════════════════════
elif page == "About":
    st.title("About this Tool")
    st.markdown("""
### What it does
This tool analyses rental listings and tenancy agreements for signs of fraud,
comparing them against two reference corpora:

| Reference corpus | Size | Source |
|---|---|---|
| **CUAD** (Contract Understanding Atticus Dataset) | 510 real legal contracts, 10,667 annotated clauses | HuggingFace `theatticusproject/cuad` |
| **AU Tenancy Baseline** | NSW residential tenancy agreement | NSW Fair Trading |

### Two detection layers

1. **Red-flag patterns** — 28 regex rules targeting known scam signals:
   payment methods (Western Union, crypto, gift cards), landlord unavailability,
   no-inspection clauses, illegal terms (rights waiver, unlimited rent increases),
   and pressure tactics.

2. **Clause anomaly scoring** — sentence-transformer cosine similarity against
   the reference corpus.  Chunks of the submitted document that have no close
   match in any known-good lease are flagged as anomalous.

### Limitations
- The tool flags *suspicious* patterns — it does not guarantee a listing is safe or a scam.
- Always inspect a property in person before signing or paying.
- For legal advice contact NSW Fair Trading or a tenancy advocacy service.

### Activate AI explanations
Set your Anthropic API key to unlock plain-English clause explanations:
```
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run app.py
```

### Tech stack
`Python` · `Streamlit` · `sentence-transformers` · `NLTK` · `pdfplumber` · `SQLite` · `Anthropic Claude` (optional)
""")
