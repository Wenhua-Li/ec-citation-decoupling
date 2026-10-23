# -*- coding: utf-8 -*-
"""Extreme-assumption bracket for the DOI parsing exposure (Phase B, 2026-10-17).

Why this file exists
--------------------
The DOI row-level resolution rate differs between the two pools and moves with the
gap (forward 0.634 -> 0.609, reverse 0.700 -> 0.744, 2019-2025; registered in
asymmetry_sensitivity.json). The standing discipline is "no correction, no bound"
because missing DOIs are not missing at random. Reviewers will still ask: how large
could the bias be at the extreme? This script answers with a worst-case BRACKET --
not a correction: every reference row without a DOI is assigned, in turn, entirely
to the target domain or entirely outside it, and the E3 gap is recomputed under each
extreme. Nothing here re-weights or imputes the headline estimates; the bracket only
delimits how far the observables could move under the worst admissible assignment.

Locked definitions (identical to the main paper-level analysis):
  * CANON / STABLE8 and the two extraction SELECTs follow
    paper_bootstrap_asymmetry.py / asymmetry_sensitivity.py (imported constants);
  * support rule = sources with a non-empty paper pool in 2021/2024/2025 in BOTH
    directions (empirically the registered 7-source common support);
  * fixed 2021 composition weights per direction over the support;
  * E3 = mean per-paper share of DOI-resolved references pointing at the target;
    zero-DOI-reference papers contribute 0.0;
  * gap_pp = 100 * (reverse relative change - forward relative change).

Bracket construction (per citing paper i, direction d, year y):
  * u_i = n_rows_all - n_rows_doi   (reference rows without a DOI; ROW-level, so
    duplicate unresolved rows make the bracket conservative/outer);
  * e3_obs = edges / n_refs_doi          (headline estimand)
  * e3_lo  = edges / (n_refs_doi + u)    (all unresolved rows are NON-target)
  * e3_hi  = (edges + u) / (n_refs_doi + u)  (all unresolved rows are target,
    each a distinct in-scope work -- the upper extreme)
  Diagnostics for E1/E2 (crude outer bounds): e1_hi = edges + u;
  e2_hi = 1 iff edges >= 1 or u >= 1.

Reported brackets:
  * scenario brackets (same assumption in both years of a window):
    all-non-target (lo/lo) and all-target (hi/hi);
  * worst-case gap bounds (year-independent extremes):
    gap_min = 100 * (reverse_rel_min - forward_rel_max),
    gap_max = 100 * (reverse_rel_max - forward_rel_min),
    where rel_max uses hi at the endpoint over lo at the start, and vice versa.

Consistency obligations (checked against locked outputs, tolerance 5e-3 in
relative-change units): (a) pooled doi_row_rate by direction/year vs
asymmetry_sensitivity.json; (b) e3_obs relative changes vs
paper_bootstrap_asymmetry.json point_estimates for 2021->2024 E3.

Read-only: exactly two SELECTs through ecdb.raw_sql; the database is never written.
"""
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ecdb

from paper_bootstrap_asymmetry import CANON, STABLE8  # locked frozen definitions

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "doi_bracket.json")
FROZEN_SENS = os.path.join(HERE, "out", "asymmetry_sensitivity.json")
FROZEN_PAPER = os.path.join(HERE, "out", "paper_bootstrap_asymmetry.json")

SCOPE_YEARS = (2019, 2021, 2024, 2025)
START_YEAR = 2021
WINDOW_ENDS = (2024, 2025)
DIRECTIONS = ("forward", "reverse")

META_SQL = (
    "SELECT p.accession_no AS acc, p.pub_year AS y, p.source AS src, "
    "d.label AS lab "
    "FROM papers p JOIN paper_domain d ON d.accession_no = p.accession_no"
)
REFS_SQL = (
    "SELECT r.accession_no AS acc, "
    "COUNT(DISTINCT CASE WHEN d.label='EC' THEN pc.accession_no END) AS n_ec, "
    "COUNT(DISTINCT CASE WHEN d.label='NON_EC' THEN pc.accession_no END) AS n_non, "
    "COUNT(DISTINCT r.cited_doi) AS n_refs_doi, "
    "COUNT(*) AS n_rows_all, "
    "COUNT(r.cited_doi) AS n_rows_doi "
    "FROM paper_refs_out r "
    "LEFT JOIN papers pc ON pc.doi = r.cited_doi "
    "LEFT JOIN paper_domain d ON d.accession_no = pc.accession_no "
    "GROUP BY r.accession_no"
)


def r6(x):
    return round(float(x), 6) if x is not None else None


def main():
    # ---- query 1: meta -------------------------------------------------------
    meta = {}
    for r in ecdb.raw_sql(META_SQL, max_rows=200000)["rows"]:
        meta[r["acc"]] = (r["y"], CANON.get(r["src"], r["src"]), r["lab"])
    # ---- query 2: per-paper reference aggregates -----------------------------
    agg = {}
    for r in ecdb.raw_sql(REFS_SQL, max_rows=400000)["rows"]:
        agg[r["acc"]] = (int(r["n_ec"]), int(r["n_non"]), int(r["n_refs_doi"]),
                         int(r["n_rows_all"]), int(r["n_rows_doi"]))

    # ---- per-paper records with bracket shares -------------------------------
    records = defaultdict(list)  # (direction, year, source) -> [per-paper tuple]
    for acc, (y, src, lab) in meta.items():
        if y not in SCOPE_YEARS or src not in STABLE8:
            continue
        d = "forward" if lab == "NON_EC" else "reverse"
        n_ec, n_non, n_refs, rows_all, rows_doi = agg.get(acc, (0, 0, 0, 0, 0))
        edges = float(n_ec if d == "forward" else n_non)
        u = float(rows_all - rows_doi)
        denom = n_refs + u
        e3_obs = edges / n_refs if n_refs else 0.0
        e3_lo = edges / denom if denom else 0.0
        e3_hi = (edges + u) / denom if denom else 0.0
        records[(d, y, src)].append((e3_obs, e3_lo, e3_hi, edges, 1.0 if edges else 0.0,
                                     u, float(n_refs), float(rows_all), float(rows_doi)))

    counts = Counter({k: len(v) for k, v in records.items()})
    support = sorted({s for (d, y, s) in records
                      if all(counts[(dd, yy, s)] > 0
                             for dd in DIRECTIONS for yy in (2021, 2024, 2025))})

    # fixed 2021 composition weights per direction (main spec)
    weights = {}
    for d in DIRECTIONS:
        n21 = [counts[(d, START_YEAR, s)] for s in support]
        tot = sum(n21)
        weights[d] = {s: n / tot for s, n in zip(support, n21)}

    def aggregate(d, y, col):
        """Fixed-2021-weight mean of per-paper quantity `col` over the support."""
        total = 0.0
        for s in support:
            recs = records[(d, y, s)]
            total += weights[d][s] * (sum(r[col] for r in recs) / len(recs))
        return total

    def rel(series, y):
        return series[y] / series[START_YEAR] - 1.0

    years = (2021, 2024, 2025)
    E3 = {"obs": 0, "lo": 1, "hi": 2}
    out = {"support": support, "weights": weights, "series": {}, "gap": {}}
    for d in DIRECTIONS:
        out["series"][d] = {}
        for name, col in E3.items():
            out["series"][d][name] = {str(y): r6(aggregate(d, y, col)) for y in years}

    # consistency checks vs locked outputs
    sens = json.load(open(FROZEN_SENS, encoding="utf-8"))
    paper = json.load(open(FROZEN_PAPER, encoding="utf-8"))
    checks = {"doi_row_rate": {}, "e3_obs_rel_change": {}}
    for d in DIRECTIONS:
        for y in SCOPE_YEARS:
            recs = [r for (dd, yy, s), lst in records.items() if dd == d and yy == y and s in support
                    for r in lst]
            rows_all = sum(r[7] for r in recs)
            rows_doi = sum(r[8] for r in recs)
            mine = rows_doi / rows_all if rows_all else None
            frozen = sens["s5_reference_doi_diagnostics"][
                "pooled_by_direction_year_support_only"][f"{d}|{y}"]["doi_row_rate"]
            checks["doi_row_rate"][f"{d}|{y}"] = {"mine": r6(mine), "frozen": frozen,
                                                  "abs_diff": r6(abs(mine - frozen))}
    pe = paper["point_estimates"]["2021->2024"]["E3"]
    for d in DIRECTIONS:
        mine = rel({y: aggregate(d, y, 0) for y in years}, 2024)
        frozen = pe["forward_rel_change" if d == "forward" else "reverse_rel_change"]
        checks["e3_obs_rel_change"][d] = {"mine": r6(mine), "frozen": frozen,
                                          "abs_diff": r6(abs(mine - frozen))}
    out["consistency_checks"] = checks

    # gap brackets
    for Y in WINDOW_ENDS:
        rels = {}
        for d in DIRECTIONS:
            for name in E3:
                rels[(d, name)] = rel({y: aggregate(d, y, E3[name]) for y in years}, Y)
        obs_gap = 100.0 * (rels[("reverse", "obs")] - rels[("forward", "obs")])
        scenario_lo = 100.0 * (rels[("reverse", "lo")] - rels[("forward", "lo")])
        scenario_hi = 100.0 * (rels[("reverse", "hi")] - rels[("forward", "hi")])
        f_max = {y: aggregate("forward", y, 2) for y in years}[Y] / \
                {y: aggregate("forward", y, 1) for y in years}[START_YEAR] - 1.0
        f_min = {y: aggregate("forward", y, 1) for y in years}[Y] / \
                {y: aggregate("forward", y, 2) for y in years}[START_YEAR] - 1.0
        r_max = {y: aggregate("reverse", y, 2) for y in years}[Y] / \
                {y: aggregate("reverse", y, 1) for y in years}[START_YEAR] - 1.0
        r_min = {y: aggregate("reverse", y, 1) for y in years}[Y] / \
                {y: aggregate("reverse", y, 2) for y in years}[START_YEAR] - 1.0
        out["gap"][f"2021->{Y}"] = {
            "right_censored": Y == 2025,
            "gap_observed_pp": r6(obs_gap),
            "gap_scenario_all_nontarget_pp": r6(scenario_lo),
            "gap_scenario_all_target_pp": r6(scenario_hi),
            "gap_worstcase_min_pp": r6(100.0 * (r_min - f_max)),
            "gap_worstcase_max_pp": r6(100.0 * (r_max - f_min)),
            "forward_rel_obs": r6(rels[("forward", "obs")]),
            "reverse_rel_obs": r6(rels[("reverse", "obs")]),
            "forward_rel_range": [r6(f_min), r6(f_max)],
            "reverse_rel_range": [r6(r_min), r6(r_max)],
        }

    # crude E1/E2 outer-bound diagnostics (row-level; reported as diagnostics only)
    def aggregate_fn(d, y, fn):
        total = 0.0
        for s in support:
            recs = records[(d, y, s)]
            total += weights[d][s] * (sum(fn(r) for r in recs) / len(recs))
        return total

    e_diag = {}
    for Y in WINDOW_ENDS:
        entry = {}
        for d in DIRECTIONS:
            e1_obs = {y: aggregate(d, y, 3) for y in years}
            e1_hi = {y: aggregate_fn(d, y, lambda r: r[3] + r[5]) for y in years}
            e2_obs = {y: aggregate(d, y, 4) for y in years}
            e2_hi = {y: aggregate_fn(d, y, lambda r: 1.0 if (r[3] >= 1 or r[5] > 0) else 0.0)
                     for y in years}
            entry[d] = {
                "e1_rel_obs": r6(rel(e1_obs, Y)),
                "e1_rel_hi": r6(rel(e1_hi, Y)),
                "e2_rel_obs": r6(rel(e2_obs, Y)),
                "e2_rel_hi": r6(rel(e2_hi, Y)),
            }
        e_diag[f"2021->{Y}"] = entry
    out["e1_e2_outer_bound_diagnostics"] = e_diag

    # tipping-point analysis: share lambda of unresolved rows assigned to the target.
    # Diagonal lambda_f = lambda_r = lambda scan + 2D break-even frontier (E3).
    def gap_under_lambda(lf, lr, Y, metric="E3"):
        def share(r, lam):
            if metric == "E3":
                denom = r[6] + r[5]
                return (r[3] + lam * r[5]) / denom if denom else 0.0
            if metric == "E1":
                return r[3] + lam * r[5]
            return 1.0 if (r[3] >= 1 or lam * r[5] >= 1.0) else 0.0  # E2: lambda*u >= 1 means >= 1 edge

        def rel_l(d, lam):
            base = aggregate_fn(d, START_YEAR, lambda r: share(r, lam))
            end = aggregate_fn(d, Y, lambda r: share(r, lam))
            return end / base - 1.0 if base else None

        rf = rel_l("forward", lf)
        rr = rel_l("reverse", lr)
        if rf is None or rr is None:
            return None
        return 100.0 * (rr - rf)

    tipping = {}
    for Y in WINDOW_ENDS:
        grid = [i / 100.0 for i in range(0, 101)]
        diag_gaps = [(lam, gap_under_lambda(lam, lam, Y)) for lam in grid]
        flip_lambda = None
        for i in range(1, len(diag_gaps)):
            if diag_gaps[i - 1][1] >= 0 and diag_gaps[i][1] < 0:
                l0, g0 = diag_gaps[i - 1]
                l1, g1 = diag_gaps[i]
                flip_lambda = l0 + (l1 - l0) * (g0 / (g0 - g1)) if g0 != g1 else l1
                break
        # 2D break-even: for each lf, find lr that zeroes the gap (linear interp)
        frontier = []
        for lf in [i / 20.0 for i in range(0, 21)]:
            prev = None
            found = None
            for lr in grid:
                g = gap_under_lambda(lf, lr, Y)
                if prev is not None and prev[1] >= 0 and g < 0:
                    l0, g0 = prev
                    found = l0 + (lr - l0) * (g0 / (g0 - g)) if g0 != g else lr
                    break
                prev = (lr, g)
            frontier.append({"lambda_forward": lf, "lambda_reverse_breakeven": r6(found) if found is not None else None})
        tipping[f"2021->{Y}"] = {
            "diagonal_flip_lambda": r6(flip_lambda) if flip_lambda is not None else None,
            "diagonal_gap_at_lambda_0_pp": r6(diag_gaps[0][1]),
            "diagonal_gap_at_lambda_1_pp": r6(diag_gaps[-1][1]),
            "frontier": frontier,
        }
    # diagonal flip for E1 / E2 (coarser grid; bounds are cruder at row level)
    for metric in ("E1", "E2"):
        for Y in WINDOW_ENDS:
            flip = None
            prev = (0.0, gap_under_lambda(0.0, 0.0, Y, metric))
            for i in range(1, 101):
                lam = i / 100.0
                g = gap_under_lambda(lam, lam, Y, metric)
                if prev[1] is not None and g is not None and prev[1] >= 0 and g < 0:
                    l0, g0 = prev
                    flip = l0 + (lam - l0) * (g0 / (g0 - g)) if g0 != g else lam
                    break
                prev = (lam, g)
            tipping[f"2021->{Y}"][f"diagonal_flip_lambda_{metric.lower()}"] = r6(flip) if flip is not None else None
    out["tipping_point"] = tipping

    out["spec"] = {
        "support_rule": "non-empty paper pool in 2021/2024/2025 in both directions (registered 7-source common support)",
        "weights": "fixed 2021 composition weights per direction (main spec)",
        "bracket_level": "reference ROW level (unresolved rows = n_rows_all - n_rows_doi); conservative/outer",
        "queries": "exactly two SELECTs via ecdb.raw_sql (read-only URI); no writes",
        "interpretation": ("worst-case bracket on the observables under extreme assignments of "
                           "unresolved references; NOT a correction, imputation or re-weighting of "
                           "the headline estimates"),
        "tipping_point_semantics": ("lambda = share of unresolved reference rows assigned to the "
                                    "target domain; E1/E3 use lambda*u continuously; E2 uses a "
                                    "per-paper threshold (a paper gains a target edge iff "
                                    "lambda*u >= 1), so the E2 flip point is stated in threshold "
                                    "semantics and is not directly comparable to E1/E3"),
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print(json.dumps({
        "support": support,
        "gap_2021_2024": out["gap"]["2021->2024"],
        "checks_max_abs_diff": {
            "doi_row_rate": max(v["abs_diff"] for v in checks["doi_row_rate"].values()),
            "e3_obs_rel_change": max(v["abs_diff"] for v in checks["e3_obs_rel_change"].values()),
        },
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
