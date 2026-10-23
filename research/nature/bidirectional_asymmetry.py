# -*- coding: utf-8 -*-
"""Bidirectional asymmetry matrix and source-cluster uncertainty.

This is a read-only downstream analysis of stable8_merged.json. It compares
NON->EC with EC->NON under the same source support, estimator, base composition,
and endpoint. It does not modify the database.
"""
import json
import os
import random
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT = os.path.join(HERE, "out", "stable8_merged.json")
OUTPUT = os.path.join(HERE, "out", "bidirectional_asymmetry.json")
SEED = 20261015
BOOTSTRAPS = 2000
START_YEAR = 2021
BASE_YEARS = (2019, 2021, 2024)
END_YEARS = (2024, 2025)
METRICS = ("E1", "E2", "E3")
REQUIRED_SUPPORT_YEARS = (2019, 2021, 2024, 2025)

with open(INPUT, encoding="utf-8") as f:
    data = json.load(f)

forward = data["per_source_e1"]
reverse = data["per_source_e1_reverse"]


def cell(table, year, source):
    return table.get(f"{year}|{source}")


def n_value(direction, row):
    return row["n_non"] if direction == "forward" else row["n_ec"]


def metric_value(direction, row, metric):
    if direction == "forward":
        return row[metric]
    return row[{"E1": "E1_to_non", "E2": "E2_to_non", "E3": "E3_to_non"}[metric]]


def all_sources(table):
    return sorted({key.split("|", 1)[1] for key in table})


def common_support(direction, start_year, end_year):
    table = forward if direction == "forward" else reverse
    sources = all_sources(table)
    return [s for s in sources if all(cell(table, y, s) and n_value(direction, cell(table, y, s)) > 0
                                      for y in REQUIRED_SUPPORT_YEARS)]


def weights(direction, base_year, support):
    table = forward if direction == "forward" else reverse
    counts = {s: n_value(direction, cell(table, base_year, s)) for s in support}
    total = sum(counts.values())
    return ({s: counts[s] / total for s in support} if total else {}), total


def aggregate(direction, year, metric, support, w):
    table = forward if direction == "forward" else reverse
    available = {s: cell(table, year, s) for s in support if cell(table, year, s)}
    weight_sum = sum(w[s] for s in available)
    if not available or not weight_sum:
        return None, weight_sum
    value = sum(w[s] * metric_value(direction, available[s], metric) for s in available)
    return value / weight_sum, weight_sum


def relative(direction, base_year, end_year, metric, support):
    w, n_base = weights(direction, base_year, support)
    if not w:
        return None
    start_value, start_cov = aggregate(direction, START_YEAR, metric, support, w)
    end_value, end_cov = aggregate(direction, end_year, metric, support, w)
    if start_value is None or end_value is None or start_value == 0:
        return None
    return {
        "start": start_value,
        "end": end_value,
        "rel_change": end_value / start_value - 1,
        "weight_sum_start": start_cov,
        "weight_sum_end": end_cov,
        "n_base": n_base,
        "weights": w,
    }


def gap_for(base_year, end_year, metric, support):
    f = relative("forward", base_year, end_year, metric, support)
    r = relative("reverse", base_year, end_year, metric, support)
    if f is None or r is None:
        return None
    return {
        "forward": f,
        "reverse": r,
        "gap_pp": 100 * (r["rel_change"] - f["rel_change"]),
        "same_direction": (r["rel_change"] >= f["rel_change"]),
    }


def percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    pos = (len(values) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(values) - 1)
    frac = pos - lo
    return values[lo] * (1 - frac) + values[hi] * frac


def bootstrap_gap(base_year, end_year, metric, support, rng):
    sampled = [rng.choice(support) for _ in support]
    multiplicity = Counter(sampled)
    f = bootstrap_relative("forward", base_year, end_year, metric, support, multiplicity)
    r = bootstrap_relative("reverse", base_year, end_year, metric, support, multiplicity)
    if f is None or r is None:
        return None
    return 100 * (r - f)


def bootstrap_relative(direction, base_year, end_year, metric, support, multiplicity):
    table = forward if direction == "forward" else reverse
    base_counts = {s: multiplicity[s] * n_value(direction, cell(table, base_year, s)) for s in support}
    total = sum(base_counts.values())
    if not total:
        return None
    w = {s: base_counts[s] / total for s in support}
    start, _ = aggregate(direction, START_YEAR, metric, support, w)
    end, _ = aggregate(direction, end_year, metric, support, w)
    if start is None or end is None or start == 0:
        return None
    return end / start - 1


# Use the complete 7-source support available across all declared years.
supports = {
    "forward": common_support("forward", START_YEAR, 2024),
    "reverse": common_support("reverse", START_YEAR, 2024),
}
support = sorted(set(supports["forward"]) & set(supports["reverse"]))

matrix = {}
for base_year in BASE_YEARS:
    for end_year in END_YEARS:
        for metric in METRICS:
            key = f"{base_year}|{START_YEAR}->{end_year}|{metric}"
            matrix[key] = gap_for(base_year, end_year, metric, support)

# Leave-one-source-out sensitivity on the same support.
loo = {}
for dropped in support:
    kept = [s for s in support if s != dropped]
    for base_year in BASE_YEARS:
        for end_year in END_YEARS:
            for metric in METRICS:
                key = f"{dropped}|{base_year}|{START_YEAR}->{end_year}|{metric}"
                loo[key] = gap_for(base_year, end_year, metric, kept)

# Source-cluster bootstrap uses the same sampled source clusters for both directions.
bootstrap = {}
for base_year in BASE_YEARS:
    for end_year in END_YEARS:
        for metric in METRICS:
            rng = random.Random(SEED + base_year * 100 + end_year * 10 + len(metric))
            values = [x for _ in range(BOOTSTRAPS)
                      if (x := bootstrap_gap(base_year, end_year, metric, support, rng)) is not None]
            key = f"{base_year}|{START_YEAR}->{end_year}|{metric}"
            bootstrap[key] = {
                "n": len(values),
                "q025": percentile(values, 0.025),
                "q50": percentile(values, 0.5),
                "q975": percentile(values, 0.975),
                "positive_share": sum(v > 0 for v in values) / len(values) if values else None,
                "seed": SEED + base_year * 100 + end_year * 10 + len(metric),
                "clusters": len(support),
            }

base_gap_values = [v["gap_pp"] for v in matrix.values() if v is not None]
result = {
    "task": "bidirectional asymmetry under common merged-name source support",
    "input": "stable8_merged.json",
    "support": support,
    "support_size": len(support),
    "direction": {
        "forward": "NON_EC_to_EC",
        "reverse": "EC_to_NON_EC",
        "gap_definition": "100 * (reverse relative change - forward relative change), percentage points",
    },
    "spec": {
        "start_year": START_YEAR,
        "base_years": list(BASE_YEARS),
        "end_years": list(END_YEARS),
        "metrics": list(METRICS),
        "endpoint_truncation": {"2024": False, "2025": True},
        "support_rule": "sources present with positive paper counts in 2019, 2021, 2024 and 2025 for both directions", "required_support_years": list(REQUIRED_SUPPORT_YEARS),
        "bootstrap": "source-cluster resampling with replacement; common sampled clusters for both directions",
        "bootstrap_reps": BOOTSTRAPS,
        "seed_base": SEED,
    },
    "matrix": matrix,
    "loo": loo,
    "bootstrap": bootstrap,
    "summary": {
        "matrix_gap_min_pp": min(base_gap_values) if base_gap_values else None,
        "matrix_gap_max_pp": max(base_gap_values) if base_gap_values else None,
        "all_matrix_gaps_positive": all(x > 0 for x in base_gap_values),
        "bootstrap_all_positive_share": all(v["positive_share"] == 1.0 for v in bootstrap.values() if v["n"]),
    },
}

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

print(json.dumps({
    "support": support,
    "matrix_gap_min_pp": round(result["summary"]["matrix_gap_min_pp"], 4) if result["summary"]["matrix_gap_min_pp"] is not None else None,
    "matrix_gap_max_pp": round(result["summary"]["matrix_gap_max_pp"], 4) if result["summary"]["matrix_gap_max_pp"] is not None else None,
    "all_matrix_gaps_positive": result["summary"]["all_matrix_gaps_positive"],
    "bootstrap_all_positive_share": result["summary"]["bootstrap_all_positive_share"],
}, ensure_ascii=False, indent=1))
