# -*- coding: utf-8 -*-
"""control_theory boundary semantic fix (2026-10-15, registered data defect).

The archived W1 boundary check resolved the topic by blindly taking the FIRST
search hit ("Control Theory" -> T11542 "Behavioral Health and Interventions",
marked pass:true -- archive/packages/w1w2/out/boundary_consistency.json:6).
Fix: re-resolve the topic with a semantic-match rule (top hit whose
display_name contains 'control' and none of health/behavioral/psychology),
then re-run the topic-vs-anchor correlation for the two control sources.

Output: research/panels/out/control_theory_boundary_fix.json
"""
import json
import os
import statistics
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from oa_client import _get, BASE, MAILTO  # noqa: E402

BAD = ("health", "behavioral", "psychology", "social")

def resolve_topic():
    r = _get(f"{BASE}/topics?search={urllib.parse.quote('control theory and systems')}&per-page=25&mailto={MAILTO}")
    for t in r.get("results", []):
        name = t["display_name"].lower()
        if "control" in name and not any(b in name for b in BAD):
            return t["id"].rsplit("/", 1)[-1], t["display_name"]
    return None, None

def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for i, idx in enumerate(order):
            r[idx] = i + 1.0
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None

panels = json.load(open(os.path.join(HERE, "..", "..", "archive", "packages", "w1w2", "..", "..",
                                     "research", "nature", "out", "w1_panels.json"), encoding="utf-8")) if False else \
    json.load(open("research/nature/out/w1_panels.json", encoding="utf-8"))

tid, tname = resolve_topic()
print("resolved topic:", tid, tname, flush=True)
result = {"defect": "original check took first search hit (T11542 Behavioral Health and Interventions) "
                    "and marked pass:true; selection rule now requires semantic match",
          "topic": {"id": tid, "display_name": tname},
          "rho_pass": 0.8, "curves": {}}

topic_curve = {}
for sid in ("S51360982", "S184954342"):
    r = _get(f"{BASE}/works?filter=primary_location.source.id:{sid},topics.id:{tid}"
             f"&group_by=publication_year&per-page=200&mailto={MAILTO}")
    for g in r.get("group_by", []):
        if g["key"].isdigit():
            topic_curve[g["key"]] = topic_curve.get(g["key"], 0) + g["count"]

for j, meta in panels["control_theory"].items():
    anchor = {y: c for y, c in meta["total"].items()}
    yrs = sorted(int(y) for y in anchor if int(y) >= 1990 and str(y) in topic_curve)
    rho = spearman([anchor[str(y)] for y in yrs], [topic_curve[str(y)] for y in yrs]) if len(yrs) >= 10 else None
    result["curves"][j] = {"rho_topic_vs_anchor": round(rho, 4) if rho is not None else None,
                           "n_years": len(yrs),
                           "pass": bool(rho is not None and rho >= 0.8)}

rhos = [c["rho_topic_vs_anchor"] for c in result["curves"].values() if c["rho_topic_vs_anchor"] is not None]
result["verdict"] = "PASS" if rhos and min(rhos) >= 0.8 else "FAIL"
with open(os.path.join(HERE, "out", "control_theory_boundary_fix.json"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in result.items() if k != "curves"}, ensure_ascii=False, indent=1))
print(result["curves"])
