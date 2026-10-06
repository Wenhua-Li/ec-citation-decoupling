# -*- coding: utf-8 -*-
"""queue_sensitivity.py — 低置信打标队列（2,528 篇）剔除敏感性。

背景：分析管线（trade.py / r3b_dims.py 等）加载 paper_domain 全部标签，低置信队列
（LLM 层 confidence < 0.75，共 2,528 篇）实际包含在已登记读数之内。本脚本复算两组
头部读数——发文池（trade.py pool 口径）与双端对外引用率（r3b_dims balance_stable
口径）——各跑"含队列 / 剔除队列"两版，供 SI 表 1 的敏感性块与 Methods 的口径句使用。

校验义务：不含队列的版本必须复现已登记值（2,995/2,789；0.686/0.358/3.217/2.803），
否则说明复制口径跑偏，拒绝写文件。

输出：research/nature/out/queue_sensitivity.json
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ecdb

QUEUE = "NOT (d.tier='llm' AND d.confidence < 0.75)"
OUT = os.path.join(HERE, "out", "queue_sensitivity.json")

# --- 队列构成 ---------------------------------------------------------------
qrows = ecdb.raw_sql(
    "SELECT d.label l, COUNT(*) n FROM paper_domain d "
    "WHERE d.tier='llm' AND d.confidence < 0.75 GROUP BY 1",
    max_rows=10,
)["rows"]
queue_comp = {r["l"]: r["n"] for r in qrows}

# --- 发文池（trade.py pool 口径：当年有参考文献列表的论文） ------------------
def pool(where_extra=""):
    rows = ecdb.raw_sql(
        f"""
        SELECT p.pub_year y, d.label l, COUNT(DISTINCT r.accession_no) n
        FROM papers p
        JOIN paper_refs_out r USING(accession_no)
        JOIN paper_domain d USING(accession_no)
        {('WHERE ' + where_extra) if where_extra else ''}
        GROUP BY p.pub_year, d.label
        """,
        max_rows=100,
    )["rows"]
    out = defaultdict(dict)
    for r in rows:
        out[r["y"]][r["l"]] = r["n"]
    return out

pool_with = pool()
pool_without = pool(QUEUE)

# --- 双端对外引用率（r3b_dims balance_stable 口径：稳定 8 刊源内） -------------
checks = json.load(open(os.path.join(HERE, "out", "checks.json"), encoding="utf-8"))
STABLE = set(checks["c2_stable_sources"])

meta = {}
for r in ecdb.raw_sql(
    "SELECT d.accession_no acc, d.label, d.tier, d.confidence conf, p.pub_year y, p.source s "
    "FROM paper_domain d JOIN papers p USING(accession_no)",
    max_rows=200000,
)["rows"]:
    meta[r["acc"]] = (r["label"], r["y"], r["s"], not (r["tier"] == "llm" and r["conf"] < 0.75))

stable_acc = {a for a, m in meta.items() if m[2] in STABLE}
edges = ecdb.raw_sql(
    "SELECT DISTINCT r.accession_no acc, pc.accession_no cited "
    "FROM paper_refs_out r JOIN papers pc ON pc.doi = r.cited_doi",
    max_rows=3000000,
)["rows"]


def balance(keep_queue: bool):
    cnt = defaultdict(lambda: {"EC": 0, "NON": 0})
    bal = defaultdict(lambda: defaultdict(int))
    for a in stable_acc:
        lab, y, _s, ok = meta[a]
        if not keep_queue and not ok:
            continue
        if y:
            cnt[y]["EC" if lab == "EC" else "NON"] += 1
    for r in edges:
        a, c = r["acc"], r["cited"]
        if a not in stable_acc or c not in stable_acc or a == c:
            continue
        la_, lb_ = meta[a], meta[c]
        if not keep_queue and (not la_[3] or not lb_[3]):
            continue
        ya = la_[1]
        if ya is None:
            continue
        la_ec, lc_ec = la_[0] == "EC", lb_[0] == "EC"
        if la_ec and not lc_ec:
            bal[ya]["e_EC_to_NON"] += 1
        elif lc_ec and not la_ec:
            bal[ya]["e_NON_to_EC"] += 1
    out = {}
    for y in sorted(bal):
        n_ec, n_non = cnt[y]["EC"], cnt[y]["NON"]
        if n_ec >= 100 and n_non >= 100:
            b = bal[y]
            out[str(y)] = {
                "N_EC": n_ec, "N_NON": n_non,
                "rate_NON_papers_cite_EC": round(b["e_NON_to_EC"] / n_non, 4),
                "rate_EC_papers_cite_NON": round(b["e_EC_to_NON"] / n_ec, 4),
            }
    return out


bal_with = balance(True)
bal_without = balance(False)

# --- 校验：含队列版必须复现已登记值 -------------------------------------------
checks_ok = (
    pool_with[2024].get("EC") == 2995
    and pool_with[2025].get("EC") == 2789
    and round(bal_with["2021"]["rate_NON_papers_cite_EC"], 3) == 0.686
    and round(bal_with["2025"]["rate_NON_papers_cite_EC"], 3) == 0.358
    and round(bal_with["2021"]["rate_EC_papers_cite_NON"], 3) == 3.217
    and round(bal_with["2025"]["rate_EC_papers_cite_NON"], 3) == 2.803
)
print("含队列版复现校验：", "PASS" if checks_ok else "FAIL")
print("  pool_EC 2024/2025:", pool_with[2024].get("EC"), pool_with[2025].get("EC"))
print("  balance 2021:", bal_with.get("2021"))
print("  balance 2025:", bal_with.get("2025"))
if not checks_ok:
    raise SystemExit("口径复制与登记值不符，拒绝写文件")

years = sorted(set(bal_with) & set(bal_without))
result = {
    "queue_definition": "paper_domain tier='llm' AND confidence < 0.75",
    "queue_composition": queue_comp,
    "pool_with_queue": {str(y): pool_with[y] for y in sorted(pool_with)},
    "pool_without_queue": {str(y): pool_without[y] for y in sorted(pool_without)},
    "balance_with_queue": bal_with,
    "balance_without_queue": bal_without,
    "headline_years": ["2021", "2024", "2025"],
    "note": "balance_stable 口径：稳定 8 刊源内双端篇均引用率；pool 口径：当年有参考文献列表的论文数（trade.py）。",
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)
print("saved", OUT)
for y in ("2021", "2025"):
    w, wo = bal_with[y], bal_without[y]
    print(f"{y}: outward(NON->EC) {w['rate_NON_papers_cite_EC']} -> {wo['rate_NON_papers_cite_EC']} | "
          f"inward(EC->NON) {w['rate_EC_papers_cite_NON']} -> {wo['rate_EC_papers_cite_NON']}")
for y in (2024, 2025):
    print(f"{y}: pool_EC {pool_with[y].get('EC')} -> {pool_without[y].get('EC')} | "
          f"pool_NON {pool_with[y].get('NON_EC')} -> {pool_without[y].get('NON_EC')}")
