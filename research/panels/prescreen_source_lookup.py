# -*- coding: utf-8 -*-
"""B 广度层候选刊源检索（预筛第一步）：按刊名查 OpenAlex source 候选，人工核验后入册。

用法：python prescreen_source_lookup.py
输出：out/source_candidates.json（每刊名前 3 候选：sid/display_name/issn/works_count）
纪律：刊名→sid 一律人工核对 display_name+ISSN（control_theory 盲选教训），本脚本只出候选。
"""
import json
import os
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from oa_client import _get, BASE, MAILTO  # noqa: E402

JOURNALS = {
    "physics": ["Physical Review Letters", "Physical Review B", "Applied Physics Letters", "Physical Review A"],
    "materials": ["Advanced Materials", "Acta Materialia", "Nano Letters", "Advanced Functional Materials"],
    "chemistry": ["Journal of the American Chemical Society", "Angewandte Chemie International Edition", "Chemical Science", "Analytical Chemistry"],
    "chemical_engineering": ["AIChE Journal", "Chemical Engineering Science", "Industrial & Engineering Chemistry Research"],
    "biology": ["Cell", "PLOS Biology", "The EMBO Journal", "Nucleic Acids Research"],
    "medicine": ["The Lancet", "JAMA", "BMJ", "The New England Journal of Medicine"],
    "computer_science": ["Journal of the ACM", "IEEE Transactions on Pattern Analysis and Machine Intelligence", "Communications of the ACM"],
    "electrical_engineering": ["Proceedings of the IEEE", "IEEE Transactions on Information Theory", "IEEE Transactions on Signal Processing"],
    "neuroscience": ["Neuron", "Nature Neuroscience", "Journal of Neuroscience"],
    "business": ["Academy of Management Journal", "Administrative Science Quarterly", "Organization Science"],
    "sociology": ["American Sociological Review", "American Journal of Sociology", "Social Forces"],
    "political_science": ["American Political Science Review", "American Journal of Political Science", "The Journal of Politics"],
    "ecology": ["Ecology Letters", "Ecology", "Global Change Biology"],
    "earth_science": ["Earth and Planetary Science Letters", "Geology", "Global Biogeochemical Cycles"],
    "statistics": ["The Annals of Statistics", "Journal of the American Statistical Association", "Biometrika"],
    "biomedical_engineering": ["Biomaterials", "IEEE Transactions on Biomedical Engineering", "Acta Biomaterialia"],
    "mechanical_engineering": ["Mechanical Systems and Signal Processing", "International Journal of Mechanical Sciences", "International Journal of Machine Tools and Manufacture"],
}

out = {}
for field, names in JOURNALS.items():
    for name in names:
        url = (f"{BASE}/sources?search={urllib.parse.quote(name)}&per-page=3&mailto={MAILTO}")
        try:
            res = _get(url).get("results", [])
        except Exception as e:
            print(f"[ERR] {name}: {e}", flush=True)
            continue
        cands = [{"sid": r["id"].rsplit("/", 1)[-1],
                  "display_name": r.get("display_name"),
                  "issn": r.get("issn"),
                  "works_count": r.get("works_count"),
                  "type": r.get("type")} for r in res]
        out.setdefault(field, {})[name] = cands
        top = cands[0] if cands else None
        print(f"{field:24s} {name:55s} -> {top['sid'] if top else '—'} {top['display_name'] if top else ''}", flush=True)

path = os.path.join(HERE, "out", "source_candidates.json")
os.makedirs(os.path.dirname(path), exist_ok=True)
json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved:", path)
