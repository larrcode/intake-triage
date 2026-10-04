"""
Storage layer for Intake Triage Assistant.

Design decision: the audit log is a SEPARATE table from requests, and
it's append-only, nothing ever updates or deletes a row in it. If a
request record is later edited or even deleted, the audit trail still
shows exactly who did what and when. An audit log that lives inside
the same mutable row it's auditing isn't really an audit log, it's
just a field that can be overwritten.
"""

import sqlite3
import hashlib
import secrets
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "intake.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'staff',  -- 'staff' or 'admin'
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    request_text TEXT NOT NULL,
    ai_category TEXT,
    ai_response TEXT,
    final_category TEXT,
    final_response TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, approved, rejected
    approved_by TEXT,
    approved_at TEXT
);

-- Append-only. No UPDATE or DELETE statements should ever target this
-- table; storage.py enforces that by never exposing one.
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


# ---------- password hashing ----------
# Same pattern as password-hashing-demo: salted SHA-256. A real
# production system would use bcrypt or argon2 (deliberately slow,
# resistant to brute-force at scale); SHA-256 with a per-user salt is
# adequate for a local single-org desktop tool but is a known
# limitation worth naming, not a production-grade choice.

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode()).hexdigest()
    return digest, salt


def create_user(conn, username, password, role="staff"):
    digest, salt = hash_password(password)
    conn.execute(
        "INSERT INTO users (username, password_hash, salt, role, created_at) VALUES (?, ?, ?, ?, ?)",
        (username, digest, salt, role, datetime.now().isoformat()),
    )
    conn.commit()


def verify_user(conn, username, password):
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        return None
    digest, _ = hash_password(password, row["salt"])
    if secrets.compare_digest(digest, row["password_hash"]):
        return row
    return None


# ---------- audit log ----------

def log_action(conn, username, action, detail=""):
    conn.execute(
        "INSERT INTO audit_log (timestamp, username, action, detail) VALUES (?, ?, ?, ?)",
        (datetime.now().isoformat(), username, action, detail),
    )
    conn.commit()


def fetch_audit_log(conn, limit=200):
    return conn.execute(
        "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()


# ---------- requests ----------

def save_pending_request(conn, request_text, ai_category, ai_response):
    cur = conn.execute(
        """INSERT INTO requests (created_at, request_text, ai_category, ai_response, status)
           VALUES (?, ?, ?, ?, 'pending')""",
        (datetime.now().isoformat(), request_text, ai_category, ai_response),
    )
    conn.commit()
    return cur.lastrowid


def approve_request(conn, request_id, final_category, final_response, approved_by):
    conn.execute(
        """UPDATE requests
           SET final_category = ?, final_response = ?, status = 'approved',
               approved_by = ?, approved_at = ?
           WHERE id = ?""",
        (final_category, final_response, approved_by, datetime.now().isoformat(), request_id),
    )
    conn.commit()
    log_action(conn, approved_by, "approve_request", f"request_id={request_id}")


def fetch_history(conn, limit=100):
    return conn.execute(
        "SELECT * FROM requests WHERE status = 'approved' ORDER BY approved_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
