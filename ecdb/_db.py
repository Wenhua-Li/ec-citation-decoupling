"""连接管理与共享的小工具，供 importer 与查询 API 共用。"""
import re
import sqlite3

from . import _paths

# papers 表字段（有序，导入与查询共用同一份定义）
PAPER_COLUMNS = [
    "accession_no", "doi", "title", "abstract", "authors_raw",
    "affiliations_raw", "corresponding_authors", "source", "source_abbr",
    "venue_tag", "publisher", "volume", "issue", "pages", "article_number",
    "pub_year", "issue_date", "language", "issn", "e_issn", "coden",
    "isbn", "isbn13", "doc_type", "num_references", "main_heading",
    "classification_code", "treatment", "funding_details", "funding_text",
    "open_access", "conf_name", "conf_date", "conf_location", "conf_code",
    "sponsor", "editor", "extra", "quality_flags", "added_at", "updated_at",
]


def connect(db_path=None, readonly=True):
    """打开连接。readonly=True 时用 URI 只读模式（库不存在会直接报错）。"""
    import pathlib
    path = pathlib.Path(db_path) if db_path is not None else _paths.db_path()
    if readonly:
        uri = path.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def fts5_available():
    """检测当前 Python 内置 SQLite 是否编译了 FTS5。"""
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE temp.__fts_check USING fts5(x)")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def db_has_fts(conn):
    """数据库里是否真的建了 papers_fts 表。"""
    try:
        conn.execute("SELECT rowid FROM papers_fts LIMIT 0")
        return True
    except sqlite3.OperationalError:
        return False


def normalize_doi(v):
    """小写化并剥离 URL/doi: 前缀；空值返回 None。"""
    if v is None:
        return None
    d = str(v).strip().lower()
    for pref in ("https://dx.doi.org/", "http://dx.doi.org/",
                 "https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(pref):
            d = d[len(pref):].strip()
    return d or None


_DOCTYPE_RE = re.compile(r"\(([A-Za-z]{1,4})\)\s*$")


def clean_doc_type(v):
    '''"Journal article (JA)" -> "JA"；无括号代码则保留原文。'''
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    m = _DOCTYPE_RE.search(s)
    return m.group(1).upper() if m else s


def like_escape(s):
    """转义 LIKE 通配符，配合 ESCAPE '\\' 使用。"""
    return str(s).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
