"""eccite 的连接管理与引文表 schema。

引文表建在主库 db/ec_papers.db 中，由本模块的 ensure_schema() 创建
（全部 IF NOT EXISTS，与 ecdb.importer 的 build 互不干扰）。
主库的常规查询仍走 ecdb；本模块只服务于引文子系统的读写。
"""
import sqlite3
import time
from datetime import datetime, timezone

from ecdb import _paths

# 增量迁移/写入时每批提交的行数：小事务把写锁让给并行运行的清洗会话。
BATCH_ROWS = 20000

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS paper_refs_out (
  accession_no TEXT NOT NULL REFERENCES papers(accession_no) ON DELETE CASCADE,
  source       TEXT NOT NULL,
  cited_key    TEXT NOT NULL,
  seq          INTEGER,
  cited_doi    TEXT,
  cited_title  TEXT,
  cited_year   INTEGER,
  PRIMARY KEY (accession_no, source, cited_key)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_refs_cited ON paper_refs_out(cited_doi);

CREATE TABLE IF NOT EXISTS paper_cited_in (
  accession_no TEXT NOT NULL REFERENCES papers(accession_no) ON DELETE CASCADE,
  source       TEXT NOT NULL,
  citing_key   TEXT NOT NULL,
  citing_doi   TEXT,
  citing_year  INTEGER,
  PRIMARY KEY (accession_no, source, citing_key)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_citedin_citing ON paper_cited_in(citing_doi);

CREATE TABLE IF NOT EXISTS paper_cit_meta (
  accession_no      TEXT PRIMARY KEY REFERENCES papers(accession_no) ON DELETE CASCADE,
  doi               TEXT,
  doi_source        TEXT,
  s2_id             TEXT,
  oa_id             TEXT,
  oa_cited_by_count INTEGER,
  cr_cit_count      INTEGER,
  cr_ref_count      INTEGER,
  s2_cit_count      INTEGER,
  s2_ref_count      INTEGER,
  refs_status       TEXT,
  cites_status      TEXT,
  cr_done           INTEGER,
  s2_done           INTEGER,
  coci_done         INTEGER,
  migrated          INTEGER DEFAULT 0,
  fetched_at        TEXT
);
CREATE INDEX IF NOT EXISTS idx_citmeta_doi ON paper_cit_meta(doi);

CREATE TABLE IF NOT EXISTS paper_cit_edges (
  citing_acc TEXT NOT NULL REFERENCES papers(accession_no) ON DELETE CASCADE,
  cited_acc  TEXT NOT NULL REFERENCES papers(accession_no) ON DELETE CASCADE,
  n_sources  INTEGER,
  PRIMARY KEY (citing_acc, cited_acc)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_edges_cited ON paper_cit_edges(cited_acc);
"""

CIT_TABLES = ("paper_refs_out", "paper_cited_in", "paper_cit_meta", "paper_cit_edges")


def db_path():
    return _paths.db_path()


def old_db_default():
    """EC_History 快照库的默认位置（项目根的兄弟目录，可被 --old-db 覆盖）。"""
    import os
    env = os.environ.get("ECCITE_OLD_DB")
    if env:
        return env
    return _paths.project_root().parent / "EC_History" / "ec_corpus.db"


def connect_ro():
    """只读连接（主库可能正被清洗会话写入，mode=ro 不会加写锁）。"""
    p = db_path()
    conn = sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def connect_rw():
    """读写连接。FK 关闭：并发清洗可能瞬时增删 papers，批量插入不能因
    瞬时孤儿行整批失败；孤儿行由 reconcile 清理、validate 的
    foreign_key_check 兜底。"""
    conn = sqlite3.connect(str(db_path()), timeout=150)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=150000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    return conn


def ensure_schema(conn):
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def missing_tables(conn):
    have = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    return [t for t in CIT_TABLES if t not in have]


def seed_meta(rw):
    """为尚无 meta 行的论文补行（幂等，不触碰已有行）。

    有 DOI -> pending 待抓；无 DOI -> no_doi（源无从抓取，留待 match-doi* 找回）。
    """
    cur = rw.execute(
        "INSERT OR IGNORE INTO paper_cit_meta "
        "(accession_no, doi, doi_source, refs_status, cites_status) "
        "SELECT p.accession_no, p.doi, 'ei', 'pending', 'pending' FROM papers p "
        "WHERE p.doi IS NOT NULL AND p.doi != ''")
    n = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    cur2 = rw.execute(
        "INSERT OR IGNORE INTO paper_cit_meta "
        "(accession_no, doi, doi_source, refs_status, cites_status) "
        "SELECT p.accession_no, NULL, 'ei', 'no_doi', 'no_doi' FROM papers p "
        "WHERE p.doi IS NULL OR p.doi = ''")
    if cur2.rowcount and cur2.rowcount > 0:
        n += cur2.rowcount
    rw.commit()
    return n


def build_active_within(minutes=10):
    """清洗会话的 build 是否刚跑过（db_meta.last_build_at 距今分钟数）。"""
    try:
        conn = connect_ro()
        row = conn.execute(
            "SELECT value FROM db_meta WHERE key='last_build_at'").fetchone()
        conn.close()
        if not row:
            return None
        ts = datetime.strptime(str(row[0])[:19], "%Y-%m-%d %H:%M:%S")
        return (datetime.now(timezone.utc).replace(tzinfo=None) - ts).total_seconds() / 60
    except Exception:
        return None


def warn_if_build_active():
    age = build_active_within()
    if age is not None and age < 10:
        print("[eccite] 警告：主库 build 最近 %.1f 分钟内运行过，清洗会话可能仍在"
              "写入；本阶段写入采用小事务+busy_timeout，如遇 database is locked "
              "请稍后重跑（幂等）。" % age)


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]
