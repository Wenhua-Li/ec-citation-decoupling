"""ecdb 命令行入口。在项目根目录运行：python -m ecdb <command>"""
import argparse
import json
import re
import sys

from . import (data_dir, db_path, export, find_papers, get_paper, info,
               raw_sql, search, stats, venues)


def _year_range(s):
    if not s:
        return None
    parts = [p.strip() for p in re.split(r"[:\-–]", s)]
    if not 1 <= len(parts) <= 2:
        raise argparse.ArgumentTypeError("年份区间格式：2020:2025 或 2020-2025")
    lo = int(parts[0]) if parts[0] else None
    hi = int(parts[1]) if len(parts) > 1 and parts[1] else None
    return (lo, hi)


def _fields(s):
    return [f.strip() for f in s.split(",") if f.strip()] or None


def _out_json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _cell(v, width=48):
    s = "" if v is None else str(v).replace("\r", " ").replace("\n", " ")
    return s if len(s) <= width else s[:width - 3] + "..."


def _print_table(rows, cols=None):
    if not rows:
        print("(无结果)")
        return
    cols = cols or list(rows[0].keys())
    table = [[_cell(r.get(c)) for c in cols] for r in rows]
    widths = [max(len(c), *(len(row[i]) for row in table)) for i, c in enumerate(cols)]
    print("  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    print("  ".join("-" * w for w in widths))
    for row in table:
        print("  ".join(v.ljust(w) for v, w in zip(row, widths)))


def _print_found(result, fields=None, shown_from=0):
    total, rows = result["total"], result["rows"]
    print("共 %d 条，显示第 %d-%d 条：" % (total, shown_from + 1, shown_from + len(rows)))
    if fields:
        rows = [{f: r.get(f) for f in fields} for r in rows]
    _print_table(rows, fields)
    if not rows:
        print("(无结果)")


def _print_paper(p):
    if p is None:
        print("未找到")
        return
    for k in ("accession_no", "doi", "title", "pub_year", "doc_type", "source",
              "source_abbr", "venue_tag", "volume", "issue", "pages",
              "article_number", "language", "issn", "num_references"):
        if p.get(k) is not None:
            print("%-22s: %s" % (k, p[k]))
    if p.get("authors"):
        print("%-22s: %s" % ("authors", "; ".join(a["name_display"] for a in p["authors"])))
    if p.get("terms"):
        print("%-22s: %s" % ("terms", "; ".join(t["term"] for t in p["terms"])))
    for a in p.get("affiliations") or []:
        print("%-22s: %s" % ("affil #%s" % a["idx"], a["affiliation"]))
    if p.get("source_files"):
        print("%-22s: %s" % ("source_files", ", ".join(p["source_files"])))
    if p.get("abstract"):
        print("%-22s: %s" % ("abstract", _cell(p["abstract"], 600)))


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def cmd_enrich(a):
    from . import enrich
    enrich.run(a.step, confirm=a.confirm)


def cmd_info(a):
    d = info()
    if a.json:
        return _out_json(d)
    if not d["exists"]:
        print("数据库不存在：%s" % d["db_path"])
        print(d["hint"])
        return
    m = d.get("meta", {})
    print("数据库        : %s (%.1f MB)" % (d["db_path"], d["size_mb"]))
    print("FTS5 全文检索 : %s" % ("启用" if d["fts5"] else "未启用（查询回退 LIKE）"))
    t = d.get("tables", {})
    print("papers        : %s 篇" % format(t.get("papers", 0), ","))
    print("作者条目      : %s" % format(t.get("paper_authors", 0), ","))
    print("机构条目      : %s" % format(t.get("paper_affiliations", 0), ","))
    print("关键词条目    : %s" % format(t.get("paper_terms", 0), ","))
    print("覆盖年份      : %s - %s" % (d.get("year_min"), d.get("year_max")))
    print("来源标签/刊源 : %s / %s" % (d.get("venues"), d.get("sources")))
    if d.get("no_abstract") is not None:
        print("无摘要(打标)  : %s 条（quality_flags 含 no_abstract，仍在库中）" % format(d["no_abstract"], ","))
    for k in ("last_build_at", "inserted", "updated_duplicates", "rows_seen", "files_processed"):
        if k in m:
            print("%-14s : %s" % ("meta." + k, m[k]))
    if "dedup_stats" in m:
        print("%-14s : %s" % ("meta.dedup_stats", m["dedup_stats"]))


def cmd_build(a):
    from .importer import build
    build(data_dir=a.data, db_path=a.db, rebuild=a.rebuild)


def cmd_search(a):
    res = search(a.query, mode=None if a.mode == "auto" else a.mode,
                 year=a.year, year_range=a.year_range, venue=a.venue,
                 doc_type=a.doctype, author=a.author, source=a.source,
                 term=a.term, limit=a.limit, offset=a.offset)
    if a.count:
        print("共 %d 条" % res["total"])
        return
    if a.json:
        return _out_json(res)
    _print_found(res, a.fields, a.offset)


def cmd_get(a):
    p = get_paper(doi=a.doi, accession=a.acc)
    if a.json:
        return _out_json(p if p is not None else {"error": "not found"})
    _print_paper(p)


def cmd_papers(a):
    res = find_papers(year=a.year, year_range=a.year_range, venue=a.venue,
                      doc_type=a.doctype, author=a.author, source=a.source,
                      term=a.term, has_abstract=a.has_abstract,
                      has_doi=a.has_doi, has_terms=a.has_terms,
                      limit=a.limit, offset=a.offset, order_by=a.order)
    if a.json:
        return _out_json(res)
    _print_found(res, a.fields, a.offset)


def cmd_stats(a):
    rows = stats(by=a.by, year_range=a.year_range, venue=a.venue,
                 doc_type=a.doctype, source=a.source, kind=a.kind, top=a.top)
    if a.json:
        return _out_json(rows)
    for r in rows:
        print("%6d  %s" % (r["count"], "(未知)" if r["value"] is None else r["value"]))


def cmd_venues(a):
    rows = venues()
    if a.json:
        return _out_json(rows)
    for r in rows:
        print("%6d 篇  %-20s %s - %s  %s" % (
            r["papers"], r["venue"], r["first_year"], r["last_year"],
            _cell(r["sample_source"], 50)))


def cmd_sql(a):
    params = json.loads(a.params) if a.params else ()
    res = raw_sql(a.sql, params=params, max_rows=a.max_rows)
    if a.json:
        return _out_json(res)
    _print_table(res["rows"], res["columns"] or None)
    if not res["rows"] and res.get("rowcount") is not None:
        print("(影响 %d 行)" % res["rowcount"])


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------

def build_parser():
    ap = argparse.ArgumentParser(prog="ecdb", description="EC 文献库查询工具（详见 docs/DATA_USAGE.md）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("info", help="数据库状态（agent 第一步）")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_info)

    p = sub.add_parser("build", help="构建/增量导入数据库")
    p.add_argument("--rebuild", action="store_true", help="丢弃旧库重建（旧库备份为 .bak）")
    p.add_argument("--data", help="覆盖原始 CSV 目录")
    p.add_argument("--db", help="覆盖数据库输出路径")
    p.set_defaults(fn=cmd_build)

    p = sub.add_parser("search", help="全文检索 title/abstract/作者/关键词")
    p.add_argument("query")
    p.add_argument("--mode", choices=["auto", "fts", "like"], default="auto")
    p.add_argument("--year", type=int)
    p.add_argument("--year-range", type=_year_range, metavar="2020:2025")
    p.add_argument("--venue", help="来源标签/刊名缩写/刊名，如 tevc")
    p.add_argument("--doctype", help="JA 或 CA")
    p.add_argument("--author")
    p.add_argument("--source")
    p.add_argument("--term", help="同时要求包含的关键词")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--fields", type=_fields, help="逗号分隔的输出字段")
    p.add_argument("--count", action="store_true", help="只显示总数")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("get", help="按 DOI 或 accession number 取单篇详情")
    p.add_argument("--doi")
    p.add_argument("--acc")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_get)

    p = sub.add_parser("papers", help="结构化过滤（不走全文索引）")
    p.add_argument("--year", type=int)
    p.add_argument("--year-range", type=_year_range, metavar="2020:2025")
    p.add_argument("--venue")
    p.add_argument("--doctype")
    p.add_argument("--author")
    p.add_argument("--source")
    p.add_argument("--term")
    p.add_argument("--has-abstract", type=lambda s: s.lower() in ("1", "true", "yes"),
                   metavar="1/0")
    p.add_argument("--has-doi", type=lambda s: s.lower() in ("1", "true", "yes"),
                   metavar="1/0")
    p.add_argument("--has-terms", type=lambda s: s.lower() in ("1", "true", "yes"),
                   metavar="1/0")
    p.add_argument("--order", default="pub_year DESC", help="如 'pub_year DESC, title'")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--fields", type=_fields)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_papers)

    p = sub.add_parser("stats", help="分组统计")
    p.add_argument("--by", default="year", choices=["year", "venue", "source", "author", "term", "doc_type"])
    p.add_argument("--top", type=int, default=None,
                   help="只取前 N 项（默认：year/venue/source 全量，author/term 前 20）")
    p.add_argument("--year-range", type=_year_range, metavar="2020:2025")
    p.add_argument("--venue")
    p.add_argument("--doctype")
    p.add_argument("--source")
    p.add_argument("--kind", choices=["controlled", "uncontrolled"],
                   help="仅 term 统计：EI 受控词 / 自由关键词")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_stats)

    p = sub.add_parser("venues", help="库内来源一览")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_venues)

    p = sub.add_parser("sql", help="执行只读 SQL（逃生口）")
    p.add_argument("sql")
    p.add_argument("--params", help="JSON 数组形式的参数")
    p.add_argument("--max-rows", type=int, default=1000)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_sql)

    p = sub.add_parser("enrich", help="数据质量补全/清理（2026-09 审查方案，见 ecdb/enrich.py 文档）")
    p.add_argument("step", help="placeholder/fix-doi/writeback-doi/fill-abstract/"
                                "fill-authors/fix-year/clean-terms/fix-affil/publisher/"
                                "flag-affil/delete-review/delete/scope-review/scope")
    p.add_argument("--confirm", action="store_true", help="delete / scope 步骤的执行确认")
    p.set_defaults(fn=cmd_enrich)

    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        print("错误：%s" % e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
