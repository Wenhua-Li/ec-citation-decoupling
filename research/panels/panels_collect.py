# -*- coding: utf-8 -*-
"""B 广度层采集（方案 v3 §5；闸门 2–4 全过后启动，2026-10-18）。

架构（本地求交，避免逐条引文解析）：
  阶段 A（被引侧 id 集）：每领域锚源（3–5 源，任意 type，to 2023-12-31）全量 work id
    -> out/idsets/{field}.json（含 per-source 计数 manifest）。跨引边判定 = 引用 id ∈ 目标领域 id 集，
    与预筛的"解析 primary_location.source.id ∈ 锚源集"语义一致。
  阶段 B（施引侧）：每（领域, 窗口）一次下载该领域全部锚源 type=article 文章
    （select=id,publication_year,referenced_works；按源分查询以免 primary_location 字段）
    -> out/citing/{field}__{wtag}.jsonl.gz。同一领域的多个方向复用同一份施引文件。
  窗口对（冻结）：early = 2011–2013，modern = 2021–2023。
  采集池（20 方向，v3 §5）：16 双 PASS 方向 + 4 存活单向；
  施引领域 19 个（earth_science 仅作被引侧）；被引领域 20 个。
预算：阶段 A 约 1.2–2 万页、阶段 B 约 0.1–0.15 万页；oa_client 密钥轮换自动处理 429。
断点续跑：按目标文件已存在且非 truncated 跳过（manifest 记录状态）。

用法：
  python panels_collect.py A     # 阶段 A（被引 id 集，长跑）
  python panels_collect.py B     # 阶段 B（施引文章）
  python panels_collect.py manifest  # 查看进度
"""
import gzip
import json
import os
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from anchors import S, WINDOWS  # noqa: E402  锚源与窗口单一来源
from oa_client import _get, BASE, MAILTO  # noqa: E402

CITING_FIELDS = ["physics", "materials", "chemistry", "chemical_engineering", "biology",
                 "medicine", "computer_science", "electrical_engineering", "neuroscience",
                 "psychology", "economics", "business", "sociology", "political_science",
                 "statistics", "mathematics", "ecology", "biomedical_engineering",
                 "mechanical_engineering"]
TARGET_FIELDS = sorted(S.keys())  # 20 个（含 earth_science）
IDSET_DIR = os.path.join(HERE, "out", "idsets")
CITING_DIR = os.path.join(HERE, "out", "citing")
MANIFEST = os.path.join(HERE, "out", "collect_manifest.json")
os.makedirs(IDSET_DIR, exist_ok=True)
os.makedirs(CITING_DIR, exist_ok=True)


def load_manifest():
    if os.path.exists(MANIFEST):
        return json.load(open(MANIFEST, encoding="utf-8"))
    return {}


def save_manifest(m):
    json.dump(m, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def iter_pages(filter_str, select):
    """cursor 生成器：逐页 yield results；空页毛刺按 RuntimeError 抛出由调用方登记。"""
    cursor, page_i = "*", 0
    while cursor:
        url = (f"{BASE}/works?filter={filter_str}&select={select}&per-page=200"
               f"&cursor={urllib.parse.quote(cursor)}&mailto={MAILTO}")
        page = _get(url)
        results = page.get("results", [])
        meta = page.get("meta") or {}
        if not results and meta.get("count", 0) > 0 and page_i == 0:
            raise RuntimeError(f"empty-first-page: {filter_str[:80]}")
        yield from results
        page_i += 1
        if page_i % 10 == 0:
            print(f"    ... {page_i} pages", flush=True)
        cursor = meta.get("next_cursor")


def _partial_path(kind, name):
    return os.path.join(HERE, "out", f"_partial_{kind}_{name}.json")


def _load_partial(kind, name):
    p = _partial_path(kind, name)
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return None


def _save_partial(kind, name, state):
    json.dump(state, open(_partial_path(kind, name), "w", encoding="utf-8"))


def _clear_partial(kind, name):
    p = _partial_path(kind, name)
    if os.path.exists(p):
        os.remove(p)


def phase_a(deadline=None, fields=None):
    """被引 id 集（页级断点：_partial_idset_{field}.json 存 cursor+已收 id）。fields 可指定子序。"""
    m = load_manifest()
    for field in (fields or TARGET_FIELDS):
        if m.get(f"idset:{field}") == "done":
            print(f"[skip] idset {field}", flush=True)
            continue
        if deadline and time.time() > deadline:
            print(f"[deadline] phase_a stops before {field}", flush=True)
            return
        ids, per_src = [], {}
        state = _load_partial("idset", field)
        sids = S[field]
        start_idx, cursor = (state["src_idx"], state["cursor"]) if state else (0, "*")
        if state:
            ids, per_src = state["ids"], state["per_src"]
            print(f"  [resume] {field} at source #{start_idx} cursor={'yes' if cursor != '*' else '*'}", flush=True)
        try:
            for i in range(start_idx, len(sids)):
                sid = sids[i]
                n0 = len(ids)
                while cursor:
                    if deadline and time.time() > deadline:
                        _save_partial("idset", field, {"src_idx": i, "cursor": cursor,
                                                       "ids": ids, "per_src": per_src})
                        print(f"[deadline] {field}/{sid} checkpoint saved", flush=True)
                        return
                    filt = (f"primary_location.source.id:{sid},"
                            "to_publication_date:2023-12-31")
                    url = (f"{BASE}/works?filter={filt}&select=id&per-page=200"
                           f"&cursor={urllib.parse.quote(cursor)}&mailto={MAILTO}")
                    page = _get(url)
                    results = page.get("results", [])
                    meta = page.get("meta") or {}
                    if not results and meta.get("count", 0) > 0 and cursor == "*":
                        raise RuntimeError(f"empty-first-page: {filt[:80]}")
                    ids += [r["id"].rsplit("/", 1)[-1] for r in results]
                    cursor = meta.get("next_cursor")
                    if len(ids) % 4000 < 200:
                        _save_partial("idset", field, {"src_idx": i, "cursor": cursor,
                                                       "ids": ids, "per_src": per_src})
                per_src[sid] = len(ids) - n0
                print(f"  {field}/{sid}: {per_src[sid]} works", flush=True)
                cursor = "*"
            json.dump({"field": field, "ids": ids, "per_source": per_src},
                      open(os.path.join(IDSET_DIR, f"{field}.json"), "w", encoding="utf-8"))
            _clear_partial("idset", field)
            m[f"idset:{field}"] = "done"
            save_manifest(m)
        except Exception as e:
            m[f"idset:{field}"] = f"error: {str(e)[:150]}"
            save_manifest(m)
            print(f"[ERR] idset {field}: {e}", flush=True)


def phase_b(deadline=None):
    """施引文章（页级断点：_partial_citing_{field}__{wtag}.json）。"""
    m = load_manifest()
    for field in CITING_FIELDS:
        for wtag, (lo, hi) in WINDOWS.items():
            key = f"citing:{field}__{wtag}"
            if str(m.get(key, "")).startswith("done"):
                print(f"[skip] {key}", flush=True)
                continue
            if deadline and time.time() > deadline:
                print(f"[deadline] phase_b stops before {key}", flush=True)
                return
            path = os.path.join(CITING_DIR, f"{field}__{wtag}.jsonl.gz")
            state = _load_partial("citing", f"{field}__{wtag}")
            sids = S[field]
            start_idx, cursor, n = (state["src_idx"], state["cursor"], state["n"]) if state else (0, "*", 0)
            mode = "at" if state else "wt"  # 无配套断点状态时重建，防旧失败残留重复
            try:
                with gzip.open(path, mode, encoding="utf-8") as f:
                    for i in range(start_idx, len(sids)):
                        sid = sids[i]
                        n0 = n
                        while cursor:
                            if deadline and time.time() > deadline:
                                _save_partial("citing", f"{field}__{wtag}",
                                              {"src_idx": i, "cursor": cursor, "n": n})
                                print(f"[deadline] {key} checkpoint saved ({n} articles)", flush=True)
                                return
                            filt = (f"primary_location.source.id:{sid},type:article,"
                                    f"from_publication_date:{lo},to_publication_date:{hi}")
                            url = (f"{BASE}/works?filter={filt}&select=id,publication_year,referenced_works"
                                   f"&per-page=200&cursor={urllib.parse.quote(cursor)}&mailto={MAILTO}")
                            page = _get(url)
                            for r in page.get("results", []):
                                f.write(json.dumps({"sid": sid,
                                                    "id": r["id"].rsplit("/", 1)[-1],
                                                    "y": r.get("publication_year"),
                                                    "refs": r.get("referenced_works") or []},
                                                   ensure_ascii=False) + "\n")
                                n += 1
                            cursor = (page.get("meta") or {}).get("next_cursor")
                            if n % 2000 < 200:
                                _save_partial("citing", f"{field}__{wtag}",
                                              {"src_idx": i, "cursor": cursor, "n": n})
                        print(f"  {field}/{wtag}/{sid}: {n - n0} articles", flush=True)
                        cursor = "*"
                _clear_partial("citing", f"{field}__{wtag}")
                m[key] = f"done ({n} articles)"
                save_manifest(m)
            except Exception as e:
                m[key] = f"error: {str(e)[:150]}"
                save_manifest(m)
                print(f"[ERR] {key}: {e}", flush=True)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "manifest"
    if arg == "A":
        phase_a()
    elif arg == "B":
        phase_b()
    else:
        m = load_manifest()
        for k in sorted(m):
            print(f"{k:60s} {m[k]}")
