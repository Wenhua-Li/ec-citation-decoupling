# -*- coding: utf-8 -*-
"""Stage 0 task 0-2: doc_type-standardised CD5 gaps (production path).

Conference/journal composition drifts strongly in EC (CA share 0.81 in 2005
to 0.33 in 2024) and was never controlled by the 17 registered robustness
checks.  This script recomputes the CD5 gap between EC and NON_EC under
document-type controls, using the SAME counting path as disruption.py
(DISTINCT (acc, cited) edges, citing window [t, t+5], |Q| >= 3, citing
papers without a reference list excluded from the vote, cohorts 2000-2020).

Four deliverables (astra spec, synthesis adjudication 4):
  S1  raw gaps by label x doc_type x cohort year (JA-only, CA-only)
  S2  jointly standardised gap: both groups reweighted to a FIXED doc_type
      distribution (pooled full-window composition; EC-comp and NON-comp
      variants as sensitivity)
  S3  per-type reference-list length and in-corpus parse rate, by label
  S4  common support: n per cell; types below the n>=30 threshold are
      reported, not silently dropped

Output: research/nature/out/doctype_cd.json
"""
import json
import os
import statistics
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ecdb

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "doctype_cd.json")

label_of, year_of, doctype_of = {}, {}, {}
for r in ecdb.raw_sql(
    "SELECT d.accession_no acc, d.label, p.pub_year y, p.doc_type dt "
    "FROM paper_domain d JOIN papers p USING(accession_no)",
    max_rows=200000,
)["rows"]:
    label_of[r["acc"]] = r["label"]
    year_of[r["acc"]] = r["y"]
    doctype_of[r["acc"]] = r["dt"]

print("loading in-db edges (refs_out doi-join) ...", flush=True)
refs = defaultdict(set)  # acc -> set(cited acc)  [in-corpus resolved refs]
edge_rows = ecdb.raw_sql(
    """
    SELECT DISTINCT r.accession_no acc, pc.accession_no cited
    FROM paper_refs_out r
    JOIN papers pc ON pc.doi = r.cited_doi
    """,
    max_rows=3000000,
)["rows"]
for r in edge_rows:
    refs[r["acc"]].add(r["cited"])
print(f"edges: {len(edge_rows)}, papers with refs: {len(refs)}", flush=True)

# total distinct non-null refs per paper (parse-rate denominator, stability.py
# convention: DISTINCT cited_doi, NULLs dropped -- includes refs that point
# outside the corpus)
tot_refs = {}
for r in ecdb.raw_sql(
    "SELECT accession_no acc, COUNT(DISTINCT cited_doi) n FROM paper_refs_out "
    "WHERE cited_doi IS NOT NULL GROUP BY 1",
    max_rows=300000,
)["rows"]:
    tot_refs[r["acc"]] = r["n"]

cited_by = defaultdict(list)
for acc, cs in refs.items():
    for c in cs:
        cited_by[c].append(acc)

def cd5(p, t):
    # identical to disruption.py
    qs = [q for q in cited_by.get(p, []) if t <= year_of.get(q, -1) <= t + 5]
    if len(qs) < 3:
        return None, len(qs)
    Rp = refs.get(p, set()) - {p}
    n_pos = n_neg = 0
    for q in qs:
        Rq = refs.get(q)
        if not Rq:
            continue
        if Rq & Rp:
            n_neg += 1
        else:
            n_pos += 1
    n = n_pos + n_neg
    if n == 0:
        return None, len(qs)
    return (n_pos - n_neg) / n, n

# ---- per-paper CD5 values by (label, doc_type, cohort year) ----------------
cell_vals = defaultdict(list)   # (label, dt, year) -> [cd5 values]
print("computing per-paper CD5 ...", flush=True)
for t in range(2000, 2021):
    for acc, y in year_of.items():
        if y != t or acc not in refs:
            continue
        lab, dt = label_of.get(acc), doctype_of.get(acc)
        if lab not in ("EC", "NON_EC") or dt not in ("JA", "CA"):
            continue
        v, _ = cd5(acc, t)
        if v is not None:
            cell_vals[(lab, dt, t)].append(v)
    print(t, {f"{k[0][:3]}-{k[1]}": len(v) for k, v in cell_vals.items() if k[2] == t}, flush=True)

def mean(xs):
    return round(statistics.mean(xs), 4) if xs else None

# S1 raw per-cell means and within-type gaps ---------------------------------
s1 = {}
for t in range(2000, 2021):
    row = {}
    for lab in ("EC", "NON_EC"):
        for dt in ("JA", "CA"):
            vals = cell_vals.get((lab, dt, t), [])
            row[f"{lab}_{dt}"] = {"n": len(vals), "mean": mean(vals)} if len(vals) >= 30 else {"n": len(vals), "mean": None}
    for dt in ("JA", "CA"):
        e, n = row.get(f"EC_{dt}"), row.get(f"NON_EC_{dt}")
        if e and n and e["mean"] is not None and n["mean"] is not None:
            row[f"gap_{dt}"] = round(e["mean"] - n["mean"], 4)
    ec_all = cell_vals.get(("EC", "JA", t), []) + cell_vals.get(("EC", "CA", t), [])
    non_all = cell_vals.get(("NON_EC", "JA", t), []) + cell_vals.get(("NON_EC", "CA", t), [])
    if ec_all and non_all:
        row["gap_raw"] = round(statistics.mean(ec_all) - statistics.mean(non_all), 4)
    s1[str(t)] = row

# S2 jointly standardised gap -------------------------------------------------
# fixed doc_type weights from the pooled (EC+NON, 2000-2020) composition of
# papers WITH a CD5 value; EC-only and NON-only compositions as sensitivity.
pooled_n = {"JA": 0, "CA": 0}
comp = {"pooled": {"JA": 0, "CA": 0}, "EC": {"JA": 0, "CA": 0}, "NON_EC": {"JA": 0, "CA": 0}}
for (lab, dt, t), vals in cell_vals.items():
    pooled_n[dt] += len(vals)
    comp["pooled"][dt] += len(vals)
    comp[lab][dt] += len(vals)
for cname, d in comp.items():
    tot = d["JA"] + d["CA"]
    comp[cname] = {k: v / tot for k, v in d.items()}

s2 = {}
for t in range(2000, 2021):
    row = {}
    for cname, w in comp.items():
        parts, used = [], []
        for dt in ("JA", "CA"):
            e = cell_vals.get(("EC", dt, t), [])
            n = cell_vals.get(("NON_EC", dt, t), [])
            if len(e) >= 30 and len(n) >= 30:
                parts.append(w[dt] * (statistics.mean(e) - statistics.mean(n)))
                used.append(w[dt])
        if used:
            # renormalise over types with common support; S4 records coverage
            row[cname] = {
                "gap": round(sum(parts) / sum(used), 4),
                "coverage": round(sum(used), 4),
                "used_types": ["JA", "CA"][: len(used)],
            }
    s2[str(t)] = row

# S3 reference-list length and parse rate by label x doc_type -----------------
s3 = {}
for lab in ("EC", "NON_EC"):
    for dt in ("JA", "CA"):
        accs = [a for a in refs if label_of.get(a) == lab and doctype_of.get(a) == dt]
        lens = [tot_refs.get(a, 0) for a in accs]
        parse = [len(refs[a]) / tot_refs[a] for a in accs if tot_refs.get(a, 0) > 0]
        s3[f"{lab}_{dt}"] = {
            "n_papers_with_refs": len(accs),
            "mean_total_refs": round(statistics.mean(lens), 2) if lens else None,
            "median_total_refs": round(statistics.median(lens), 2) if lens else None,
            "mean_parse_rate": round(statistics.mean(parse), 4) if parse else None,
        }

# S4 common support ------------------------------------------------------------
s4 = {}
for t in range(2000, 2021):
    bad = []
    for lab in ("EC", "NON_EC"):
        for dt in ("JA", "CA"):
            n = len(cell_vals.get((lab, dt, t), []))
            if n < 30:
                bad.append({"cell": f"{lab}_{dt}", "n": n})
    if bad:
        s4[str(t)] = bad

# window summaries (anchor windows used in the registry) -----------------------
def wgap(d, key, years):
    vals = []
    for y in years:
        v = d.get(str(y), {}).get(key)
        if isinstance(v, dict):
            v = v.get("gap")
        if v is not None:
            vals.append(v)
    return round(statistics.mean(vals), 4) if vals else None

summary = {
    "raw_gap_2018_20": wgap(s1, "gap_raw", [2018, 2019, 2020]),
    "raw_gap_2005_07": wgap(s1, "gap_raw", [2005, 2006, 2007]),
    "JA_gap_2018_20": wgap(s1, "gap_JA", [2018, 2019, 2020]),
    "JA_gap_2005_07": wgap(s1, "gap_JA", [2005, 2006, 2007]),
    "CA_gap_2018_20": wgap(s1, "gap_CA", [2018, 2019, 2020]),
    "CA_gap_2005_07": wgap(s1, "gap_CA", [2005, 2006, 2007]),
    "std_pooled_2018_20": wgap(s2, "pooled", [2018, 2019, 2020]),
    "std_pooled_2005_07": wgap(s2, "pooled", [2005, 2006, 2007]),
    "std_ECcomp_2018_20": wgap(s2, "EC", [2018, 2019, 2020]),
    "std_NONcomp_2018_20": wgap(s2, "NON_EC", [2018, 2019, 2020]),
}

result = {
    "task": "0-2 doc_type standardised CD5",
    "production_path": "identical to disruption.py (DISTINCT (acc,cited) edges, [t,t+5] window, |Q|>=3, no-reflist citers excluded)",
    "s1_raw_cells_and_type_gaps": s1,
    "s2_standardised_gaps": s2,
    "s2_fixed_weights": {k: {d: round(v, 6) for d, v in w.items()} for k, w in comp.items()},
    "s3_reflist_and_parse": s3,
    "s4_common_support_violations": s4,
    "window_summary": summary,
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)
print(json.dumps({"window_summary": summary, "s3": s3, "s4": s4}, ensure_ascii=False, indent=1))
