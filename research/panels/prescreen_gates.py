# -*- coding: utf-8 -*-
"""采集前硬闸门 2+3 探针（方案 v3 §5，2026-10-18）。

闸门 2 = 冻结抽样规则后复验阈值边界方向（现代窗 2021–2023）：
  chemistry→chemical_engineering（5.5）、statistics↔computer_science（8.8/6.5）、
  mathematics→physics（8.8）、ecology→earth_science（6.0）、physics→mathematics（2.1，REFUSE 稳健性）。
  判定：与 v2 判定一致 -> 稳定；翻转 -> BORDERLINE（不作二元判定）。
闸门 3 = 早端点窗（2011–2013）密度预探针，覆盖采集池全部 20 方向（16 双 PASS + 4 存活单向）：
  判定：早窗 PASS -> 维持候选档；早窗 REFUSE -> 降为 E1 级候选（分析时按校准阈值定档）。

抽样规则（冻结，登记 NUMBERS）：年份分层随机抽样——每（源, 年）cursor 全翻 article id，
本地 random.Random(SEED) 无放回抽 k=min(50, n)；每方向前 2 锚源、每源 150 篇（50×3 年）；
候选总量与采样 id 全量落盘（out/gate_probe_results.json）可复现。种子 = 20261018 + 方向全局序号。
判据（沿用 v2 阈值）：E2_pool < 0.01 或 每源年均边 < 2.5 -> REFUSE。
端点窗对（冻结，登记 NUMBERS）：早窗 2011–2013 对现代窗 2021–2023（沿用 econ→psych 先例）。

用法：python prescreen_gates.py
输出：out/gate_probe_results.json（断点续跑：已完成探针跳过）
"""
import json
import os
import random
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from oa_client import _get, BASE, MAILTO  # noqa: E402

S = {  # 与 prescreen_pairs.py v2.1 完全一致（含三处死档换新）
    "economics": ["S23254222", "S203860005", "S95323914", "S95464858", "S88935262"],
    "psychology": ["S58854535", "S62013203", "S88198767", "S35223124"],
    "mathematics": ["S45918994", "S98347115", "S130224168", "S171170845"],
    "physics": ["S24807848", "S4210237713", "S105243760", "S164566984"],
    "materials": ["S99352657", "S64016596", "S143846845", "S135204980"],
    "chemistry": ["S111155417", "S67393510", "S184645833", "S191963794"],
    "chemical_engineering": ["S147177414", "S33892871", "S202680183"],
    "biology": ["S110447773", "S154343897", "S127916151", "S134668137"],
    "medicine": ["S49861241", "S172573765", "S4393917726", "S62468778"],
    "computer_science": ["S118992489", "S199944782", "S103482838"],
    "electrical_engineering": ["S68686220", "S4502562", "S168680287"],
    "neuroscience": ["S45757444", "S2298632", "S5555990"],
    "business": ["S117778295", "S143668711", "S206124708", "S33323087"],
    "sociology": ["S157620343", "S122471516", "S130611943"],
    "political_science": ["S176007004", "S90314269", "S95650557"],
    "ecology": ["S80967739", "S35917800", "S74970393"],
    "earth_science": ["S119230507", "S56162041", "S32973720"],
    "statistics": ["S119757635", "S4394736638", "S172180718"],
    "biomedical_engineering": ["S163807576", "S5240358", "S173145877"],
    "mechanical_engineering": ["S128368299", "S72716621", "S154368109"],
}
WINDOWS = {"early": ("2011-01-01", "2013-12-31"), "modern": ("2021-01-01", "2023-12-31")}
N_PER_YEAR = 50
N_PROBE = 2
SEED_BASE = 20261018
E2_MIN = 0.01
EDGES_PER_SRC_PER_YEAR_MIN = 2.5

GATE2 = [("chemistry", "chemical_engineering"), ("chemical_engineering", "chemistry"),
         ("statistics", "computer_science"), ("computer_science", "statistics"),
         ("mathematics", "physics"), ("ecology", "earth_science"), ("physics", "mathematics")]
V2_VERDICT = {"chemistry->chemical_engineering": "PASS", "chemical_engineering->chemistry": "PASS",
              "statistics->computer_science": "PASS", "computer_science->statistics": "PASS",
              "mathematics->physics": "PASS", "ecology->earth_science": "PASS",
              "physics->mathematics": "REFUSE"}
DOUBLE = [("physics", "materials"), ("materials", "physics"),
          ("chemistry", "chemical_engineering"), ("chemical_engineering", "chemistry"),
          ("biology", "medicine"), ("medicine", "biology"),
          ("computer_science", "electrical_engineering"), ("electrical_engineering", "computer_science"),
          ("neuroscience", "psychology"), ("psychology", "neuroscience"),
          ("economics", "business"), ("business", "economics"),
          ("sociology", "political_science"), ("political_science", "sociology"),
          ("statistics", "computer_science"), ("computer_science", "statistics")]
SINGLE = [("ecology", "earth_science"), ("biomedical_engineering", "medicine"),
          ("mathematics", "physics"), ("mechanical_engineering", "materials")]
GATE3 = DOUBLE + SINGLE

REF_CACHE = os.path.join(HERE, "out", "ref_source_cache.json")
ID_CACHE_DIR = os.path.join(HERE, "out", "id_cache")
os.makedirs(ID_CACHE_DIR, exist_ok=True)
_ref_src = {}
if os.path.exists(REF_CACHE):
    try:
        _ref_src.update(json.load(open(REF_CACHE, encoding="utf-8")))
    except Exception:
        pass


def resolve_sources(ids):
    out = {}
    todo = []
    for i in dict.fromkeys(ids):
        if i in _ref_src:
            out[i] = _ref_src[i]
        else:
            todo.append(i)
    for k in range(0, len(todo), 50):
        batch = todo[k:k + 50]
        url = (f"{BASE}/works?filter=openalex:{'|'.join(batch)}"
               f"&select=id,primary_location&per-page=50&mailto={MAILTO}")
        got = set()
        for r in _get(url).get("results", []):
            src = ((r.get("primary_location") or {}).get("source") or {})
            rid = r["id"].rsplit("/", 1)[-1]
            _ref_src[rid] = (src.get("id") or "").rsplit("/", 1)[-1]
            got.add(rid)
        for rid in batch:
            if rid not in got:
                _ref_src[rid] = ""
        out.update({i: _ref_src[i] for i in batch})
    json.dump(_ref_src, open(REF_CACHE, "w", encoding="utf-8"))
    return out


def year_ids(sid, year):
    """cursor 全翻某源某年的 article id（本地缓存，采集阶段复用）。"""
    cache = os.path.join(ID_CACHE_DIR, f"{sid}_{year}.json")
    if os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    ids, cursor = [], "*"
    while cursor:
        filt = (f"primary_location.source.id:{sid},type:article,"
                f"from_publication_date:{year}-01-01,to_publication_date:{year}-12-31")
        url = (f"{BASE}/works?filter={filt}&select=id&per-page=200&cursor="
               f"{urllib.parse.quote(cursor)}&mailto={MAILTO}")
        page = _get(url)
        ids += [r["id"].rsplit("/", 1)[-1] for r in page.get("results", [])]
        cursor = (page.get("meta") or {}).get("next_cursor")
    json.dump(ids, open(cache, "w", encoding="utf-8"))
    return ids


def fetch_works(ids):
    """按 id 批取 referenced_works（每批 50）。"""
    arts = []
    for k in range(0, len(ids), 50):
        batch = ids[k:k + 50]
        url = (f"{BASE}/works?filter=openalex:{'|'.join(batch)}"
               f"&select=id,referenced_works&per-page=50&mailto={MAILTO}")
        got = {}
        for r in _get(url).get("results", []):
            got[r["id"].rsplit("/", 1)[-1]] = r.get("referenced_works") or []
        for i in batch:
            arts.append(got.get(i))
    return arts


def probe(citing, cited, win_key, seed):
    """冻结抽样规则的密度探针：返回 per-source 与池化指标 + 采样 id 留痕。"""
    lo, hi = WINDOWS[win_key]
    years = [int(lo[:4]), int(lo[:4]) + 1, int(hi[:4])]
    target = set(S[cited])
    probes = []
    for sid in S[citing][:N_PROBE]:
        rng = random.Random(seed)
        sampled = []
        for y in years:
            ids = year_ids(sid, y)
            k = min(N_PER_YEAR, len(ids))
            sampled += rng.sample(ids, k) if k else []
        arts = [a for a in fetch_works(sampled) if a is not None]
        per_art = [list(a) if a else [] for a in arts]
        refs = [w.rsplit("/", 1)[-1] for r in per_art for w in r]
        src_of = resolve_sources(refs)
        hits = [sum(1 for w in r if src_of.get(w.rsplit("/", 1)[-1]) in target) for r in per_art]
        n = len(per_art)
        probes.append({"source": sid, "n_articles": n, "candidate_pool_note": "见 out/id_cache",
                       "E1_est": round(sum(hits) / max(1, n), 4),
                       "E2_est": round(sum(1 for h in hits if h) / max(1, n), 4),
                       "edges_per_year": round(sum(hits) / 3.0, 1),
                       "sampled_ids": sampled})
    ok = [p for p in probes if p["n_articles"] > 0]
    if not ok:
        return {"probes": probes, "verdict": "CHECK_SOURCE"}
    n_tot = sum(p["n_articles"] for p in ok)
    e2_pool = sum(p["E2_est"] * p["n_articles"] for p in ok) / max(1, n_tot)
    eps = sum(p["edges_per_year"] for p in ok) / len(ok)
    verdict = "REFUSE" if (e2_pool < E2_MIN or eps < EDGES_PER_SRC_PER_YEAR_MIN) else "PASS"
    return {"probes": [{k: v for k, v in p.items() if k != "sampled_ids"} for p in ok],
            "E2_pool": round(e2_pool, 4), "edges_per_year_per_source": round(eps, 1),
            "verdict": verdict, "sampled_ids": [p["sampled_ids"] for p in ok]}


path = os.path.join(HERE, "out", "gate_probe_results.json")
tasks = ([("gate2_modern", a, b, "modern") for a, b in GATE2]
         + [("gate3_early", a, b, "early") for a, b in GATE3])
result = {}
if os.path.exists(path):
    try:
        result = json.load(open(path, encoding="utf-8")).get("probes_done", {})
    except Exception:
        result = {}

for idx, (gate, citing, cited, win) in enumerate(tasks):
    key = f"{gate}:{citing}->{cited}"
    if key in result:
        print(f"[skip] {key}", flush=True)
        continue
    seed = SEED_BASE + idx
    try:
        r = probe(citing, cited, win, seed)
    except Exception as e:
        r = {"verdict": "ERROR", "error": str(e)[:200]}
    if gate == "gate2_modern":
        v2 = V2_VERDICT.get(f"{citing}->{cited}", "?")
        r["v2_verdict"] = v2
        if r["verdict"] in ("PASS", "REFUSE"):
            r["gate2"] = "stable" if r["verdict"] == v2 else "BORDERLINE"
        else:
            r["gate2"] = r["verdict"]
    else:
        r["gate3"] = "keep_tier" if r["verdict"] == "PASS" else "downgrade_e1_tier"
    result[key] = r
    slim = {k: v for k, v in r.items() if k != "sampled_ids"}
    print(key, json.dumps(slim, ensure_ascii=False), flush=True)
    json.dump({"design": {"sampling": "year-stratified random, k=min(50,n)/year, 2 probe sources x 3 years",
                          "seed_base": SEED_BASE, "windows": WINDOWS,
                          "thresholds": f"E2_pool<{E2_MIN} or edges/yr/src<{EDGES_PER_SRC_PER_YEAR_MIN}",
                          "note": "闸门 2+3 探针，不进正文数字；采样 id 留痕于本文件"},
               "probes_done": result},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved:", path)
