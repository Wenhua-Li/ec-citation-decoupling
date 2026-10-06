"""validate —— 验收检查（方案第 5 节 A/B/C/D 组），结果写 reports/citation_validation.json。

A 组（迁移完整性）需要 EC_History 旧库（--old-db 或 ECCITE_OLD_DB）；
旧库缺失时 A1/A2/A3 自动降级为 SKIP，不阻塞 B/C 组。
"""
import json
import random
import sqlite3
import statistics
import time
from pathlib import Path

from ecdb import _paths
from ecdb.cleaning import normalize_title

from . import _db

NSGA2_DOI = "10.1109/4235.996017"
NSGA3_DOI = "10.1109/tevc.2013.2281535"
YEAR_BANDS = [(None, 1995, "≤1995"), (1996, 2005, "1996-2005"),
              (2006, 2015, "2006-2015"), (2016, 2020, "2016-2020"),
              (2021, None, "2021+")]


def _band(year):
    for lo, hi, name in YEAR_BANDS:
        if (lo is None or year >= lo) and (hi is None or year <= hi):
            return name
    return "?"


def _chunk_in(conn, sql_tpl, values, chunk=800):
    """按 IN 分块的聚合查询助手，返回 {key: count}。"""
    out = {}
    for c in _db.chunked(values, chunk):
        ph = ",".join("?" * len(c))
        for k, n in conn.execute(sql_tpl % ph, c):
            out[k] = out.setdefault(k, 0) + n
    return out


def _build_mapping(old, conn_ro):
    doi2accs = {}
    for acc, doi in conn_ro.execute(
            "SELECT accession_no, doi FROM papers WHERE doi IS NOT NULL AND doi != ''"):
        doi2accs.setdefault(doi.strip().lower(), []).append(acc)
    pid2accs = {}
    for pid, doi in old.execute(
            "SELECT p.id, p.doi FROM papers p JOIN cit_meta m ON m.paper_id=p.id "
            "WHERE p.id=p.canonical_id AND p.doi IS NOT NULL AND p.doi != ''"):
        accs = doi2accs.get(doi.strip().lower())
        if accs:
            pid2accs[pid] = accs
    return pid2accs


def validate(old_db=None):
    conn = _db.connect_ro()
    missing = _db.missing_tables(conn)
    if missing:
        print("[validate] 引文表尚未创建（缺 %s），请先运行 python -m eccite init" % missing)
        return None
    res = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "checks": []}

    def check(name, ok, detail, state=None):
        state = state or ("PASS" if ok else "FAIL")
        res["checks"].append({"name": name, "state": state, "detail": detail})
        print("[validate] %-4s %s | %s" % (state, name, detail))

    # ---- 基本量 ----
    totals = {}
    for t in ("paper_refs_out", "paper_cited_in", "paper_cit_meta", "paper_cit_edges"):
        totals[t] = conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
    res["totals"] = totals
    res["per_source"] = {
        "refs_out": dict(conn.execute(
            "SELECT source, COUNT(*) FROM paper_refs_out GROUP BY source")),
        "cited_in": dict(conn.execute(
            "SELECT source, COUNT(*) FROM paper_cited_in GROUP BY source")),
    }
    n_papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    n_doi = conn.execute(
        "SELECT COUNT(*) FROM papers WHERE doi IS NOT NULL AND doi != ''").fetchone()[0]

    # ---- A 组：迁移完整性（需旧库） ----
    old = None
    try:
        old_path = str(old_db) if old_db else str(_db.old_db_default())
        old = sqlite3.connect(f"file:{old_path}?mode=ro", uri=True, timeout=30)
    except sqlite3.Error:
        pass
    if old is not None:
        pid2accs = _build_mapping(old, conn)
        pids = list(pid2accs)
        accs_all = [a for v in pid2accs.values() for a in v]

        # 旧库基准 = 去重后计数：迁移的主键是 (acc, source, cited_key)，
        # cited_key 与下方 COALESCE 表达式一一对应（doi / oa:W / r:rowid），
        # 同一论文同一源里重复出现的 DOI 在新库只占一行。
        old_out = _chunk_in(old, (
            "SELECT source, COUNT(*) FROM (SELECT DISTINCT paper_id, source, "
            "COALESCE(cited_doi, 'oa:'||COALESCE(cited_oa, 'r:'||rowid)) k "
            "FROM cit_out WHERE paper_id IN (%s)) GROUP BY source"), pids)
        old_in = _chunk_in(old, (
            "SELECT source, COUNT(*) FROM (SELECT DISTINCT paper_id, source, "
            "COALESCE(citing_doi, 'oa:'||COALESCE(citing_oa, 'r:'||rowid)) k "
            "FROM cit_in WHERE paper_id IN (%s)) GROUP BY source"), pids)
        new_out = _chunk_in(conn, "SELECT source, COUNT(*) FROM paper_refs_out "
                                  "WHERE accession_no IN (%s) GROUP BY source", accs_all)
        new_in = _chunk_in(conn, "SELECT source, COUNT(*) FROM paper_cited_in "
                                 "WHERE accession_no IN (%s) GROUP BY source", accs_all)
        for tag, o, n in (("refs_out", old_out, new_out), ("cited_in", old_in, new_in)):
            diffs = {s: (o.get(s, 0), n.get(s, 0)) for s in set(o) | set(n)}
            worst = max((abs(a - b) / a for a, b in diffs.values() if a), default=0)
            res["a1_%s" % tag] = {"old": o, "new": n,
                                  "worst_rel_diff": round(worst, 6)}
            check("A1 迁移行数逐源一致(%s)" % tag, worst < 0.001,
                  "旧=%s 新=%s 最大相对差 %.4f%%" % (o, n, worst * 100))

        rng = random.Random(42)
        sample = rng.sample(pids, min(100, len(pids)))
        bad = 0
        worst_ratio = 0.0
        for pid in sample:
            for old_tbl, new_tbl, col in (("cit_out", "paper_refs_out", "cited_doi"),
                                          ("cit_in", "paper_cited_in", "citing_doi")):
                oa_col = col.replace("doi", "oa")
                o = dict(old.execute(
                    "SELECT source, COUNT(*) FROM (SELECT DISTINCT source, "
                    "COALESCE(%s, 'oa:'||COALESCE(%s, 'r:'||rowid)) k "
                    "FROM %s WHERE paper_id=?) GROUP BY source" % (col, oa_col, old_tbl),
                    (pid,)))
                acc = pid2accs[pid][0]
                n = dict(conn.execute("SELECT %s, COUNT(*) FROM %s WHERE accession_no=? "
                                      "GROUP BY %s" % ("source", new_tbl, "source"), (acc,)))
                for s in set(o) | set(n):
                    a, b = o.get(s, 0), n.get(s, 0)
                    if a == 0 and b == 0:
                        continue
                    if a == 0:
                        bad += 1
                        continue
                    rel = abs(a - b) / a
                    worst_ratio = max(worst_ratio, rel)
                    if rel > 0.005 and abs(a - b) > 2:
                        bad += 1
        res["a2_sample"] = {"n": len(sample), "mismatched": bad,
                            "worst_rel_diff": round(worst_ratio, 6)}
        check("A2 抽样 100 篇逐篇一致", bad == 0,
              "mismatch=%d worst_rel=%.4f%%" % (bad, worst_ratio * 100))

        row = conn.execute(
            "SELECT cr_cit_count, s2_cit_count, s2_ref_count FROM paper_cit_meta "
            "WHERE accession_no = (SELECT accession_no FROM papers WHERE doi=?)",
            (NSGA2_DOI,)).fetchone()
        ok = row and row[0] == 43014 and row[1] == 49151
        res["a3_anchor"] = {"doi": NSGA2_DOI,
                            "cr_cit_count": row[0] if row else None,
                            "s2_cit_count": row[1] if row else None,
                            "s2_ref_count": row[2] if row else None}
        check("A3 锚点 NSGA-II 计数在库", bool(ok),
              "cr=%s s2=%s（期望 cr=43014, s2=49151）" % (
                  row[0] if row else None, row[1] if row else None))
        old.close()
    else:
        check("A1-A3 迁移完整性", False, "旧库不可用，跳过", state="SKIP")

    # ---- B4 meta 覆盖 ----
    row = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN refs_status!='pending' OR cites_status!='pending' "
        "THEN 1 ELSE 0 END) FROM paper_cit_meta").fetchone()
    meta_n, done_n = row[0], row[1] or 0
    rate = done_n / n_doi if n_doi else 0
    res["b4"] = {"papers_with_doi": n_doi, "meta_done": done_n, "rate": round(rate, 4)}
    check("B4 meta 覆盖与抓取发起率 ≥99.5%%", rate >= 0.995,
          "有DOI论文 %d，已发起 %d（%.2f%%）" % (n_doi, done_n, rate * 100))

    # ---- B5 参考文献列表覆盖率（总体 + 分年份段） ----
    have_refs = {r[0] for r in conn.execute("SELECT DISTINCT accession_no FROM paper_refs_out")}
    year_rows = conn.execute(
        "SELECT accession_no, pub_year FROM papers WHERE doi IS NOT NULL AND doi != ''").fetchall()
    band_stat = {}
    for acc, yr in year_rows:
        b = _band(yr if yr is not None else -1)
        s = band_stat.setdefault(b, [0, 0])
        s[0] += 1
        if acc in have_refs:
            s[1] += 1
    total_cov = len(have_refs) / n_doi if n_doi else 0
    res["b5"] = {"overall": round(total_cov, 4),
                 "by_band": {b: {"papers": v[0], "with_refs": v[1],
                                 "rate": round(v[1] / v[0], 4) if v[0] else None}
                             for b, v in sorted(band_stat.items())}}
    check("B5 参考文献列表覆盖率 ≥90%%", total_cov >= 0.90,
          "总体 %.2f%%；分年份段 %s" % (
              total_cov * 100,
              {b: "%.1f%%" % (v[1] / v[0] * 100) for b, v in sorted(band_stat.items())}))

    # ---- B6 title_match ----
    tm = conn.execute(
        "SELECT COUNT(*) FROM paper_cit_meta WHERE doi_source='title_match'").fetchone()[0]
    n_nodoi = conn.execute(
        "SELECT COUNT(*) FROM papers WHERE doi IS NULL OR doi=''").fetchone()[0]
    res["b6"] = {"title_matched": tm, "papers_no_doi": n_nodoi}
    check("B6 title_match 统计", True,
          "无DOI论文 %d，标题匹配找回 DOI %d（抽样核对 reports/title_match.csv）"
          % (n_nodoi, tm), state="INFO")

    # ---- C7 Crossref 参考清单 vs EI num_references ----
    # 主口径：全部存缴条目（含无 DOI 条目）——出版商存缴的是完整参考清单，
    # 约 28% 条目没有 DOI，只数有 DOI 条目会把中位比压到 ~0.72 造成假阴性。
    ratios = [r[0] for r in conn.execute(
        "SELECT 1.0*COUNT(*)/p.num_references "
        "FROM papers p JOIN paper_refs_out r ON r.accession_no=p.accession_no "
        "AND r.source='crossref' "
        "WHERE p.num_references > 0 GROUP BY p.accession_no")]
    ratios_doi = [r[0] for r in conn.execute(
        "SELECT 1.0*COUNT(DISTINCT r.cited_doi)/p.num_references "
        "FROM papers p JOIN paper_refs_out r ON r.accession_no=p.accession_no "
        "AND r.source='crossref' AND r.cited_doi IS NOT NULL "
        "WHERE p.num_references > 0 GROUP BY p.accession_no")]
    if ratios:
        med = statistics.median(ratios)
        out15 = sum(1 for x in ratios if x > 1.5)
        res["c7"] = {"n": len(ratios), "median_ratio_all_entries": round(med, 4),
                     "median_ratio_doi_only": round(statistics.median(ratios_doi), 4)
                     if ratios_doi else None,
                     "over_1_5": out15}
        check("C7 参考清单召回（全条目口径中位比 ≥0.85）", med >= 0.85,
              "n=%d 全条目median=%.3f 仅DOI条目median=%.3f 超1.5的论文=%d"
              "（超1.5属EI计数偏少，告警不判失败）"
              % (len(ratios), med,
                 statistics.median(ratios_doi) if ratios_doi else 0, out15))
    else:
        check("C7 参考清单召回", False, "无 crossref 出边可比", state="SKIP")

    # ---- C8 入边时序（按源）----
    # oc 源年份=记录创建年，s2 源=施引论文发表年；EI pub_year 常取正式出版年，
    # 在线优先发表的论文会合法出现"被引早于出版年 1 年以上"（s2 源集中），
    # 故 s2 阈值放宽到 0.25%，oc 保持 0.1%。
    temporal = {}
    for src, n_y, viol in conn.execute(
            "SELECT c.source, COUNT(*), SUM(CASE WHEN c.citing_year < p.pub_year - 1 "
            "THEN 1 ELSE 0 END) FROM paper_cited_in c "
            "JOIN papers p ON p.accession_no=c.accession_no "
            "WHERE c.citing_year IS NOT NULL AND p.pub_year IS NOT NULL GROUP BY c.source"):
        temporal[src] = {"edges_with_year": n_y, "violations": viol,
                         "rate": round(viol / n_y, 6) if n_y else None}
    res["c8"] = temporal
    for src, limit in (("oc", 0.001), ("s2", 0.0025)):
        t = temporal.get(src)
        if not t or not t["edges_with_year"]:
            check("C8 时序违例率 %s 源" % src, True, "无含年份数据", state="SKIP")
            continue
        check("C8 时序违例率 %s 源 ≤%.2f%%" % (src, limit * 100),
              t["rate"] <= limit,
              "含年份入边 %d，违例 %d（%.4f%%）" % (
                  t["edges_with_year"], t["violations"], t["rate"] * 100))

    # ---- C9 正负例边 ----
    pos_hits, neg_hits = 0, 0
    n3 = conn.execute("SELECT accession_no FROM papers WHERE doi=?",
                      (NSGA3_DOI,)).fetchone()
    n2 = conn.execute("SELECT accession_no FROM papers WHERE doi=?",
                      (NSGA2_DOI,)).fetchone()
    if n3 and n2:
        pos_hits = conn.execute(
            "SELECT COUNT(*) FROM paper_refs_out WHERE accession_no=? AND cited_doi=?",
            (n3[0], NSGA2_DOI)).fetchone()[0]
    neg_hits = conn.execute(
        "SELECT COUNT(*) FROM paper_refs_out WHERE cited_doi=? AND accession_no="
        "(SELECT accession_no FROM papers WHERE doi=?)",
        (NSGA3_DOI, NSGA2_DOI)).fetchone()[0] if n2 else -1
    res["c9"] = {"positive_hits": pos_hits, "negative_hits": neg_hits}
    check("C9 正例 NSGA-III→NSGA-II 存在", pos_hits > 0, "hits=%d" % pos_hits)
    check("C9 负例 NSGA-II→NSGA-III 不存在", neg_hits == 0, "hits=%d" % neg_hits)

    # ---- C10 S2 入边截断一致性 ----
    mx = conn.execute(
        "SELECT MAX(n) FROM (SELECT COUNT(*) n FROM paper_cited_in "
        "WHERE source='s2' GROUP BY accession_no)").fetchone()[0]
    res["c10"] = {"max_s2_in_edges": mx}
    check("C10 S2 单篇入边 ≤10000", (mx or 0) <= 10000, "max=%s" % mx)

    # ---- C11 完整性 ----
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    res["c11"] = {"fk_violations": len(fk)}
    check("C11 foreign_key_check 零违规", len(fk) == 0, "violations=%d" % len(fk))

    conn.close()
    reports = _paths.project_root() / "reports"
    reports.mkdir(exist_ok=True)
    dest = reports / "citation_validation.json"
    dest.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    n_fail = sum(1 for c in res["checks"] if c["state"] == "FAIL")
    print("[validate] %d 项检查，FAIL %d 项 -> %s" % (
        len(res["checks"]), n_fail, dest))
    return res
