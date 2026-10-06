"""ecdomain 的连接管理与标签表 schema（建在主库，全部 IF NOT EXISTS，
与 ecdb.importer 的 build、eccite 的引文表互不干扰）。"""
import sqlite3
from datetime import datetime, timezone

from ecdb import _paths

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS venue_tier (
  venue_tag  TEXT PRIMARY KEY,
  tier       TEXT NOT NULL,           -- A_pure_ec / B_ci_broad / C_mixed_appl
  decided_by TEXT NOT NULL,           -- proposed / user（user 行不被覆盖）
  note       TEXT
);

CREATE TABLE IF NOT EXISTS paper_domain (
  accession_no TEXT PRIMARY KEY REFERENCES papers(accession_no) ON DELETE CASCADE,
  label        TEXT NOT NULL,          -- EC / NON_EC
  tier         TEXT NOT NULL,          -- venue / rule / llm / llm2 / human
  confidence   REAL,
  evidence     TEXT,
  model        TEXT,
  rule_ver     TEXT,
  judged_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pdomain_label ON paper_domain(label);
CREATE INDEX IF NOT EXISTS idx_pdomain_tier  ON paper_domain(tier);

CREATE TABLE IF NOT EXISTS domain_meta (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,           -- JSON
  updated_at TEXT NOT NULL
);
"""


def db_path():
    return _paths.db_path()


def connect_ro():
    conn = sqlite3.connect(db_path().resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def connect_rw():
    conn = sqlite3.connect(str(db_path()), timeout=150)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=150000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    return conn


def ensure_schema(conn):
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def set_meta(rw, key, value):
    rw.execute(
        "INSERT INTO domain_meta(key, value, updated_at) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value, utcnow()))


def get_meta(key):
    conn = connect_ro()
    try:
        row = conn.execute("SELECT value FROM domain_meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
