# -*- coding: utf-8 -*-
"""W2 预实验（PLAN v3 硬标准）：OpenAlex 对历史衰退案例的数据覆盖可行性。

案例：专家系统（1978-1993）、符号 AI（1980-1995）、模糊逻辑（1975-2000）、
      感知机/控制论（1955-1975，预期失败对照）。
硬验收标准（可判定）：
  (a) 目标区间内每年 ≥50 篇有参考文献记录的论文；
  (b) 参考文献中位被引年龄可计算（抽样论文的参考文献年份可解析比例 + 中位年龄分布）。
方法：OpenAlex works 检索 + group_by 年份（总量 vs has_references:true）+ 抽样解析参考年份。
输出：research/nature/out/w2_pilot.json + 控制台判定。
"""
import json
import os
import statistics
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

MAILTO = "ecmap.project@outlook.com"
BASE = "https://api.openalex.org"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": f"ecmap-w2pilot ({MAILTO})"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def group_by_year(params, extra=""):
    q = urllib.parse.quote(params)
    url = f"{BASE}/works?search={q}&group_by=publication_year&per-page=200&mailto={MAILTO}{extra}"
    return {int(b["key"]): b["count"] for b in get(url)["group_by"]}


CASES = [
    ("expert_systems", '"expert system" OR "knowledge based system"', 1978, 1993),
    ("symbolic_ai", '"knowledge representation" OR "theorem proving" OR "logic programming"', 1980, 1995),
    ("fuzzy_logic", '"fuzzy logic" OR "fuzzy set"', 1975, 2000),
    ("perceptron_cybernetics", 'perceptron OR cybernetics', 1955, 1975),
]

out = {}
for name, query, y0, y1 in CASES:
    print(f"\n===== {name} ({y0}-{y1}) =====", flush=True)
    total = group_by_year(query, "&filter=from_publication_date:{}-01-01,to_publication_date:{}-12-31".format(y0, y1))
    withref = group_by_year(
        query,
        "&filter=from_publication_date:{}-01-01,to_publication_date:{}-12-31,has_references:true".format(y0, y1),
    )
    years = [y for y in sorted(total) if y0 <= y <= y1]
    vol = {y: total.get(y, 0) for y in years}
    volr = {y: withref.get(y, 0) for y in years}
    peak_y = max(vol, key=vol.get)
    ok_years = [y for y in years if volr.get(y, 0) >= 50]
    print(f"total works {sum(vol.values())}, with-refs {sum(volr.values())}, peak year {peak_y} (n={vol[peak_y]})")
    print("with-refs per year:", {y: volr[y] for y in years if y % 3 == 0})

    # 抽样解析参考年份（中位被引年龄可算性）
    q = urllib.parse.quote(query)
    sample_url = (
        f"{BASE}/works?search={q}&filter=from_publication_date:{y0}-01-01,to_publication_date:{y1}-12-31,"
        f"has_references:true&select=id,publication_year,referenced_works&per-page=50&page={max(1, (len(years) // 4) or 1)}"
        f"&mailto={MAILTO}"
    )
    works = get(sample_url)["results"]
    cited_ages, resolve_rates = [], []
    for w in works[:25]:
        refs = w.get("referenced_works") or []
        if not refs:
            continue
        ryears = {}
        for i in range(0, len(refs), 50):
            batch = refs[i:i + 50]
            url = f"{BASE}/works?filter=openalex:{'|'.join(batch[:50])}&select=id,publication_year&per-page=50&mailto={MAILTO}"
            for r in get(url)["results"]:
                rid = r["id"].rsplit("/", 1)[-1]
                ryears[rid] = r.get("publication_year")
            time.sleep(0.12)
        known = [v for v in ryears.values() if v]
        if known:
            resolve_rates.append(len(known) / len(refs))
            med_ref_year = statistics.median(known)
            cited_ages.append(w["publication_year"] - med_ref_year)
    med_resolve = round(statistics.median(resolve_rates), 3) if resolve_rates else None
    med_age = round(statistics.median(cited_ages), 1) if cited_ages else None
    verdict_a = "PASS" if len(ok_years) >= (y1 - y0) * 0.6 else "FAIL"
    verdict_b = "PASS" if (med_resolve or 0) >= 0.5 and len(cited_ages) >= 15 else "FAIL"
    print(f"sampled={len(works)}, ref-year resolve rate (median)={med_resolve}, median cited age={med_age} (n={len(cited_ages)})")
    print(f"标准(a) 每年>=50 篇带参考文献: {verdict_a}（{len(ok_years)}/{len(years)} 年达标）")
    print(f"标准(b) 中位被引年龄可算:   {verdict_b}")
    out[name] = {
        "query": query, "window": [y0, y1],
        "volume_by_year": vol, "with_refs_by_year": volr,
        "peak_year": peak_y, "peak_n": vol[peak_y],
        "years_meeting_50": ok_years,
        "ref_year_resolve_rate_median": med_resolve,
        "median_cited_age_sample": med_age, "n_cited_age": len(cited_ages),
        "verdict_a": verdict_a, "verdict_b": verdict_b,
    }

with open(os.path.join(OUT, "w2_pilot.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("\nsaved w2_pilot.json")
