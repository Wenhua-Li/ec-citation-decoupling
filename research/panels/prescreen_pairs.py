# -*- coding: utf-8 -*-
"""B 广度层密度预筛（v2，2026-10-17 评审修订）：采样估计每个候选领域对的双向跨引密度，按冻结三态阈值的估计版判淘汰。

v1 -> v2 变更（方案评审修正，三处）：
  1) 采样窗口 2011–2013 -> 2021–2023：与主分析端点窗（2021→2024）对齐；参考文献表十年间变长，
     旧窗口密度不代表现窗口（v1 首探 physics->materials 即在错位窗口上 REFUSE，作废重探）。
  2) 探针源 1 个 -> 2 个：v1 单源探针系统性低估面板密度约"源数"倍，等于按单源判全家死刑。
  3) 阈值按源折算并显式登记：E2 阈值不变（施引侧源数不改变参与率，参与率由被引侧锚源集决定）；
     年均边阈值改为"每探针源 >= 2.5 条/年"。换算链：v1 单源 5 条/年 隐含 4 源面板约 20 条/年；
     v2 = 每源 2.5 条/年 => 2 源池化 5 条/年 => 4 源面板约 10 条/年——判据较 v1 面板级显式放宽一倍，
     理由：逐源记分卡只需窗口端点非零水平，三年窗累计约 30 条/方向即可支撑符号判定，20 条/年属过苛。

方法（估计用，不进正文数字）：每方向取施引侧前 2 个锚源 2021–2023 窗 type=article 各前 150 篇，
批解析其 referenced_works 的 primary_location.source.id，命中对侧锚源集计为跨引边。
判据（冻结三态的估计版）：E2_pool < 0.01 或 每源年均边 < 2.5 -> REFUSE（登记，不采集）。

用法：python prescreen_pairs.py
输出：out/pair_prescreen.json（v1 设计与结果整包移入 superseded_v1 字段留档，审计链不断）
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from anchors import S  # noqa: E402  锚源字典单一来源（含三处死档换新注记，见 anchors.py）
from oa_client import _get, BASE, MAILTO  # noqa: E402

PAIRS = [("physics", "materials"), ("chemistry", "chemical_engineering"),
         ("biology", "medicine"), ("computer_science", "electrical_engineering"),
         ("neuroscience", "psychology"), ("economics", "business"),
         ("sociology", "political_science"), ("ecology", "earth_science"),
         ("statistics", "computer_science"), ("biomedical_engineering", "medicine"),
         ("mathematics", "physics"), ("mechanical_engineering", "materials")]
N_SAMPLE = 150
N_PROBE = 2
WINDOW = ("2021-01-01", "2023-12-31")
E2_MIN = 0.01
EDGES_PER_SRC_PER_YEAR_MIN = 2.5


def sample_works(sid):
    filt = (f"primary_location.source.id:{sid},type:article,"
            f"from_publication_date:{WINDOW[0]},to_publication_date:{WINDOW[1]}")
    url = (f"{BASE}/works?filter={filt}&select=id,referenced_works&per-page={N_SAMPLE}&mailto={MAILTO}")
    return _get(url).get("results", [])


REF_CACHE = os.path.join(HERE, "out", "ref_source_cache.json")
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
        for rid in batch:  # 死 id 缓存为空串，防反复重查
            if rid not in got:
                _ref_src[rid] = ""
        out.update({i: _ref_src[i] for i in batch})
    json.dump(_ref_src, open(REF_CACHE, "w", encoding="utf-8"))
    return out


def probe_one(citing_sid, target):
    arts = sample_works(citing_sid)
    if not arts:  # 死档/错档防护：0 篇不参与平均，方向判 CHECK_SOURCE 人工修锚
        return {"source": citing_sid, "n_articles": 0, "flag": "SOURCE_ZERO"}
    per_art = [a.get("referenced_works") or [] for a in arts]
    refs = [w for r in per_art for w in r]
    src_of = resolve_sources([w.rsplit("/", 1)[-1] for w in refs])
    hits = [sum(1 for w in r if src_of.get(w.rsplit("/", 1)[-1]) in target) for r in per_art]
    n = max(1, len(arts))
    return {"source": citing_sid, "n_articles": len(arts),
            "E1_est": round(sum(hits) / n, 4), "E2_est": round(sum(1 for h in hits if h) / n, 4),
            "edges_per_year": round(sum(hits) / 3.0, 1)}


def prescreen(citing, cited):
    target = set(S[cited])
    probes = [probe_one(sid, target) for sid in S[citing][:N_PROBE]]
    ok = [p for p in probes if "flag" not in p]
    if not ok:
        return {"probes": probes, "verdict": "CHECK_SOURCE"}
    n_tot = sum(p["n_articles"] for p in ok)
    e1_pool = sum(p["E1_est"] * p["n_articles"] for p in ok) / max(1, n_tot)
    e2_pool = sum(p["E2_est"] * p["n_articles"] for p in ok) / max(1, n_tot)
    eps_mean = sum(p["edges_per_year"] for p in ok) / len(ok)
    verdict = "REFUSE" if (e2_pool < E2_MIN or eps_mean < EDGES_PER_SRC_PER_YEAR_MIN) else "PASS"
    if len(ok) < len(probes):
        verdict = "CHECK_SOURCE"
    return {"probes": probes, "E1_pool": round(e1_pool, 4), "E2_pool": round(e2_pool, 4),
            "edges_per_year_per_source": round(eps_mean, 1), "verdict": verdict}


path = os.path.join(HERE, "out", "pair_prescreen.json")
os.makedirs(os.path.dirname(path), exist_ok=True)

design = {"sample": f"first {N_SAMPLE} articles x first {N_PROBE} sources, "
                    f"{WINDOW[0][:4]}-{WINDOW[1][:4]} window",
          "thresholds": f"E2_pool < {E2_MIN} or edges/year/source < {EDGES_PER_SRC_PER_YEAR_MIN} -> REFUSE",
          "note": "go/no-go 估计，不进正文数字；v2 修订三处见脚本 docstring"}

result, superseded_v1 = {}, None
if os.path.exists(path):  # v1 结果（2011-2013 单源设计）整包作废留档，v2 从头跑
    try:
        old = json.load(open(path, encoding="utf-8"))
        if "2011-2013" in old.get("design", {}).get("sample", ""):
            superseded_v1 = old
        else:
            result = old.get("directions", {})
    except Exception:
        result = {}

for a, b in PAIRS:
    for x, y in ((a, b), (b, a)):
        key = f"{x}->{y}"
        if key in result and result[key].get("verdict") in ("PASS", "REFUSE"):
            print(f"[skip] {key}", flush=True)
            continue
        try:
            result[key] = prescreen(x, y)
        except Exception as e:
            result[key] = {"verdict": "ERROR", "error": str(e)[:200]}
        print(key, json.dumps(result[key], ensure_ascii=False), flush=True)
        payload = {"design": design, "directions": result}
        if superseded_v1 is not None:
            payload["superseded_v1"] = superseded_v1
        json.dump(payload, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved:", path)
