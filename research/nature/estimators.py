# -*- coding: utf-8 -*-
"""Stage 0 task 0-3 + 0-4: the three-estimator decomposition of cross-field
citation strength, with endpoint-censoring sensitivity.

Any statement about "knowledge flow / citation strength" must name its
estimator (AGENTS methodology rule 3):
  E1  mean cross-field edges per citing-side paper
  E2  share of citing-side papers with >=1 cross-field edge
  E3  cross-field edges as a share of the paper's reference list
      (per-paper mean; aggregate ratio reported alongside)

Directions: NON_EC -> EC (headline) and EC -> NON_EC.
Scopes: "stable8" restricts the CITING side to the fixed eight-source name
list while the cited side covers the whole in-corpus target label (a
single-end anchor reading); "full" uses the whole corpus on both sides.
NOTE (2026-10-15, D0 review): the eight-name list carries a source-title
variant -- "Applied Soft Computing Journal" (through 2020) vs "Applied
Soft Computing" (2015-2025; same Elsevier journal, ISSN 1568-4946) -- and
Computers and Industrial Engineering drops out after 2021, so this scope's
within-window support changes.  Recompute under the merged name before any
manuscript use.  Endpoints: 2021->2025 and, for censoring sensitivity
(task 0-4), 2021->2024 (2025 is the corpus's last, partially truncated year).

Output: research/nature/out/estimators.json
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
OUT = os.path.join(HERE, "out", "estimators.json")

stable = {
    "Applied Soft Computing Journal",
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
    meta[r["acc"]] = (r["y"], r["src"], r["lab"])

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

print("counting edges to EC and to NON_EC ...", flush=True)
to_ec = cross_edges("EC")
to_non = cross_edges("NON_EC")

tot_refs = {}
for r in ecdb.raw_sql(
    "SELECT accession_no acc, COUNT(DISTINCT cited_doi) n FROM paper_refs_out "
    "WHERE cited_doi IS NOT NULL GROUP BY 1",
    max_rows=300000,
)["rows"]:
    tot_refs[r["acc"]] = r["n"]

# pool definitions: citing side label x scope
def pool(label: str, scope: str):
    out = []
    for acc, (y, src, lab) in meta.items():
        if lab != label:
            continue
        if scope == "stable8" and src not in stable:
            continue
        if 2005 <= y <= 2025:
            out.append(acc)
    return out

series = {}
for scope in ("stable8", "full"):
    for side, edges in (("NON_EC", to_ec), ("EC", to_non)):
        accs = pool(side, scope)
        by_year = defaultdict(lambda: [0, 0, 0, 0.0, 0])  # n, n_with_edge, sum_edges, sum_share, sum_totrefs
        for acc in accs:
            y = meta[acc][0]
            e = edges.get(acc, 0)
            tr = tot_refs.get(acc, 0)
            c = by_year[y]
            c[0] += 1
            c[1] += 1 if e else 0
            c[2] += e
            c[3] += (e / tr) if tr else 0.0
            c[4] += tr
        key = f"{scope}_{side}_to_{'EC' if side == 'NON_EC' else 'NON_EC'}"
        series[key] = {
            str(y): {
                "n": c[0],
                "E1_mean_edges": round(c[2] / c[0], 6),
                "E2_participation": round(c[1] / c[0], 6),
                "E3_mean_share_of_refs": round(c[3] / c[0], 6),
                "E3_aggregate_share": round(c[2] / c[4], 6) if c[4] else None,
                "edges": c[2],
            }
            for y, c in sorted(by_year.items())
        }

def endpoints(s, a_year="2021", b_year="2025"):
    a, b = s.get(a_year), s.get(b_year)
    if not a or not b:
        return None
    out = {}
    for k in ("E1_mean_edges", "E2_participation", "E3_mean_share_of_refs", "E3_aggregate_share"):
        out[k] = {
            a_year: a[k],
            b_year: b[k],
            "rel_change": round(b[k] / a[k] - 1, 4) if a[k] else None,
        }
    out["edges"] = {a_year: a["edges"], b_year: b["edges"],
                    "rel_change": round(b["edges"] / a["edges"] - 1, 4) if a["edges"] else None}
    return out

result = {
    "task": "0-3 three-estimator decomposition + 0-4 endpoint censoring",
    "estimator_definitions": {
        "E1": "mean cross-field in-corpus edges per citing-side paper",
        "E2": "share of citing-side papers with >=1 cross-field in-corpus edge",
        "E3": "cross-field edges / total distinct non-null refs (per-paper mean; aggregate alongside)",
    },
    "series": series,
    "endpoints_2021_2025": {k: endpoints(v, "2021", "2025") for k, v in series.items()},
    "endpoints_2021_2024": {k: endpoints(v, "2021", "2024") for k, v in series.items()},
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)
print(json.dumps(result["endpoints_2021_2025"], ensure_ascii=False, indent=1))
print("== 2021->2024 (censoring sensitivity) ==")
print(json.dumps(result["endpoints_2021_2024"], ensure_ascii=False, indent=1))
