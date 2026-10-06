"""report / status —— 覆盖率报告（MD + CSV）与进度查询。"""
import json
import time
from pathlib import Path

from ecdb import _paths

from . import _db
from ._cache import cache_dir

YEAR_BANDS = [(-1, 1995, "≤1995"), (1996, 2005, "1996-2005"),
              (2006, 2015, "2006-2015"), (2016, 2020, "2016-2020"),
              (2021, 9999, "2021+")]


def _band(y):
    for lo, hi, name in YEAR_BANDS:
        if lo <= (y if y is not None else -1) <= hi:
            return name
    return "?"


def status():
    conn = _db.connect_ro()
    missing = _db.missing_tables(conn)
    if missing:
        print("[status] 引文表尚未创建（缺 %s），请先运行 python -m eccite init" % missing)
        return
    n_papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    counts = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
              for t in _db.CIT_TABLES}
    statuses = dict(conn.execute(
        "SELECT refs_status, COUNT(*) FROM paper_cit_meta GROUP BY refs_status"))
    statuses_in = dict(conn.execute(
        "SELECT cites_status, COUNT(*) FROM paper_cit_meta GROUP BY cites_status"))
    migrated = conn.execute(
        "SELECT COUNT(*) FROM paper_cit_meta WHERE migrated=1").fetchone()[0]
    conn.close()
    caches = {}
    for f in sorted(cache_dir().glob("*.jsonl")):
        caches[f.name] = "%.1f MB" % (f.stat().st_size / 1048576)
    print("[status] papers=%d" % n_papers)
    for t, n in counts.items():
        print("[status] %-18s %12d" % (t, n))
    print("[status] meta 迁移标记=%d；refs_status=%s" % (migrated, statuses))
    print("[status] cites_status=%s" % statuses_in)
    print("[status] 缓存：%s" % (caches or "空"))


def report():
    conn = _db.connect_ro()
    lines = ["# 引文数据覆盖率报告", "",
             "生成时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"), ""]
    n_papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    n_doi = conn.execute(
        "SELECT COUNT(*) FROM papers WHERE doi IS NOT NULL AND doi != ''").fetchone()[0]
    lines += ["## 总览", "",
              "| 指标 | 数值 |", "|---|---|",
              "| papers | %d |" % n_papers,
              "| 有 DOI | %d |" % n_doi]
    for t in _db.CIT_TABLES:
        n = conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        lines.append("| %s | %d |" % (t, n))
    lines.append("")
    lines += ["## 出边/入边按源", "", "| 表 | 源 | 行数 |", "|---|---|---|"]
    for tbl in ("paper_refs_out", "paper_cited_in"):
        for src, n in conn.execute(
                "SELECT source, COUNT(*) FROM %s GROUP BY source ORDER BY 2 DESC" % tbl):
            lines.append("| %s | %s | %d |" % (tbl, src, n))
    lines.append("")

    # 分年份段覆盖
    have_refs = {r[0] for r in conn.execute(
        "SELECT DISTINCT accession_no FROM paper_refs_out")}
    have_cites = {r[0] for r in conn.execute(
        "SELECT DISTINCT accession_no FROM paper_cited_in")}
    rows = conn.execute(
        "SELECT accession_no, pub_year FROM papers").fetchall()
    band = {}
    for acc, yr in rows:
        b = _band(yr)
        s = band.setdefault(b, [0, 0, 0])
        s[0] += 1
        s[1] += acc in have_refs
        s[2] += acc in have_cites
    lines += ["## 分年份段覆盖", "",
              "| 年份段 | 论文 | 有参考文献列表 | 有被引列表 |", "|---|---|---|---|"]
    csv_lines = ["year_band,papers,with_refs,with_cites"]
    for lo, hi, name in YEAR_BANDS:
        if name not in band:
            continue
        p, r, c = band[name]
        lines.append("| %s | %d | %d (%.1f%%) | %d (%.1f%%) |" % (
            name, p, r, r / p * 100, c, c / p * 100))
        csv_lines.append("%s,%d,%d,%d" % (name, p, r, c))
    lines.append("")

    # 库内网络 top 被引
    top = conn.execute(
        "SELECT e.cited_acc, COUNT(*) n, p.title, p.doi FROM paper_cit_edges e "
        "JOIN papers p ON p.accession_no=e.cited_acc "
        "GROUP BY e.cited_acc ORDER BY n DESC LIMIT 15").fetchall()
    lines += ["## 库内被引 Top 15", ""]
    for acc, n, title, doi in top:
        lines.append("- %d 次 —— %s（%s）" % (n, (title or "")[:80], doi or acc))
    lines.append("")
    conn.close()

    reports = _paths.project_root() / "reports"
    reports.mkdir(exist_ok=True)
    md = reports / "citations_report.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (reports / "citations_coverage_by_year.csv").write_text(
        "\n".join(csv_lines), encoding="utf-8-sig")
    print("[report] -> %s" % md)
    print("[report] -> %s" % (reports / "citations_coverage_by_year.csv"))
    return str(md)
