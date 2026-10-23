# -*- coding: utf-8 -*-
"""P0-1 (batch 2, 2026-10-20): subfamily debut-author shares under dual denominators.

Methodology replicated verbatim from archive/packages/r3a/r3a_execute.py lines 57-118
(frozen R3E_FREEZE spec): EC papers classified with the frozen FAMILIES_V3 patterns
(17 families + OTHER fallback); authors aggregated by name_display; debut year =
earliest corpus publication year (authors debuting before 2003 excluded); the
all-field debut pool N_pool counts every debut author in G1=2003-2007 /
G2=2019-2022 regardless of direction; an author whose debut-year papers are
majority-EC (ec > non) is an EC-direction debut and casts ONE vote for the modal
family of their debut-year EC papers (ties -> OTHER).

NEW (batch-2 dual-scope extension): alongside the frozen corpus scope
(share = n / N_pool, all-field debuts), each family also gets the EC-debut scope
(share = n / M, where M = EC-direction debut authors in that period), with a
two-sided two-proportion z test in the new scope and the frozen one-sided test
in the corpus scope. Trigger recheck: >=3 classified eligible families with
|rel_change_ec_debut| >= 25% and significant (p_two < 0.05 and BH < 0.05).

Consistency: per-family counts, N1/N2 and the OTHER rate are compared exactly
against archive/packages/r3a/out/r3a_results.json (read-only); the yearly
first-direction series is checked against PKG-A authors_flow.json as in the
original script.

Output: research/nature/out/subfamily_dual_share.json
"""
import json
import math
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
for p in (ROOT, os.path.join(ROOT, "release_repo", "research", "nature")):
    if p not in sys.path:
        sys.path.insert(0, p)

import ecdb
from r3e_coverage import FAMILIES_V3  # frozen pattern registry (surviving copy, byte-identical to archived one)

OUT = os.path.join(HERE, "out", "subfamily_dual_share.json")

G1 = range(2003, 2008)
G2 = range(2019, 2023)


def bh_adjust(pvals):
    """Benjamini-Hochberg step-up (dict name->p  =>  name->p_BH)."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    adj, prev = {}, 1.0
    for i in range(m - 1, -1, -1):
        name, p = items[i]
        rank = i + 1
        val = min(prev, p * m / rank)
        adj[name] = round(val, 6)
        prev = val
    return adj


def phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# --- 1) EC paper family assignment (replicates r3a_execute.py:57-79) ----------------
print("classifying EC papers with frozen patterns ...", flush=True)
import re
pats = [(name, re.compile(pat, re.I)) for name, pat in FAMILIES_V3]
ec_rows = ecdb.raw_sql(
    "SELECT p.accession_no acc, p.pub_year y, p.title t, p.abstract ab "
    "FROM papers p JOIN paper_domain d ON d.accession_no=p.accession_no WHERE d.label='EC'",
    max_rows=60000,
)["rows"]
fam_of = {}
n_other = 0
for r in ec_rows:
    txt = ((r["t"] or "") + " \n " + (r["ab"] or "")).lower()
    hit = None
    for name, pat in pats:
        if pat.search(txt):
            hit = name
            break
    if hit is None:
        hit = "OTHER"
        n_other += 1
    fam_of[r["acc"]] = hit
validity_other_rate = round(n_other / len(ec_rows), 4)
print(f"EC papers: {len(ec_rows)}; OTHER rate: {validity_other_rate:.1%}", flush=True)

# --- 2) author debut year and first-direction family vote (replicates :82-118) ------
print("loading author-paper-label rows ...", flush=True)
arows = ecdb.raw_sql(
    "SELECT a.name_display nm, p.accession_no acc, p.pub_year y, d.label l "
    "FROM paper_authors a JOIN papers p USING(accession_no) JOIN paper_domain d USING(accession_no)",
    max_rows=2000000,
)["rows"]
author_papers = defaultdict(list)
for r in arows:
    if r["nm"] is None or r["y"] is None:
        continue
    author_papers[r["nm"]].append((r["y"], r["l"], r["acc"]))
print(f"authors: {len(author_papers)}", flush=True)

n_s = defaultdict(lambda: [0, 0])           # family -> [n_G1, n_G2]
N_pool = [0, 0]                              # all-field debut denominators
share_year = defaultdict(lambda: [0, 0])     # year -> [n_ec_debut, n_debut] (PKG-A check)
for nm, papers in author_papers.items():
    first_y = min(y for y, _, _ in papers)
    if first_y < 2003:
        continue
    first_papers = [(y, l, a) for y, l, a in papers if y == first_y]
    ec = sum(1 for _, l, _ in first_papers if l == "EC")
    non = len(first_papers) - ec
    gi = 0 if first_y in G1 else (1 if first_y in G2 else None)
    if gi is not None:
        N_pool[gi] += 1
    share_year[first_y][1] += 1
    if ec > non:  # debut-year direction == EC
        share_year[first_y][0] += 1
        counts = Counter(fam_of[a] for _, l, a in first_papers if l == "EC")
        maxc = max(counts.values())
        winners = [f for f, c in counts.items() if c == maxc]
        fam = winners[0] if len(winners) == 1 else "OTHER"  # ties -> OTHER
        if gi is not None:
            n_s[fam][gi] += 1

# --- 3) dual-scope statistics -------------------------------------------------------
N1, N2 = N_pool
M1 = sum(v[0] for v in n_s.values())   # EC-direction debut authors, G1
M2 = sum(v[1] for v in n_s.values())   # EC-direction debut authors, G2
print(f"N1={N1} N2={N2}  M1={M1} M2={M2}", flush=True)

subfamilies = []
for fam in sorted(n_s, key=lambda f: -(n_s[f][0] + n_s[f][1])):
    c1, c2 = n_s[fam]
    p1, p2 = c1 / N1, c2 / N2          # corpus scope (frozen)
    q1, q2 = c1 / M1, c2 / M2          # EC-debut scope (new)
    rec = {
        "family": fam,
        "classified": fam != "OTHER",
        "n_G1": c1, "n_G2": c2,
        "share_corpus_G1": round(p1, 6), "share_corpus_G2": round(p2, 6),
        "share_ec_debut_G1": round(q1, 6), "share_ec_debut_G2": round(q2, 6),
        "rel_change_corpus": round((p1 - p2) / p1, 4) if p1 > 0 else None,   # frozen: positive = decline
        "rel_change_ec_debut": round((q2 - q1) / q1, 4) if q1 > 0 else None, # signed: positive = rise
    }
    rec["eligible"] = c1 >= 200 and c2 >= 200
    if rec["eligible"]:
        pp = (c1 + c2) / (N1 + N2)     # frozen corpus-scope one-sided decline test
        se = math.sqrt(pp * (1 - pp) * (1 / N1 + 1 / N2))
        z = (p1 - p2) / se
        rec["corpus_test"] = {"z": round(z, 3), "p_raw_one_sided": round(1 - phi(z), 6)}
        pp2 = (c1 + c2) / (M1 + M2)    # new EC-debut-scope two-sided test
        se2 = math.sqrt(pp2 * (1 - pp2) * (1 / M1 + 1 / M2))
        z2 = (q1 - q2) / se2
        rec["ec_debut_test"] = {"z": round(z2, 3),
                                "p_two_sided": round(2 * (1 - phi(abs(z2))), 6)}
    subfamilies.append(rec)

elig = [r for r in subfamilies if r["eligible"]]
p_bh_corpus = bh_adjust({r["family"]: r["corpus_test"]["p_raw_one_sided"] for r in elig})
p_bh_ecd = bh_adjust({r["family"]: r["ec_debut_test"]["p_two_sided"] for r in elig})
for r in elig:
    r["corpus_test"]["p_BH"] = p_bh_corpus[r["family"]]
    r["ec_debut_test"]["p_BH"] = p_bh_ecd[r["family"]]

# --- 4) trigger recheck (batch-2 formulation) + frozen trigger replication ----------
classified_elig = [r for r in elig if r["classified"]]
pass25 = [r for r in classified_elig
          if abs(r["rel_change_ec_debut"]) >= 0.25
          and r["ec_debut_test"]["p_two_sided"] < 0.05
          and r["ec_debut_test"]["p_BH"] < 0.05]
trigger_recheck = {
    "rule": ">=3 classified eligible families with |rel_change_ec_debut|>=25% and two-sided p<0.05 (raw and BH)",
    "classified_eligible": [r["family"] for r in classified_elig],
    "n_pass": len(pass25),
    "pass_families": [
        {"family": r["family"], "rel_change_ec_debut": r["rel_change_ec_debut"],
         "p_two_sided": r["ec_debut_test"]["p_two_sided"]} for r in pass25],
    "threshold_met": len(pass25) >= 3,
    "verdict_flip": len(pass25) < 3,
}
cond1_all_frozen = bool(elig) and all(
    r["rel_change_corpus"] >= 0.25
    and r["corpus_test"]["p_raw_one_sided"] < 0.05
    and r["corpus_test"]["p_BH"] < 0.05 for r in elig)
trigger_input_A_replication = {
    "cond1_ge3_subfamilies": len(elig) >= 3,
    "cond1_all_eligible_decline_ge25_signif_rawBH": cond1_all_frozen,
    "cond3_validity_le10pct": validity_other_rate <= 0.10,
}

# --- 5) consistency: exact match vs archived r3a output + PKG-A yearly series -------
arch = json.load(open(os.path.join(ROOT, "archive", "packages", "r3a", "out", "r3a_results.json"),
                      encoding="utf-8"))
arch_n = {r["family"]: (r["n_G1"], r["n_G2"]) for r in arch["subfamilies"]}
mine_n = {r["family"]: (r["n_G1"], r["n_G2"]) for r in subfamilies}
mismatch = {f: (mine_n.get(f), arch_n.get(f)) for f in set(mine_n) | set(arch_n)
            if mine_n.get(f) != arch_n.get(f)}
pkg = json.load(open(os.path.join(ROOT, "archive", "packages", "w6_authors", "out", "authors_flow.json"),
                     encoding="utf-8"))["first_dir_series"]["full"]
bad = []
for y, v in pkg.items():
    mine = share_year[int(y)][0] / share_year[int(y)][1] if share_year[int(y)][1] >= 100 else None
    if mine is not None and abs(mine - v) > 0.002:
        bad.append((y, round(mine, 4), v))
consistency = {
    "counts_vs_archive_r3a": "PASS exact" if not mismatch else f"FAIL {dict(list(mismatch.items())[:5])}",
    "denominators_vs_archive": "PASS exact" if (N1, N2) == (arch["denominators"]["N_G1"], arch["denominators"]["N_G2"])
                               else f"FAIL mine=({N1},{N2}) arch={arch['denominators']}",
    "other_rate_vs_archive": "PASS exact" if validity_other_rate == arch["validity_other_rate"]
                             else f"FAIL mine={validity_other_rate} arch={arch['validity_other_rate']}",
    "first_choice_yearly_vs_PKG_A": "PASS" if not bad else f"FAIL {bad[:5]}",
}

result = {
    "method_source": "archive/packages/r3a/r3a_execute.py:57-118 replicated verbatim (read-only); frozen patterns imported from the byte-identical surviving registry copy",
    "periods": {"G1": "2003-2007", "G2": "2019-2022"},
    "units": "authors aggregated by name_display; debut year = earliest corpus publication year; EC-direction debut = majority of debut-year papers EC; family = modal family of debut-year EC papers, ties to OTHER",
    "denominators": {"N1_allfield_debuts": N1, "N2_allfield_debuts": N2,
                     "M1_ec_debuts": M1, "M2_ec_debuts": M2},
    "validity_other_rate_papers": validity_other_rate,
    "subfamilies": subfamilies,
    "trigger_recheck": trigger_recheck,
    "trigger_input_A_replication": trigger_input_A_replication,
    "consistency": consistency,
}
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

print(f"\nconsistency: {json.dumps(consistency, ensure_ascii=False)}")
print(f"trigger recheck: {len(pass25)} classified eligible families pass the 25% line "
      f"(threshold >=3; verdict_flip={trigger_recheck['verdict_flip']})")
for r in subfamilies:
    if r["eligible"]:
        ecd = r["ec_debut_test"]
        print(f"  {r['family']:<20} n {r['n_G1']:>5}->{r['n_G2']:<5} "
              f"corpus {r['rel_change_corpus']:+.4f}  ec_debut {r['rel_change_ec_debut']:+.4f} "
              f"(z2={ecd['z']:+.2f}, p2={ecd['p_two_sided']:.2g}, pBH={ecd['p_BH']:.2g})")
print("saved", os.path.relpath(OUT, ROOT))
