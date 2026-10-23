# -*- coding: utf-8 -*-
"""P1-4: flip-share lambda under the two denominator conventions (batch 3, 2026-10-20).

The frozen tipping-point analysis (doi_bracket.py) computes the symmetric-diagonal
flip share lambda* with the E3 share written as (e_i + lambda*u_i)/(d_i + u_i):
the denominator ABSORBS all unparsed rows (consistent with the all-target
scenario bracket at lambda = 1). The S4.2 frontier sentence only states that
lambda*u_i expected target edges are added per paper, leaving the denominator
convention unspecified. This script re-solves the flip share under BOTH
conventions, per the S4.1 directional parsing-rate exposure:

  * Version A (denominator absorbs all unparsed rows; frozen pipeline):
        E3_i(lambda) = (e_i + lambda*u_i) / (d_i + u_i)
  * Version B (numerator-only assignment; denominator stays at parsed rows):
        E3_i(lambda) = (e_i + lambda*u_i) / d_i

E1 (e_i + lambda*u_i) carries no denominator and is therefore identical across
the two conventions; it is re-solved once and asserted against the frozen
0.206 registration. E3 Version A is asserted against the frozen 0.239.

Data assembly replicates doi_bracket.py verbatim (same two SELECTs, CANON/STABLE8,
support rule, fixed 2021 composition weights, row-level u_i = n_rows_all -
n_rows_doi). Grid scan at 0.001 steps with linear interpolation, along the
symmetric diagonal lambda_forward = lambda_reverse = lambda, for the primary
(2021->2024) and right-censored (2021->2025) windows.

Output: research/nature/out/flip_lambda_dual.json
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
OUT = os.path.join(HERE, "out", "flip_lambda_dual.json")
FROZEN_BRACKET = os.path.join(HERE, "out", "doi_bracket.json")

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
    return None if x is None else round(float(x), 6)


def main():
    meta = {}
    for r in ecdb.raw_sql(META_SQL, max_rows=200000)["rows"]:
        meta[r["acc"]] = (r["y"], CANON.get(r["src"], r["src"]), r["lab"])
    agg = {}
    for r in ecdb.raw_sql(REFS_SQL, max_rows=400000)["rows"]:
        agg[r["acc"]] = (int(r["n_ec"]), int(r["n_non"]), int(r["n_refs_doi"]),
                         int(r["n_rows_all"]), int(r["n_rows_doi"]))

    records = defaultdict(list)  # (direction, year, source) -> [(edges, u, d)]
    for acc, (y, src, lab) in meta.items():
        if y not in SCOPE_YEARS or src not in STABLE8:
            continue
        d = "forward" if lab == "NON_EC" else "reverse"
        n_ec, n_non, n_refs, rows_all, rows_doi = agg.get(acc, (0, 0, 0, 0, 0))
        edges = float(n_ec if d == "forward" else n_non)
        u = float(rows_all - rows_doi)
        records[(d, y, src)].append((edges, u, float(n_refs)))

    counts = Counter({k: len(v) for k, v in records.items()})
    support = sorted({s for (d, y, s) in records
                      if all(counts[(dd, yy, s)] > 0
                             for dd in DIRECTIONS for yy in (2021, 2024, 2025))})
    weights = {}
    for d in DIRECTIONS:
        n21 = [counts[(d, START_YEAR, s)] for s in support]
        tot = sum(n21)
        weights[d] = {s: n / tot for s, n in zip(support, n21)}

    def aggregate_fn(d, y, fn):
        total = 0.0
        for s in support:
            recs = records[(d, y, s)]
            total += weights[d][s] * (sum(fn(r) for r in recs) / len(recs))
        return total

    def share_e3_absorb(r, lam):     # Version A (frozen): denominator absorbs all u
        denom = r[2] + r[1]
        return (r[0] + lam * r[1]) / denom if denom else 0.0

    def share_e3_numerator(r, lam):  # Version B: numerator-only, denominator d_i
        return (r[0] + lam * r[1]) / r[2] if r[2] else 0.0

    def share_e1(r, lam):
        return r[0] + lam * r[1]

    def gap_diag(lam, Y, share):
        def rel_l(d):
            base = aggregate_fn(d, START_YEAR, lambda r: share(r, lam))
            end = aggregate_fn(d, Y, lambda r: share(r, lam))
            return end / base - 1.0 if base else None
        rf = rel_l("forward")
        rr = rel_l("reverse")
        if rf is None or rr is None:
            return None
        return 100.0 * (rr - rf)

    def solve_flip(Y, share):
        prev = (0.0, gap_diag(0.0, Y, share))
        for i in range(1, 1001):
            lam = i / 1000.0
            g = gap_diag(lam, Y, share)
            if prev[1] is not None and g is not None and prev[1] >= 0 and g < 0:
                l0, g0 = prev
                return l0 + (lam - l0) * (g0 / (g0 - g)) if g0 != g else lam
            prev = (lam, g)
        return None

    frozen = json.load(open(FROZEN_BRACKET, encoding="utf-8"))["tipping_point"]
    out = {"spec": {
        "question": ("flip share lambda* under the two readings of the S4.2 frontier sentence: "
                     "whether the E3 denominator absorbs the unparsed rows (Version A, frozen "
                     "pipeline, (e+lu)/(d+u)) or absorbs nothing (Version B, numerator-only, "
                     "(e+lu)/d)"),
        "e1_note": "E1 = e_i + lambda*u_i carries no denominator and is identical across versions",
        "grid": "symmetric diagonal, 0.001 steps, linear interpolation (frozen solver method)",
        "consistency": "Version A and E1 asserted against frozen doi_bracket.json tipping points",
    }, "windows": {}}

    for Y in WINDOW_ENDS:
        window = "2021->%d" % Y
        lam_e1 = solve_flip(Y, share_e1)
        lam_a = solve_flip(Y, share_e3_absorb)
        lam_b = solve_flip(Y, share_e3_numerator)
        fz = frozen[window]
        entry = {
            "right_censored": Y == 2025,
            "lambda_star_e1_both_versions": r6(lam_e1),
            "lambda_star_e3_versionA_denominator_absorbs": r6(lam_a),
            "lambda_star_e3_versionB_numerator_only": r6(lam_b),
            "gap_at_lambda0_pp": r6(gap_diag(0.0, Y, share_e3_absorb)),
            "frozen": {"e1": fz["diagonal_flip_lambda_e1"], "e3": fz["diagonal_flip_lambda"]},
            "consistency": {
                "e1_abs_diff": r6(abs(lam_e1 - fz["diagonal_flip_lambda_e1"])),
                "e3_versionA_abs_diff": r6(abs(lam_a - fz["diagonal_flip_lambda"])),
            },
        }
        out["windows"][window] = entry
        print("%s  E1 lambda*=%.4f (frozen %.3f) | E3 A=%.4f (frozen %.3f) | E3 B=%.4f"
              % (window, lam_e1, fz["diagonal_flip_lambda_e1"], lam_a,
                 fz["diagonal_flip_lambda"], lam_b), flush=True)
        assert entry["consistency"]["e1_abs_diff"] < 5e-3, "E1 flip diverges from frozen"
        assert entry["consistency"]["e3_versionA_abs_diff"] < 5e-3, "E3-A flip diverges from frozen"

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("saved:", OUT, flush=True)


if __name__ == "__main__":
    main()
