# -*- coding: utf-8 -*-
"""control_theory 边界一致性——规范化重跑（v2，2026-10-15）。

背景（项目登记的数据缺陷，见 research/panels/out/control_theory_boundary_fix.json）：
  - 原 W1 边界查（research/nature/out/boundary_consistency.json）control_theory 行
    盲取 topics 搜索首命中 T11542"Behavioral Health and Interventions"并标 pass:true；
  - control_boundary_fix.py 以"名称含 control"的语义规则重解析为 T10820
    "Fuzzy Logic and Control Systems"，但仍是关键词搜索规则、只用 topics.id 过滤、
    只报单刊水平相关。
本脚本按**先冻结的规程**规范化重跑（不覆盖以上两份旧输出、不写数据库、不写本年缓存）：

  ① 主题候选：两本锚定刊各自 primary_topic.id 的 group_by 前十（全库年份），保存候选表；
  ② 选择规则（确定性、可复现）：两刊前 3 交集唯一 → 选之（common_top3_unique）；
     交集不唯一但两刊 argmax 一致 → 选 argmax（common_top3+consistent_argmax）；
     交集为空且 argmax 一致 → 选 argmax（consistent_argmax）；
     其余 → INDETERMINATE（不产出主结果、不做事后择优）；
  ③ 统一口径：primary_topic.id 过滤、年份窗 1990–2024、最小锚点 50 篇/年、
     最少 20 个合格年、主题曲线窗内总量 >= 200（三单位同口径）；
  ④ 主口径 = 合并两刊锚点 vs 合并两刊主题曲线；逐刊同口径附列；另附两个敏感性窗；
  ⑤ 相关系数 = 并列平均秩 Spearman（水平 / 一阶差分 / 线性去趋势 三式齐出）；
  ⑥ 状态区分：BLOCKED（API 预算/网络）/ API_EMPTY（API 返回空）/
     INDETERMINATE（选择不确定）/ DATA_INSUFFICIENT（样本不足）/ PASS / FAIL（科学判定，
     阈值 0.8，沿用登记口径）。任何阻塞只留错误详情，不伪造任何数值。

运行（项目根目录）：python research/panels/control_boundary_v2.py
自检（不访问 API）：python research/panels/control_boundary_v2.py --selftest
输出：research/panels/out/control_boundary_v2.json
      research/panels/out/control_boundary_v2_candidates.json
退出码：0 = 已产出确定状态（PASS/FAIL/INDETERMINATE/API_EMPTY/DATA_INSUFFICIENT）；
        2 = BLOCKED（API 阻塞，输出文件内含错误详情）；1 = 内部错误。
"""
import json
import os
import re
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))         # .../research/panels
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))    # 项目根（脚本自身向上两级）
OUT_DIR = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
from oa_client import _get, BASE, MAILTO, API_KEYS  # noqa: E402

# ---------------------------------------------------------------- 冻结规格
JOURNALS = [
    {"journal": "Automatica", "sid": "S51360982"},
    {"journal": "IEEE Transactions on Automatic Control", "sid": "S184954342"},
]
TOP_N = 10                        # 候选：每刊 group_by 前十
TOP_K = 3                         # 选择规则用前 3
Y0, Y1 = 1990, 2024               # 主年份窗（统一；2025 右删失排除）
EDGE_WINDOW = (1990, 2023)        # 敏感性：去末年
RECENT_WINDOW = (2000, 2024)      # 敏感性：近段
MIN_ANCHOR_PER_YEAR = 50          # 合格年：该单位锚点年度量 >= 50（沿用登记口径）
MIN_YEARS = 20                    # 合格年数下限
MIN_DIFF_PAIRS = 10               # 一阶差分年对下限
MIN_TOPIC_TOTAL = 200             # 主题曲线窗内总量下限
RHO_PASS = 0.8                    # 科学判定阈值（沿用登记口径）
# 两次旧口径选中的主题（审计用：看它们是否在新候选表内）
LEGACY_TOPICS = {
    "T10820": "control_boundary_fix.py 语义规则选中（Fuzzy Logic and Control Systems）",
    "T11542": "W1 原版盲选首命中（Behavioral Health and Interventions）",
}
LOCAL_PANEL = os.path.join(ROOT, "research", "nature", "out", "w1_panels.json")
OUT_MAIN = os.path.join(OUT_DIR, "control_boundary_v2.json")
OUT_CAND = os.path.join(OUT_DIR, "control_boundary_v2_candidates.json")

SPEC_FROZEN = {
    "candidates": f"每刊 primary_location.source.id 过滤 + group_by=primary_topic.id 前十（全库年份，不设窗）",
    "selection_rule": ("前3交集唯一 -> common_top3_unique；交集不唯一且两刊 argmax 一致 -> "
                       "common_top3+consistent_argmax；交集空且 argmax 一致 -> consistent_argmax；"
                       "其余 INDETERMINATE（不事后择优）"),
    "topic_filter": "primary_topic.id（两阶段一致）",
    "year_window_main": [Y0, Y1],
    "year_window_sensitivity": {"edge_drop_last_year": list(EDGE_WINDOW), "post_2000": list(RECENT_WINDOW)},
    "min_anchor_per_year": MIN_ANCHOR_PER_YEAR,
    "min_years": MIN_YEARS,
    "min_diff_pairs": MIN_DIFF_PAIRS,
    "min_topic_total": MIN_TOPIC_TOTAL,
    "anchor_definition": "该单位所有 works 的 publication_year 年度量（无类型过滤，含日期窗；与 w1_panels.json total 同定义）",
    "anchor_source": "OpenAlex 当次快照（同日抓取；本地 w1_panels.json 仅作交叉核验）",
    "main_unit": "pooled = 两刊锚点逐年和 / 两刊主题曲线逐年和",
    "rho": "并列平均秩 Spearman；水平 / 一阶差分（相邻合格年）/ 线性去趋势",
    "pass_threshold": RHO_PASS,
}

API_CALLS = []


def utcnow():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def api_get(url, purpose):
    """_get 包装：记录调用与失败详情（URL 本身不含 api_key，由 oa_client 内部注入）。"""
    rec = {"purpose": purpose, "url": url, "t": utcnow()}
    try:
        r = _get(url)
    except BaseException as e:  # RuntimeError/HTTPError/URLError 等一律记录后上抛
        rec["status"] = "ERROR"
        rec["error"] = f"{type(e).__name__}: {e}"
        API_CALLS.append(rec)
        raise
    rec["status"] = "OK"
    rec["n_groups_or_results"] = len(r.get("group_by", r.get("results", [])))
    API_CALLS.append(rec)
    return r


def year_groups(url, purpose):
    r = api_get(url, purpose)
    return {int(g["key"]): g["count"] for g in r.get("group_by", [])
            if str(g.get("key", "")).isdigit()}


# ---------------------------------------------------------------- 统计
def avg_ranks(v):
    """并列平均秩（ties -> average rank）。"""
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman_avg(xs, ys):
    """并列平均秩 Spearman；任一侧为常数序列（秩方差 0）时返回 None。"""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    rx, ry = avg_ranks(xs), avg_ranks(ys)
    mx = sum(rx) / len(rx)
    my = sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None


def ols_resid(years, vals):
    """对年份做一元线性 OLS，返回残差（去趋势）。"""
    n = len(years)
    xm = sum(years) / n
    ym = sum(vals) / n
    sxx = sum((x - xm) ** 2 for x in years)
    if sxx == 0:
        return None
    b = sum((x - xm) * (v - ym) for x, v in zip(years, vals)) / sxx
    a = ym - b * xm
    return [v - (a + b * x) for x, v in zip(years, vals)]


def window_result(anchor, topic, y0, y1):
    """单位 × 窗口：水平 / 一阶差分 / 去趋势三式 Spearman + 样本充分性判定。"""
    res = {"window": [y0, y1], "status": "OK", "reason": None,
           "anchor_total": sum(anchor.get(y, 0) for y in range(y0, y1 + 1)),
           "topic_total": sum(topic.get(y, 0) for y in range(y0, y1 + 1)),
           "n_years_level": None, "n_pairs_diff": None,
           "rho_level": None, "rho_first_diff": None, "rho_detrended": None,
           "notes": []}
    if res["topic_total"] < MIN_TOPIC_TOTAL:
        res.update(status="DATA_INSUFFICIENT",
                   reason=f"主题曲线窗内总量 {res['topic_total']} < {MIN_TOPIC_TOTAL}")
        return res
    years = [y for y in range(y0, y1 + 1) if anchor.get(y, 0) >= MIN_ANCHOR_PER_YEAR]
    res["n_years_level"] = len(years)
    if len(years) < MIN_YEARS:
        res.update(status="DATA_INSUFFICIENT",
                   reason=f"合格年份（锚点 >= {MIN_ANCHOR_PER_YEAR}）{len(years)} < {MIN_YEARS}")
        return res
    A = [anchor.get(y, 0) for y in years]
    T = [topic.get(y, 0) for y in years]
    res["rho_level"] = spearman_avg(A, T)
    ys = set(years)
    dA = [anchor.get(y + 1, 0) - anchor.get(y, 0) for y in years if (y + 1) in ys]
    dT = [topic.get(y + 1, 0) - topic.get(y, 0) for y in years if (y + 1) in ys]
    res["n_pairs_diff"] = len(dA)
    if len(dA) >= MIN_DIFF_PAIRS:
        res["rho_first_diff"] = spearman_avg(dA, dT)
    else:
        res["notes"].append(f"一阶差分年对 {len(dA)} < {MIN_DIFF_PAIRS}，不予计算")
    rA, rT = ols_resid(years, A), ols_resid(years, T)
    if rA and rT:
        res["rho_detrended"] = spearman_avg(rA, rT)
    if res["rho_level"] is None:
        res["notes"].append("水平相关不可计算（某一侧为常数序列）")
    return res


# ---------------------------------------------------------------- 阶段 1：候选
def fetch_candidates():
    out = {}
    for j in JOURNALS:
        url = (f"{BASE}/works?filter=primary_location.source.id:{j['sid']}"
               f"&group_by=primary_topic.id&per-page={TOP_N}&mailto={MAILTO}")
        r = api_get(url, f"candidates:{j['journal']}")
        groups = r.get("group_by", [])
        rows, other = [], []
        for g in groups:
            key = str(g.get("key", ""))
            tid = key.rsplit("/", 1)[-1]
            row = {"topic_id": tid, "display_name": g.get("display_name"), "count": g.get("count")}
            (rows if re.match(r"^T\d+$", tid) else other).append(row)
        rows.sort(key=lambda r_: (-r_["count"], r_["topic_id"]))
        for i, r_ in enumerate(rows):
            r_["rank"] = i + 1
        out[j["journal"]] = {"source_id": j["sid"], "top": rows[:TOP_N],
                             "non_topic_groups": other, "empty": len(groups) == 0}
    return out


def resolve_topic_names(topic_ids):
    """批量解析主题 display_name（仅展示用；失败不阻断，选择只用 id）。"""
    ids = [t for t in dict.fromkeys(topic_ids) if t]
    names, warn = {}, None
    for k in range(0, len(ids), 50):
        batch = ids[k:k + 50]
        url = (f"{BASE}/topics?filter=openalex:{'|'.join(batch)}"
               f"&per-page=50&select=id,display_name&mailto={MAILTO}")
        try:
            r = api_get(url, "topic_names")
        except Exception as e:  # 名称缺失不改变选择与统计
            warn = f"主题名称解析失败（仅缺 display_name，不影响选择）：{type(e).__name__}: {e}"
            break
        for t in r.get("results", []):
            names[t["id"].rsplit("/", 1)[-1]] = t.get("display_name")
    return names, warn


def select_topic(cand):
    """确定性选择规则；不唯一且无一致 argmax 时 certain=False（-> INDETERMINATE）。"""
    j1, j2 = JOURNALS[0]["journal"], JOURNALS[1]["journal"]
    t1 = [r["topic_id"] for r in cand[j1]["top"][:TOP_K]]
    t2 = [r["topic_id"] for r in cand[j2]["top"][:TOP_K]]
    common = [t for t in t1 if t in set(t2)]
    am1 = t1[0] if t1 else None
    am2 = t2[0] if t2 else None
    sel = {"top3": {j1: t1, j2: t2}, "argmax": {j1: am1, j2: am2},
           "common_top3": common, "argmax_agreement": bool(am1) and am1 == am2,
           "certain": False, "rule": None, "topic_id": None,
           "flags": [], "reasons": [], "legacy_audit": {}}
    for tid, why in LEGACY_TOPICS.items():
        sel["legacy_audit"][tid] = {"desc": why}
        for name in (j1, j2):
            hit = next((r for r in cand[name]["top"] if r["topic_id"] == tid), None)
            sel["legacy_audit"][tid][name] = None if hit is None else f"rank {hit['rank']}"
    if not t1 or not t2:
        sel["reasons"].append("候选表为空，无法选择（见状态 API_EMPTY）")
        return sel
    if len(common) == 1:
        sel.update(certain=True, rule="common_top3_unique", topic_id=common[0])
    elif len(common) > 1 and sel["argmax_agreement"] and am1 in common:
        sel.update(certain=True, rule="common_top3+consistent_argmax", topic_id=am1)
        sel["flags"].append(f"前3交集含 {len(common)} 项，由一致 argmax 收敛")
    elif not common and sel["argmax_agreement"]:
        sel.update(certain=True, rule="consistent_argmax", topic_id=am1)
    else:
        sel["reasons"].append(
            f"选择不确定：前3交集={common or '空'}，两刊 argmax={am1}/{am2}"
            f"（{'一致但与交集无解' if sel['argmax_agreement'] else '不一致'}）；"
            f"按冻结规则输出 INDETERMINATE，不做事后择优")
        return sel
    if not sel["argmax_agreement"]:
        sel["flags"].append("argmax_disagreement：规则唯一选定，但两刊首位主题不同，解释须谨慎")
    return sel


# ---------------------------------------------------------------- 阶段 2：曲线
def fetch_curves(topic_id, partial):
    """取同日快照的锚点曲线与主题曲线（统一 primary_topic.id + 年份窗）；失败时 partial 保留已取部分。"""
    window = f",from_publication_date:{Y0}-01-01,to_publication_date:{Y1}-12-31"
    partial["anchor"], partial["topic"] = {}, {}
    for j in JOURNALS:
        sid, name = j["sid"], j["journal"]
        partial["anchor"][name] = year_groups(
            f"{BASE}/works?filter=primary_location.source.id:{sid}{window}"
            f"&group_by=publication_year&per-page=200&mailto={MAILTO}", f"anchor:{name}")
        partial["topic"][name] = year_groups(
            f"{BASE}/works?filter=primary_location.source.id:{sid},primary_topic.id:{topic_id}{window}"
            f"&group_by=publication_year&per-page=200&mailto={MAILTO}", f"topic_curve:{name}")
    names = [j["journal"] for j in JOURNALS]
    partial["anchor"]["pooled"] = {y: sum(partial["anchor"][n].get(y, 0) for n in names)
                                   for y in range(Y0, Y1 + 1)}
    partial["topic"]["pooled"] = {y: sum(partial["topic"][n].get(y, 0) for n in names)
                                  for y in range(Y0, Y1 + 1)}
    return partial


def local_crosscheck(anchors):
    """与本地 w1_panels.json 锚点交叉核验（索引漂移量 + 两快照秩相关）。"""
    out = {"available": False, "path": "research/nature/out/w1_panels.json", "note": None, "per_journal": {}}
    if not os.path.exists(LOCAL_PANEL):
        out["note"] = "本地面板文件不存在，跳过交叉核验"
        return out
    try:
        with open(LOCAL_PANEL, encoding="utf-8") as f:
            panel = json.load(f).get("control_theory", {})
        by_sid = {v.get("source_id"): (k, v) for k, v in panel.items()}
    except Exception as e:
        out["note"] = f"本地面板读取失败：{type(e).__name__}: {e}"
        return out
    out["available"] = True
    for j in JOURNALS:
        hit = by_sid.get(j["sid"])
        if not hit:
            out["per_journal"][j["journal"]] = {"note": "本地面板无该 source_id"}
            continue
        _, meta = hit
        local = {int(y): c for y, c in meta["total"].items()}
        fresh = anchors[j["journal"]]
        yrs = [y for y in range(Y0, Y1 + 1) if y in local and y in fresh]
        lo = sum(local[y] for y in yrs)
        fr = sum(fresh[y] for y in yrs)
        out["per_journal"][j["journal"]] = {
            "n_years": len(yrs),
            "local_total_window": lo,
            "fresh_total_window": fr,
            "drift_pct": round(100.0 * (fr - lo) / lo, 3) if lo else None,
            "rho_local_vs_fresh": spearman_avg([local[y] for y in yrs], [fresh[y] for y in yrs])
            if len(yrs) >= 3 else None,
        }
    return out


# ---------------------------------------------------------------- 输出
def relpath(p):
    try:
        return os.path.relpath(p, ROOT).replace(os.sep, "/")
    except Exception:
        return p


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    return path


LIMITATIONS = [
    "primary_topic 为 OpenAlex 每篇 work 的单一主主题分配：多主题论文被折叠，主题曲线是"
    "“主题归属代理”，本相关只度量代理与锚点曲线的单调同向性，不构成主题边界有效性的充分条件。",
    "锚点与主题曲线均取自同一次 API 快照（同日），但本地 w1_panels.json 为历史快照；两者漂移"
    "（索引追加）已在 local_w1_crosscheck 中量化，不用于主结果。",
    "年份窗 1990–2024 为脚本冻结常量（2025 右删失排除；1980 年代早期年份过薄）；两个敏感性窗"
    "（1990–2023、2000–2024）为附列。",
    "Spearman 未给 p 值/置信区间：年份序列自相关使常规 p 值不可靠，且本任务只要求秩相关口径。",
    "选择规则是人为冻结的规程（前3交集 / 一致 argmax），对候选表的小扰动敏感；全部 top10 原表"
    "与选择记录已随候选表保存，便于复算与审计。",
    "本次为重跑（primary_topic 规范化口径），不覆盖、不改写 research/panels/out/"
    "control_theory_boundary_fix.json 与 research/nature/out/boundary_consistency.json 两份旧输出；"
    "与旧口径（topics.id / 语义规则 T10820）不直接数值可比。",
    "本脚本不改数据库、不打印 API key；key 预算耗尽或网络阻塞时状态为 BLOCKED，只留错误详情。",
]


def _selftest():
    """并列平均秩 Spearman 自检（不访问 API）。"""
    cases = [
        ([1, 2, 3], [3, 2, 1], -1.0),
        ([1, 2, 3], [1, 2, 3], 1.0),
        ([1, 1, 2], [1, 2, 3], 0.8660254037844386),   # 并列平均秩手算值
        ([5, 5, 5, 5], [1, 2, 3, 4], None),          # 常数序列
        ([1, 2], [1, 2], None),                      # 样本过短
    ]
    bad = 0
    for xs, ys, want in cases:
        got = spearman_avg(xs, ys)
        ok = (got is None and want is None) or (
            got is not None and want is not None and abs(got - want) < 1e-9)
        print(("PASS " if ok else "FAIL "), xs, ys, "->", got, "want", want)
        bad += 0 if ok else 1
    print("selftest:", "OK" if bad == 0 else f"{bad} FAILED")
    return 0 if bad == 0 else 1


def main():
    started = time.time()
    out = {"script": relpath(os.path.abspath(__file__)), "run_utc": utcnow(),
           "status": None, "stage": "candidates", "spec_frozen": SPEC_FROZEN,
           "api": {"base": BASE, "mailto": MAILTO, "keys_enabled": bool(API_KEYS), "calls": [],
                   "blocked": None},
           "selection": None, "curves": None, "results": None, "verdict": None,
           "local_w1_crosscheck": None, "warnings": [],
           "outputs": {"main": relpath(OUT_MAIN), "candidates": relpath(OUT_CAND)},
           "limitations": LIMITATIONS}
    print(f"=== control_theory 边界规范化重跑 v2 | {out['run_utc']} | keys={bool(API_KEYS)} ===", flush=True)

    # —— 阶段 1：候选与选择 ——
    try:
        cand = fetch_candidates()
    except BaseException as e:
        out.update(status="BLOCKED", stage="candidates",
                   api={**out["api"], "calls": API_CALLS,
                        "blocked": f"候选阶段 API 阻塞：{type(e).__name__}: {e}"})
        write_json(OUT_MAIN, out)
        print(f"[BLOCKED] 候选阶段 API 阻塞：{type(e).__name__}: {e}")
        print(f"错误详情已写入 {relpath(OUT_MAIN)}；未产出任何数值。")
        return 2

    if any(c["empty"] for c in cand.values()):
        empty = [n for n, c in cand.items() if c["empty"]]
        out.update(status="API_EMPTY", stage="candidates",
                   api={**out["api"], "calls": API_CALLS},
                   selection={"note": f"group_by 返回空：{empty}"})
        write_json(OUT_CAND, {"run_utc": out["run_utc"], "candidates": cand, "selection": None,
                              "api": {"calls": API_CALLS}})
        write_json(OUT_MAIN, out)
        print(f"[API_EMPTY] group_by 返回空：{empty}；未产出数值。")
        return 0

    names, warn = resolve_topic_names([r["topic_id"] for c in cand.values() for r in c["top"]])
    if warn:
        out["warnings"].append(warn)
        print(f"[warn] {warn}")
    for c in cand.values():
        for r in c["top"]:
            if not r.get("display_name"):
                r["display_name"] = names.get(r["topic_id"])

    sel = select_topic(cand)
    sel["topic_display_name"] = names.get(sel["topic_id"])
    out["selection"] = sel
    cand_doc = {"run_utc": out["run_utc"], "spec": SPEC_FROZEN, "candidates": cand,
                "selection": sel, "api": {"calls": API_CALLS}}
    write_json(OUT_CAND, cand_doc)
    j1, j2 = JOURNALS[0]["journal"], JOURNALS[1]["journal"]
    print(f"候选（{TOP_N} 项/刊）已存 {relpath(OUT_CAND)}")
    for n in (j1, j2):
        top3 = [f"#{r['rank']} {r['topic_id']} {r['display_name'] or ''} ({r['count']})"
                for r in cand[n]["top"][:TOP_K]]
        print(f"  {n}: " + " | ".join(top3))

    if not sel["certain"]:
        out.update(status="INDETERMINATE", stage="selection",
                   api={**out["api"], "calls": API_CALLS},
                   verdict={"status": "INDETERMINATE", "rule": SPEC_FROZEN["selection_rule"],
                            "detail": "; ".join(sel["reasons"]),
                            "pass_threshold": RHO_PASS})
        write_json(OUT_MAIN, out)
        print(f"[INDETERMINATE] {out['verdict']['detail']}")
        print(f"未产出主结果（冻结规则禁止事后择优）。候选表见 {relpath(OUT_CAND)}")
        return 0

    tid = sel["topic_id"]
    print(f"选择：rule={sel['rule']} topic={tid} ({sel['topic_display_name'] or '名称未解析'})"
          f" flags={sel['flags'] or '无'}", flush=True)
    for lt, rec in sel["legacy_audit"].items():
        print(f"  旧口径主题 {lt}（{rec['desc']}）在新候选表内："
              + "，".join(f"{n}={rec[n] or '不在前十'}" for n in (j1, j2)))

    # —— 阶段 2：曲线 ——
    partial = {}
    try:
        fetch_curves(tid, partial)
    except BaseException as e:
        out.update(status="BLOCKED", stage="curves",
                   api={**out["api"], "calls": API_CALLS,
                        "blocked": f"曲线阶段 API 阻塞：{type(e).__name__}: {e}"},
                   curves={"partial": partial or None,
                           "note": "阻塞于曲线抓取，partial 为已取部分（如未完整则不可用于任何计算）"})
        write_json(OUT_MAIN, out)
        print(f"[BLOCKED] 曲线阶段 API 阻塞：{type(e).__name__}: {e}")
        print(f"错误详情与已取部分已写入 {relpath(OUT_MAIN)}；未产出相关系数。")
        return 2

    anchors, topics = partial["anchor"], partial["topic"]
    out["curves"] = {
        "anchor": anchors, "topic": topics,
        "off_window_years": {k: {str(y): c for y, c in v.items() if not (Y0 <= y <= Y1)}
                             for k, v in {**anchors, **topics}.items()
                             if any(not (Y0 <= y <= Y1) for y in v)},
        "note": "锚点=source 全部 works 年度量；主题=同 source + primary_topic.id 过滤；pooled=两刊逐年和",
    }
    print(f"曲线：{j1} 锚点合计 {sum(anchors[j1].values())} / 主题合计 {sum(topics[j1].values())}；"
          f"{j2} 锚点合计 {sum(anchors[j2].values())} / 主题合计 {sum(topics[j2].values())}",
          flush=True)

    # —— 计算与判定 ——
    units = [("pooled", anchors["pooled"], topics["pooled"]),
             (j1, anchors[j1], topics[j1]), (j2, anchors[j2], topics[j2])]
    results = {"main_window": {}, "sensitivity": {}}
    for name, a, t in units:
        results["main_window"][name] = window_result(a, t, Y0, Y1)
    for label, (wy0, wy1) in (("edge_drop_last_year", EDGE_WINDOW), ("post_2000", RECENT_WINDOW)):
        results["sensitivity"][label] = {name: window_result(a, t, wy0, wy1)
                                         for name, a, t in units}
    out["results"] = results
    out["local_w1_crosscheck"] = local_crosscheck(anchors)

    pm = results["main_window"]["pooled"]
    if pm["status"] != "OK" or pm["rho_level"] is None:
        status, detail = "DATA_INSUFFICIENT", pm["reason"] or "主口径相关系数不可计算"
    else:
        status = "PASS" if pm["rho_level"] >= RHO_PASS else "FAIL"
        ranks = {n: results["main_window"][n]["rho_level"] for n in (j1, j2)}
        detail = (f"合并口径 {Y0}–{Y1} 水平 rho={pm['rho_level']:.4f}（阈 {RHO_PASS}）；"
                  f"逐刊 {j1}={_fmt(ranks[j1])}、{j2}={_fmt(ranks[j2])}")
    out["verdict"] = {
        "status": status, "rule": f"主口径（合并两刊）水平 rho >= {RHO_PASS}",
        "pass_threshold": RHO_PASS, "detail": detail,
        "modes": {"rho_level": pm["rho_level"], "rho_first_diff": pm["rho_first_diff"],
                  "rho_detrended": pm["rho_detrended"]},
        "flags": [],
    }
    below = {k: v for k, v in out["verdict"]["modes"].items() if v is not None and v < RHO_PASS}
    if status == "PASS" and below:
        label = {"rho_first_diff": "一阶差分", "rho_detrended": "去趋势"}
        out["verdict"]["flags"].append("level_pass_dynamic_below_threshold")
        out["verdict"]["detail"] += ("；注意：动态口径低于阈值（"
                                     + "、".join(f"{label[k]}={_fmt(v)}" for k, v in below.items())
                                     + "）——水平共趋势不得外推为动态一致")
    out["status"] = status
    out["stage"] = "done"
    out["api"] = {**out["api"], "calls": API_CALLS}
    out["elapsed_s"] = round(time.time() - started, 1)
    write_json(OUT_MAIN, out)

    print(f"主口径（pooled，{Y0}–{Y1}，n_years={pm['n_years_level']}）："
          f"水平 rho={_fmt(pm['rho_level'])}，一阶差分 rho={_fmt(pm['rho_first_diff'])}"
          f"（n={pm['n_pairs_diff']}），去趋势 rho={_fmt(pm['rho_detrended'])}")
    for n in (j1, j2):
        r = results["main_window"][n]
        print(f"  {n}（同口径）：水平 {_fmt(r['rho_level'])}，差分 {_fmt(r['rho_first_diff'])}，"
              f"去趋势 {_fmt(r['rho_detrended'])}，n_years={r['n_years_level']}")
    cc = out["local_w1_crosscheck"]
    if cc.get("available") and cc["per_journal"]:
        drift = ", ".join(f"{k}: {v.get('drift_pct')}%" for k, v in cc["per_journal"].items()
                          if v.get("drift_pct") is not None)
        print(f"本地 w1_panels 交叉核验（锚点漂移）：{drift}")
    print(f"[{status}] {out['verdict']['detail']}")
    print(f"输出：{relpath(OUT_MAIN)}；候选表：{relpath(OUT_CAND)}；API 调用 {len(API_CALLS)} 次")
    return 0


def _fmt(v):
    return "null" if v is None else f"{v:.4f}"


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as e:
        print(f"[INTERNAL ERROR] {type(e).__name__}: {e}")
        sys.exit(1)
