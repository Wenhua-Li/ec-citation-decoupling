# -*- coding: utf-8 -*-
"""B 广度层地图分析（方案 v3 §5；采集完成后本地计算，2026-10-18）。

输入：out/idsets/{field}.json（被引 id 集）、out/citing/{field}__{wtag}.jsonl.gz（施引文章）。
对 20 个采集方向（16 双 PASS + 4 存活单向），早窗 2011–2013 → 现代窗 2021–2023：

  逐源（共同支持 = 两窗均有文章）：
    E1 = 篇均跨引边数；E2 = 有跨引边论文比例；E3 = 跨引边占 referenced_works 份额（无参考文献计 0）
    相对变化 rel = m1/m0 − 1（零基源单列，不进聚合）
  聚合（构成权重 = 源在施引池的文章份额；固定权重聚合比的相对变化）：
    Laspeyres（早窗权重）/ Paasche（现代窗权重）/ pooled（池级直接比）
    宽度 = 100 ×（Paasche_rel − Laspeyres_rel）pp
  符号记分卡：逐源相对变化符号全一致 → 方向读数符号稳健（命题 2 反面）；混号 → 对合法重加权不稳健。
  gap（双 PASS 对）：gap_pp = 100 ×（反向池 rel − 正向池 rel），按三权重 × 三估计量分别给；
    pooled E1 gap 另给论文级分层重抽分位数（2,000 次）。
  分档（冻结阈值 100 条边/窗，NUMBERS 2026-10-18）：全部共同支持源两窗边数 ≥100 → full；
    池化两窗边数 ≥100 → e1_tier；否则 refused。逐源边数全部披露。
  逐源留一（full 档方向）：每剔一源重算 pooled/L/P 相对变化与宽度。
  不做来源级聚类重抽（3–5 源近退化，如实声明）。

种子纪律：基种子 20261018；方向种子 = 基种子 + 方向序号（不用 hash()，跨进程可复现）。
用法：python fieldmap.py            输出：out/fieldmap.json + 控制台摘要
"""
import gzip
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from anchors import S, WINDOWS, DOUBLE_PAIRS, SINGLE_DIRS  # noqa: E402

TIER_EDGES = 100  # 冻结阈值（NUMBERS 2026-10-18）
NBOOT = 2000
BOOT_CHUNK = 200
SEED = 20261018

ALL_DIRS = [(a, b) for a, b in DOUBLE_PAIRS] + [(b, a) for a, b in DOUBLE_PAIRS] + SINGLE_DIRS


def load_field_articles(field):
    """-> {wtag: {sid: [(id, refs-list), ...]}}"""
    per = {}
    for wtag in WINDOWS:
        path = os.path.join(HERE, "out", "citing", f"{field}__{wtag}.jsonl.gz")
        arts = {sid: [] for sid in S[field]}
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                arts[r["sid"]].append((r["id"], r["refs"]))
        per[wtag] = arts
    return per


def source_arrays(articles, target_set):
    """-> hits(int64), n_refs(int64)（逐篇文章）。"""
    h = np.zeros(len(articles), dtype=np.int64)
    n = np.zeros(len(articles), dtype=np.int64)
    for i, (_id, refs) in enumerate(articles):
        n[i] = len(refs)
        h[i] = sum(1 for w in refs if w.rsplit("/", 1)[-1] in target_set)
    return h, n


def estimands(h, n):
    e3 = float(np.mean(np.divide(h, n, out=np.zeros_like(h, dtype=float), where=n > 0))) if len(h) else 0.0
    return {"n_articles": int(len(h)), "edges": int(h.sum()),
            "refs_total": int(n.sum()), "with_edge": int((h > 0).sum()),
            "E1": round(float(h.mean()), 6) if len(h) else 0.0,
            "E2": round(float((h > 0).mean()), 6) if len(h) else 0.0, "E3": round(e3, 6)}


def rel(m0, m1):
    return None if m0 == 0 else round(m1 / m0 - 1.0, 6)


def sign_of(r):
    if r is None:
        return 0
    return 1 if r > 0 else (-1 if r < 0 else 0)


def weighted_rel(per_src, srcs, w0, w1, est):
    L0 = sum(w0[s] * per_src[s]["early"][est] for s in srcs) / (sum(w0[s] for s in srcs) or 1.0)
    L1 = sum(w0[s] * per_src[s]["modern"][est] for s in srcs) / (sum(w0[s] for s in srcs) or 1.0)
    P0 = sum(w1[s] * per_src[s]["early"][est] for s in srcs) / (sum(w1[s] for s in srcs) or 1.0)
    P1 = sum(w1[s] * per_src[s]["modern"][est] for s in srcs) / (sum(w1[s] for s in srcs) or 1.0)
    return L0, L1, P0, P1


def pooled_edges_articles(per_src, srcs, wtag):
    e = sum(per_src[s][wtag]["edges"] for s in srcs)
    a = sum(per_src[s][wtag]["n_articles"] for s in srcs)
    return e, a


def analyze_direction(citing, cited, arts_cache, idsets):
    if citing not in arts_cache:
        arts_cache[citing] = load_field_articles(citing)
    arts = arts_cache[citing]
    target = idsets[cited]
    per_src, harr = {}, {}
    for sid in S[citing]:
        per_src[sid] = {}
        for wtag in WINDOWS:
            h, n = source_arrays(arts[wtag][sid], target)
            per_src[sid][wtag] = estimands(h, n)
            harr[(sid, wtag)] = h
    support = [s for s in S[citing]
               if per_src[s]["early"]["n_articles"] > 0 and per_src[s]["modern"]["n_articles"] > 0]
    zero_base = [s for s in support if per_src[s]["early"]["edges"] == 0]
    usable = [s for s in support if per_src[s]["early"]["edges"] > 0]
    w0 = {s: per_src[s]["early"]["n_articles"] for s in usable}
    w1 = {s: per_src[s]["modern"]["n_articles"] for s in usable}
    scorecard = {}
    for est in ("E1", "E2", "E3"):
        signs = [sign_of(rel(per_src[s]["early"][est], per_src[s]["modern"][est])) for s in usable]
        pos = all(x > 0 for x in signs) if signs else False
        neg = all(x < 0 for x in signs) if signs else False
        scorecard[est] = {"signs": signs, "consistent": bool(pos or neg), "direction": "up" if pos else ("down" if neg else "mixed")}
    aggregates = {}
    # 池化水平：E1 = 总边/总文；E2 = 有边论文合计/总文；E3 = 总边/总参考文献
    pooled_edges = {}
    pooled_levels = {}
    for wtag in WINDOWS:
        e = sum(per_src[s][wtag]["edges"] for s in support)
        a = sum(per_src[s][wtag]["n_articles"] for s in support)
        we = sum(per_src[s][wtag]["with_edge"] for s in support)
        rt = sum(per_src[s][wtag]["refs_total"] for s in support)
        pooled_edges[wtag] = e
        pooled_levels[wtag] = {"E1": e / a if a else 0.0, "E2": we / a if a else 0.0,
                               "E3": e / rt if rt else 0.0}
    for est in ("E1", "E2", "E3"):
        if usable:
            L0, L1, P0, P1 = weighted_rel(per_src, usable, w0, w1, est)
            lr, pr = rel(L0, L1), rel(P0, P1)
            width = round(100.0 * ((P1 / P0) - (L1 / L0)), 4) if (L0 and P0) else None
        else:
            lr = pr = width = None
        pl0, pl1 = pooled_levels["early"][est], pooled_levels["modern"][est]
        aggregates[est] = {"laspeyres_rel": lr, "paasche_rel": pr,
                           "pooled_rel": rel(pl0, pl1) if (pl0 and pl1) else None,
                           "width_pp": width}
    src_ok = all(per_src[s][w]["edges"] >= TIER_EDGES for s in support for w in WINDOWS)
    tier = ("full" if (support and src_ok)
            else ("e1_tier" if (pooled_edges["early"] >= TIER_EDGES and pooled_edges["modern"] >= TIER_EDGES)
                  else "refused"))
    loo = {}
    if tier == "full" and len(support) > 2:
        for s_drop in support:
            keep = [s for s in support if s != s_drop]
            k0 = {s: per_src[s]["early"]["n_articles"] for s in keep if per_src[s]["early"]["edges"] > 0}
            k1 = {s: per_src[s]["modern"]["n_articles"] for s in keep if per_src[s]["early"]["edges"] > 0}
            ku = [s for s in keep if per_src[s]["early"]["edges"] > 0]
            L0, L1, P0, P1 = weighted_rel(per_src, ku, k0, k1, "E1")
            ke0, ka0 = pooled_edges_articles(per_src, keep, "early")
            ke1, ka1 = pooled_edges_articles(per_src, keep, "modern")
            loo[s_drop] = {"pooled_rel": rel(ke0 / ka0, ke1 / ka1) if (ka0 and ka1) else None,
                           "laspeyres_rel": rel(L0, L1), "paasche_rel": rel(P0, P1)}
    pooled_h = {w: np.concatenate([harr[(s, w)] for s in support]) if support else np.array([], dtype=np.int64)
                for w in WINDOWS}
    return {"per_source": per_src, "support": support, "zero_base_sources": zero_base,
            "scorecard": scorecard, "aggregates": aggregates, "pooled_edges": pooled_edges,
            "tier": tier, "loo_e1": loo, "_pooled_h": pooled_h}


def _finite(x):
    return x[np.isfinite(x)]


def boot_pooled_rel(h0, h1, seed):
    rng = np.random.default_rng(seed)
    reps_rel = []
    done = 0
    while done < NBOOT:
        r = min(BOOT_CHUNK, NBOOT - done)
        i0 = rng.integers(0, len(h0), (r, len(h0)))
        i1 = rng.integers(0, len(h1), (r, len(h1)))
        m0, m1 = h0[i0].mean(axis=1), h1[i1].mean(axis=1)
        reps_rel.append(np.divide(m1, m0, out=np.full_like(m1, np.nan), where=m0 > 0) - 1.0)
        done += r
    x = _finite(np.concatenate(reps_rel))
    if not len(x):
        return {}
    return {"q025": round(float(np.quantile(x, 0.025)), 6), "q50": round(float(np.quantile(x, 0.5)), 6),
            "q975": round(float(np.quantile(x, 0.975)), 6), "pos_share": round(float((x > 0).mean()), 4),
            "n_valid": int(len(x))}


def boot_pair_gap(hA0, hA1, hB0, hB1, seed):
    rng = np.random.default_rng(seed)
    gaps = []
    done = 0
    while done < NBOOT:
        r = min(BOOT_CHUNK, NBOOT - done)
        iA0 = rng.integers(0, len(hA0), (r, len(hA0)))
        iA1 = rng.integers(0, len(hA1), (r, len(hA1)))
        iB0 = rng.integers(0, len(hB0), (r, len(hB0)))
        iB1 = rng.integers(0, len(hB1), (r, len(hB1)))
        relA = np.divide(hA1[iA1].mean(axis=1), hA0[iA0].mean(axis=1),
                         out=np.full((r,), np.nan), where=hA0[iA0].mean(axis=1) > 0) - 1.0
        relB = np.divide(hB1[iB1].mean(axis=1), hB0[iB0].mean(axis=1),
                         out=np.full((r,), np.nan), where=hB0[iB0].mean(axis=1) > 0) - 1.0
        gaps.append(100.0 * (relB - relA))
        done += r
    x = _finite(np.concatenate(gaps))
    if not len(x):
        return {}
    return {"q025": round(float(np.quantile(x, 0.025)), 4), "q50": round(float(np.quantile(x, 0.5)), 4),
            "q975": round(float(np.quantile(x, 0.975)), 4), "pos_share": round(float((x > 0).mean()), 4),
            "n_valid": int(len(x))}


def main():
    idsets = {}
    for field in sorted({c for _, c in ALL_DIRS} | {c for c, _ in ALL_DIRS}):
        p = os.path.join(HERE, "out", "idsets", f"{field}.json")
        d = json.load(open(p, encoding="utf-8"))
        idsets[field] = set(d["ids"])
        print(f"idset {field}: {len(d['ids'])} works", flush=True)
    arts_cache = {}
    directions = {}
    for idx, (citing, cited) in enumerate(ALL_DIRS):
        print(f"analyzing {citing}->{cited} ...", flush=True)
        r = analyze_direction(citing, cited, arts_cache, idsets)
        r["bootstrap_pooled_e1"] = boot_pooled_rel(r["_pooled_h"]["early"], r["_pooled_h"]["modern"], SEED + idx) \
            if len(r["_pooled_h"]["early"]) else {}
        directions[f"{citing}->{cited}"] = r
    pair_gaps, pair_boot = {}, {}
    for pidx, (a, b) in enumerate(DOUBLE_PAIRS):
        fwd, rev = directions[f"{a}->{b}"], directions[f"{b}->{a}"]
        g = {}
        for est in ("E1", "E2", "E3"):
            for agg in ("laspeyres_rel", "paasche_rel", "pooled_rel"):
                f, rv = fwd["aggregates"][est][agg], rev["aggregates"][est][agg]
                g[f"{est}.{agg}"] = round(100.0 * (rv - f), 4) if (f is not None and rv is not None) else None
        pair_gaps[f"{a}<->{b}"] = g
        # 双向联合 gap 重抽：复用已算好的池化数组（_pooled_h 在 pair 循环后才剥离）
        pair_boot[f"{a}<->{b}"] = boot_pair_gap(fwd["_pooled_h"]["early"], fwd["_pooled_h"]["modern"],
                                                rev["_pooled_h"]["early"], rev["_pooled_h"]["modern"],
                                                SEED + 100 + pidx)
    for r in directions.values():
        r.pop("_pooled_h", None)
    out = {"design": {"windows": dict(WINDOWS), "tier_edges_threshold": TIER_EDGES,
                      "nboot": NBOOT, "seed_base": SEED,
                      "note": "共同支持=两窗均有文章；零基源单列；E3 无参考文献计 0；"
                              "符号稳健=逐源同号（命题2 反面）；gap=反向−正向（pp）；"
                              "来源级聚类重抽未做（3–5 源近退化）"},
           "directions": directions, "pair_gaps_pp": pair_gaps, "pair_gap_bootstrap_e1": pair_boot}
    path = os.path.join(HERE, "out", "fieldmap.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved:", path)
    for k, v in directions.items():
        e1 = v["aggregates"]["E1"]
        print(f"{k:46s} tier={v['tier']:8s} L={e1['laspeyres_rel']} P={e1['paasche_rel']} "
              f"pooled={e1['pooled_rel']} width={e1['width_pp']}pp sign={v['scorecard']['E1']['direction']}")


if __name__ == "__main__":
    main()
