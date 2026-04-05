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

# ── Global CSS ───────────────────────────────────────────────────
st.markdown("""
<style>
/* ---- typography & base ---- */
html, body, [class*="css"] { font-family: "Inter", sans-serif; }

/* ---- sidebar ---- */
section[data-testid="stSidebar"] {
    background: #0f1117;
    border-right: 1px solid #1e2130;
}
section[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
section[data-testid="stSidebar"] .stTextInput input {
    background: #1e2130;
    border: 1px solid #2d3148;
    border-radius: 8px;
    color: #fff !important;
}
section[data-testid="stSidebar"] hr { border-color: #2d3148; }

/* ---- primary button ---- */
button[kind="primary"] {
    background: linear-gradient(135deg, #6c63ff, #48cfad) !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    transition: opacity 0.2s !important;
}
button[kind="primary"]:hover { opacity: 0.88 !important; }

/* ---- metric cards ---- */
div[data-testid="stMetric"] {
    background: #1e2130;
    border: 1px solid #2d3148;
    border-radius: 12px;
    padding: 16px 20px;
}
div[data-testid="stMetricValue"] { font-size: 2rem !important; font-weight: 700 !important; }

/* ---- expander ---- */
details { border: 1px solid #2d3148 !important; border-radius: 10px !important; }

/* ---- file uploader ---- */
[data-testid="stFileUploader"] {
    border: 2px dashed #2d3148;
    border-radius: 12px;
    padding: 8px;
}

/* ---- progress bar ---- */
div[data-testid="stProgressBar"] > div > div {
    border-radius: 99px;
}

/* ---- dataframe ---- */
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

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
    "HIGH":   ("#e74c3c", "🔴"),
    "MEDIUM": ("#f39c12", "🟡"),
    "LOW":    ("#2ecc71", "🟢"),
}

RISK_BG = {
    "HIGH":   "#2d1515",
    "MEDIUM": "#2d2210",
    "LOW":    "#102d1a",
}

def risk_level(verdict: str) -> str:
    v = verdict.upper()
    if "HIGH"   in v: return "HIGH"
    if "MEDIUM" in v: return "MEDIUM"
    return "LOW"


def render_verdict_card(result: dict):
    level = risk_level(result["verdict"])
    color, icon = RISK_COLORS[level]
    bg    = RISK_BG[level]
    risk  = result["combined_risk"]

    st.markdown(
        f"""
        <div style="
            background:{bg};
            border:1.5px solid {color}55;
            border-radius:14px;
            padding:24px 28px;
            margin-bottom:24px">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
            <span style="font-size:2.2rem">{icon}</span>
            <h2 style="margin:0;color:{color};font-size:1.6rem;font-weight:700">
              {result['verdict']}
            </h2>
          </div>
          <p style="margin:0;color:#aaa;font-size:0.9rem">
            Document scanned against 510 CUAD contracts + NSW Tenancy Baseline
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Risk Score", f"{risk}%")
    c2.metric("Red Flags", result["n_flags"])
    c3.metric("Anomalous Clauses", f"{result['n_anomalous']}/{result['total_chunks']}")
    safe = result["total_chunks"] - result["n_anomalous"]
    c4.metric("Safe Clauses", safe)

    bar_color = color
    st.markdown(
        f"""
        <div style="margin:16px 0 4px;height:10px;border-radius:99px;
                    background:#1e2130;overflow:hidden">
          <div style="height:100%;width:{min(risk,100)}%;
                      background:linear-gradient(90deg,{bar_color}99,{bar_color});
                      border-radius:99px;transition:width 0.6s ease"></div>
        </div>
        <p style="margin:4px 0 0;color:#666;font-size:0.78rem;text-align:right">
          {risk}% overall risk
        </p>
        """,
        unsafe_allow_html=True,
    )


def render_red_flags(red_flags: list[dict]):
    if not red_flags:
        st.markdown(
            """
            <div style="background:#102d1a;border:1px solid #2ecc7155;
                        border-radius:10px;padding:14px 18px;margin-bottom:8px">
              <span style="color:#2ecc71;font-weight:600">✓ No red-flag patterns detected</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"""
        <div style="background:#2d1515;border:1px solid #e74c3c55;
                    border-radius:10px;padding:14px 18px;margin-bottom:12px">
          <span style="color:#e74c3c;font-weight:700;font-size:1rem">
            ⚠ {len(red_flags)} Red Flag{"s" if len(red_flags) != 1 else ""} Detected
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for rf in red_flags:
        with st.expander(f"🚩 {rf['flag']}"):
            st.code(rf["snippet"], language=None)


def render_llm_card(llm: dict):
    powered = llm.get("powered_by_ai")
    badge_color = "#6c63ff" if powered else "#555"
    badge_text  = "✨ AI-powered" if powered else "📋 Rule-based"

    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
          <h3 style="margin:0">Analysis</h3>
          <span style="background:{badge_color}33;color:{badge_color};
                       border:1px solid {badge_color}66;
                       border-radius:20px;padding:2px 10px;font-size:0.78rem;
                       font-weight:600">{badge_text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div style="background:#1a1d2e;border-left:4px solid #6c63ff;
                    border-radius:8px;padding:14px 18px;margin-bottom:14px;
                    color:#ccc;line-height:1.6">
          {llm["summary"]}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if llm.get("clause_advice"):
        st.markdown("**Clause notes:**")
        for line in llm["clause_advice"]:
            st.markdown(f"- {line}")

    st.markdown("**What you should do:**")
    for bullet in llm["user_action"].split("\n"):
        if bullet.strip():
            st.markdown(bullet.strip())

    if not powered:
        st.caption("💡 Set `ANTHROPIC_API_KEY` to unlock Claude AI explanations.")


def render_chunk_table(details: pd.DataFrame):
    if details.empty:
        return
    with st.expander("📊 Detailed clause scores"):
        styled = details.style.background_gradient(
            subset=["best_score"], cmap="RdYlGn", vmin=0, vmax=0.5
        ).format({"best_score": "{:.3f}"})
        st.dataframe(styled, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
# Sidebar — user identity + navigation
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        """
        <div style="padding:8px 0 4px">
          <span style="font-size:1.6rem">🏠</span>
          <span style="font-size:1.1rem;font-weight:700;margin-left:8px;
                       color:#fff">Rental Scam Detector</span>
        </div>
        <p style="margin:0 0 12px;font-size:0.78rem;color:#666">
          Powered by CUAD + AU Tenancy Baseline
        </p>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    with st.form("user_form"):
        st.markdown("<p style='margin:0 0 6px;font-size:0.85rem;color:#aaa'>Your profile</p>",
                    unsafe_allow_html=True)
        name  = st.text_input("Name",  placeholder="Jane Smith",  label_visibility="collapsed")
        email = st.text_input("Email", placeholder="jane@email.com", label_visibility="collapsed")
        st.form_submit_button("Save profile", use_container_width=True)

    st.divider()

    st.markdown("<p style='margin:0 0 8px;font-size:0.8rem;color:#666;text-transform:uppercase;"
                "letter-spacing:0.08em'>Navigation</p>", unsafe_allow_html=True)
    page = st.radio(
        "Navigate",
        ["Analyse Document", "My History", "About"],
        label_visibility="collapsed",
    )


# ═══════════════════════════════════════════════════════════════
# Page 1 — Analyse Document
# ═══════════════════════════════════════════════════════════════
if page == "Analyse Document":
    st.markdown(
        """
        <h1 style="margin-bottom:4px">Analyse a Rental Document</h1>
        <p style="color:#888;margin-top:0;margin-bottom:24px">
          Upload or paste a rental listing or tenancy agreement to check for scam signals.
        </p>
        """,
        unsafe_allow_html=True,
    )

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
            st.success(f"Loaded **{filename}** ({len(raw_text):,} characters)")
    else:
        raw_text = st.text_area(
            "Paste text",
            height=220,
            placeholder="e.g. 'Send $2000 via Western Union to secure this property...'",
            label_visibility="collapsed",
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    analyse_btn = st.button("🔍 Analyse Document", type="primary", use_container_width=True)

    if analyse_btn:
        if not raw_text.strip():
            st.warning("Please provide some text or upload a file first.")
            st.stop()

        detector = get_detector()

        with st.spinner("Analysing document…"):
            result  = detector.analyse(raw_text)
            llm_out = llm_analyser.explain(result)

        if email.strip():
            uid = database.get_or_create_user(
                name or email.split("@")[0], email
            )
            database.save_analysis(uid, result, llm_out, filename)

        st.divider()
        render_verdict_card(result)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        col1, col2 = st.columns([1, 1], gap="large")
        with col1:
            render_red_flags(result["red_flags"])
        with col2:
            render_llm_card(llm_out)

        render_chunk_table(result["details"])

        if not email.strip():
            st.markdown(
                """
                <div style="background:#1a1d2e;border:1px solid #2d3148;border-radius:10px;
                            padding:12px 16px;margin-top:16px;color:#aaa;font-size:0.88rem">
                  💾 Enter your name and email in the sidebar to save this result to your history.
                </div>
                """,
                unsafe_allow_html=True,
            )


# ═══════════════════════════════════════════════════════════════
# Page 2 — My History
# ═══════════════════════════════════════════════════════════════
elif page == "My History":
    st.markdown(
        """
        <h1 style="margin-bottom:4px">My Past Analyses</h1>
        <p style="color:#888;margin-top:0;margin-bottom:24px">
          Your previously submitted documents and their results.
        </p>
        """,
        unsafe_allow_html=True,
    )

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
            st.markdown(
                f"<p style='color:#aaa;margin-bottom:16px'>"
                f"Found <strong style='color:#fff'>{len(history)}</strong> past "
                f"analysis/analyses for <code>{lookup_email}</code></p>",
                unsafe_allow_html=True,
            )

            rows = []
            for h in history:
                level = risk_level(h["verdict"])
                _, icon = RISK_COLORS[level]
                rows.append({
                    "Date (UTC)": h["created_at"][:16].replace("T", " "),
                    "File":       h["filename"] or "pasted text",
                    "Verdict":    f"{icon} {h['verdict']}",
                    "Risk %":     h["combined_risk"],
                    "Red Flags":  h["n_flags"],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            for h in history:
                level = risk_level(h["verdict"])
                color, icon = RISK_COLORS[level]
                label = (
                    f"{icon} {h['created_at'][:16].replace('T', ' ')} — "
                    f"{h['filename'] or 'pasted text'} — Risk: {h['combined_risk']}%"
                )
                with st.expander(label):
                    st.markdown(f"**Verdict:** {h['verdict']}")
                    if h.get("llm_summary"):
                        st.markdown(
                            f"<div style='background:#1a1d2e;border-left:4px solid #6c63ff;"
                            f"border-radius:8px;padding:12px 16px;color:#ccc;margin:8px 0'>"
                            f"{h['llm_summary']}</div>",
                            unsafe_allow_html=True,
                        )
                    if h["red_flags"]:
                        st.markdown("**Red flags:**")
                        for rf in h["red_flags"]:
                            st.markdown(f"- 🚩 **{rf['flag']}** — `{rf['snippet']}`")
                    else:
                        st.success("No red flags in this analysis.")


# ═══════════════════════════════════════════════════════════════
# Page 3 — About
# ═══════════════════════════════════════════════════════════════
elif page == "About":
    st.markdown(
        """
        <h1 style="margin-bottom:4px">About this Tool</h1>
        <p style="color:#888;margin-top:0;margin-bottom:28px">
          How it works, its limitations, and the tech behind it.
        </p>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("#### How it works")
        st.markdown(
            """
            This tool analyses rental listings and tenancy agreements for signs of fraud,
            comparing them against two reference corpora:
            """
        )
        st.markdown("""
| Corpus | Details |
|---|---|
| **CUAD** | 510 real legal contracts, 10,667 annotated clauses — HuggingFace |
| **AU Tenancy Baseline** | NSW residential tenancy agreement — NSW Fair Trading |
        """)

        st.markdown("#### Two detection layers")
        st.markdown("""
1. **Red-flag patterns** — 28 regex rules targeting known scam signals: payment methods
   (Western Union, crypto, gift cards), landlord unavailability, no-inspection clauses,
   illegal terms, and pressure tactics.

2. **Clause anomaly scoring** — sentence-transformer cosine similarity against the
   reference corpus. Chunks with no close match in any known-good lease are flagged.
        """)

    with col2:
        st.markdown("#### Limitations")
        st.markdown(
            """
            <div style="background:#2d2210;border:1px solid #f39c1255;border-radius:10px;
                        padding:16px 20px;color:#ccc;line-height:1.8">
              ⚠ This tool flags <em>suspicious</em> patterns — it does not guarantee a
              listing is safe or a scam.<br><br>
              Always inspect a property in person before signing or paying.<br><br>
              For legal advice, contact NSW Fair Trading or a tenancy advocacy service.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown("#### Activate AI explanations")
        st.code("export ANTHROPIC_API_KEY=sk-ant-...\nstreamlit run app.py", language="bash")
        st.caption("On Streamlit Cloud, add secrets via the app dashboard instead.")

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown("#### Tech stack")
        st.markdown(
            """
            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:4px">
              """ +
            "".join(
                f'<span style="background:#1e2130;border:1px solid #2d3148;'
                f'border-radius:20px;padding:4px 12px;font-size:0.82rem;color:#ccc">{t}</span>'
                for t in ["Python", "Streamlit", "sentence-transformers",
                          "NLTK", "pdfplumber", "SQLite", "Anthropic Claude"]
            ) +
            """
            </div>
            """,
            unsafe_allow_html=True,
        )
