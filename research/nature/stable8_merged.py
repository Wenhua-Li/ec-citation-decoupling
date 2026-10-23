# -*- coding: utf-8 -*-
"""Stage 0 task 0-6: stable-set recomputation under the merged journal name.

D0 review (2026-10-15) established that the frozen eight-name list carried a
source-title variant: "Applied Soft Computing Journal" (2002-2020) and
"Applied Soft Computing" (2015-2025) are the same Elsevier journal (all DOIs
under 10.1016/j.asoc.*, legacy prefix s1568-494* = ISSN 1568-4946), and that
Computers and Industrial Engineering coverage ends after 2021 (collection
side).  This script canonicalises the name and recomputes the cross-field
series under two registered scopes:

  S2 double-end (the registered -48% spec, r3b_dims.py): citing NON_EC and
     cited EC papers BOTH restricted to the merged stable set.
  S1 single-end anchor (the estimators.py stable8 spec): citing NON_EC in
     the merged set, cited = all in-corpus EC.  E1/E2/E3 reported.

For each scope and endpoint year Y in {2024, 2025} a same-support variant
restricts sources to those present in BOTH 2021 and Y (canonical names) and
recomputes the 2021 base on that intersection, with 2021 weights frozen
within it.  Old frozen outputs (checks.json / estimators.json /
c2_composition_sensitivity.json) are NOT touched.

Completion pass (2026-10-15, plan step 1) -- all additive, no existing field
value or name changes:
  * per_source_e1_reverse cells carry E2_to_non / E3_to_non plus the raw
    denominators (n_edges_to_non, n_participating, n_refs, sum_share_of_refs),
    so E1/E2/E3 are reproducible from the cell alone.
  * s1_reverse_full carries E2_participation / E3_mean_share_of_refs.
  * same_support_reverse gains an explicit pooled block covering E1/E2/E3
    (the fixed-2021-weights block already covered all three).
  * baseline_table calls extended to the 2025 endpoint (1925/2125/2425 keys,
    forward and reverse); every baseline row now reports weight_sum (base
    weight usable at both endpoints) and coverage_share (base weight retained
    inside the compared support vs the base year's full set), so support loss
    cannot happen silently.
  * top-level endpoint_censoring marker: 2025 is the final collection year
    (right censoring), so every 2025-endpoint ratio mixes trend with
    truncation and must be read next to its 2024 counterpart.

Output: research/nature/out/stable8_merged.json
"""
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ecdb

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "stable8_merged.json")

CANON = {
    "Applied Soft Computing Journal": "Applied Soft Computing",  # same journal, EI title variant
    "Information sciences": "Information Sciences",              # case variant, 99 papers, year 2000 only
    "Computers & Operations Research": "Computers and Operations Research",  # ampersand variant, 1 paper, 2000
}
STABLE8 = {
    "Applied Soft Computing",
    "Computers and Industrial Engineering",
    "Computers and Operations Research",
    "Engineering Applications of Artificial Intelligence",
    "European Journal of Operational Research",
    "Expert Systems with Applications",
    "IEEE Transactions on Fuzzy Systems",
    "Information Sciences",
}

meta = {}
for r in ecdb.raw_sql(
    "SELECT accession_no acc, pub_year y, source src, "
    "(SELECT label FROM paper_domain d WHERE d.accession_no=p.accession_no) lab "
    "FROM papers p",
    max_rows=200000,
)["rows"]:
    src = CANON.get(r["src"], r["src"])
    meta[r["acc"]] = (r["y"], src, r["lab"])

print("counting edges to EC and to NON_EC ...", flush=True)
def cross_edges(target_label: str) -> Counter:
    rows = ecdb.raw_sql(
        f"""
        SELECT r.accession_no acc, COUNT(DISTINCT pc.accession_no) n
        FROM paper_refs_out r
        JOIN papers pc ON pc.doi=r.cited_doi
        JOIN paper_domain dc ON dc.accession_no=pc.accession_no
        WHERE dc.label='{target_label}'
        GROUP BY 1
        """,
        max_rows=3000000,
    )["rows"]
    return Counter({r["acc"]: r["n"] for r in rows})

to_ec_all = cross_edges("EC")
to_non_all = cross_edges("NON_EC")

# within-set edges for the double-end scope (both endpoints in the set)
within = Counter()
for r in ecdb.raw_sql(
    "SELECT DISTINCT r.accession_no acc, pc.accession_no cited "
    "FROM paper_refs_out r JOIN papers pc ON pc.doi=r.cited_doi",
    max_rows=3000000,
)["rows"]:
    a, c = r["acc"], r["cited"]
    if a in meta and c in meta:
        ya, sa, la = meta[a]
        _, sc, lc = meta[c]
        if sa in STABLE8 and sc in STABLE8 and la != lc:
            key = (ya, "NON_to_EC" if la == "NON_EC" else "EC_to_NON")
            within[key] += 1

tot_refs = {}
for r in ecdb.raw_sql(
    "SELECT accession_no acc, COUNT(DISTINCT cited_doi) n FROM paper_refs_out "
    "WHERE cited_doi IS NOT NULL GROUP BY 1",
    max_rows=300000,
)["rows"]:
    tot_refs[r["acc"]] = r["n"]

def in_set(label, src):
    return src in STABLE8

# per-year aggregates
s1 = defaultdict(lambda: [0, 0, 0, 0.0])   # n, n_part, sum_edges, sum_share  (NON in set -> all EC)
s2 = defaultdict(lambda: [0, 0])           # n_non, edges_non_to_ec_in_set
per_source = defaultdict(lambda: [0, 0, 0, 0.0])  # (year, src) -> [n_non, sum_edges, n_part, sum_share]
set_ec = defaultdict(int)                  # year -> n EC in set (S2 denominator context)
for acc, (y, src, lab) in meta.items():
    if not y or not (2005 <= y <= 2025) or src not in STABLE8:
        continue
    if lab == "NON_EC":
        e = to_ec_all.get(acc, 0)
        tr = tot_refs.get(acc, 0)
        c = s1[y]
        c[0] += 1
        c[1] += 1 if e else 0
        c[2] += e
        c[3] += (e / tr) if tr else 0.0
        ps = per_source[(y, src)]
        ps[0] += 1
        ps[1] += e
        ps[2] += 1 if e else 0
        ps[3] += (e / tr) if tr else 0.0
        s2[y][0] += 1
        s2[y][1] += within.get((y, "NON_to_EC"), 0) if False else 0
    elif lab == "EC":
        set_ec[y] += 1
# fill S2 edges from the within-set counter
for (y, k), n in within.items():
    if k == "NON_to_EC":
        s2[y][1] += n

def series_s1():
    return {str(y): {
        "n": c[0],
        "E1_mean_edges": round(c[2] / c[0], 6),
        "E2_participation": round(c[1] / c[0], 6),
        "E3_mean_share_of_refs": round(c[3] / c[0], 6),
    } for y, c in sorted(s1.items())}

def series_s2():
    return {str(y): {
        "n_non": c[0],
        "E1_within_set_edges_per_non_paper": round(c[1] / c[0], 6) if c[0] else None,
        "edges_within_set": c[1],
    } for y, c in sorted(s2.items())}

def same_support_s1(end_year):
    # sources present in both 2021 and end_year
    srcs_2021 = {s for (y, s) in per_source if y == 2021 and per_source[(y, s)][0] > 0}
    srcs_end = {s for (y, s) in per_source if y == end_year and per_source[(y, s)][0] > 0}
    inter = srcs_2021 & srcs_end
    def weighted(year):
        cells = {s: per_source[(year, s)] for s in inter if (year, s) in per_source}
        tot = sum(c[0] for c in cells.values())
        if not tot:
            return None, 0
        return sum(c[1] for c in cells.values()) / tot, tot  # pooled E1 over intersection
    # fixed 2021 weights within the intersection (weights = share of NON papers)
    base_cells = {s: per_source[(2021, s)][0] for s in inter}
    base_tot = sum(base_cells.values())
    w = {s: n / base_tot for s, n in base_cells.items()}
    def fixedw(year, col):
        # col: 1 = sum edges (E1), 2 = participants (E2), 3 = sum shares (E3)
        val, cov = 0.0, 0.0
        for s, ws in w.items():
            cell = per_source.get((year, s))
            if cell and cell[0] > 0:
                val += ws * (cell[col] / cell[0])
                cov += ws
        return (val / cov if cov else None), cov
    b21, _ = weighted(2021)
    e_end, _ = weighted(end_year)
    out = {
        "intersection_sources": sorted(inter),
        "n_intersection": len(inter),
        "pooled": {
            "E1_2021": round(b21, 6), f"E1_{end_year}": round(e_end, 6) if e_end else None,
            "rel_change": round(e_end / b21 - 1, 4) if (e_end and b21) else None,
        },
        "fixed_2021_weights": {},
    }
    for name, col in (("E1", 1), ("E2", 2), ("E3", 3)):
        b, _ = fixedw(2021, col)
        e_endw, cov = fixedw(end_year, col)
        out["fixed_2021_weights"][name] = {
            "2021": round(b, 6) if b else None,
            str(end_year): round(e_endw, 6) if e_endw else None,
            "rel_change": round(e_endw / b - 1, 4) if (e_endw and b) else None,
        }
        if name == "E1":
            out["fixed_2021_weights"]["coverage_share"] = round(cov, 6)
    return out

result = {
    "task": "0-6 merged-name stable-set recomputation",
    "merge_evidence": "ASCJ/ASC same journal: all DOIs 10.1016/j.asoc.*, legacy s1568-494* = ISSN 1568-4946; dual strings overlap 2015-2020; C&IE coverage ends 2021 (collection side)",
    "s1_single_end_anchor": series_s1(),
    "s2_double_end": series_s2(),
    "same_support": {str(y): same_support_s1(y) for y in (2024, 2025)},
    "per_source_e1": {f"{y}|{s}": {"n_non": c[0], "E1": round(c[1] / c[0], 6),
                                    "E2": round(c[2] / c[0], 6), "E3": round(c[3] / c[0], 6)}
                      for (y, s), c in sorted(per_source.items())},
}

# --- reverse direction (EC in set -> all in-corpus NON_EC), same ladder --------
# cell = [n_ec, sum_edges_to_non, n_participating, sum_share_of_refs, n_refs]
# n_refs = sum of the distinct-reference counts over the cell's EC papers, i.e.
# the reference denominator behind E3 (papers without references count 0 on
# both sides); the raw counters make E1/E2/E3 reproducible from the cell alone.
per_source_rev = defaultdict(lambda: [0, 0, 0, 0.0, 0])
for acc, (y, src, lab) in meta.items():
    if not y or not (2005 <= y <= 2025) or src not in STABLE8 or lab != "EC":
        continue
    e = to_non_all.get(acc, 0)
    tr = tot_refs.get(acc, 0)
    c = per_source_rev[(y, src)]
    c[0] += 1
    c[1] += e
    c[2] += 1 if e else 0
    c[3] += (e / tr) if tr else 0.0
    c[4] += tr

def same_support_rev(end_year):
    srcs_2021 = {s for (y, s) in per_source_rev if y == 2021 and per_source_rev[(y, s)][0] > 0}
    srcs_end = {s for (y, s) in per_source_rev if y == end_year and per_source_rev[(y, s)][0] > 0}
    inter = srcs_2021 & srcs_end
    base_cells = {s: per_source_rev[(2021, s)][0] for s in inter}
    base_tot = sum(base_cells.values())
    if not base_tot:
        return None
    w = {s: n / base_tot for s, n in base_cells.items()}
    def pooled(year, col):
        # pooled (unweighted) mean over the intersection support; col picks the
        # per-paper quantity: 1 = edges (E1), 2 = participation (E2), 3 = share (E3)
        cells = {s: per_source_rev[(year, s)] for s in inter if (year, s) in per_source_rev}
        tot = sum(c[0] for c in cells.values())
        if not tot:
            return None, 0
        return sum(c[col] for c in cells.values()) / tot, tot
    def fixedw(year, col, div):
        # col: 1 = sum edges (E1), 2 = participants (E2), 3 = sum shares (E3); div by n (col 0)
        val, cov = 0.0, 0.0
        for s, ws in w.items():
            cell = per_source_rev.get((year, s))
            if cell and cell[0] > 0:
                val += ws * (cell[col] / cell[0] if div else cell[col])
                cov += ws
        return (val / cov if cov else None), cov
    out = {"intersection_sources": sorted(inter), "pooled": {}, "fixed_2021_weights": {}}
    for name, col in (("E1", 1), ("E2", 2), ("E3", 3)):
        b, n21 = pooled(2021, col)
        e_endp, n_endp = pooled(end_year, col)
        out["pooled"][name] = {
            "2021": round(b, 6) if b is not None else None,
            str(end_year): round(e_endp, 6) if e_endp is not None else None,
            "rel_change": round(e_endp / b - 1, 4) if (e_endp and b) else None,
            "n_2021": n21, f"n_{end_year}": n_endp,
        }
    for name, col, div in (("E1", 1, True), ("E2", 2, True), ("E3", 3, True)):
        b, _ = fixedw(2021, col, div)
        e_end, cov = fixedw(end_year, col, div)
        out["fixed_2021_weights"][name] = {
            "2021": round(b, 6) if b else None,
            str(end_year): round(e_end, 6) if e_end else None,
            "rel_change": round(e_end / b - 1, 4) if (e_end and b) else None,
        }
        if name == "E1":
            out["fixed_2021_weights"]["coverage_share"] = round(cov, 6)
    return out

s1_rev = defaultdict(lambda: [0, 0, 0, 0.0])   # n_ec, sum_edges, n_part, sum_share
for acc, (y, src, lab) in meta.items():
    if not y or not (2005 <= y <= 2025) or src not in STABLE8 or lab != "EC":
        continue
    e = to_non_all.get(acc, 0)
    tr = tot_refs.get(acc, 0)
    c = s1_rev[y]
    c[0] += 1
    c[1] += e
    c[2] += 1 if e else 0
    c[3] += (e / tr) if tr else 0.0

result["s1_reverse_full"] = {str(y): {
    "n_ec": c[0],
    "E1_mean_edges_to_non": round(c[1] / c[0], 6),
    "E2_participation": round(c[2] / c[0], 6),
    "E3_mean_share_of_refs": round(c[3] / c[0], 6),
} for y, c in sorted(s1_rev.items())}
result["same_support_reverse"] = {str(y): same_support_rev(y) for y in (2024, 2025)}
result["per_source_e1_reverse"] = {f"{y}|{s}": {
    "n_ec": c[0],
    "n_refs": c[4],
    "n_edges_to_non": c[1],
    "E1_to_non": round(c[1] / c[0], 6),
    "n_participating": c[2],
    "E2_to_non": round(c[2] / c[0], 6),
    "sum_share_of_refs": c[3],   # full precision: round(sum/n_ec, 6) must reproduce E3_to_non
    "E3_to_non": round(c[3] / c[0], 6),
} for (y, s), c in sorted(per_source_rev.items())}

# --- full-series fixed-composition ladder (constant 7-source support) ---------
# Weights = 2021 composition over the 2021∩2024 intersection (the 7 sources
# continuously present); per year, weights renormalised over available sources
# with coverage reported.  Columns: 1=E1 edges, 2=E2 participation, 3=E3 share.
def fixed_series(ps):
    years = sorted({y for (y, s) in ps})
    inter = sorted({s for (y, s) in ps if y == 2021 and ps[(y, s)][0] > 0}
                   & {s for (y, s) in ps if y == 2024 and ps[(y, s)][0] > 0})
    base = {s: ps[(2021, s)][0] for s in inter if (2021, s) in ps}
    tot = sum(base.values())
    w = {s: n / tot for s, n in base.items()}
    out = {"sources": inter, "weights_2021": {s: round(v, 6) for s, v in w.items()}, "series": {}}
    for y in years:
        if not (2005 <= y <= 2025):
            continue
        row = {"n": sum(ps[(y, s)][0] for s in inter if (y, s) in ps)}
        for name, col in (("E1", 1), ("E2", 2), ("E3", 3)):
            val, cov = 0.0, 0.0
            for s, ws in w.items():
                cell = ps.get((y, s))
                if cell and cell[0] > 0:
                    val += ws * (cell[col] / cell[0])
                    cov += ws
            row[name] = round(val / cov, 6) if cov else None
            if name == "E1":
                row["coverage"] = round(cov, 6)
        out["series"][str(y)] = row
    return out

result["fixed_ladder_forward"] = fixed_series(per_source)
result["fixed_ladder_reverse"] = fixed_series(per_source_rev)

# --- U0 (2026-10-15): baseline-choice table ------------------------------------
# For each direction and endpoint comparison, recompute the fixed-composition
# aggregate ratio under weights from three different base years (2019/2021/2024).
# Laspeyres = start-year weights; Paasche = end-year weights; 2019 = pre-period.
def baseline_table(ps, start=2021, end=2024):
    srcs = sorted({s for (y, s) in ps if y == start and ps[(y, s)][0] > 0}
                  & {s for (y, s) in ps if y == end and ps[(y, s)][0] > 0})
    out = {"sources": srcs}
    for base in (2019, 2021, 2024):
        bcells = {s: ps[(base, s)] for s in srcs if (base, s) in ps and ps[(base, s)][0] > 0}
        tot = sum(c[0] for c in bcells.values())
        row = {"n_base": tot, "base_sources": len(bcells)}
        if tot:
            w = {s: c[0] / tot for s, c in bcells.items()}
            # support diagnostics (2026-10-15): (a) weight_sum = base weight whose
            # source has cells at BOTH endpoints (must be 1.0; below that means a
            # base source silently dropped out of the aggregates); (b) coverage_share
            # = base weight retained inside the compared support vs the base year's
            # full stable8 support (e.g. C&IE leaving the set after 2021).
            used = [s for s in bcells if (start, s) in ps and ps[(start, s)][0] > 0
                    and (end, s) in ps and ps[(end, s)][0] > 0]
            row["weight_sum"] = round(sum(w[s] for s in used), 6)
            full_base = sum(c[0] for (y, _), c in ps.items() if y == base)
            row["coverage_share"] = round(tot / full_base, 6) if full_base else None
            for name, col in (("E1", 1), ("E2", 2), ("E3", 3)):
                den = sum(w[s] * (ps[(start, s)][col] / ps[(start, s)][0]) for s in used)
                num = sum(w[s] * (ps[(end, s)][col] / ps[(end, s)][0]) for s in used)
                row[name] = {"start": round(den, 6), "end": round(num, 6),
                             "rel_change": round(num / den - 1, 4) if den else None}
        else:
            row["weight_sum"] = 0.0
            row["coverage_share"] = None
        out[str(base)] = row
    return out

result["baseline_table_forward_2124"] = baseline_table(per_source)
result["baseline_table_reverse_2124"] = baseline_table(per_source_rev)
result["baseline_table_forward_1924"] = baseline_table(per_source, 2019, 2024)
result["baseline_table_reverse_1924"] = baseline_table(per_source_rev, 2019, 2024)
# 2025 endpoint (censored, see endpoint_censoring below): 2125 / 1925 / 2425
result["baseline_table_forward_2125"] = baseline_table(per_source, 2021, 2025)
result["baseline_table_reverse_2125"] = baseline_table(per_source_rev, 2021, 2025)
result["baseline_table_forward_1925"] = baseline_table(per_source, 2019, 2025)
result["baseline_table_reverse_1925"] = baseline_table(per_source_rev, 2019, 2025)
result["baseline_table_forward_2425"] = baseline_table(per_source, 2024, 2025)
result["baseline_table_reverse_2425"] = baseline_table(per_source_rev, 2024, 2025)

# --- top-level endpoint-censoring marker (2026-10-15) --------------------------
# 2025 is the final collection year (citing-year rows > 2025 are dropped on the
# collection side), so EVERY 2025-endpoint ratio below mixes trend with
# truncation.  Registered magnitude (task 0-4, NUMBERS 0-4 row): on the old-name
# anchor the 2025 endpoint amplifies the 2021-base E1 decline by ~13 pp versus
# the 2024 endpoint (-25.7% vs -39.5%), both directions same sign.  Read 2025
# endpoints only alongside their 2024 counterparts.
result["endpoint_censoring"] = {
    "censored_endpoint_years": [2025],
    "note": ("2025 is right-censored (final collection year). Treat every 2025-endpoint "
             "estimate as censoring-sensitive; the registered 0-4 sensitivity is ~13 pp of "
             "extra decline on the 2021->2025 window vs 2021->2024 on the old-name anchor, "
             "same sign in both directions. Report 2024 endpoints alongside."),
    "series_reaching_2025": [
        "s1_single_end_anchor", "s2_double_end", "same_support['2025']",
        "s1_reverse_full", "same_support_reverse['2025']",
        "fixed_ladder_forward", "fixed_ladder_reverse",
        "per_source_e1", "per_source_e1_reverse",
        "baseline_table_forward_2125", "baseline_table_reverse_2125",
        "baseline_table_forward_1925", "baseline_table_reverse_1925",
        "baseline_table_forward_2425", "baseline_table_reverse_2425",
    ],
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

def ep(s, a="2021", b="2025"):
    x, y2 = s.get(a), s.get(b)
    return (round(100 * (y2["E1_mean_edges"] / x["E1_mean_edges"] - 1), 2),
            round(100 * (y2["E2_participation"] / x["E2_participation"] - 1), 2),
            round(100 * (y2["E3_mean_share_of_refs"] / x["E3_mean_share_of_refs"] - 1), 2)) if x and y2 else None

s1s = result["s1_single_end_anchor"]
s2s = result["s2_double_end"]
print("S1 merged full-support: 2021", s1s.get("2021"), "2024", s1s.get("2024"), "2025", s1s.get("2025"))
print("S1 rel-change 2021->2025 (E1,E2,E3 %):", ep(s1s))
print("S2 merged full-support: 2021", s2s.get("2021"), "2024", s2s.get("2024"), "2025", s2s.get("2025"))
print("same_support:", json.dumps(result["same_support"], ensure_ascii=False, indent=1))

# --- self-checks (2026-10-15 completion pass) ---------------------------------
# (a) reverse per-source cells must aggregate exactly to the yearly series
chk = defaultdict(lambda: [0, 0, 0])
for (y, s), c in per_source_rev.items():
    chk[y][0] += c[0]
    chk[y][1] += c[1]
    chk[y][2] += c[2]
bad = [y for y in chk if chk[y][0] != s1_rev[y][0] or chk[y][1] != s1_rev[y][1]
       or chk[y][2] != s1_rev[y][2]]
print("reverse per-source vs yearly aggregation:", "OK" if not bad else f"MISMATCH {bad}")
# (b) cell-internal identities: emitted ratios must reproduce from the raw
# counters (n_refs >= n_edges holds because every edge points at a distinct ref)
cell_out = result["per_source_e1_reverse"]
bad2 = [f"{y}|{s}" for (y, s), c in per_source_rev.items()
        if cell_out[f"{y}|{s}"]["E1_to_non"] != round(c[1] / c[0], 6)
        or cell_out[f"{y}|{s}"]["E2_to_non"] != round(c[2] / c[0], 6)
        or cell_out[f"{y}|{s}"]["E3_to_non"] != round(c[3] / c[0], 6)
        or c[4] < c[1]]
print("reverse cell identities (emitted E1/E2/E3 reproduce from counters, n_refs >= n_edges):",
      "OK" if not bad2 else f"MISMATCH {bad2}")
s1r = result["s1_reverse_full"]
print("S1-reverse full-support 2021:", s1r["2021"], "2024:", s1r["2024"], "2025:", s1r["2025"])
print("S1-reverse rel-change 2021->2025 (E1,E2,E3 %):",
      (round(100 * (s1r["2025"]["E1_mean_edges_to_non"] / s1r["2021"]["E1_mean_edges_to_non"] - 1), 2),
       round(100 * (s1r["2025"]["E2_participation"] / s1r["2021"]["E2_participation"] - 1), 2),
       round(100 * (s1r["2025"]["E3_mean_share_of_refs"] / s1r["2021"]["E3_mean_share_of_refs"] - 1), 2)))
for k in ("E1", "E2", "E3"):
    print(f"same_support_reverse pooled {k} 2021->2025:",
          json.dumps(result["same_support_reverse"]["2025"]["pooled"][k], ensure_ascii=False))
for key in ("baseline_table_forward_2125", "baseline_table_reverse_2125",
            "baseline_table_forward_1925", "baseline_table_reverse_1925",
            "baseline_table_forward_2425", "baseline_table_reverse_2425"):
    t = result[key]
    print(key, "coverage_share:", {b: t[b]["coverage_share"] for b in ("2019", "2021", "2024")},
          "weight_sum:", {b: t[b]["weight_sum"] for b in ("2019", "2021", "2024")},
          "E1 rel:", {b: t[b]["E1"]["rel_change"] for b in ("2019", "2021", "2024")})
