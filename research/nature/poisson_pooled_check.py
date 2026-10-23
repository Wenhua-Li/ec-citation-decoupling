# -*- coding: utf-8 -*-
"""P1-9: pooled-statistic definition check for the Poisson power calibration (batch 3).

The S6.3 calibration table reports a pooled (k=4 sources) sign-error column whose
statistic was never spelled out in prose. The frozen generator (tier_calibration.py)
defines the pooled statistic as the SUM of edge counts over k=4 sources with the
baseline split equally (each source Pois(lambda0/4)); by the additive closure of
the Poisson family this sum is distributionally identical to a single Pois(lambda0)
draw, so the pooled column must equal the per-source column at the same total up
to Monte Carlo error. This script:

  1. evaluates the EXACT sign-error probability P(m1 <= m0) for
     m0 ~ Pois(lambda0), m1 ~ Pois(lambda0*(1+delta)) by direct pmf summation
     (no simulation), for every (lambda0, delta) cell that the S6.3 table reports
     in the pooled column (lambda0_total in {50, 100}, delta = 0.20), plus the
     locked-gate per-source cell (lambda0 = 100, delta = 0.20);
  2. reruns the frozen Monte Carlo estimators (per-source err_rate and pooled_err,
     k=4 equal split) at the frozen 20,000 replicates with a fresh fixed seed
     (code-internal only) and compares against both the exact values and the
     registered readings 0.0920 / 0.1772 / 0.0949.

Output: research/nature/out/poisson_pooled_check.json
Pure computation on frozen constants; the database is not touched.
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "poisson_pooled_check.json")

SEED = 20261020          # fixed seed, code-internal only
NREP = 20000             # frozen replicate count (tier_calibration.py)
K_SOURCES = 4            # frozen pooled split

# cells carried by the S6.3 table: (lambda0_total, delta, registered MC value, column)
CELLS = [
    (50, 0.20, 0.1772, "pooled k=4, delta=+20%"),
    (100, 0.20, 0.0949, "pooled k=4, delta=+20%"),
    (100, 0.20, 0.0920, "per-source, delta=+20% (locked gate)"),
]


def pois_pmf(k, lam):
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))


def exact_sign_error(lam0, delta):
    """Exact P(m1 <= m0) for independent m0~Pois(lam0), m1~Pois(lam0*(1+delta))."""
    hi = int(lam0 + 40 * math.sqrt(lam0) + 80)
    pmf0 = [pois_pmf(k, lam0) for k in range(hi + 1)]
    pmf1 = [pois_pmf(k, lam0 * (1.0 + delta)) for k in range(hi + 1)]
    cdf1 = np.cumsum(pmf1)
    return float(sum(p0 * cdf1[k] for k, p0 in enumerate(pmf0)))


def mc_per_source(lam0, delta, rng):
    m0 = rng.poisson(lam0, NREP)
    m1 = rng.poisson(lam0 * (1.0 + delta), NREP)
    return float(np.mean(m1 <= m0))


def mc_pooled(lam0_total, delta, rng):
    per = lam0_total / K_SOURCES
    m0 = rng.poisson(per, (NREP, K_SOURCES)).sum(axis=1)
    m1 = rng.poisson(per * (1.0 + delta), (NREP, K_SOURCES)).sum(axis=1)
    return float(np.mean(m1 <= m0))


def main():
    rng = np.random.default_rng(SEED)
    cells = []
    for lam0, delta, registered, label in CELLS:
        exact = exact_sign_error(lam0, delta)
        mc_pool = mc_pooled(lam0, delta, rng)
        mc_single = mc_per_source(lam0, delta, rng)
        mc_se = math.sqrt(exact * (1 - exact) / NREP)
        cells.append({
            "lambda0_total": lam0,
            "delta": delta,
            "column": label,
            "exact_sign_error": round(exact, 6),
            "mc_pooled_k4_rerun": round(mc_pool, 6),
            "mc_single_poisson_rerun": round(mc_single, 6),
            "registered_mc_value": registered,
            "mc_standard_error": round(mc_se, 6),
            "abs_diff_exact_vs_registered": round(abs(exact - registered), 6),
            "within_mc_error": abs(exact - registered) <= 3 * mc_se,
        })
        print("lam0=%d d=%.2f  exact=%.4f  pooled-rerun=%.4f  single-rerun=%.4f  registered=%.4f  %s"
              % (lam0, delta, exact, mc_pool, mc_single, registered,
                 "OK" if cells[-1]["within_mc_error"] else "MISMATCH"), flush=True)

    out = {
        "spec": {
            "statistic_definition": ("pooled statistic = SUM of edge counts over k=4 sources, "
                                     "baseline split equally (Pois(lambda0/4) each); by Poisson "
                                     "additive closure the sum is distributionally identical to a "
                                     "single Pois(lambda0) draw, so pooled and per-source columns "
                                     "at the same total coincide up to Monte Carlo error"),
            "sign_error_rule": "P(m1 <= m0) with ties conservatively counted as errors (frozen rule)",
            "replicates": NREP,
            "seed": "fresh fixed seed recorded in poisson_pooled_check.py (code-internal)",
            "exact_method": "direct Poisson pmf summation (no simulation)",
        },
        "cells": cells,
        "all_within_mc_error": all(c["within_mc_error"] for c in cells),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("saved:", OUT, flush=True)


if __name__ == "__main__":
    main()
