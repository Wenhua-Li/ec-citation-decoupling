# -*- coding: utf-8 -*-
"""P1-2: gold-standard labelling audit + label flip-noise sensitivity (batch 3, 2026-10-20).

Two deliverables, one output file (research/nature/out/gold_label_audit.json):

(1) Confusion matrix of the automated EC/NON_EC domain labels against the frozen
    200-paper hand-labelled gold sample (archive/labeling/gold_set_200.csv; judging
    rules in gold_set_README.md). Reports the 2x2 matrix, per-class precision and
    recall, and overall agreement, cross-checked against the registered 97%
    accuracy (Q33).

(2) Label flip-noise sensitivity of the headline bidirectional E1 readings.
    Symmetric independent label flips at rates pi in {0.03, 0.05, 0.10} are applied
    to every in-scope paper (EC <-> NON_EC swaps move the paper between the forward
    and reverse citing pools AND retarget its edge count). Per replicate we
    recompute the fixed-2021-weight E1 relative change 2021->2024 for both
    directions and the unpaired gap, on the frozen seven-source common support.
    Data assembly, CANON/STABLE8 canonicalization, the support rule and the fixed
    2021 composition weights replicate paper_bootstrap_asymmetry.py verbatim
    (constants imported, not copied). 2,000 replicates per rate, fixed seed
    (recorded in this file only; never cited in prose).

Consistency obligations: observed (zero-noise) point estimates must match the
frozen paper_bootstrap_asymmetry.json point_estimates within 5e-3.

Read-only: exactly two SELECTs through ecdb.raw_sql; the database is never written.
"""
import csv
import json
import os
import sys
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
OUT = os.path.join(HERE, "out", "gold_label_audit.json")
GOLD = os.path.join(ROOT, "archive", "labeling", "gold_set_200.csv")
FROZEN_PAPER = os.path.join(HERE, "out", "paper_bootstrap_asymmetry.json")

SEED_NOISE = 20261020          # fixed seed, code-internal only
REPS = 2000
FLIP_RATES = (0.03, 0.05, 0.10)
SCOPE_YEARS = (2021, 2024, 2025)
START_YEAR = 2021
END_YEAR = 2024
DIRECTIONS = ("forward", "reverse")


def r6(x):
    return None if x is None else round(float(x), 6)


def r4(x):
    return None if x is None else round(float(x), 4)


def quantiles(values):
    qs = np.quantile(values, [0.025, 0.5, 0.975])
    return {"q025": r6(qs[0]), "q50": r6(qs[1]), "q975": r6(qs[2])}


def gold_confusion():
    """2x2 confusion of corpus labels vs the frozen 200-paper gold sample."""
    rows = list(csv.DictReader(open(GOLD, encoding="utf-8-sig")))
    accs = ",".join("'%s'" % r["accession_no"] for r in rows)
    got = ecdb.raw_sql(
        "SELECT accession_no acc, label FROM paper_domain WHERE accession_no IN (%s)" % accs,
        max_rows=500,
    )["rows"]
    lab = {r["acc"]: r["label"] for r in got}
    tp = fp = fn = tn = 0
    for r in rows:
        g = "EC" if r["label"].strip() == "EC" else "NON_EC"
        c = lab.get(r["accession_no"])
        if g == "EC" and c == "EC":
            tp += 1
        elif g == "EC":
            fn += 1
        elif c == "EC":
            fp += 1
        else:
            tn += 1
    n = tp + fp + fn + tn
    strata = Counter(r["stratum"] for r in rows)
    return {
        "n": n,
        "gold_ec": tp + fn,
        "gold_non_ec": tn + fp,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": r4((tp + tn) / n),
        "precision_ec": r4(tp / (tp + fp)),
        "precision_non_ec": r4(tn / (tn + fn)),
        "recall_ec": r4(tp / (tp + fn)),
        "recall_non_ec": r4(tn / (tn + fp)),
        "strata_composition": dict(sorted(strata.items())),
        "registered_accuracy_Q33": 0.97,
        "accuracy_matches_registered": abs((tp + tn) / n - 0.97) < 5e-3,
    }


def load_strata():
    """Replicate paper_bootstrap_asymmetry.py data assembly verbatim (E1 fields)."""
    meta = {}
    for r in ecdb.raw_sql(META_SQL, max_rows=200000)["rows"]:
        meta[r["acc"]] = (r["y"], CANON.get(r["src"], r["src"]), r["lab"])
    agg = {}
    for r in ecdb.raw_sql(REFS_SQL, max_rows=300000)["rows"]:
        agg[r["acc"]] = (int(r["n_ec"]), int(r["n_non"]))
    records = defaultdict(list)  # (year, source) -> [(acc, lab, n_ec, n_non)]
    for acc, (y, src, lab) in meta.items():
        if y not in SCOPE_YEARS or src not in STABLE8:
            continue
        n_ec, n_non = agg.get(acc, (0, 0))
        records[(y, src)].append((acc, lab, float(n_ec), float(n_non)))
    counts = Counter({k: len(v) for k, v in records.items()})
    dcounts = Counter()
    for (y, s), recs in records.items():
        for _acc, lab, _e, _n in recs:
            dcounts[("forward" if lab == "NON_EC" else "reverse", y, s)] += 1
    # same rule as the frozen bootstrap: non-empty pool in every scope year,
    # both directions
    support = sorted({s for (_y, s) in records
                      if all(counts[(yy, s)] > 0 and
                             dcounts[("forward", yy, s)] > 0 and
                             dcounts[("reverse", yy, s)] > 0
                             for yy in SCOPE_YEARS)})
    # paper-level arrays per (year, source), sorted by accession (order-stable)
    strata = {}
    for y in SCOPE_YEARS:
        for s in support:
            recs = sorted(records[(y, s)])
            strata[(y, s)] = {
                "lab": np.array([1 if r[1] == "EC" else 0 for r in recs], dtype=np.int8),
                "n_ec": np.array([r[2] for r in recs], dtype=np.float64),
                "n_non": np.array([r[3] for r in recs], dtype=np.float64),
            }
    return support, strata


def e1_readings(strata, support, flips):
    """Fixed-2021-weight E1 relative changes under a flip matrix.

    flips: dict (year, source) -> bool array (True = label swapped this replicate).
    Direction assignment follows the frozen rule: forward iff (post-flip) label is
    NON_EC; edges = n_ec for forward papers, n_non for reverse papers.
    Composition weights are recomputed per replicate from the post-flip 2021 pools.
    """
    mean = {}
    npool = {}
    for d in DIRECTIONS:
        for y in SCOPE_YEARS:
            num = 0.0
            cnt = 0
            for s in support:
                st = strata[(y, s)]
                is_ec = st["lab"].astype(bool) ^ flips[(y, s)]
                if d == "forward":
                    mask = ~is_ec
                    edges = st["n_ec"]
                else:
                    mask = is_ec
                    edges = st["n_non"]
                num += float(edges[mask].sum())
                cnt += int(mask.sum())
            mean[(d, y)] = num / cnt if cnt else np.nan
            npool[(d, y)] = cnt
    w = {}
    for d in DIRECTIONS:
        tot = 0.0
        for s in support:
            st = strata[(START_YEAR, s)]
            is_ec = st["lab"].astype(bool) ^ flips[(START_YEAR, s)]
            mask = is_ec if d == "reverse" else ~is_ec
            w.setdefault(d, {})[s] = float(mask.sum())
            tot += w[d][s]
        for s in support:
            w[d][s] /= tot
    agg = {}
    for d in DIRECTIONS:
        for y in SCOPE_YEARS:
            a = 0.0
            for s in support:
                st = strata[(y, s)]
                is_ec = st["lab"].astype(bool) ^ flips[(y, s)]
                mask = is_ec if d == "reverse" else ~is_ec
                edges = st["n_non"] if d == "reverse" else st["n_ec"]
                a += w[d][s] * (float(edges[mask].mean()) if mask.any() else np.nan)
            agg[(d, y)] = a
    f = agg[("forward", END_YEAR)] / agg[("forward", START_YEAR)] - 1.0
    rv = agg[("reverse", END_YEAR)] / agg[("reverse", START_YEAR)] - 1.0
    return f, rv, 100.0 * (rv - f)


def main():
    print("[1/3] gold-standard confusion matrix ...", flush=True)
    confusion = gold_confusion()
    print("     accuracy:", confusion["accuracy"], "TP/FP/FN/TN:",
          confusion["tp"], confusion["fp"], confusion["fn"], confusion["tn"], flush=True)

    print("[2/3] loading frozen strata (same two SELECTs as the main bootstrap) ...", flush=True)
    support, strata = load_strata()
    print("     support:", support, flush=True)

    frozen = json.load(open(FROZEN_PAPER, encoding="utf-8"))
    pe = frozen["point_estimates"]["2021->2024"]["E1"]

    # zero-noise observed check (no flips anywhere)
    noflip = {k: np.zeros(v["lab"].shape, dtype=bool) for k, v in strata.items()}
    f0, r0, g0 = e1_readings(strata, support, noflip)
    checks = {
        "forward_rel_change": {"mine": r6(f0), "frozen": pe["forward_rel_change"],
                               "abs_diff": r6(abs(f0 - pe["forward_rel_change"]))},
        "reverse_rel_change": {"mine": r6(r0), "frozen": pe["reverse_rel_change"],
                               "abs_diff": r6(abs(r0 - pe["reverse_rel_change"]))},
        "gap_pp": {"mine": r6(g0), "frozen": pe["gap_pp"],
                   "abs_diff": r6(abs(g0 - pe["gap_pp"]))},
    }
    ok = max(v["abs_diff"] for v in checks.values()) < 5e-3
    print("     zero-noise check vs frozen point estimates:",
          "PASS" if ok else "FAIL", checks, flush=True)
    if not ok:
        raise SystemExit("zero-noise readings diverge from frozen point estimates")

    print("[3/3] flip-noise simulation (%d replicates x %d rates) ..." % (REPS, len(FLIP_RATES)),
          flush=True)
    rng = np.random.default_rng(SEED_NOISE)
    noise = {}
    for pi in FLIP_RATES:
        fwd = np.empty(REPS)
        rev = np.empty(REPS)
        gap = np.empty(REPS)
        for rep in range(REPS):
            flips = {k: rng.random(v["lab"].shape) < pi for k, v in strata.items()}
            fwd[rep], rev[rep], gap[rep] = e1_readings(strata, support, flips)
        noise[str(pi)] = {
            "flip_rate": pi,
            "n_reps": REPS,
            "forward_rel_change": quantiles(fwd),
            "reverse_rel_change": quantiles(rev),
            "gap_pp": quantiles(gap),
            "gap_positive_share": r6(float((gap > 0).mean())),
            "forward_positive_share": r6(float((fwd > 0).mean())),
            "reverse_positive_share": r6(float((rev > 0).mean())),
            "median_gap_retention_vs_observed": r4(float(np.median(gap) / g0)),
        }
        print("     pi=%.2f  gap q50=%.2fpp  P(gap>0)=%.3f  fwd q50=%.4f"
              % (pi, np.median(gap), float((gap > 0).mean()), np.median(fwd)), flush=True)

    out = {
        "spec": {
            "gold_sample": "archive/labeling/gold_set_200.csv (frozen 200-paper hand-labelled audit; "
                           "rules in gold_set_README.md)",
            "noise_model": "symmetric independent EC<->NON_EC label flips at rate pi; flipped papers "
                           "move pools and retarget edges; composition weights recomputed per replicate "
                           "at the 2021 baseline; frozen seven-source common support retained",
            "windows": "2021->2024 primary window, E1 edge-count estimand",
            "replicates": REPS,
            "seed": "fixed seed recorded in gold_label_audit.py (code-internal, not cited in prose)",
            "scope": "sensitivity of the headline bidirectional E1 readings to hypothetical label "
                     "noise; NOT a bias correction of any headline estimate",
        },
        "gold_confusion": confusion,
        "zero_noise_consistency": checks,
        "flip_noise": noise,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("saved:", OUT, flush=True)


if __name__ == "__main__":
    main()
