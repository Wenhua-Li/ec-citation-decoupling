# -*- coding: utf-8 -*-
"""W1 mini-pilot（PLAN v3 第四节）：OpenAlex 对齐试验——用一家 A 类期刊实测定夺全景路线。

步骤：
  1) OpenAlex API 找 IEEE Transactions on Evolutionary Computation 的 source id
  2) 拉 2020-2025 该刊 works（分页，select 最小字段集：doi/title/publication_year/referenced_works/cited_by_count）
  3) 与本库逐篇对齐（DOI 小写规范化），报告：
     - OpenAlex 覆盖篇数 / 有 DOI 比例 / 与本库 DOI 命中率
     - 命中论文的参考文献数量对比（OpenAlex referenced_works vs 本库 refs_out 总数）——检验外库参考列表质量
  4) 输出 research/nature/out/openalex_pilot.json
网络不可达则明确报告并退出（pilot 结论 = 当前环境需代理/离线快照路线）。
"""
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ecdb

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

MAILTO = "ecmap.project@outlook.com"  # OpenAlex polite pool
BASE = "https://api.openalex.org"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": f"ecmap-pilot ({MAILTO})"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


try:
    src = get(f"{BASE}/sources?search={urllib.parse.quote('IEEE Transactions on Evolutionary Computation')}&mailto={MAILTO}")
    sid = src["results"][0]["id"].rsplit("/", 1)[-1]
    print(f"source id: {sid}  ({src['results'][0]['display_name']})")
except Exception as e:
    print(f"NETWORK/QUERY FAILED: {type(e).__name__}: {e}")
    print("pilot conclusion: OpenAlex API unreachable from this environment — W1 需代理或离线快照路线")
    sys.exit(2)

works = []
for year in range(2020, 2026):
    cursor = "*"
    n_this_year = 0
    while True:
        url = (f"{BASE}/works?filter=primary_location.source.id:{sid},publication_year:{year}"
               f"&select=doi,title,publication_year,referenced_works,cited_by_count"
               f"&per-page=200&cursor={cursor}&mailto={MAILTO}")
        page = get(url)
        works.extend(page["results"])
        n_this_year += len(page["results"])
        cursor = (page.get("meta") or {}).get("next_cursor")
        if not cursor or n_this_year >= 1000:
            break
    print(f"year {year}: {n_this_year} works")

our_dois = set()
for r in ecdb.raw_sql(
    "SELECT p.doi FROM papers p JOIN paper_sources s USING(accession_no) WHERE p.doi IS NOT NULL", max_rows=300000
)["rows"]:
    our_dois.add(r["doi"].lower())

matched = [w for w in works if w.get("doi")]
hit = [w for w in matched if w["doi"].lower().replace("https://doi.org/", "") in our_dois]

# 参考文献数量对比（命中样本）
refcmp = []
for w in hit[:400]:
    doi = w["doi"].lower().replace("https://doi.org/", "")
    row = ecdb.raw_sql(
        "SELECT COUNT(DISTINCT cited_doi) n FROM paper_refs_out r "
        "JOIN papers p ON p.accession_no = r.accession_no WHERE p.doi = ? AND r.cited_doi IS NOT NULL",
        params=(doi,), max_rows=1,
    )["rows"][0]
    refcmp.append({"doi": doi, "oa_refs": len(w.get("referenced_works") or []), "our_refs": row["n"]})

oa_only = [w for w in matched if w not in hit]
out = {
    "source_id": sid,
    "oa_total": len(works),
    "oa_with_doi": len(matched),
    "doi_hit_in_our_lib": len(hit),
    "hit_rate": round(len(hit) / len(matched), 4) if matched else None,
    "oa_only_sample_titles": [w.get("title", "")[:90] for w in oa_only[:20]],
    "ref_count_compare_sample": refcmp[:200],
    "ref_count_median_oa": sorted(x["oa_refs"] for x in refcmp)[len(refcmp) // 2] if refcmp else None,
    "ref_count_median_ours": sorted(x["our_refs"] for x in refcmp)[len(refcmp) // 2] if refcmp else None,
}
with open(os.path.join(OUT, "openalex_pilot.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in out.items() if k not in ("ref_count_compare_sample", "oa_only_sample_titles")}, ensure_ascii=False, indent=1))
