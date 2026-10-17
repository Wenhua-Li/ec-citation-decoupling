# -*- coding: utf-8 -*-
"""Composition sensitivity for the fixed eight-source outside-to-field rate.

This is a sensitivity analysis.  It keeps the registered numerator and source
set, then reweights annual rates to the 2021 composition of (i) source and
(ii) a mutually exclusive title/abstract topic flag.  It does not alter the
registered headline reading.
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

edge_rows = ecdb.raw_sql(
    """
    SELECT DISTINCT r.accession_no acc
    FROM paper_refs_out r
    JOIN papers pc ON pc.doi=r.cited_doi
    JOIN paper_domain dc ON dc.accession_no=pc.accession_no
    WHERE dc.label='EC'
    """,
    max_rows=3000000,
)["rows"]

edges = Counter()
for r in edge_rows:
    if r["acc"] in meta:
        edges[r["acc"]] += 1

counts = defaultdict(lambda: defaultdict(lambda: [0, 0]))
for acc, m in meta.items():
    y = m["year"]
    for key in (m["source"], m["topic"]):
        counts[key][y][0] += 1
        counts[key][y][1] += edges.get(acc, 0)

def reweighted(key: str, target_year: int = 2021):
    # For a dimension, collect its group names from the stored keys.
    groups = sorted({m[key] for m in meta.values()})
    # Groups absent in the target year have zero target weight and do not
    # block earlier years from being evaluated.
    target_counts = {g: counts[g][target_year][0] for g in groups}
    target_n = sum(target_counts.values())
    active = [g for g in groups if target_counts[g] > 0]
    shares = {g: target_counts[g] / target_n for g in active} if target_n else {}
    out = {}
    for y in sorted({m["year"] for m in meta.values()}):
        if y < 2005 or y > 2025:
            continue
        rates = {g: (counts[g][y][1] / counts[g][y][0]) if counts[g][y][0] else None for g in active}
        available = [g for g in active if rates[g] is not None]
        if not available:
            continue
        denom = sum(shares[g] for g in available)
        weights = {g: shares[g] / denom for g in available}
        out[str(y)] = {
            "rate": sum(weights[g] * rates[g] for g in available),
            "n_non": sum(counts[g][y][0] for g in groups),
            "target_shares": shares,
            "available_groups": available,
            "group_rates": rates,
        }
    return out

def endpoint(series):
    a, b = series.get("2021"), series.get("2025")
    if not a or not b:
        return None
    return {
        "rate_2021": round(a["rate"], 6),
        "rate_2025": round(b["rate"], 6),
        "relative_change": round(b["rate"] / a["rate"] - 1, 6) if a["rate"] else None,
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
        "unit": "citations from stable-source NON_EC papers to in-corpus EC papers per NON_EC paper",
        "topic_text": "mutually exclusive title/abstract flag, priority ordered; sensitivity only",
        "edge_definition": "distinct paper_refs_out source-to-target pairs after DOI resolution",
        "registered_headline_unchanged": True,
    },
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)
print(json.dumps({k: v.get("endpoints") for k, v in result.items() if isinstance(v, dict) and "endpoints" in v}, ensure_ascii=False, indent=1))
