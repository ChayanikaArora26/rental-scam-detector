# ============================================================
# Rental Scam Detector — Local Version
# Converted from Google Colab: Copy of Rental_Scam_Detector_MVP.ipynb
# ============================================================
#
# HOW IT WORKS
# ─────────────────────────────────────────────────────────────
# 1. LOAD CUAD  — 510 real legal contracts with 41 annotated
#    clause types each (termination, payment, liability, etc.)
#    Used as a reference library of "what legitimate clauses
#    look like".
#
# 2. LOAD AU FORMS — Australian tenancy agreement PDFs/DOCX
#    from data/au_tenancy_forms/ chunked into 4-sentence blocks.
#    These are the baseline "normal" rental clauses.
#
# 3. DETECT SCAMS — Given a suspicious rental listing or
#    agreement, chunk it and compare every chunk against the
#    AU baseline using sentence-transformer embeddings (semantic
#    cosine similarity). Chunks with no close semantic match in
#    any known-good lease are flagged as suspicious.
#
# USAGE
#   python rental_scam_detector.py                  # run demo
#   python rental_scam_detector.py path/to/doc.pdf  # check a file
# ============================================================

import os
import sys
import json
import re
import pathlib
import nltk
import pdfplumber
import pandas as pd
import numpy as np
from docx import Document
from fastembed import TextEmbedding
from nltk.tokenize import sent_tokenize

# ──────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────
PROJECT_ROOT  = pathlib.Path(__file__).parent
DATA_DIR      = PROJECT_ROOT / "data"
CUAD_PATH     = DATA_DIR / "cuad" / "CUAD_v1" / "CUAD_v1.json"
FORMS_DIR     = DATA_DIR / "au_tenancy_forms"
PROCESSED_DIR = DATA_DIR / "processed"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Semantic similarity threshold (sentence-transformer cosine similarity, 0–1).
# Chunks scoring below this have no semantic match in any known-good lease.
SUSPICION_THRESHOLD = 0.30

# Embedding model via fastembed (ONNX, no PyTorch, ~60MB)
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_CACHE = pathlib.Path(__file__).parent / "data" / "processed" / "ref_embeddings.npy"

# ──────────────────────────────────────────────────────────────
# NLTK setup
# ──────────────────────────────────────────────────────────────
nltk.download("punkt",     quiet=True)
nltk.download("punkt_tab", quiet=True)


# ──────────────────────────────────────────────────────────────
# Text utilities
# ──────────────────────────────────────────────────────────────
def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_legal_text(text: str, max_sentences: int = 4, min_chars: int = 80) -> list[str]:
    """Split text into overlapping sentence-window chunks."""
    sents = [s.strip() for s in sent_tokenize(text) if s.strip()]
    chunks, buf = [], []
    for s in sents:
        buf.append(s)
        if len(buf) >= max_sentences:
            c = " ".join(buf).strip()
            if len(c) >= min_chars:
                chunks.append(c)
            buf = []
    if buf:
        c = " ".join(buf).strip()
        if len(c) >= min_chars:
            chunks.append(c)
    return chunks


# ──────────────────────────────────────────────────────────────
# Document loaders
# ──────────────────────────────────────────────────────────────
def extract_pdf_text(path: str) -> str:
    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if t.strip():
                parts.append(t)
    return "\n".join(parts)


def extract_docx_text(path: str) -> str:
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def load_document(path: str) -> str:
    """Load text from a PDF or DOCX file."""
    p = path.lower()
    if p.endswith(".pdf"):
        return extract_pdf_text(path)
    elif p.endswith(".docx"):
        return extract_docx_text(path)
    else:
        with open(path, "r", errors="ignore") as f:
            return f.read()


# ──────────────────────────────────────────────────────────────
# CUAD — build clause reference library
# ──────────────────────────────────────────────────────────────
def explode_into_clauses(cuad_data: list) -> list[dict]:
    """
    Iterate every CUAD contract and extract each annotated clause
    answer as a separate row.

    CUAD structure:
      data[i]  → { title, paragraphs: [{ context, qas: [{ question, answers }] }] }
      question → describes the clause TYPE (e.g. "Termination for convenience")
      answers  → list of text spans from the contract that match that clause type
    """
    rows = []
    for contract in cuad_data:
        title = contract.get("title", "")
        for para in contract.get("paragraphs", []):
            for qa in para.get("qas", []):
                # Strip the boilerplate prompt and keep just the clause type label
                clause_type = re.sub(
                    r'Highlight the parts.*?"(.+?)".*',
                    r"\1",
                    qa.get("question", ""),
                    flags=re.S
                ).strip()
                for answer in qa.get("answers", []):
                    text = answer.get("text", "").strip()
                    if text and len(text) > 30:
                        rows.append({
                            "contract_title": title,
                            "clause_type":    clause_type,
                            "text":           text,
                        })
    return rows


def load_cuad() -> tuple[list[dict], list[str]]:
    """Load CUAD and return (clause_rows, all_clause_texts)."""
    assert CUAD_PATH.exists(), (
        f"CUAD not found at {CUAD_PATH}\n"
        "Run:  python3 -c \"from huggingface_hub import hf_hub_download; "
        "hf_hub_download('theatticusproject/cuad','CUAD_v1/CUAD_v1.json',"
        "repo_type='dataset',local_dir='data/cuad')\""
    )
    print("Loading CUAD …", end=" ", flush=True)
    with open(CUAD_PATH) as f:
        cuad = json.load(f)
    clauses = explode_into_clauses(cuad["data"])
    print(f"{len(cuad['data'])} contracts → {len(clauses)} clause annotations")
    return clauses, [c["text"] for c in clauses]


# ──────────────────────────────────────────────────────────────
# AU tenancy forms — baseline corpus
# ──────────────────────────────────────────────────────────────
def load_forms_and_chunk(forms_dir: pathlib.Path) -> list[dict]:
    rows = []
    for fname in os.listdir(forms_dir):
        path = forms_dir / fname
        if fname.lower().endswith((".pdf", ".docx")):
            raw = normalize_text(load_document(str(path)))
            for i, ch in enumerate(chunk_legal_text(raw)):
                rows.append({
                    "source_file": fname,
                    "chunk_id":    f"{fname}__{i:05d}",
                    "text":        ch,
                })
    return rows


# ──────────────────────────────────────────────────────────────
# Red-flag pattern library
# ──────────────────────────────────────────────────────────────
# Tuples of (regex, label, severity_score, severity_label)
# severity_score drives the risk percentage:
#   50 = CRITICAL  — near-certain scam, one flag alone = HIGH RISK
#   30 = HIGH      — strong scam indicator
#   15 = MEDIUM    — concerning, warrants caution
#   8  = LOW       — worth noting but not alarming alone
#   3  = MINIMAL   — very mild, common in legitimate listings
RED_FLAGS: list[tuple[str, str, int, str]] = [
    # ── Payment scams ────────────────────────────────────────
    (r"\bwestern\s+union\b",
     "requests Western Union transfer", 50, "CRITICAL"),
    (r"\bmoneygram\b",
     "requests MoneyGram transfer", 50, "CRITICAL"),
    (r"\bcrypto(?:currency)?\b|\bbitcoin\b|\bethereum\b|\busdt\b",
     "requests cryptocurrency payment", 50, "CRITICAL"),
    (r"\bgift\s+card\b",
     "requests gift card payment", 50, "CRITICAL"),
    (r"\bwire\s+transfer\b",
     "requests wire transfer", 30, "HIGH"),
    (r"\bsend\s+(cash|money|funds|payment|the\s+bond)\b",
     "requests cash/money transfer", 30, "HIGH"),
    (r"\bfull\s+(bond|deposit|month).{0,20}before\b",
     "large upfront payment demanded before viewing", 30, "HIGH"),
    (r"\bdeposit\b.{0,30}\bbefore\s+viewing\b",
     "deposit required before inspection", 15, "MEDIUM"),
    (r"\bdirect\s+deposit.*\bsecure\b|\beft.*\bsecure\b",
     "requests direct deposit to 'secure' property", 15, "MEDIUM"),

    # ── Landlord unavailability ───────────────────────────────
    (r"\bkeys\s+(will\s+be\s+)?sent\s+by\s+(post|mail)\b|\bkeys.*\bdelivered\b",
     "keys sent by post / delivered without meeting", 30, "HIGH"),
    (r"\bno\s+inspection\b|\bcannot\s+inspect\b|\bviewing\s+not\s+(possible|available)\b",
     "inspection/viewing denied", 30, "HIGH"),
    (r"\boverseas\b.*\blandlord\b|\blandlord\b.*\boverseas\b",
     "landlord claims to be overseas", 15, "MEDIUM"),
    (r"\bcurrently\s+(overseas|abroad|out\s+of\s+(the\s+)?country|interstate)\b",
     "owner claims to be away / out of country", 8, "LOW"),
    (r"\bcannot\s+meet\b|\bunable\s+to\s+meet\b|\bno\s+meetup\b",
     "landlord refuses to meet in person", 15, "MEDIUM"),
    (r"\bwhatsapp\s+only\b|\bcontact.*\bwhatsapp\b|\bvia\s+whatsapp\b",
     "WhatsApp-only contact (avoids traceable calls)", 15, "MEDIUM"),

    # ── Rights waiver / illegal terms ────────────────────────
    (r"\bwaives?\s+all\s+rights\b",
     "tenant waives all rights (illegal in AU)", 50, "CRITICAL"),
    (r"\bnon.?refundable\b.*\ball\s+circumstances\b",
     "non-refundable under all circumstances (illegal in AU)", 15, "MEDIUM"),
    (r"\benter.*without.*notice\b|\bno\s+notice.*entry\b",
     "landlord entry without notice (illegal in AU)", 15, "MEDIUM"),
    (r"\bincrease.*\b(20|25|30|40|50)\s*%\b",
     "excessive rent increase clause", 8, "LOW"),
    (r"\bno\s+pets\b.*\bno\s+guests\b|\bno\s+guests\b.*\bno\s+pets\b",
     "overly restrictive lifestyle controls", 8, "LOW"),

    # ── Classic scam language ────────────────────────────────
    (r"\bgod.?fearing\b|\btrust\s+in\s+god\b",
     "religious appeals ('God-fearing') — classic scam signal", 50, "CRITICAL"),
    (r"\bmissionary\b|\bchurch\s+work\b",
     "missionary/church-work story — common scam pretext", 30, "HIGH"),
    (r"\bmanagement\s+company\s+will\b|\bagent\s+will\s+deliver\b",
     "fictitious management company delivering keys", 30, "HIGH"),
    (r"\bkeys.*\bairbnb\b|\bairbnb.*\bkeys\b",
     "subletting via Airbnb without owner knowledge", 8, "LOW"),

    # ── Pressure tactics ─────────────────────────────────────
    (r"\bimmediately\b.*\bsecure\b|\bsecure\b.*\bimmediately\b",
     "urgency pressure to secure property", 8, "LOW"),
    (r"\blimited\s+time\b|\bact\s+now\b|\bfirst\s+come\s+first\s+served\b",
     "high-pressure time limit", 8, "LOW"),
    (r"\bmany\s+(applicants|interested|enquiries)\b",
     "artificial scarcity / fake competition pressure", 8, "LOW"),
    (r"\bno\s+questions\s+asked\b",
     "no-questions-asked clause", 3, "MINIMAL"),
]


def check_red_flags(text: str) -> list[dict]:
    """Return list of triggered red flags with matched snippet, severity score and label."""
    hits = []
    text_lower = text.lower()
    for pattern, label, severity, severity_label in RED_FLAGS:
        m = re.search(pattern, text_lower)
        if m:
            start = max(0, m.start() - 30)
            end   = min(len(text), m.end() + 30)
            hits.append({
                "flag":           label,
                "snippet":        text[start:end].strip(),
                "severity":       severity,
                "severity_label": severity_label,
            })
    # Sort by severity descending so most critical flags appear first
    hits.sort(key=lambda x: x["severity"], reverse=True)
    return hits


# ──────────────────────────────────────────────────────────────
# Scam detector — TF-IDF similarity + red-flag patterns
# ──────────────────────────────────────────────────────────────
class RentalScamDetector:
    """
    Two-layer analysis:
      Layer 1 — Red-flag patterns: 28 regex rules for known scam signals
                (payment methods, overseas landlord, WhatsApp-only, etc.)
      Layer 2 — Semantic anomaly: sentence-transformer embeddings compared
                against AU tenancy forms + CUAD legal clauses via cosine
                similarity. Catches paraphrased scams that exact keyword
                rules miss (e.g. "transfer funds" ≈ "send cash").

    Embeddings are cached to disk after the first run for fast startup.
    Final risk score combines both layers.
    """

    def __init__(self, reference_texts: list[str]):
        print(f"Loading embedding model ({EMBED_MODEL}) …", end=" ", flush=True)
        self.model = TextEmbedding(EMBED_MODEL)
        print("done")

        if EMBED_CACHE.exists():
            print("Loading cached reference embeddings …", end=" ", flush=True)
            self.ref_embeddings = np.load(EMBED_CACHE)
            print(f"done  ({len(self.ref_embeddings):,} vectors)")
        else:
            print(f"Encoding {len(reference_texts):,} reference texts "
                  f"(one-time, ~60 s on CPU) …")
            self.ref_embeddings = np.array(list(self.model.embed(reference_texts)))
            # Normalise to unit vectors so dot product = cosine similarity
            norms = np.linalg.norm(self.ref_embeddings, axis=1, keepdims=True)
            self.ref_embeddings = self.ref_embeddings / np.maximum(norms, 1e-9)
            np.save(EMBED_CACHE, self.ref_embeddings)
            print(f"Embedding cache saved to {EMBED_CACHE}")

    def score_chunks(self, chunks: list[str]) -> pd.DataFrame:
        """Return a DataFrame with each chunk and its best semantic similarity score."""
        if not chunks:
            return pd.DataFrame()
        query_embs = np.array(list(self.model.embed(chunks)))
        norms = np.linalg.norm(query_embs, axis=1, keepdims=True)
        query_embs = query_embs / np.maximum(norms, 1e-9)
        # Matrix multiply gives cosine similarity for unit-norm vectors
        sims = query_embs @ self.ref_embeddings.T   # shape: (n_chunks, n_ref)
        best_scores = sims.max(axis=1)
        return pd.DataFrame({
            "chunk":      chunks,
            "best_score": best_scores,
            "anomalous":  best_scores < SUSPICION_THRESHOLD,
        })

    def analyse(self, text: str) -> dict:
        """Full analysis of a raw text string."""
        text   = normalize_text(text)
        chunks = chunk_legal_text(text)
        df     = self.score_chunks(chunks)

        # Layer 1: red flags
        red_flags  = check_red_flags(text)
        n_flags    = len(red_flags)
        flag_score = sum(rf["severity"] for rf in red_flags)

        # Layer 2: anomalous chunks
        n_anomalous = int(df["anomalous"].sum()) if not df.empty else 0
        anomaly_pct = round(100 * n_anomalous / max(len(df), 1), 1)

        # Combined risk: severity-weighted flags dominate; anomaly adds up to 20 pts
        combined_risk = min(100, flag_score + round(anomaly_pct * 0.4))

        # Verdict thresholds:
        #   CRITICAL flag alone = 50 pts → HIGH RISK
        #   2× HIGH flags       = 60 pts → HIGH RISK
        #   1× HIGH flag        = 30 pts → MEDIUM RISK
        #   MEDIUM/illegal flag = 15 pts → LOW-MEDIUM (caution)
        #   LOW flags / anomaly only → LOW RISK
        has_critical = any(rf["severity_label"] == "CRITICAL" for rf in red_flags)
        if has_critical or combined_risk >= 45:
            verdict = "HIGH RISK — strong scam indicators detected"
        elif combined_risk >= 25:
            verdict = "MEDIUM RISK — some suspicious elements"
        elif combined_risk >= 10 or anomaly_pct >= 30:
            verdict = "LOW-MEDIUM RISK — one or more clauses need attention"
        else:
            verdict = "LOW RISK — looks similar to standard AU leases"

        return {
            "verdict":       verdict,
            "combined_risk": combined_risk,
            "flag_score":    min(100, flag_score),
            "red_flags":     red_flags,
            "n_flags":       n_flags,
            "total_chunks":  len(df),
            "n_anomalous":   n_anomalous,
            "anomaly_pct":   anomaly_pct,
            "details":       df,
            "doc_text":      text,
        }


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────
def main():
    # 1. Load reference data
    cuad_clauses, cuad_texts = load_cuad()
    au_chunks = load_forms_and_chunk(FORMS_DIR)
    au_texts  = [r["text"] for r in au_chunks]
    print(f"AU baseline: {len(au_chunks)} chunks from {FORMS_DIR.name}/")

    # 2. Save processed data for inspection
    pd.DataFrame(cuad_clauses).to_csv(PROCESSED_DIR / "cuad_clauses.csv", index=False)
    pd.DataFrame(au_chunks).to_csv(PROCESSED_DIR / "au_baseline_chunks.csv", index=False)
    print(f"Saved CSVs to {PROCESSED_DIR}/")

    # 3. Build detector (reference = AU forms + CUAD clauses)
    reference_texts = au_texts + cuad_texts
    detector = RentalScamDetector(reference_texts)

    # 4. Analyse: either a file from argv or a built-in demo text
    if len(sys.argv) > 1:
        doc_path = sys.argv[1]
        print(f"\nAnalysing: {doc_path}")
        text = load_document(doc_path)
    else:
        print("\nNo file supplied — running built-in demo …")
        text = """
        Send $2000 Western Union to secure this property immediately.
        The landlord is overseas and cannot meet in person.
        You will receive the keys by post after payment is confirmed.
        No inspection is possible before signing.
        This agreement is binding and non-refundable under all circumstances.
        The tenant waives all rights under the Residential Tenancies Act.
        Monthly rent shall increase by 20% each quarter without notice.
        The landlord may enter the premises at any time without prior notice.
        """

    result = detector.analyse(text)

    print("\n" + "═" * 55)
    print(f"  VERDICT:  {result['verdict']}")
    print(f"  Combined risk score: {result['combined_risk']}%")
    print(f"  Red flags triggered: {result['n_flags']}")
    print(f"  Anomalous chunks:    {result['n_anomalous']}/{result['total_chunks']}"
          f"  ({result['anomaly_pct']}%)")
    print("═" * 55)

    if result["red_flags"]:
        print("\nRed flags detected:\n")
        for rf in result["red_flags"]:
            print(f"  ⚠  {rf['flag']}")
            print(f"     … {rf['snippet']} …\n")

    anomalous = result["details"][result["details"]["anomalous"]]
    if not anomalous.empty:
        print("\nAnomaly-detected chunks (no close match in known AU leases):\n")
        for _, row in anomalous.iterrows():
            print(f"  [score={row['best_score']:.3f}] {row['chunk'][:120]} …")

    # Save detailed results
    out = PROCESSED_DIR / "last_analysis.csv"
    result["details"].to_csv(out, index=False)
    print(f"\nFull results saved to {out}")


if __name__ == "__main__":
    main()
