# -*- coding: utf-8 -*-
"""P1-3: per-source bootstrap quantiles for the bidirectional E1/E2/E3 changes (batch 3).

The frozen paper-level stratified bootstrap (paper_bootstrap_asymmetry.py) reports
pooled quantiles only. Reviewers asked for the per-source resampling spread behind
the sign scorecard. This script reruns the IDENTICAL resampling specification
(same two SELECTs, CANON/STABLE8, support rule, stratum arrays sorted by
accession, fixed 2021 composition weights, chunked vectorised resampling,
independent non-paired SeedSequence streams per direction, linear-interpolated
quantiles) and additionally records, for each of the seven common-support
sources, the resampling quantiles of the per-source relative change
mean(2024)/mean(2021)-1 (and the right-censored 2021->2025 window) for E1, E2
and E3, using the same replicate index pairing of start and end draws as the
pooled design.

Differences from the frozen run, by design: a new fixed seed (code-internal,
never cited in prose) and per-source (instead of pooled) aggregation. Pooled
quantiles from the same draws are reproduced as a consistency check against the
frozen JSON (tolerance: quantiles within 0.02 in relative-change units, since a
new seed draws different strata resamples).

Output: research/nature/out/persource_bootstrap.json
Read-only: exactly two SELECTs through ecdb.raw_sql; the database is never written.
"""
import json
import os
import sys
import time
from collections import Counter, defaultdict

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ecdb

from paper_bootstrap_asymmetry import (  # locked frozen definitions
    CANON, META_SQL, REFS_SQL, STABLE8,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "persource_bootstrap.json")
FROZEN_PAPER = os.path.join(HERE, "out", "paper_bootstrap_asymmetry.json")

SEED = 20261020                      # fixed seed, code-internal only
SEED_FORWARD = [SEED, 1]
SEED_REVERSE = [SEED, 2]
REPS = 4000
CHUNK = 1000
START_YEAR = 2021
WINDOW_ENDS = (2024, 2025)
SCOPE_YEARS = (START_YEAR, 2024, 2025)
METRICS = ("E1", "E2", "E3")
M_IDX = {m: i for i, m in enumerate(METRICS)}
DIRECTIONS = ("forward", "reverse")


def r6(x):
    return None if x is None else round(float(x), 6)


def quantiles(values):
    qs = np.quantile(values, [0.025, 0.5, 0.975])  # linear interpolation, as frozen
    return {"q025": r6(qs[0]), "q50": r6(qs[1]), "q975": r6(qs[2])}


def main():
    t0 = time.time()
    meta = {}
    for r in ecdb.raw_sql(META_SQL, max_rows=200000)["rows"]:
        meta[r["acc"]] = (r["y"], CANON.get(r["src"], r["src"]), r["lab"])
    agg = {}
    for r in ecdb.raw_sql(REFS_SQL, max_rows=300000)["rows"]:
        agg[r["acc"]] = (int(r["n_ec"]), int(r["n_non"]), int(r["n_refs_doi"]))

    records = defaultdict(list)  # (direction, year, source) -> [(acc, e1, e2, e3)]
    for acc, (y, src, lab) in meta.items():
        if y not in SCOPE_YEARS or src not in STABLE8:
            continue
        d = "forward" if lab == "NON_EC" else "reverse"
        n_ec, n_non, n_refs = agg.get(acc, (0, 0, 0))
        edges = n_ec if d == "forward" else n_non
        records[(d, y, src)].append((acc, float(edges), 1.0 if edges else 0.0,
                                     (edges / n_refs) if n_refs else 0.0))

    counts = Counter({k: len(v) for k, v in records.items()})
    support = sorted({s for (d, y, s) in records
                      if all(counts[(dd, yy, s)] > 0
                             for dd in DIRECTIONS for yy in SCOPE_YEARS)})
    print("support (%d): %s" % (len(support), support), flush=True)

    strata = {}
    for d in DIRECTIONS:
        for y in SCOPE_YEARS:
            for s in support:
                recs = sorted(records[(d, y, s)])
                strata[(d, y, s)] = np.array([[r[1], r[2], r[3]] for r in recs],
                                             dtype=np.float64)

    weights = {}
    for d in DIRECTIONS:
        n21 = [counts[(d, START_YEAR, s)] for s in support]
        tot = sum(n21)
        weights[d] = {s: n / tot for s, n in zip(support, n21)}

    # observed per-source point estimates
    obs_src = {}
    for d in DIRECTIONS:
        obs_src[d] = {}
        for s in support:
            base = strata[(d, START_YEAR, s)].mean(axis=0)
            obs_src[d][s] = {}
            for Y in WINDOW_ENDS:
                end = strata[(d, Y, s)].mean(axis=0)
                with np.errstate(divide="ignore", invalid="ignore"):
                    rel = np.where(base > 0, end / np.where(base > 0, base, 1.0) - 1.0, np.nan)
                obs_src[d][s][str(Y)] = {m: r6(rel[i]) for m, i in M_IDX.items()}

    # resampling, identical spec (independent non-paired streams per direction)
    def resample_means(rng, arr):
        n = arr.shape[0]
        out = np.empty((REPS, arr.shape[1]), dtype=np.float64)
        for lo in range(0, REPS, CHUNK):
            hi = min(lo + CHUNK, REPS)
            idx = rng.integers(0, n, size=(hi - lo, n), dtype=np.int64)
            for m in range(arr.shape[1]):
                out[lo:hi, m] = arr[idx, m].mean(axis=1)
        return out

    res = {}
    for d in DIRECTIONS:
        rng = np.random.default_rng(
            np.random.SeedSequence(SEED_FORWARD if d == "forward" else SEED_REVERSE))
        for y in SCOPE_YEARS:
            for s in support:
                res[(d, y, s)] = resample_means(rng, strata[(d, y, s)])
    print("resampling done (%.1fs)" % (time.time() - t0), flush=True)

    # per-source relative-change quantiles (same replicate index pairing)
    persource = {}
    for Y in WINDOW_ENDS:
        window = "%d->%d" % (START_YEAR, Y)
        persource[window] = {"right_censored": Y == 2025}
        for d in DIRECTIONS:
            persource[window][d] = {}
            for s in support:
                entry = {}
                for m, i in M_IDX.items():
                    base = res[(d, START_YEAR, s)][:, i]
                    end = res[(d, Y, s)][:, i]
                    with np.errstate(divide="ignore", invalid="ignore"):
                        rel = np.where(base > 0, end / np.where(base > 0, base, 1.0) - 1.0,
                                       np.nan)
                    rel = rel[np.isfinite(rel)]
                    q = quantiles(rel)
                    q["positive_share"] = r6(float((rel > 0).mean()))
                    q["observed"] = obs_src[d][s][str(Y)][m]
                    entry[m] = q
                persource[window][d][s] = entry

    # pooled aggregation from the same draws (consistency with frozen pooled run)
    boot_A = {}
    for d in DIRECTIONS:
        for y in SCOPE_YEARS:
            acc = np.zeros((REPS, 3), dtype=np.float64)
            for s in support:
                acc += weights[d][s] * res[(d, y, s)]
            boot_A[(d, y)] = acc
    pooled_check = {}
    frozen = json.load(open(FROZEN_PAPER, encoding="utf-8"))
    for Y in WINDOW_ENDS:
        window = "%d->%d" % (START_YEAR, Y)
        for m, i in M_IDX.items():
            f = boot_A[("forward", Y)][:, i] / boot_A[("forward", START_YEAR)][:, i] - 1.0
            rv = boot_A[("reverse", Y)][:, i] / boot_A[("reverse", START_YEAR)][:, i] - 1.0
            mine = quantiles(100.0 * (rv - f))
            fz = frozen["bootstrap"]["%s|%s" % (window, m)]["gap_pp"]
            pooled_check["%s|%s" % (window, m)] = {
                "mine_gap_q025_q50_q975": [mine["q025"], mine["q50"], mine["q975"]],
                "frozen_gap_q025_q50_q975": [fz["q025"], fz["q50"], fz["q975"]],
                "max_abs_diff": r6(max(abs(mine[k] - fz[k]) for k in ("q025", "q50", "q975"))),
            }
    max_diff = max(v["max_abs_diff"] for v in pooled_check.values())
    print("pooled consistency vs frozen bootstrap: max |diff| = %.4f" % max_diff, flush=True)

    out = {
        "spec": {
            "resampling": ("identical to paper_bootstrap_asymmetry.py: citing papers resampled "
                           "with replacement within direction x year x source strata at observed "
                           "sizes; %d replicates; independent non-paired streams per direction; "
                           "linear-interpolated quantiles" % REPS),
            "aggregation": "per-source relative change mean(end)/mean(start)-1 with the pooled "
                           "design's replicate index pairing; pooled gap reproduced as a "
                           "consistency check",
            "seed": "fixed seed recorded in persource_bootstrap.py (code-internal, not cited in prose)",
            "interpretation": ("quantiles of the resampling design only; not frequentist confidence "
                               "intervals; source-selection, labelling and parsing uncertainty sit "
                               "outside the resampling model"),
        },
        "support": support,
        "weights_2021": weights,
        "stratum_sizes": {"%s|%d|%s" % k: int(v.shape[0]) for k, v in sorted(strata.items())},
        "observed_per_source": obs_src,
        "per_source_quantiles": persource,
        "pooled_consistency_check": pooled_check,
        "pooled_consistency_max_abs_diff": r6(max_diff),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("saved:", OUT, flush=True)


if __name__ == "__main__":
    main()
