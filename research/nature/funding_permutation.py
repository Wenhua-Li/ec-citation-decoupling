# -*- coding: utf-8 -*-
"""P1-11: exact permutation null for the funding-agenda lag-0 correlation (batch 3).

The registered reading (Q77) is the first-difference Pearson correlation at lag 0
between the grant-funded EC subset's external-frontier theme share and the full-EC
external theme share (r = +0.926, n = 9 difference pairs, years 2017-2025 over the
2016-2025 main segment). This script recomputes the two series from the frozen
outputs (archive w8 funding_agenda.json funded_subset_share external_sum; full-EC
series = sum of the five external frontier term shares from research/nature/
out/terms.json, same construction as the frozen package), reproduces the observed
lag-0 first-difference correlation, and enumerates the COMPLETE permutation null:
all 9! = 362,880 reorderings of one differenced series against the other
(>= the pre-specified 10,000; exact enumeration removes Monte Carlo error and any
seed dependence). Reports the null mean/sd and exact one- and two-sided tail
shares for the observed r.

Read-only: parses two frozen JSON files; the database is not touched.
"""
import itertools
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
FUNDING = os.path.join(ROOT, "archive", "packages", "w8_funding", "out", "funding_agenda.json")
TERMS = os.path.join(HERE, "out", "terms.json")
OUT = os.path.join(HERE, "out", "funding_permutation.json")

EXTERNAL = ["deep learning", "reinforcement learning", "LLM/GPT", "transformer", "explainable AI"]
YEARS = list(range(2016, 2026))
REGISTERED_R = 0.926


def pearson(x, y):
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    xc = x - x.mean()
    yc = y - y.mean()
    denom = np.sqrt((xc ** 2).sum() * (yc ** 2).sum())
    return float((xc * yc).sum() / denom) if denom else np.nan


def main():
    agenda = json.load(open(FUNDING, encoding="utf-8"))
    terms = json.load(open(TERMS, encoding="utf-8"))

    funded = np.array([agenda["funded_subset_share"][str(y)]["external_sum"] for y in YEARS],
                      dtype=np.float64)
    full = np.zeros(len(YEARS))
    for name in EXTERNAL:
        for i, y in enumerate(YEARS):
            v = terms["share"][name].get(str(y), {}).get("ec")
            if v is not None:
                full[i] += v

    d_f = np.diff(funded)   # 9 difference pairs, 2017..2025
    d_g = np.diff(full)
    r_obs = pearson(d_f, d_g)
    print("first-difference pairs (n=%d):" % len(d_f))
    print("  funded diffs:", np.round(d_f, 4).tolist())
    print("  full-EC diffs:", np.round(d_g, 4).tolist())
    print("observed lag-0 first-difference r = %.4f (registered +0.926)" % r_obs, flush=True)
    assert abs(r_obs - REGISTERED_R) < 0.01, "observed r diverges from registered +0.926"

    # exact permutation null: all reorderings of d_f against fixed d_g
    perms = np.array(list(itertools.permutations(range(len(d_f)))), dtype=np.int16)
    x = d_f[perms]                                # (362880, 9)
    xc = x - x.mean(axis=1, keepdims=True)
    yc = d_g - d_g.mean()
    denom = np.sqrt((xc ** 2).sum(axis=1) * (yc ** 2).sum())
    r_null = (xc * yc).sum(axis=1) / denom
    n_perm = int(perms.shape[0])
    p_one = float((r_null >= r_obs - 1e-12).mean())
    p_two = float((np.abs(r_null) >= abs(r_obs) - 1e-12).mean())
    print("permutation null: N=%d  mean=%.4f  sd=%.4f  max=%.4f" %
          (n_perm, r_null.mean(), r_null.std(), r_null.max()), flush=True)
    print("exact one-sided P(r >= r_obs) = %.6f ; two-sided P(|r| >= |r_obs|) = %.6f"
          % (p_one, p_two), flush=True)

    out = {
        "spec": {
            "series": ("grant-funded EC subset external-frontier theme share vs full-EC external "
                       "theme share, 2016-2025 main segment; first differences (n=9 pairs); "
                       "lag 0; series rebuilt from frozen funding_agenda.json and terms.json"),
            "null_model": ("exact enumeration of all 9! = 362,880 reorderings of one differenced "
                           "series (>= pre-specified 10,000 permutations; seed-free)"),
            "interpretation": ("permutation tail for a Pearson correlation under exchangeability "
                               "of the year pairs; no causal or lead-lag claim"),
            "note": ("funded series enters at its registered 4-decimal precision; the observed r "
                     "is recomputed from those registered values"),
        },
        "n_pairs": int(len(d_f)),
        "observed_r_lag0_first_difference": round(r_obs, 4),
        "registered_r": REGISTERED_R,
        "n_permutations": n_perm,
        "null_mean": round(float(r_null.mean()), 6),
        "null_sd": round(float(r_null.std()), 6),
        "null_max": round(float(r_null.max()), 6),
        "exact_p_one_sided": round(p_one, 6),
        "exact_p_two_sided": round(p_two, 6),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("saved:", OUT, flush=True)


if __name__ == "__main__":
    main()
