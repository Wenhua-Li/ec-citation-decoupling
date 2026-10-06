"""ecdb —— EC 文献库轻量查询接口（SQLite，零第三方依赖）。

在项目根目录下使用：
    Python:  import ecdb; ecdb.search("genetic algorithm", year_range=(2020, 2025))
    CLI:     python -m ecdb info | search | get | papers | stats | venues | sql

完整字段字典与注意事项见 docs/DATA_USAGE.md。
"""
import csv
import json
import re
import sqlite3
from pathlib import Path

from . import _db, _paths

__version__ = "1.0.0"

__all__ = ["search", "get_paper", "find_papers", "stats", "venues", "export",
           "raw_sql", "info", "db_path", "data_dir"]


def db_path():
    """数据库文件路径（可用环境变量 ECDB_DB 覆盖）。"""
    return _paths.db_path()


def data_dir():
    """原始 CSV 目录路径（可用环境变量 ECDB_DATA 覆盖）。"""
    return _paths.data_dir()


def _open():
    p = _paths.db_path()
    if not p.exists():
        raise FileNotFoundError("数据库不存在：%s\n请先在项目根目录运行: python -m ecdb build" % p)
    return _db.connect(p, readonly=True)


# ---------------------------------------------------------------------------
# 过滤条件构造（search / find_papers / stats 共用）
# ---------------------------------------------------------------------------

def _filters(year=None, year_range=None, venue=None, doc_type=None,
             author=None, source=None, term=None):
    where, params = [], []
    if year is not None:
        where.append("p.pub_year = ?")
        params.append(int(year))
    if year_range:
        lo, hi = year_range
        if lo:
            where.append("p.pub_year >= ?")
            params.append(int(lo))
        if hi:
            where.append("p.pub_year <= ?")
            params.append(int(hi))
    if doc_type:
        where.append("p.doc_type = ?")
        params.append(_db.clean_doc_type(doc_type) or str(doc_type).upper())
    if source:
        where.append("(p.source LIKE ? OR p.source_abbr LIKE ?)")
        params += ["%" + str(source) + "%"] * 2
    if venue:
        v = str(venue).lower()
        where.append("(p.venue_tag = ? OR p.venue_tag LIKE ? OR p.source_abbr LIKE ? OR p.source LIKE ?)")
        params += [v, "%" + v + "%", "%" + str(venue) + "%", "%" + str(venue) + "%"]
    if author:
        where.append("EXISTS (SELECT 1 FROM paper_authors pa WHERE pa.accession_no = p.accession_no "
                     "AND (pa.name_display LIKE ? OR pa.name_raw LIKE ?))")
        params += ["%" + str(author) + "%"] * 2
    if term:
        where.append("EXISTS (SELECT 1 FROM paper_terms pt WHERE pt.accession_no = p.accession_no "
                     "AND pt.term LIKE ?)")
        params.append("%" + str(term) + "%")
    return where, params


# ---------------------------------------------------------------------------
# 全文检索
# ---------------------------------------------------------------------------

_FTS_TOK_RE = re.compile(r'"[^"]*"|[^\s"]+')
_FTS_BARE_RE = re.compile(r"[A-Za-z0-9_\u0080-\uffff*^]+")


def _fts_query_string(q):
    """把用户输入安全转成 FTS5 MATCH 语法。

    含特殊字符（连字符等）的 token 加引号变成短语；已加引号的短语与
    AND/OR/NOT/NEAR 关键字、* 前缀通配保持原样。
    """
    fixed = []
    for tok in _FTS_TOK_RE.findall(str(q)):
        if tok.startswith('"') or _FTS_BARE_RE.fullmatch(tok):
            fixed.append(tok)
        else:
            fixed.append('"' + tok.replace('"', '""') + '"')
    return " ".join(fixed)


def search(query, mode=None, year=None, year_range=None, venue=None,
           doc_type=None, author=None, source=None, term=None,
           limit=50, offset=0, fields=None):
    """全文检索 title / abstract / 作者 / 关键词，支持结构化过滤。

    返回 {"total": 匹配总数, "rows": [dict, ...]}。
    mode: None=自动（优先 FTS5），"fts"，"like"。
    year_range: (起, 止)，闭区间，任一端可为 None。
    """
    if not query or not str(query).strip():
        raise ValueError("query 不能为空")
    conn = _open()
    try:
        has_fts = _db.db_has_fts(conn)
        if mode == "fts" and not has_fts:
            raise RuntimeError("当前数据库未启用 FTS5，请使用 mode='like'")
        use_fts = has_fts if mode is None else (mode != "like")
        where, params = _filters(year, year_range, venue, doc_type, author, source, term)
        cond = (" AND " + " AND ".join(where)) if where else ""
        if use_fts:
            base = ("FROM papers_fts JOIN papers p ON p.rowid = papers_fts.rowid "
                    "WHERE papers_fts MATCH ?")
            bp = [_fts_query_string(query)]
            order = "papers_fts.rank"
        else:
            pat = "%" + _db.like_escape(query) + "%"
            base = ("FROM papers p WHERE (p.title LIKE ? ESCAPE '\\' "
                    "OR p.abstract LIKE ? ESCAPE '\\' "
                    "OR p.authors_raw LIKE ? ESCAPE '\\' "
                    "OR EXISTS (SELECT 1 FROM paper_terms pt WHERE pt.accession_no = p.accession_no "
                    "AND pt.term LIKE ? ESCAPE '\\'))")
            bp = [pat] * 4
            order = "p.pub_year DESC, p.title"
        total = conn.execute("SELECT COUNT(*) " + base + cond, bp + params).fetchone()[0]
        sql = "SELECT p.* " + base + cond + " ORDER BY %s LIMIT ? OFFSET ?" % order
        rows = [dict(r) for r in conn.execute(sql, bp + params + [int(limit), int(offset)])]
        if fields:
            rows = [{f: r.get(f) for f in fields} for r in rows]
        return {"total": total, "rows": rows}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 单篇与结构化查询
# ---------------------------------------------------------------------------

def get_paper(doi=None, accession=None):
    """按 DOI 或 Accession number 取单篇详情（含作者/机构/关键词/来源文件）。未命中返回 None。"""
    if not doi and not accession:
        raise ValueError("必须提供 doi 或 accession 之一")
    conn = _open()
    try:
        if doi:
            row = conn.execute("SELECT * FROM papers WHERE doi = ?",
                               (_db.normalize_doi(doi),)).fetchone()
        else:
            row = conn.execute("SELECT * FROM papers WHERE accession_no = ?",
                               (accession,)).fetchone()
        if row is None:
            return None
        paper = dict(row)
        acc = paper["accession_no"]
        paper["authors"] = [dict(r) for r in conn.execute(
            "SELECT position, name_raw, name_display, affil_refs FROM paper_authors "
            "WHERE accession_no=? ORDER BY position", (acc,))]
        paper["affiliations"] = [dict(r) for r in conn.execute(
            "SELECT idx, affiliation FROM paper_affiliations "
            "WHERE accession_no=? ORDER BY idx", (acc,))]
        paper["terms"] = [dict(r) for r in conn.execute(
            "SELECT kind, term FROM paper_terms WHERE accession_no=? ORDER BY kind, term", (acc,))]
        paper["source_files"] = [r[0] for r in conn.execute(
            "SELECT filename FROM paper_sources WHERE accession_no=? ORDER BY filename", (acc,))]
        return paper
    finally:
        conn.close()


_ORDER_COLS = set(_db.PAPER_COLUMNS) - {"extra"}


def _safe_order(order_by):
    parts = []
    for token in str(order_by).split(","):
        bits = token.strip().split()
        if not bits:
            continue
        col = bits[0]
        direction = bits[1].upper() if len(bits) > 1 else "DESC"
        if col not in _ORDER_COLS or direction not in ("ASC", "DESC"):
            raise ValueError("非法排序字段: %r" % token)
        parts.append("%s %s" % (col, direction))
    return ", ".join(parts) or "pub_year DESC"


def find_papers(year=None, year_range=None, venue=None, doc_type=None,
                author=None, source=None, term=None, has_abstract=None,
                has_doi=None, has_terms=None, limit=100, offset=0,
                order_by="pub_year DESC", fields=None):
    """结构化过滤（不走全文索引）。order_by 形如 "pub_year DESC, title"。"""
    where, params = _filters(year, year_range, venue, doc_type, author, source, term)
    if has_abstract is not None:
        where.append("p.abstract IS %sNULL" % (" NOT " if has_abstract else ""))
    if has_doi is not None:
        where.append("p.doi IS %sNULL" % (" NOT " if has_doi else ""))
    if has_terms is not None:
        neg = "" if has_terms else "NOT "
        where.append("%sEXISTS (SELECT 1 FROM paper_terms pt WHERE pt.accession_no = p.accession_no)" % neg)
    cond = (" WHERE " + " AND ".join(where)) if where else ""
    order = _safe_order(order_by)
    conn = _open()
    try:
        total = conn.execute("SELECT COUNT(*) FROM papers p" + cond, params).fetchone()[0]
        sql = ("SELECT p.* FROM papers p" + cond +
               " ORDER BY %s LIMIT ? OFFSET ?" % order)
        rows = [dict(r) for r in conn.execute(sql, params + [int(limit), int(offset)])]
        if fields:
            rows = [{f: r.get(f) for f in fields} for r in rows]
        return {"total": total, "rows": rows}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 统计
# ---------------------------------------------------------------------------

_STATS_BY = ("year", "venue", "source", "author", "term", "doc_type")


def stats(by="year", year_range=None, venue=None, doc_type=None, source=None,
          kind=None, top=None):
    """分组计数（文献计量）。by ∈ year/venue/source/author/term/doc_type。

    返回 [{"value": ..., "count": ...}, ...]。term 统计可用 kind 过滤
    （controlled=EI 受控词 / uncontrolled=自由关键词）。
    top=None 时不加 LIMIT，但 author/term 维度默认截断前 20（结果集过大）。
    """
    if by not in _STATS_BY:
        raise ValueError("by 必须是 %s 之一" % "/".join(_STATS_BY))
    if top is None and by in ("author", "term"):
        top = 20
    where, params = _filters(year_range=year_range, venue=venue,
                             doc_type=doc_type, source=source)
    if by == "author":
        sql_from = "FROM paper_authors pa JOIN papers p ON p.accession_no = pa.accession_no"
        group = "pa.name_display"
    elif by == "term":
        sql_from = "FROM paper_terms pt JOIN papers p ON p.accession_no = pt.accession_no"
        group = "pt.term"
        if kind:
            where.append("pt.kind = ?")
            params.append(kind)
    else:
        sql_from = "FROM papers p"
        group = {"year": "p.pub_year", "venue": "p.venue_tag",
                 "source": "p.source", "doc_type": "p.doc_type"}[by]
    cond = (" WHERE " + " AND ".join(where)) if where else ""
    sql = ("SELECT %s AS value, COUNT(*) AS count %s%s GROUP BY %s ORDER BY %s" %
           (group, sql_from, cond, group,
            "value" if by in ("year",) else "count DESC, value"))
    if top:
        sql += " LIMIT %d" % int(top)
    conn = _open()
    try:
        return [{"value": r["value"], "count": r["count"]} for r in conn.execute(sql, params)]
    finally:
        conn.close()


def venues():
    """库内来源一览：[{venue, sample_source, papers, first_year, last_year}]。

    sample_source 取该标签下出现次数最多的刊名/会议名（MIN 会误取少数
    EI 记录错误的变体刊名）。
    """
    conn = _open()
    try:
        span = {r["venue_tag"]: dict(r) for r in conn.execute(
            "SELECT venue_tag, COUNT(*) AS papers, "
            "MIN(pub_year) AS first_year, MAX(pub_year) AS last_year "
            "FROM papers GROUP BY venue_tag")}
        for r in conn.execute(
                "SELECT venue_tag, source, COUNT(*) AS c FROM papers "
                "WHERE source IS NOT NULL GROUP BY venue_tag, source"):
            cur = span[r["venue_tag"]]
            if "sample_source" not in cur or r["c"] > cur["_c"]:
                cur["sample_source"] = r["source"]
                cur["_c"] = r["c"]
        out = []
        for d in sorted(span.values(), key=lambda d: -d["papers"]):
            d.pop("_c", None)
            d["venue"] = d.pop("venue_tag")
            out.append(d)
        return out
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 导出与逃生口
# ---------------------------------------------------------------------------

def export(rows, path, fmt="csv"):
    """把 search/find_papers 等返回的行导出为 csv（utf-8-sig，Excel 友好）或 json。"""
    path = Path(path)
    rows = list(rows)
    if not rows:
        raise ValueError("没有数据可导出")
    if fmt == "json":
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    elif fmt == "csv":
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    else:
        raise ValueError("fmt 只支持 csv / json")
    return str(path)


def raw_sql(sql, params=(), max_rows=1000, allow_write=False):
    """执行任意 SQL（默认只允许 SELECT/WITH）。返回 {"columns": [...], "rows": [...]}。"""
    stmt = str(sql).lstrip()
    if not allow_write and not re.match(r"(?is)^(select|with)\b", stmt):
        raise ValueError("raw_sql 默认只允许 SELECT/WITH；确需写入请传 allow_write=True")
    conn = _db.connect(readonly=not allow_write)
    try:
        cur = conn.execute(sql, params)
        if cur.description is None:
            conn.commit()
            return {"columns": [], "rows": [], "rowcount": cur.rowcount}
        rows = [dict(r) for r in cur.fetchmany(int(max_rows))]
        return {"columns": [d[0] for d in cur.description], "rows": rows}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 库状态
# ---------------------------------------------------------------------------

def info():
    """数据库状态（agent 使用前建议先调用）。库不存在时返回带提示的 dict。"""
    p = _paths.db_path()
    out = {"db_path": str(p), "exists": p.exists()}
    if not p.exists():
        out["hint"] = "请先在项目根目录运行: python -m ecdb build"
        return out
    out["size_mb"] = round(p.stat().st_size / 1048576, 1)
    conn = _open()
    try:
        out["fts5"] = _db.db_has_fts(conn)
        out["tables"] = {
            t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
            for t in ("papers", "paper_authors", "paper_affiliations",
                      "paper_terms", "paper_sources")}
        out["meta"] = {k: v for k, v in
                       conn.execute("SELECT key, value FROM db_meta")}
        (out["year_min"], out["year_max"], out["venues"], out["sources"]) = conn.execute(
            "SELECT MIN(pub_year), MAX(pub_year), COUNT(DISTINCT venue_tag), "
            "COUNT(DISTINCT source) FROM papers").fetchone()
        out["no_abstract"] = conn.execute(
            "SELECT COUNT(*) FROM papers WHERE quality_flags LIKE '%no_abstract%'").fetchone()[0]
        return out
    finally:
        conn.close()
