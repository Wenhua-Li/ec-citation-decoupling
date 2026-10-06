# -*- coding: utf-8 -*-
"""沉睡美人 / 唤醒事件分析。

定义（库内被引时序，paper_cited_in 的 citing_year）：
  - 睡眠期：连续 >= 6 年年年被引 <= 2 次（且发表 >= 3 年后才开始统计）
  - 唤醒：睡眠期后某年开始 3 年平均被引 >= 睡眠期均值 5 倍且绝对值 >= 8 次/年
  - 唤醒者画像：唤醒后 3 年引用者中 EC / 非 EC 占比（用 citing_doi 回连 paper_domain）
输出：research/nature/out/beauty.json（含 Top 唤醒事件清单）
"""
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ecdb

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

year_of = {}
title_of = {}
label_of = {}
doi_of = {}
for r in ecdb.raw_sql(
    "SELECT p.accession_no acc, p.pub_year y, p.title, p.doi, d.label "
    "FROM papers p JOIN paper_domain d USING(accession_no)",
    max_rows=200000,
)["rows"]:
    year_of[r["acc"]] = r["y"]
    title_of[r["acc"]] = r["title"]
    label_of[r["acc"]] = r["label"]
    doi_of[r["acc"]] = r["doi"]
print(f"papers loaded {len(year_of)}", flush=True)

# 每篇每年的被引次数（全源，citing_year）
print("aggregating per-year citation series ...", flush=True)
rows = ecdb.raw_sql(
    "SELECT accession_no acc, citing_year cy, COUNT(*) n FROM paper_cited_in "
    "WHERE citing_year IS NOT NULL GROUP BY accession_no, citing_year",
    max_rows=500000,
)["rows"]
series = defaultdict(dict)
for r in rows:
    series[r["acc"]][r["cy"]] = r["n"]
print(f"papers with >=1 citation: {len(series)}", flush=True)

# 唤醒者画像需要：citing_doi -> 库内 label
citing_label = {}
for r in ecdb.raw_sql(
    "SELECT DISTINCT c.citing_doi doi, d.label l FROM paper_cited_in c "
    "JOIN papers p ON p.doi = c.citing_doi JOIN paper_domain d ON d.accession_no = p.accession_no "
    "WHERE c.citing_doi IS NOT NULL",
    max_rows=200000,
)["rows"]:
    citing_label[r["doi"]] = r["l"]
print(f"citing-in-db label coverage: {len(citing_label)}", flush=True)

events = []
for acc, s in series.items():
    y0 = year_of.get(acc)
    if y0 is None or y0 > 2016:
        continue  # 需要足够的睡眠窗口与唤醒后观测
    # 唤醒候选年 a：a >= y0+4, a <= 2022（留 3 年观测）
    for a in range(y0 + 4, 2023):
        pre = [s.get(y, 0) for y in range(max(y0, a - 8), a)]
        if len(pre) < 6 or max(pre) > 2:
            continue
        pre_mean = sum(pre) / len(pre)
        post = [s.get(y, 0) for y in range(a, a + 3)]
        if len(post) < 3:
            continue
        post_mean = sum(post) / 3
        if post_mean >= max(8.0, 5 * max(pre_mean, 0.5)):
            # 找最早唤醒年（回溯合并）
            while a - 1 > y0 + 3:
                pp = [s.get(y, 0) for y in range(a - 1, a + 2)]
                if len(pp) == 3 and sum(pp) / 3 >= max(8.0, 5 * max(pre_mean, 0.5)):
                    a -= 1
                else:
                    break
            # 唤醒后 3 年引用者画像
            lab_rows = ecdb.raw_sql(
                "SELECT DISTINCT citing_doi FROM paper_cited_in WHERE accession_no=? AND citing_year BETWEEN ? AND ?",
                params=(acc, a, a + 2),
                max_rows=50000,
            )["rows"]
            n_in = sum(1 for lr in lab_rows if citing_label.get(lr["citing_doi"]))
            n_out = sum(1 for lr in lab_rows if lr["citing_doi"] and lr["citing_doi"] not in citing_label)
            n_unk = sum(1 for lr in lab_rows if not lr["citing_doi"])
            events.append(
                {
                    "acc": acc,
                    "title": title_of.get(acc, "")[:110],
                    "year": y0,
                    "awake_year": a,
                    "slept_years": a - y0,
                    "pre_mean": round(pre_mean, 2),
                    "post_mean": round(post_mean, 1),
                    "fold": round(post_mean / max(pre_mean, 0.5), 1),
                    "label": label_of.get(acc),
                    "awakeners_in_db_ec": n_in,
                    "awakeners_outside": n_out,
                    "awakeners_unknown_doi": n_unk,
                }
            )
            break

events.sort(key=lambda e: -e["fold"] * e["post_mean"])
with open(os.path.join(OUT, "beauty.json"), "w", encoding="utf-8") as f:
    json.dump(events, f, ensure_ascii=False, indent=1)

print(f"\nwake-up events found: {len(events)}")
ec_ev = [e for e in events if e["label"] == "EC"]
print(f"of which EC papers: {len(ec_ev)}")
ext_dom = [e for e in events if e["awakeners_outside"] > e["awakeners_in_db_ec"]]
print(f"awakened mostly from OUTSIDE the corpus: {len(ext_dom)}/{len(events)}")
print("\n=== Top 25 唤醒事件 ===")
for e in events[:25]:
    print(
        f"[{e['year']}->{e['awake_year']}] fold={e['fold']} {e['pre_mean']}->{e['post_mean']}/yr "
        f"in_db={e['awakeners_in_db_ec']} out={e['awakeners_outside']} [{e['label']}] {e['title']}"
    )
