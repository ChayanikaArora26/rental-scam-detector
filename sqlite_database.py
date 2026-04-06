"""
database.py — SQLite persistence layer for the Rental Scam Detector.

Tables
──────
users       — one row per person who uses the tool
analyses    — one row per document analysed
red_flags   — one row per triggered red flag in an analysis
"""

import sqlite3
import pathlib
from datetime import datetime

import os as _os
DB_PATH = pathlib.Path(_os.environ.get("DB_PATH", "") or (pathlib.Path(__file__).parent / "data" / "rental_scam.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # rows behave like dicts
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables if they don't already exist."""
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                email      TEXT    NOT NULL UNIQUE,
                created_at TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS analyses (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL REFERENCES users(id),
                filename      TEXT,
                verdict       TEXT    NOT NULL,
                combined_risk INTEGER NOT NULL,
                n_flags       INTEGER NOT NULL,
                n_anomalous   INTEGER NOT NULL,
                llm_summary   TEXT,
                created_at    TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS red_flags (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL REFERENCES analyses(id),
                flag        TEXT    NOT NULL,
                snippet     TEXT
            );
        """)


def get_or_create_user(name: str, email: str) -> int:
    """Return the user's id, creating the row if this email is new."""
    email = email.strip().lower()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO users (name, email, created_at) VALUES (?, ?, ?)",
            (name.strip(), email, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def save_analysis(
    user_id: int,
    result: dict,
    llm_result: dict | None,
    filename: str = "",
) -> int:
    """
    Persist one analysis run.  Returns the new analysis id.

    Parameters
    ──────────
    user_id    — from get_or_create_user()
    result     — dict returned by RentalScamDetector.analyse()
    llm_result — dict returned by llm_analyser.explain(), or None
    filename   — original filename (empty string for pasted text)
    """
    llm_summary = None
    if llm_result:
        llm_summary = llm_result.get("summary", "")

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO analyses
               (user_id, filename, verdict, combined_risk, n_flags,
                n_anomalous, llm_summary, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                filename,
                result["verdict"],
                int(result["combined_risk"]),
                result["n_flags"],
                result["n_anomalous"],
                llm_summary,
                datetime.utcnow().isoformat(),
            ),
        )
        analysis_id = cur.lastrowid

        for rf in result.get("red_flags", []):
            conn.execute(
                "INSERT INTO red_flags (analysis_id, flag, snippet) VALUES (?, ?, ?)",
                (analysis_id, rf["flag"], rf.get("snippet", "")),
            )

    return analysis_id


def get_user_history(email: str) -> list[dict]:
    """
    Return all past analyses for this email, newest first.
    Each item includes the list of red flags from that run.
    """
    email = email.strip().lower()
    with _connect() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if not user:
            return []

        rows = conn.execute(
            """SELECT a.id, a.filename, a.verdict, a.combined_risk,
                      a.n_flags, a.n_anomalous, a.llm_summary, a.created_at
               FROM   analyses a
               WHERE  a.user_id = ?
               ORDER  BY a.created_at DESC""",
            (user["id"],),
        ).fetchall()

        history = []
        for row in rows:
            flags = conn.execute(
                "SELECT flag, snippet FROM red_flags WHERE analysis_id = ?",
                (row["id"],),
            ).fetchall()
            history.append({
                **dict(row),
                "red_flags": [dict(f) for f in flags],
            })
        return history
