"""
anonymiser/pipeline.py — PII scrubbing before any text reaches the LLM.

Strategy (layered):
  1. Regex — high-precision patterns for structured PII (email, phone, card, etc.)
  2. spaCy NER — catches names and organisations missed by regex

anonymise(text) -> (anonymised_text, pii_map)
  pii_map: {placeholder: original_value} for optional local de-anonymisation
"""
import re
import uuid
from functools import lru_cache
from typing import Any

try:
    import spacy
    _nlp = spacy.load("en_core_web_sm")
    _SPACY_AVAILABLE = True
except Exception:
    _SPACY_AVAILABLE = False

# ── Regex patterns ─────────────────────────────────────────────────────────

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL",     re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("PHONE",     re.compile(
        r"(?:\+?61|0)(?:\s*\(?\d\)?\s*){8,9}"           # AU mobile/landline
        r"|(?:\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}"  # US
        r"|\b\d{2}[\s\-]\d{4}[\s\-]\d{4}\b"
    )),
    ("CARD",      re.compile(r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6011)[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?:[\s\-]?\d{3,4})?\b")),
    ("DOB",       re.compile(r"\b(?:0?[1-9]|[12]\d|3[01])[/\-\.](?:0?[1-9]|1[012])[/\-\.](?:19|20)\d{2}\b")),
    ("HEALTH_ID", re.compile(r"\b\d{10}[A-Z]\b|\bMC\d{9}\b|\bDVA\s*[A-Z]\d{6,9}\b")),  # AU Medicare / DVA
    ("TFN",       re.compile(r"\b\d{3}\s?\d{3}\s?\d{3}\b")),  # AU Tax File Number (9 digits)
    ("ADDRESS",   re.compile(
        r"\b\d{1,5}\s+[A-Za-z0-9\s,]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|"
        r"Drive|Dr|Lane|Ln|Court|Ct|Place|Pl|Way|Terrace|Tce|Circuit|Cct|Close|Cl)\b",
        re.IGNORECASE,
    )),
]


def _placeholder(label: str, idx: int) -> str:
    return f"[{label}_{idx}]"


def anonymise(text: str) -> tuple[str, dict[str, str]]:
    """
    Scrub PII from text.

    Returns:
        anonymised_text — safe to send to LLM
        pii_map         — {placeholder: original} for local de-anonymisation
    """
    if not text:
        return text, {}

    pii_map: dict[str, str] = {}
    counters: dict[str, int] = {}
    result = text

    # ── Phase 1: regex ───────────────────────────────────────────
    for label, pattern in _PATTERNS:
        def _replace(m: re.Match, _label=label) -> str:
            original = m.group(0)
            # Reuse placeholder if same value seen twice
            for ph, orig in pii_map.items():
                if orig == original:
                    return ph
            counters[_label] = counters.get(_label, 0) + 1
            ph = _placeholder(_label, counters[_label])
            pii_map[ph] = original
            return ph

        result = pattern.sub(_replace, result)

    # ── Phase 2: spaCy NER for names/orgs ────────────────────────
    if _SPACY_AVAILABLE:
        doc = _nlp(result)
        # Process in reverse so offsets stay valid
        for ent in reversed(doc.ents):
            if ent.label_ not in ("PERSON", "ORG", "GPE"):
                continue
            label_map = {"PERSON": "PERSON", "ORG": "ORG", "GPE": "LOCATION"}
            label = label_map[ent.label_]
            original = ent.text
            # Skip if already replaced
            if original.startswith("[") and original.endswith("]"):
                continue
            # Reuse if seen
            existing = next((ph for ph, v in pii_map.items() if v == original), None)
            if existing:
                result = result[:ent.start_char] + existing + result[ent.end_char:]
            else:
                counters[label] = counters.get(label, 0) + 1
                ph = _placeholder(label, counters[label])
                pii_map[ph] = original
                result = result[:ent.start_char] + ph + result[ent.end_char:]

    return result, pii_map


def deanonymise(text: str, pii_map: dict[str, str]) -> str:
    """Restore original values using the local map — never sent outside the process."""
    for placeholder, original in pii_map.items():
        text = text.replace(placeholder, original)
    return text
