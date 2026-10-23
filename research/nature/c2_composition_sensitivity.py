# -*- coding: utf-8 -*-
"""Composition sensitivity for the fixed eight-source outside-to-field rate.

Unit fix (2026-10-14, NC reboot stage 0 task 0-1).  The original version
counted each citing paper once (``SELECT DISTINCT accession_no``), so its
"rate" was actually the share of NON_EC papers citing >=1 EC paper (a binary
participation rate, estimator E2) while being labelled per-paper citations
(E1).  This version counts distinct (citing, cited) edges -- aligned with
checks.py -- and reports BOTH estimators explicitly:

  E1  mean in-corpus EC citation edges per NON_EC paper
  E2  share of NON_EC papers with >=1 in-corpus EC citation edge

Years in which a 2021-active group is absent are reweighted over the
available groups with explicit ``coverage_share`` and ``excluded_groups``
(no silent renormalisation).  This remains a sensitivity analysis; the
registered headline reading is unchanged.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ecdb

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "c2_composition_sensitivity.json")

stable = {
    "Applied Soft Computing Journal",
    "Computers and Industrial Engineering",
    "Computers and Operations Research",
    "Engineering Applications of Artificial Intelligence",
    "European Journal of Operational Research",
    "Expert Systems with Applications",
    "IEEE Transactions on Fuzzy Systems",
    "Information Sciences",
}

# Priority makes the topic flag mutually exclusive.  These broad categories
# are used only for sensitivity weighting, not as a new substantive result.
TOPICS = [
    ("LLM_or_GPT", re.compile(r"large language model|\bllms?\b|\bgpt\b|chatgpt", re.I)),
    ("deep_learning", re.compile(r"deep learning|deep neural", re.I)),
    ("reinforcement_learning", re.compile(r"reinforcement learning", re.I)),
    ("transformer", re.compile(r"transformer\s+(models?|architectures?|networks?|encoders?|decoders?)", re.I)),
    ("explainable_AI", re.compile(r"explainab|interpretab", re.I)),
]

def topic_of(title: str | None, abstract: str | None) -> str:
    text = f"{title or ''} {abstract or ''}"
    for name, pat in TOPICS:
        if pat.search(text):
            return name
    return "other"

rows = ecdb.raw_sql(
    """
    SELECT p.accession_no acc, p.pub_year y, p.source src, p.title, p.abstract,
           d.label lab
    FROM papers p JOIN paper_domain d USING(accession_no)
    WHERE d.label='NON_EC' AND p.source IN (?,?,?,?,?,?,?,?)
    """,
    params=tuple(sorted(stable)), max_rows=200000,
)["rows"]

meta = {r["acc"]: {"year": r["y"], "source": r["src"], "topic": topic_of(r["title"], r["abstract"])} for r in rows}

# Edge-level counting, aligned with checks.py: DISTINCT over the
# (citing accession, cited accession) pair, not the citing paper alone.
edge_rows = ecdb.raw_sql(
    """
    SELECT DISTINCT r.accession_no acc, pc.accession_no cited
    FROM paper_refs_out r
    JOIN papers pc ON pc.doi=r.cited_doi
    JOIN paper_domain dc ON dc.accession_no=pc.accession_no
    WHERE dc.label='EC'
    """,
    max_rows=3000000,
)["rows"]

paper_edges = Counter()
for r in edge_rows:
    if r["acc"] in meta:
        paper_edges[r["acc"]] += 1

# counts[key][year] = [n_papers, sum_edges, n_papers_with_ge1_edge]
counts: dict = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
for acc, m in meta.items():
    e = paper_edges.get(acc, 0)
    for key in (m["source"], m["topic"]):
        c = counts[key][m["year"]]
        c[0] += 1
        c[1] += e
        c[2] += 1 if e else 0

def reweighted(key: str, target_year: int = 2021):
    groups = sorted({m[key] for m in meta.values()})
    target_counts = {g: counts[g].get(target_year, [0, 0, 0])[0] for g in groups}
    target_n = sum(target_counts.values())
    active = [g for g in groups if target_counts[g] > 0]
    shares = {g: target_counts[g] / target_n for g in active} if target_n else {}
    out = {}
    for y in sorted({m["year"] for m in meta.values()}):
        if y < 2005 or y > 2025:
            continue
        n_g = {g: counts[g].get(y, [0, 0, 0])[0] for g in active}
        rates_e1 = {g: (counts[g][y][1] / n_g[g]) if n_g[g] else None for g in active}
        rates_e2 = {g: (counts[g][y][2] / n_g[g]) if n_g[g] else None for g in active}
        available = [g for g in active if rates_e1[g] is not None]
        if not available:
            continue
        denom = sum(shares[g] for g in available)
        weights = {g: shares[g] / denom for g in available}
        out[str(y)] = {
            "e1_rate": sum(weights[g] * rates_e1[g] for g in available),
            "e2_rate": sum(weights[g] * rates_e2[g] for g in available),
            "n_non": sum(counts[g].get(y, [0, 0, 0])[0] for g in groups),
            "coverage_share": round(denom, 6),
            "excluded_groups": {g: round(shares[g], 6) for g in active if rates_e1[g] is None},
            "available_groups": available,
            "group_rates_e1": rates_e1,
        }
    return out

def endpoint(series):
    a, b = series.get("2021"), series.get("2025")
    if not a or not b:
        return None
    return {
        # E1 endpoints keep the legacy field names so registry references
        # (NUMBERS.md Q57/Q58 -> source_standardized.endpoints) stay valid.
        "rate_2021": round(a["e1_rate"], 6),
        "rate_2025": round(b["e1_rate"], 6),
        "relative_change": round(b["e1_rate"] / a["e1_rate"] - 1, 6) if a["e1_rate"] else None,
        "e2_rate_2021": round(a["e2_rate"], 6),
        "e2_rate_2025": round(b["e2_rate"], 6),
        "e2_relative_change": round(b["e2_rate"] / a["e2_rate"] - 1, 6) if a["e2_rate"] else None,
        "coverage_share_2025": b["coverage_share"],
        "excluded_groups_2025": b["excluded_groups"],
    }

source_series = reweighted("source")
topic_series = reweighted("topic")
result = {
    "stable_sources": sorted(stable),
    "topic_priority": [n for n, _ in TOPICS],
    "target_year": 2021,
    "source_standardized": {"series": source_series, "endpoints": endpoint(source_series)},
    "topic_standardized": {"series": topic_series, "endpoints": endpoint(topic_series)},
    "meta": {
        "unit_e1": "E1: distinct in-corpus EC citation edges per stable-source NON_EC paper (mean edges per paper)",
        "unit_e2": "E2: share of stable-source NON_EC papers with >=1 in-corpus EC citation edge (binary participation rate)",
        "unit_fix_note": "2026-10-14: original run counted DISTINCT citing papers (E2 mislabelled as E1); this run counts DISTINCT (acc, cited) edges aligned with checks.py and reports both estimators",
        "topic_text": "mutually exclusive title/abstract flag, priority ordered; sensitivity only",
        "edge_definition": "distinct paper_refs_out source-to-target pairs after DOI resolution",
        "missing_group_policy": "years lacking a 2021-active group are reweighted over available groups; coverage_share and excluded_groups (with their 2021 target shares) are reported explicitly",
        "registered_headline_unchanged": True,
    },
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)
print(json.dumps({k: v["endpoints"] for k, v in result.items() if isinstance(v, dict) and "endpoints" in v}, ensure_ascii=False, indent=1))
