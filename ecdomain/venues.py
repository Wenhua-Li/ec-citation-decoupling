"""venue 分层：把 78 个 venue_tag 划入 A(纯EC) / B(CI大类) / C(混合应用)。

proposed 归属由本文件常量给出，写入 venue_tier 表（decided_by='proposed'）；
用户在 labeling/venue_tier_review.csv 核定后改为 decided_by='user' 的行
不会被后续重跑覆盖（INSERT OR IGNORE）。
"""
from collections import defaultdict

from . import TIER_A, TIER_B, TIER_C, TIER_NAMES
from . import _db

# --- A：纯 EC 期刊/会议（整体判 EC） ---
A_EXACT = {
    "tevc", "swevc", "ec_mit", "evolutionary_intelligence", "gpem", "memetic_comp",
    "natural_computing", "swarm_intelligence", "foga", "acm_elo", "emo", "eurogp",
    "evoapplications", "evocop", "ppsn", "icsi", "ijbic",
}
A_PREFIX = ("gecco_", "cec_")

# --- B：计算智能大类（EC 占比中等，论文级判定） ---
B_EXACT = {"tetci", "tai", "cim", "jas", "joh", "soft_computing"}
B_PREFIX = ("ssci_", "tcyb_", "tsmc_", "tfs_")

# --- C：混合应用期刊（OR/AI/应用，论文级判定） ---
C_PREFIX = ("eswa_", "asoc_", "caie_", "cor_", "ejor_", "ins_", "eaai_")

# 需要用户重点核对的边界刊源
FLAG_NOTES = {
    "ssci": "IEEE SSCI 系列含 DE/PSO/EDA/模糊等多个方向研讨会，EC 占比高但非全部",
    "joh": "Journal of Heuristics：元启发式为主（广义口径下 EC 占比高），但含精确/OR 方法",
    "natural_computing": "以 EC 为主，另含量子计算/复杂系统等；如从严可改 B",
    "soft_computing": "Springer Soft Computing：模糊+神经+启发式混合的 CI 大类",
    "jas": "IEEE/CAA J. Automatica Sinica：自动化为主，EC 占比预期较低",
    "icsi": "ICSI 国际群智能会议，主题即群智能",
    "ijbic": "Int. J. Bio-Inspired Computation，生物启发计算",
    "evocop": "EvoCOP：进化计算在组合优化中的应用会议",
    "evoapplications": "EvoApplications 系列（LNCS），含多个应用方向分场",
    "tcyb": "IEEE TCYB：CI 大类（含 RL/模糊/优化）",
    "tsmc": "IEEE TSMC: Systems：CI 大类",
    "tfs": "IEEE TFS：模糊系统为主，EC 占比中等",
    "tetci": "IEEE TETCI：CI 新兴主题",
    "tai": "IEEE TAI：AI 大类，EC 占比预期较低",
    "cim": "IEEE CIM：计算智能综述/科普为主",
}


def tier_of(tag):
    if tag in A_EXACT or tag.startswith(A_PREFIX):
        return TIER_A
    if tag in B_EXACT or tag.startswith(B_PREFIX):
        return TIER_B
    if tag.startswith(C_PREFIX):
        return TIER_C
    return None


def note_for(tag):
    base = tag.rstrip("_0123456789")
    for k, v in FLAG_NOTES.items():
        if tag == k or base == k or tag.startswith(k):
            return v
    return None


def proposed_rows():
    """全部 venue_tag 的 proposed 分层行 [(venue_tag, tier, note), ...]。"""
    conn = _db.connect_ro()
    try:
        tags = [r[0] for r in conn.execute(
            "SELECT venue_tag FROM papers GROUP BY venue_tag")]
    finally:
        conn.close()
    rows = []
    for t in tags:
        tier = tier_of(t)
        if tier is None:
            raise ValueError(f"venue_tag 未归类：{t}（请在 venues.py 常量中补充）")
        rows.append((t, tier, note_for(t)))
    return rows


def ensure_venue_tiers():
    """把 proposed 分层写入 venue_tier（幂等；decided_by='user' 的行不覆盖）。"""
    rows = proposed_rows()
    conn = _db.connect_rw()
    try:
        _db.ensure_schema(conn)
        cur = conn.executemany(
            "INSERT OR IGNORE INTO venue_tier(venue_tag, tier, decided_by, note) "
            "VALUES(?,?,'proposed',?)", [(t, tier, note) for t, tier, note in rows])
        conn.commit()
        n_new = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        have = conn.execute("SELECT COUNT(*) FROM venue_tier").fetchone()[0]
    finally:
        conn.close()
    return n_new, have, rows


def write_venue_labels():
    """A 档论文写 tier='venue' 的 EC 标签（幂等 reconcile 式）：
    新增缺失的；删除已不属于 A 档的 venue 行。LLM 全量跑前自动调用。"""
    conn = _db.connect_rw()
    try:
        _db.ensure_schema(conn)
        now = _db.utcnow()
        cur = conn.execute(
            "INSERT OR IGNORE INTO paper_domain"
            "(accession_no, label, tier, confidence, evidence, model, rule_ver, judged_at) "
            "SELECT p.accession_no, 'EC', 'venue', 0.99, 'venue=A_pure_ec', NULL, NULL, ? "
            "FROM papers p JOIN venue_tier vt ON vt.venue_tag = p.venue_tag "
            "WHERE vt.tier = 'A_pure_ec'", (now,))
        n_add = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        cur2 = conn.execute(
            "DELETE FROM paper_domain WHERE tier='venue' AND accession_no IN ("
            "  SELECT p.accession_no FROM papers p "
            "  LEFT JOIN venue_tier vt ON vt.venue_tag = p.venue_tag "
            "  WHERE vt.tier IS NULL OR vt.tier != 'A_pure_ec')")
        n_del = cur2.rowcount if cur2.rowcount and cur2.rowcount > 0 else 0
        conn.commit()
    finally:
        conn.close()
    return n_add, n_del


def tier_counts():
    conn = _db.connect_ro()
    try:
        return {r[0]: r[1] for r in conn.execute(
            "SELECT vt.tier, COUNT(*) FROM venue_tier vt "
            "JOIN papers p ON p.venue_tag = vt.venue_tag GROUP BY vt.tier")}
    finally:
        conn.close()


def write_review_csv(path):
    """生成用户核定表：每个 venue_tag 一行，含篇数/年份跨度/刊名样例/分层。"""
    import csv
    conn = _db.connect_ro()
    try:
        stats = {r["venue_tag"]: r for r in conn.execute(
            "SELECT venue_tag, COUNT(*) AS n, MIN(pub_year) AS y0, MAX(pub_year) AS y1 "
            "FROM papers GROUP BY venue_tag")}
        src = defaultdict(list)
        for r in conn.execute(
                "SELECT venue_tag, source, COUNT(*) AS n FROM papers "
                "GROUP BY venue_tag, source ORDER BY venue_tag, n DESC"):
            src[r["venue_tag"]].append(r["source"])
        tiers = {r["venue_tag"]: (r["tier"], r["decided_by"], r["note"])
                 for r in conn.execute("SELECT * FROM venue_tier")}
    finally:
        conn.close()

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["venue_tag", "tier_当前分层", "decided_by", "n_papers",
                    "year_跨度", "刊名样例(source)", "备注", "你的裁定(留空=维持)"])
        for tag in sorted(tiers, key=lambda t: -stats[t]["n"] if t in stats else 0):
            tier, by, note = tiers[tag]
            st = dict(stats.get(tag, {}))
            names = src.get(tag, [])
            sample = " | ".join(names[:2]) + (f" （共{len(names)}个刊名变体）" if len(names) > 2 else "")
            w.writerow([tag, TIER_NAMES.get(tier, tier), by, st.get("n", 0),
                        f"{st.get('y0','')}-{st.get('y1','')}", sample, note or "", ""])


def write_review_md(path):
    counts = tier_counts()
    total = sum(counts.values())
    lines = [
        "# venue 分层核定表（EC / 非EC 打标第 0 层）\n",
        "分层含义：**A_纯EC** 全库直接判 EC；**B_CI大类 / C_混合应用** 进入论文级判定"
        "（规则层 + LLM）。\n",
        "| 分层 | 篇数 | 占比 |", "|---|---:|---:|",
    ]
    for t in (TIER_A, TIER_B, TIER_C):
        n = counts.get(t, 0)
        lines.append(f"| {TIER_NAMES[t]} | {n:,} | {n/total:.1%} |")
    lines += [
        f"| 合计 | {total:,} | 100% |\n",
        "逐刊明细见 `labeling/venue_tier_review.csv`（Excel 可直接打开）。"
        "如需调整某刊分层：在最后一列写上裁定（A/B/C），发回后由我更新库表"
        "（或直接改 venue_tier 表中该行 tier 并把 decided_by 置为 user）。\n",
        "## 需重点核对的边界刊源\n",
    ]
    conn = _db.connect_ro()
    try:
        rows = conn.execute(
            "SELECT vt.venue_tag, vt.tier, vt.note, COUNT(p.accession_no) AS n "
            "FROM venue_tier vt LEFT JOIN papers p ON p.venue_tag = vt.venue_tag "
            "WHERE vt.note IS NOT NULL GROUP BY vt.venue_tag "
            "ORDER BY n DESC").fetchall()
    finally:
        conn.close()
    for r in rows:
        lines.append(f"- **{r['venue_tag']}**（{TIER_NAMES.get(r['tier'], r['tier'])}，"
                     f"{r['n']:,} 篇）：{r['note']}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
