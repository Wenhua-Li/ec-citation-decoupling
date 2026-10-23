# -*- coding: utf-8 -*-
"""Audit U1 horizontal interaction and exact pairwise width contributions.

Reads the production stable-set output and writes a deterministic audit table.
This is an analysis-layer check only; it does not touch the database.
"""
import itertools
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT = os.path.join(HERE, "out", "stable8_merged.json")
OUTPUT = os.path.join(HERE, "out", "u1_contributions.json")

with open(INPUT, encoding="utf-8") as f:
    data = json.load(f)

end_year = 2024
support = data["same_support"][str(end_year)]["intersection_sources"]
per_source = data["per_source_e1"]

def cell(year, source):
    return per_source[f"{year}|{source}"]

n0 = {s: cell(2021, s)["n_non"] for s in support}
n1 = {s: cell(end_year, s)["n_non"] for s in support}
N0, N1 = sum(n0.values()), sum(n1.values())
wx = {s: n0[s] / N0 for s in support}
wy = {s: n1[s] / N1 for s in support}
a = {s: cell(2021, s)["E1"] for s in support}
b = {s: cell(end_year, s)["E1"] for s in support}
B0 = sum(wx[s] * a[s] for s in support)
B1 = sum(wy[s] * a[s] for s in support)

pair_terms = []
for i, j in itertools.combinations(support, 2):
    numerator = (wy[i] * wx[j] - wx[i] * wy[j]) * (b[i] * a[j] - a[i] * b[j])
    pair_terms.append({
        "sources": [i, j],
        "numerator": numerator,
        "width_contribution": numerator / (B1 * B0),
    })

interaction = [
    {
        "source": s,
        "delta_weight": wy[s] - wx[s],
        "delta_level": b[s] - a[s],
        "interaction": (wy[s] - wx[s]) * (b[s] - a[s]),
    }
    for s in support
]

laspeyres = sum(wx[s] * b[s] for s in support) / B0 - 1
paasche = sum(wy[s] * b[s] for s in support) / B1 - 1
width = paasche - laspeyres
result = {
    "task": "U1 exact pairwise width versus horizontal interaction audit",
    "window": "2021->2024",
    "support": support,
    "conditions": {
        "common_support": True,
        "nonnegative_weights": True,
        "positive_base_aggregates": B0 > 0 and B1 > 0,
        "finite_nonzero_source_bases": all(a[s] > 0 for s in support),
    },
    "aggregates": {
        "B0": B0,
        "B1": B1,
        "laspeyres_change": laspeyres,
        "paasche_change": paasche,
        "exact_width": width,
        "exact_width_percentage_points": width * 100,
    },
    "horizontal_interaction": interaction,
    "horizontal_interaction_sum": sum(x["interaction"] for x in interaction),
    "pairwise_terms": sorted(pair_terms, key=lambda x: abs(x["width_contribution"]), reverse=True),
    "pairwise_width_sum": sum(x["width_contribution"] for x in pair_terms),
}

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

print(json.dumps({
    "window": result["window"],
    "exact_width_percentage_points": round(result["aggregates"]["exact_width_percentage_points"], 4),
    "horizontal_interaction_sum": round(result["horizontal_interaction_sum"], 6),
    "pairwise_width_sum": round(result["pairwise_width_sum"], 6),
}, ensure_ascii=False, indent=1))
