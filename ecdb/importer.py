"""从 Engineering Village（EI Compendex）CSV 导出构建 SQLite 数据库。

用法（在项目根目录运行）：
    python -m ecdb build             # 首次构建或增量导入（幂等，可重跑）
    python -m ecdb build --rebuild   # 丢弃旧库（自动备份为 .bak）后全量重建

数据流：data_from_EI/*.csv -> 清洗/剔除/去重/拆表 -> db/ec_papers.db
"""
import csv
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import _db, _paths, cleaning
from ._db import PAPER_COLUMNS

SCHEMA_VERSION = "1.1"
KEEP_DOC_TYPES = {"JA", "CA"}  # 仅保留期刊文章与会议文章（用户决定）

# EI 原始列名（小写、空白归一后）-> papers 字段。
# @controlled/@uncontrolled 为拆表字段；未列出的列进入 extra JSON，
# DROPPED_COLUMNS 中的列直接丢弃（内容恒定或极少使用）。
COLUMN_MAP = {
    "title": "title",
    "accession number": "accession_no",
    "author": "authors_raw",
    "authors": "authors_raw",
    "author affiliation": "affiliations_raw",
    "author affiliations": "affiliations_raw",
    "corresponding author(s)": "corresponding_authors",
    "corresponding author": "corresponding_authors",
    "source": "source",
    "abbreviated source title": "source_abbr",
    "publisher/repository": "publisher",
    "volume": "volume",
    "issue": "issue",
    "pages": "pages",
    "article number": "article_number",
    "article or paper number": "article_number",
    "issue date": "issue_date",
    "publication year": "pub_year",
    "language": "language",
    "issn": "issn",
    "e-issn": "e_issn",
    "eissn": "e_issn",
    "coden": "coden",
    "isbn": "isbn",
    "isbn13": "isbn13",
    "isbn 13": "isbn13",
    "doi": "doi",
    "document type": "doc_type",
    "abstract": "abstract",
    "number of references": "num_references",
    "main heading": "main_heading",
    "controlled/subject terms": "@controlled",
    "uncontrolled terms": "@uncontrolled",
    "classification code": "classification_code",
    "treatment": "treatment",
    "funding details": "funding_details",
    "funding text": "funding_text",
    "open access type(s)": "open_access",
    "open access": "open_access",
    "conference name": "conf_name",
    "conference date": "conf_date",
    "conference location": "conf_location",
    "conference code": "conf_code",
    "sponsor": "sponsor",
    "editor": "editor",
}

DROPPED_COLUMNS = {
    "database", "copyright", "data provider", "part number",
    "monograph title", "volume title", "title of translation",
    "abstract type", "link to proquest dissertations",
}

TABLES_SQL = """
CREATE TABLE IF NOT EXISTS papers (
    accession_no          TEXT PRIMARY KEY,
    doi                   TEXT,
    title                 TEXT NOT NULL,
    abstract              TEXT,
    authors_raw           TEXT,
    affiliations_raw      TEXT,
    corresponding_authors TEXT,
    source                TEXT,
    source_abbr           TEXT,
    venue_tag             TEXT,
    publisher             TEXT,
    volume                TEXT,
    issue                 TEXT,
    pages                 TEXT,
    article_number        TEXT,
    pub_year              INTEGER,
    issue_date            TEXT,
    language              TEXT,
    issn                  TEXT,
    e_issn                TEXT,
    coden                 TEXT,
    isbn                  TEXT,
    isbn13                TEXT,
    doc_type              TEXT,
    num_references        INTEGER,
    main_heading          TEXT,
    classification_code   TEXT,
    treatment             TEXT,
    funding_details       TEXT,
    funding_text          TEXT,
    open_access           TEXT,
    conf_name             TEXT,
    conf_date             TEXT,
    conf_location         TEXT,
    conf_code             TEXT,
    sponsor               TEXT,
    editor                TEXT,
    extra                 TEXT,
    quality_flags         TEXT,
    added_at              TEXT,
    updated_at            TEXT
);
CREATE TABLE IF NOT EXISTS paper_authors (
    accession_no TEXT NOT NULL REFERENCES papers(accession_no) ON DELETE CASCADE,
    position     INTEGER NOT NULL,
    name_raw     TEXT,
    name_display TEXT,
    affil_refs   TEXT,
    PRIMARY KEY (accession_no, position)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS paper_affiliations (
    accession_no TEXT NOT NULL REFERENCES papers(accession_no) ON DELETE CASCADE,
    idx          INTEGER NOT NULL,
    affiliation  TEXT,
    PRIMARY KEY (accession_no, idx)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS paper_terms (
    accession_no TEXT NOT NULL REFERENCES papers(accession_no) ON DELETE CASCADE,
    kind         TEXT NOT NULL,
    term         TEXT NOT NULL,
    PRIMARY KEY (accession_no, kind, term)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS paper_sources (
    accession_no TEXT NOT NULL REFERENCES papers(accession_no) ON DELETE CASCADE,
    filename     TEXT NOT NULL,
    PRIMARY KEY (accession_no, filename)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS db_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_papers_doi    ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_year   ON papers(pub_year);
CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source);
CREATE INDEX IF NOT EXISTS idx_papers_doctype ON papers(doc_type);
CREATE INDEX IF NOT EXISTS idx_papers_venue  ON papers(venue_tag);
CREATE INDEX IF NOT EXISTS idx_pa_name       ON paper_authors(name_display);
CREATE INDEX IF NOT EXISTS idx_pt_term       ON paper_terms(term);
"""

VIEW_SQL = """
CREATE VIEW IF NOT EXISTS v_papers_flat AS
SELECT p.accession_no, p.doi, p.title, p.abstract, p.pub_year, p.doc_type,
       p.source, p.source_abbr, p.venue_tag, p.publisher, p.volume, p.issue,
       p.pages, p.article_number, p.language, p.issn, p.e_issn,
       p.num_references, p.main_heading, p.funding_details, p.open_access,
       p.conf_name, p.conf_date, p.conf_location,
       (SELECT GROUP_CONCAT(pa.name_display, '; ') FROM paper_authors pa
        WHERE pa.accession_no = p.accession_no) AS authors,
       (SELECT GROUP_CONCAT(pt.term, '; ') FROM paper_terms pt
        WHERE pt.accession_no = p.accession_no) AS terms
FROM papers p;
"""

# ---------------------------------------------------------------------------
# 文本解析与清洗
# ---------------------------------------------------------------------------

_AUTHOR_REF_RE = re.compile(r"^(.*?)\s*\((\d+(?:\s*;\s*\d+)*)\)\s*$", re.S)
_AFFIL_SPLIT_RE = re.compile(r"(?=\(\d+\))")
_AFFIL_HEAD_RE = re.compile(r"^\((\d+)\)\s*")


def _nz(v):
    """去首尾空白；空串 -> None（保留内部换行）。"""
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _collapse(v):
    """去首尾空白并把内部所有空白（含换行）折叠为单个空格。"""
    if v is None:
        return None
    s = " ".join(str(v).split())
    return s or None


def _display_name(name_raw):
    """"Yazdani, Danial" -> "Danial Yazdani"。"""
    if "," in name_raw:
        last, first = name_raw.split(",", 1)
        return (first.strip() + " " + last.strip()).strip()
    return name_raw


def parse_authors(raw):
    """解析 EI 作者串 "Yazdani, Danial (1); Luo, Wenjian (2)"。

    返回 [(name_raw, name_display, affil_refs)]；affil_refs 形如 "1" / "1;2"。
    """
    out = []
    if not raw:
        return out
    for part in str(raw).split(";"):
        part = _collapse(part)
        if not part:
            continue
        m = _AUTHOR_REF_RE.match(part)
        if m:
            name = m.group(1).strip()
            if not name:  # 裸 "(1)" 碎片
                continue
            refs = ";".join(x.strip() for x in m.group(2).split(";"))
        else:
            name, refs = part, None
        out.append((name, _display_name(name), refs))
    return out


def parse_affiliations(raw):
    """解析机构串 "(1) Dept, Univ, City (2) ..." -> [(idx, affiliation)]。

    EI 的机构标记 "(n)" 之间可能没有分号（分号只出现在地址内部），
    因此按零宽前瞻在 "(数字)" 前切分；"(Shenzhen)" 这类非数字括号不会误切。
    """
    out = []
    if not raw:
        return out
    text = " ".join(str(raw).split())
    segments = _AFFIL_SPLIT_RE.split(text)
    next_idx = 1
    for seg in segments:
        seg = seg.strip().rstrip(";").strip()
        if not seg:
            continue
        m = _AFFIL_HEAD_RE.match(seg)
        if m:
            idx, body = int(m.group(1)), seg[m.end():].strip()
        else:
            idx, body = next_idx, seg
        next_idx = idx + 1
        if body:
            out.append((idx, body))
    return out


def parse_terms(raw, kind):
    """切分关键词串 -> [(kind, term)]。

    EI 用 " - "（空格-连字符-空格）分隔关键词，个别导出用分号；
    连字符两侧无空格时属于词本身（如 "Linear-programming"），不切。
    """
    out = []
    if not raw:
        return out
    for part in re.split(r"\s+-\s+|\s*;\s*|\n", str(raw)):
        t = _collapse(part)
        if t:
            out.append((kind, t))
    return out


def _clean_year(v):
    if v is None:
        return None
    m = re.search(r"\d{4}", str(v))
    return int(m.group()) if m else None


def _clean_int(v):
    if v is None:
        return None
    digits = re.sub(r"\D", "", str(v))
    return int(digits) if digits else None


def venue_tag_from_filename(name):
    """从 CSV 文件名推导来源标签（小写）。

    TEVC_detailed_7-31-2026_16225998.csv -> "tevc"
    Engineering_Village_GECCO_2020_2026_detailed_9-26-2026_1.csv -> "gecco_2020_2026"
    """
    stem = Path(name).stem
    low = stem.lower()
    if low.startswith("engineering_village_"):
        stem = stem[len("engineering_village_"):]
    pos = stem.lower().find("_detailed")
    if pos > 0:
        stem = stem[:pos]
    return stem.lower() or Path(name).stem.lower()


def _prepare(raw_row, venue_tag):
    """一行 CSV -> (rec, authors, affils, terms)。未做剔除判断。"""
    row = {}
    extras = {}
    funding_d, funding_t = [], []
    controlled = uncontrolled = None
    for k, v in raw_row.items():
        if k is None or v is None:
            continue
        key = " ".join(str(k).lower().split())
        if not key or key in DROPPED_COLUMNS:
            continue
        if key.startswith("funding text"):
            funding_t.append(str(v).strip())
            continue
        if key.startswith("funding details"):
            funding_d.append(str(v).strip())
            continue
        dest = COLUMN_MAP.get(key)
        if dest == "@controlled":
            controlled = str(v)
        elif dest == "@uncontrolled":
            uncontrolled = str(v)
        elif dest:
            row[dest] = str(v)
        else:
            extras[k.strip()] = str(v)

    rec = {c: None for c in PAPER_COLUMNS}
    for f in ("title", "abstract", "authors_raw", "affiliations_raw",
              "corresponding_authors", "source", "source_abbr", "publisher",
              "volume", "issue", "pages", "article_number", "issue_date",
              "language", "issn", "e_issn", "coden", "isbn", "isbn13",
              "main_heading", "classification_code", "treatment", "open_access",
              "conf_name", "conf_date", "conf_location", "conf_code",
              "sponsor", "editor"):
        rec[f] = _collapse(row.get(f))
    rec["accession_no"] = _collapse(row.get("accession_no"))
    rec["doi"] = _db.normalize_doi(row.get("doi"))
    rec["venue_tag"] = venue_tag
    rec["pub_year"] = _clean_year(row.get("pub_year"))
    rec["doc_type"] = _db.clean_doc_type(row.get("doc_type"))
    rec["num_references"] = _clean_int(row.get("num_references"))
    rec["funding_details"] = "; ".join(funding_d) or None
    rec["funding_text"] = "; ".join(funding_t) or None
    rec["extra"] = json.dumps(extras, ensure_ascii=False) if extras else None

    authors = parse_authors(rec["authors_raw"])
    affils = parse_affiliations(rec["affiliations_raw"])
    terms = parse_terms(controlled, "controlled") + parse_terms(uncontrolled, "uncontrolled")
    return rec, authors, affils, terms


def _exclusion_reason(rec):
    if not rec["accession_no"]:
        return "no_accession"
    if rec["doc_type"] not in KEEP_DOC_TYPES:
        return "doc_type:%s" % (rec["doc_type"] or "(empty)")
    if not rec["title"]:
        return "missing_title"
    if not rec["authors_raw"] and not rec["abstract"]:
        return "front_matter:F4"  # 无作者无摘要，疑似会议前言
    return None


# ---------------------------------------------------------------------------
# 去重 / 质量标签 / 清洗报告
# ---------------------------------------------------------------------------

# 去重回填时允许从 loser 补进 keeper 的字段（键值类与溯源字段不回填）
_FILLABLE = [c for c in PAPER_COLUMNS
             if c not in ("accession_no", "title", "venue_tag", "quality_flags",
                          "added_at", "updated_at")]

_CHILD_TABLES = (
    ("paper_authors", "position, name_raw, name_display, affil_refs"),
    ("paper_affiliations", "idx, affiliation"),
    ("paper_terms", "kind, term"),
)


def _ensure_columns(conn):
    """增量构建时为旧库补齐缺失列。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(papers)")}
    if "quality_flags" not in cols:
        conn.execute("ALTER TABLE papers ADD COLUMN quality_flags TEXT")


def _dedup_phase(conn, verbose=False):
    """同 DOI 与同题同年（≥25 字符）去重。

    每组保留完整度最高者（completeness_key，平手取 accession_no 较小），
    先把 loser 的来源文件与 NULL 字段合并进 keeper，再删除 loser（FK 级联）。
    返回 (stats, doi_detail, title_detail, fill_log, acc_info)。
    """
    rows = [dict(r) for r in conn.execute(
        "SELECT accession_no, doi, title, pub_year, abstract, authors_raw, "
        "num_references, venue_tag FROM papers")]
    acc_info = {r["accession_no"]: r for r in rows}
    tc = {a: n for a, n in conn.execute(
        "SELECT accession_no, COUNT(*) FROM paper_terms GROUP BY accession_no")}

    def sort_key(r):
        return cleaning.completeness_key(r, tc.get(r["accession_no"], 0))

    losers = {}
    doi_detail, title_detail = [], []

    by_doi = {}
    for r in rows:
        if r["doi"]:
            by_doi.setdefault(r["doi"], []).append(r)
    for doi, members in by_doi.items():
        if len(members) < 2:
            continue
        members.sort(key=lambda r: r["accession_no"])
        members.sort(key=sort_key, reverse=True)
        keeper = members[0]["accession_no"]
        for m in members[1:]:
            losers[m["accession_no"]] = keeper
        doi_detail.append((doi, keeper, [m["accession_no"] for m in members[1:]]))

    by_title = {}
    for r in rows:
        if r["accession_no"] in losers:
            continue
        nt = cleaning.normalize_title(r["title"])
        if len(nt) >= cleaning.TITLE_MIN_LEN:
            by_title.setdefault((nt, r["pub_year"]), []).append(r)
    for (nt, year), members in by_title.items():
        if len(members) < 2:
            continue
        members.sort(key=lambda r: r["accession_no"])
        members.sort(key=sort_key, reverse=True)
        keeper = members[0]["accession_no"]
        for m in members[1:]:
            losers[m["accession_no"]] = keeper
        title_detail.append((nt, year, keeper, [m["accession_no"] for m in members[1:]]))

    # 合并：keeper <- loser（按完整度从高到低）
    groups = {}
    for loser, keeper in losers.items():
        groups.setdefault(keeper, []).append(loser)
    update_sql = ("UPDATE papers SET " +
                  ", ".join("%s=(CASE WHEN %s IS NULL THEN ? ELSE %s END)" % (c, c, c)
                            for c in _FILLABLE) +
                  " WHERE accession_no=?")
    fill_log = []
    for keeper in sorted(groups):
        keeper_row = dict(conn.execute(
            "SELECT * FROM papers WHERE accession_no=?", (keeper,)).fetchone())
        lrows = []
        for l in sorted(groups[keeper]):
            lr = conn.execute("SELECT * FROM papers WHERE accession_no=?", (l,)).fetchone()
            if lr is not None:
                lrows.append(dict(lr))
        lrows.sort(key=sort_key, reverse=True)
        for lr in lrows:
            conn.execute("INSERT OR IGNORE INTO paper_sources SELECT ?, filename "
                         "FROM paper_sources WHERE accession_no=?",
                         (keeper, lr["accession_no"]))
            filled = [c for c in _FILLABLE if lr[c] is not None and keeper_row[c] is None]
            if filled:
                conn.execute(update_sql, [lr[c] for c in _FILLABLE] + [keeper])
                for c in filled:
                    keeper_row[c] = lr[c]
                fill_log.append((keeper, lr["accession_no"], filled))
            for table, cols in _CHILD_TABLES:
                if not conn.execute("SELECT 1 FROM %s WHERE accession_no=? LIMIT 1"
                                    % table, (keeper,)).fetchone():
                    conn.execute("INSERT INTO %s (accession_no, %s) SELECT ?, %s FROM %s "
                                 "WHERE accession_no=?" % (table, cols, cols, table),
                                 (keeper, lr["accession_no"]))
    conn.executemany("DELETE FROM papers WHERE accession_no=?",
                     [(a,) for a in sorted(losers)])

    stats = {
        "doi_groups": len(doi_detail),
        "doi_dropped": sum(len(d[2]) for d in doi_detail),
        "title_groups": len(title_detail),
        "title_dropped": sum(len(d[3]) for d in title_detail),
        "merged_groups": len(groups),
        "filled_groups": len({f[0] for f in fill_log}),
        "filled_fields_total": sum(len(f[2]) for f in fill_log),
    }
    if verbose:
        print("[build] 去重：同DOI %d 组删 %d，同题 %d 组删 %d，字段回填 %d 组/%d 字段次" % (
            stats["doi_groups"], stats["doi_dropped"], stats["title_groups"],
            stats["title_dropped"], stats["filled_groups"], stats["filled_fields_total"]))
    return stats, doi_detail, title_detail, fill_log, acc_info


def _quality_flags_phase(conn, verbose=False):
    """为幸存记录计算 quality_flags（去重回填之后执行）。返回带标签的记录数。"""
    tc = {a: n for a, n in conn.execute(
        "SELECT accession_no, COUNT(*) FROM paper_terms GROUP BY accession_no")}
    updates, flagged = [], 0
    for r in conn.execute("SELECT accession_no, doi, abstract, authors_raw, "
                          "article_number, pages FROM papers"):
        d = dict(r)
        flags = cleaning.quality_flags(d, tc.get(d["accession_no"], 0))
        if flags:
            flagged += 1
            updates.append((json.dumps(flags, ensure_ascii=False), d["accession_no"]))
        else:
            updates.append((None, d["accession_no"]))
    conn.executemany("UPDATE papers SET quality_flags=? WHERE accession_no=?", updates)
    if verbose:
        print("[build] 质量标签：%d 条记录带缺失标记" % flagged)
    return flagged


def _write_cleaning_report(path, now, summary, excluded, rule_samples,
                           dedup_stats, doi_detail, title_detail, fill_log, acc_info):
    """生成 db/cleaning_report.md 供人工抽查。"""
    lines = []
    add = lines.append
    add("# 数据清洗报告")
    add("")
    add("构建时间：%s ｜ ecdb schema v%s" % (now, SCHEMA_VERSION))
    add("")
    add("## 概览")
    add("")
    add("| 指标 | 数值 |")
    add("|---|---|")
    add("| 原始 CSV 行 | %s |" % format(summary["rows_seen"], ","))
    add("| doc_type 剔除（非 JA/CA 等） | %s |" % format(
        sum(v for k, v in excluded.items() if k.startswith(("doc_type:", "no_accession", "missing_title"))), ","))
    add("| 噪声规则剔除（R/E/F/D） | %s |" % format(
        sum(v for k, v in excluded.items()
            if k.startswith(("editorial:", "front_matter:", "discussion:", "retraction_notice:"))), ","))
    add("| 去重删除（同DOI + 同题同年） | %s |" % format(
        dedup_stats["doi_dropped"] + dedup_stats["title_dropped"], ","))
    add("| 最终 papers | %s |" % format(summary["counts"]["papers"], ","))
    add("")
    add("## 噪声规则命中")
    add("")
    add("| 规则 | 数量 |")
    add("|---|---|")
    for k in sorted(excluded):
        if k.startswith(("editorial:", "front_matter:", "discussion:", "retraction_notice:")):
            add("| %s | %s |" % (k, format(excluded[k], ",")))
    add("")
    for k in sorted(excluded):
        if k in rule_samples and rule_samples[k]:
            add("**%s 样例：**" % k)
            for venue, year, title, acc in rule_samples[k]:
                add("- `[%s %s]` %s（acc=%s）" % (venue or "?", year or "?", title, acc))
            add("")
    add("## 去重")
    add("")
    add("### 同 DOI（%d 组，删除 %d 条）" % (dedup_stats["doi_groups"], dedup_stats["doi_dropped"]))
    add("")
    big = [d for d in doi_detail if len(d[2]) >= 2]
    small = [d for d in doi_detail if len(d[2]) == 1]
    for doi, keeper, ls in sorted(big, key=lambda d: -len(d[2])):
        add("- `%s` 保留 %s(%s)，删除 %s" % (
            doi, keeper, acc_info[keeper]["venue_tag"],
            "，".join("%s(%s)" % (a, acc_info[a]["venue_tag"]) for a in ls)))
        add("")
    add("（另有 %d 组为 2 条记录，保留完整度更高者，明细从略；可用 "
        "`python -m ecdb sql \"SELECT ...\"` 复核。）" % len(small))
    add("")
    add("### 同题同年·长题（%d 组，删除 %d 条）" % (
        dedup_stats["title_groups"], dedup_stats["title_dropped"]))
    add("")
    for nt, year, keeper, ls in sorted(title_detail, key=lambda d: d[1] or 0):
        add("- `%s`（%s）保留 %s(%s)，删除 %s" % (
            (nt[:60] + "…") if len(nt) > 60 else nt, year, keeper,
            acc_info[keeper]["venue_tag"],
            "，".join("%s(%s)" % (a, acc_info[a]["venue_tag"]) for a in ls)))
    add("")
    add("### 字段回填（%d 组，共 %d 字段次）" % (
        dedup_stats["filled_groups"], dedup_stats["filled_fields_total"]))
    add("")
    for keeper, loser, fields in fill_log[:30]:
        add("- %s <- %s：%s" % (keeper, loser, "、".join(fields)))
    if len(fill_log) > 30:
        add("- ……（其余 %d 条略）" % (len(fill_log) - 30))
    add("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# 构建
# ---------------------------------------------------------------------------

_UPSERT_SQL = None


def _upsert_sql():
    global _UPSERT_SQL
    if _UPSERT_SQL is None:
        cols = ", ".join(PAPER_COLUMNS)
        ph = ", ".join("?" for _ in PAPER_COLUMNS)
        upd = [c for c in PAPER_COLUMNS if c not in ("accession_no", "added_at")]
        sets = ", ".join("%s=COALESCE(excluded.%s, papers.%s)" % (c, c, c) for c in upd)
        _UPSERT_SQL = ("INSERT INTO papers (%s) VALUES (%s) "
                       "ON CONFLICT(accession_no) DO UPDATE SET %s" % (cols, ph, sets))
    return _UPSERT_SQL


def build(data_dir=None, db_path=None, rebuild=False, verbose=True):
    """构建/增量更新数据库。幂等：重复运行结果一致。返回统计摘要 dict。"""
    t0 = time.time()
    if sqlite3.sqlite_version_info < (3, 24, 0):
        raise RuntimeError("需要 SQLite >= 3.24（当前 %s）" % sqlite3.sqlite_version)
    csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))

    ddir = Path(data_dir) if data_dir else _paths.data_dir()
    dbp = Path(db_path) if db_path else _paths.db_path()
    files = sorted(ddir.glob("*.csv"))
    if not files:
        raise FileNotFoundError("在 %s 未找到任何 CSV 文件" % ddir)

    if rebuild and dbp.exists():
        bak = dbp.with_name(dbp.name + ".bak")
        if bak.exists():
            bak.unlink()
        dbp.rename(bak)
        if verbose:
            print("[build] 旧库已备份为 %s" % bak.name)

    dbp.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(dbp))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=OFF")
    conn.executescript(TABLES_SQL)
    _ensure_columns(conn)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    existing = {r[0] for r in conn.execute("SELECT accession_no FROM papers")}
    # 已加载过子表的 accession 集合：重复记录需先清空对应子表再重灌。
    # 增量重跑时从现有库预热，避免旧记录残留多余的作者/机构/关键词条目。
    loaded_authors = {r[0] for r in conn.execute("SELECT DISTINCT accession_no FROM paper_authors")}
    loaded_affils = {r[0] for r in conn.execute("SELECT DISTINCT accession_no FROM paper_affiliations")}
    loaded_terms_c = {r[0] for r in conn.execute(
        "SELECT DISTINCT accession_no FROM paper_terms WHERE kind='controlled'")}
    loaded_terms_u = {r[0] for r in conn.execute(
        "SELECT DISTINCT accession_no FROM paper_terms WHERE kind='uncontrolled'")}

    rows_seen = inserted = updated = 0
    excluded = {}
    rule_samples = {}
    file_rows = {}

    for fi, path in enumerate(files, 1):
        venue_tag = venue_tag_from_filename(path.name)
        paper_rows, src_rows = [], []
        clear_a, clear_f, clear_t = [], [], []
        author_rows, affil_rows, term_rows = [], [], []
        seen_in_file = 0

        with open(path, newline="", encoding="utf-8-sig") as fh:
            for raw_row in csv.DictReader(fh):
                rows_seen += 1
                seen_in_file += 1
                rec, authors, affils, terms = _prepare(raw_row, venue_tag)
                reason = _exclusion_reason(rec)
                if reason is None:
                    hit = cleaning.classify_noise(rec, terms)
                    if hit:
                        reason = "%s:%s" % hit
                if reason:
                    excluded[reason] = excluded.get(reason, 0) + 1
                    samples = rule_samples.setdefault(reason, [])
                    if len(samples) < 5:
                        samples.append((venue_tag, rec.get("pub_year"),
                                        rec.get("title"), rec["accession_no"]))
                    continue
                acc = rec["accession_no"]
                rec["added_at"] = now
                rec["updated_at"] = now
                paper_rows.append(tuple(rec[c] for c in PAPER_COLUMNS))
                src_rows.append((acc, path.name))
                if acc in existing:
                    updated += 1
                else:
                    inserted += 1
                    existing.add(acc)
                # 子表刷新条件：本文件提供了对应原始字段，且此前已加载过（避免无谓 DELETE）
                if rec["authors_raw"] is not None:
                    if acc in loaded_authors:
                        clear_a.append((acc,))
                    loaded_authors.add(acc)
                    author_rows.extend(
                        (acc, i, n, d, r) for i, (n, d, r) in enumerate(authors, 1))
                if rec["affiliations_raw"] is not None:
                    if acc in loaded_affils:
                        clear_f.append((acc,))
                    loaded_affils.add(acc)
                    affil_rows.extend((acc, i, t) for i, t in affils)
                for kind, loaded_set in (("controlled", loaded_terms_c),
                                         ("uncontrolled", loaded_terms_u)):
                    if any(k == kind for k, _ in terms):
                        if acc in loaded_set:
                            clear_t.append((acc, kind))
                        loaded_set.add(acc)
                term_rows.extend((acc, k, t) for k, t in terms)

        conn.executemany(_upsert_sql(), paper_rows)
        if clear_a:
            conn.executemany("DELETE FROM paper_authors WHERE accession_no=?", clear_a)
        conn.executemany(
            "INSERT OR REPLACE INTO paper_authors (accession_no, position, name_raw, name_display, affil_refs) "
            "VALUES (?,?,?,?,?)", author_rows)
        if clear_f:
            conn.executemany("DELETE FROM paper_affiliations WHERE accession_no=?", clear_f)
        conn.executemany(
            "INSERT OR REPLACE INTO paper_affiliations (accession_no, idx, affiliation) VALUES (?,?,?)",
            affil_rows)
        if clear_t:
            conn.executemany(
                "DELETE FROM paper_terms WHERE accession_no=? AND kind=?", clear_t)
        conn.executemany(
            "INSERT OR IGNORE INTO paper_terms (accession_no, kind, term) VALUES (?,?,?)", term_rows)
        conn.executemany(
            "INSERT OR IGNORE INTO paper_sources (accession_no, filename) VALUES (?,?)", src_rows)

        file_rows[path.name] = seen_in_file
        if verbose:
            print("[build] (%2d/%d) %-58s %6d 行" % (fi, len(files), path.name[:58], seen_in_file))

    # 去重（同 DOI / 同题同年）与质量标签，然后索引、FTS、视图、统计信息
    dedup_stats, doi_detail, title_detail, fill_log, acc_info = _dedup_phase(conn, verbose)
    flagged = _quality_flags_phase(conn, verbose)
    conn.executescript(INDEXES_SQL)
    fts = _db.fts5_available()
    if fts:
        if verbose:
            print("[build] 重建 FTS5 全文索引 ...")
        conn.execute("DROP TABLE IF EXISTS papers_fts")
        conn.execute("CREATE VIRTUAL TABLE papers_fts USING fts5(title, abstract, authors, terms)")
        conn.execute(
            "INSERT INTO papers_fts(rowid, title, abstract, authors, terms) "
            "SELECT p.rowid, COALESCE(p.title,''), COALESCE(p.abstract,''), "
            "COALESCE((SELECT GROUP_CONCAT(pa.name_display,'; ') FROM paper_authors pa "
            "         WHERE pa.accession_no=p.accession_no),''), "
            "COALESCE((SELECT GROUP_CONCAT(pt.term,'; ') FROM paper_terms pt "
            "         WHERE pt.accession_no=p.accession_no),'') "
            "FROM papers p")
    conn.executescript(VIEW_SQL)
    conn.execute("ANALYZE")

    counts = {}
    for t in ("papers", "paper_authors", "paper_affiliations", "paper_terms", "paper_sources"):
        counts[t] = conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
    meta = {
        "schema_version": SCHEMA_VERSION,
        "last_build_at": now,
        "fts5": "1" if fts else "0",
        "source_dir": str(ddir),
        "files_processed": len(files),
        "rows_seen": rows_seen,
        "inserted": inserted,
        "updated_duplicates": updated,
        "excluded": json.dumps(excluded, ensure_ascii=False),
        "dedup_stats": json.dumps(dedup_stats, ensure_ascii=False),
        "quality_flagged": str(flagged),
        "file_rows": json.dumps(file_rows, ensure_ascii=False),
        "table_counts": json.dumps(counts),
    }
    conn.executemany("INSERT OR REPLACE INTO db_meta (key, value) VALUES (?,?)",
                     list(meta.items()))
    conn.commit()
    conn.execute("PRAGMA optimize")
    conn.close()

    duration = time.time() - t0
    size_mb = dbp.stat().st_size / 1048576
    summary = {
        "db_path": str(dbp), "files": len(files), "rows_seen": rows_seen,
        "inserted": inserted, "updated_duplicates": updated,
        "excluded": excluded, "dedup": dedup_stats, "quality_flagged": flagged,
        "counts": counts, "fts5": fts,
        "size_mb": round(size_mb, 1), "duration_s": round(duration, 1),
    }
    report_path = dbp.parent / "cleaning_report.md"
    _write_cleaning_report(report_path, now, summary, excluded, rule_samples,
                           dedup_stats, doi_detail, title_detail, fill_log, acc_info)
    if verbose:
        print("\n[build] 完成：%d 个文件，%d 行原始记录，耗时 %.1f 秒" % (len(files), rows_seen, duration))
        print("[build] 新入库 %d 条，跨文件去重更新 %d 条" % (inserted, updated))
        if excluded:
            detail = "，".join("%s=%d" % kv for kv in sorted(excluded.items()))
            print("[build] 剔除明细（共 %d）：%s" % (sum(excluded.values()), detail))
        print("[build] papers=%d authors=%d affiliations=%d terms=%d sources=%d" % (
            counts["papers"], counts["paper_authors"], counts["paper_affiliations"],
            counts["paper_terms"], counts["paper_sources"]))
        print("[build] FTS5=%s，数据库大小 %.1f MB" % ("启用" if fts else "不可用（查询回退 LIKE）", size_mb))
        print("[build] 清洗报告：%s" % report_path)
    return summary
