# doc-id 索引（Q 编号 ↔ 登记行 ↔ 输出字段路径）

**建立**：2026-10-02（初版）。**权威处**：本文件是 Q 编号的分配处；投稿件的 SI 表 13 从本文件生成。
**用途**：让正文的每一个数字都能被审稿人（以及内部的核验脚本）追到可复算的源头。

## 使用规则

1. **先登记后使用**：任何数字进正文前，须在 `research/nature/NUMBERS.md` 有登记行；本文件为它分配 Q 编号。
2. **正文标注方式**：LaTeX 中用 `\qid{Q1}` 在数字后就近标注（内部校对可见，终稿可关）。
3. **核验脚本的回查键**：`verify_numbers.py` 扩展后以 Q 编号为索引键，检查"正文引用的 Q 编号 ↔ 登记值 ↔ 输出字段值"三方一致。
4. **不手工维护数字列**：本文件的 Value 列仅作人工阅读参考；比对以 NUMBERS.md 与输出文件为准。

## 编号方案

| 段 | 范围 | 用途 |
|---|---|---|
| Q0 | Q0-1 … Q0-9 | 库概况与基础设施（语料、打标、边、覆盖面） |
| Q1–Q6 | | 主主张：单向脱钩（双端 + 单端锚 + 分子分母） |
| Q7–Q12 | | 腿 3：颠覆指数分化与稳健性 |
| Q13–Q20 | | 腿 2：首个方向选择与子方向异质性 |
| Q21–Q30 | | 交付层：校准读数与负例 |
| Q31–Q42 | | 背景层：引用年龄、议程、作者流动、资金 |
| Q43–Q52 | | 反证层与机制辅助 |

---

## Q 编号表

| Q | 含义 | 值 | 登记位置（NUMBERS.md 节） | 脚本 | 输出文件 | 字段路径 |
|---|---|---|---|---|---|---|
| Q0-1 | 语料总篇数 | 146,785 | 库概况 | — | — | — |
| Q0-2 | 领域打标子集 | 47,834 | 库概况 | — | — | — |
| Q0-3 | 库内引用边（DOI 直连） | 922,842 | 库概况 | — | — | — |
| Q0-4 | 打标准确率（金标准 200 篇） | 97% | 库概况 | — | 归档材料 | — |
| Q0-5 | 右删失剔除行数 | 607,204 | 总口径 / 右删失 | memory.py 等 | memory.json | — |
| Q0-6 | 边表总行数（含杂凑回连） | 990,612 | 库概况 | — | — | — |
| Q0-7 | 多源共同支持边数 | 908,668 | 库概况 | — | — | — |
| Q0-8 | 低置信标签队列 | 2,528 篇 | 库概况 | — | 归档材料 | — |
| Q0-9 | 非 EC 打标子集 | 98,951 | 库概况 | — | — | — |
| **Q1** | 非领域→领域篇均强度 2021 峰 | 0.686 | R3-B | r3b 复算 | r3b_dims.json | balance_stable |
| **Q2** | 领域→非领域篇均强度 2021 / 2025 | 3.217 / 2.803 | R3-B | r3b 复算 | r3b_dims.json | balance_stable |
| **Q3** | 非领域→领域篇均强度 2025 | 0.358（−48%） | R3-B | r3b 复算 | r3b_dims.json | balance_stable |
| Q4 | 领域发文量 2024 顶点 | 2,995 篇 | 库概况 / Fig1 补登记 | — | — | — |
| Q5 | 经典成果年被引 2020 → 2025 | 2,636 → 4,518 | P5 | checks.py | checks.json | c3_nsga2_series.oc |
| Q6 | 固定期刊集出口率 2021 峰 / 2025 | 0.830 / 0.503 | P2（C2 修复后） | checks.py | checks.json | c2_fixed_venue_export[].rate |
| Q7 | 二维同格 8 格差距区间 | −0.245 ～ −0.079 | P3 / R3-O | stability.py | stability.json | c_cd5_2d_strata |
| Q8 | 领域 CD5 均值 2003 → 2019 | +0.34 → −0.248 | P3 颠覆指数 | disruption.py | disruption.json | [year=2003].EC.mean |
| Q9 | 非领域 CD5 均值 2002 / 2010 / 2020 | +0.28 / +0.04 / +0.278 | P3 颠覆指数 | disruption.py | disruption.json | [year=2002].NON_EC.mean |
| Q10 | 稳定对照组 2019 差距 | −0.248 vs +0.161 | P3 | stability.py | stability.json | b_stable_control_cd5 |
| Q11 | 团队规模同桶差距 | 每桶低 0.34–0.73 | W4a | w4a.py | w4a.json | team_size.buckets |
| Q12 | 桥接 cd2 2023 差距 | −0.616 | R3-B | r3b 复算 | r3b_cd.json | — |
| Q13 | 首发作者首选份额 2005 峰 → 2025 | 44.8% → 13.5% | W6 作者流动 | authors.py | authors.json | entrants |
| Q14 | 构成校正比（论文权重）2005 / 2022 / 2025 | 0.898 / 0.788 / 0.663 | R3-O | r3o_register.py | r3o_quantities.json | corrected_first_choice_ratio_paper_weight |
| Q14b | 构成校正比（论文权重）**2003** → 2025 | 0.930 → 0.663 | R3-O | 同上 | 同上 | 同上 |
| Q15 | 构成校正比（槽位权重）2005 / 2022 / 2025 | 0.875 / 0.823 / 0.714 | R3-O | 同上 | 同上 | corrected_first_choice_ratio_slot_weight |
| Q16 | 构成解释占比（**2003→2025 区间**、论文权重版） | 55.2% | R3-O 派生 | r3o_register.py | r3o_quantities.json | 派生自 Q14b |
| Q17 | 子方向深跌族区间 | 48–77%（7 族） | R3-A | r3a | r3a_results.json | — |
| Q18 | 粒子群族变化 | +31.5%（p<1e-6） | R3-A | r3a | r3a_results.json | — |
| Q19 | 二维同格覆盖度 领域 / 非领域 | 84.1% / 67.0% | R3-O | r3o_register.py | r3o_quantities.json | strata_coverage_2018_20 |
| Q20 | 解析率 领域 / 非领域 2025 | 0.406 / 0.151 | P3 | stability.py | stability.json | a_resolution_rate |
| Q21 | 校准命中 | 6/9 | W1/W2 外部轮廓 | — | early_warning_table.json | summary.per_metric_hits |
| Q22 | 提前量区间与中位 | 1–10 年 / 中位 4.5 | W1/W2 外部轮廓 | — | early_warning_table.json | summary.hit_years_summary |
| Q23 | 负例假阳性次数 | 7 | W1/W2 | — | early_warning_table.json | negative_false_positive_count |
| Q24 | 超窗**未命中**读数 | 2 个（模糊逻辑案例 m1_median_age 与 m1_share_ge5，转折 1978 vs 事件 2000，提前 22 年，**`hit: False`，不在 6/9 之内**） | W1/W2 外部轮廓 | — | early_warning_table.json | rows[1].lead_years |
| Q31 | 引用偏好比 2006 / 2016 / 2024 | 0.472 / 1.092 / 1.607 | P1 | memory.py | memory.json | by_citing_year_oc |
| Q32 | 队列被引前置化 **2000 队列 → 2019 队列** | 26.1% → 37.0% | P1 | memory.py | memory.json | cohort_windows[].early_share_01_of_0_3 |
| Q35 | 外部主题合计份额 | ~1.9% → ~17% | P4 | terms.py | terms.json | share |
| Q36 | 地标成果引用份额 2025 | 0.68% | W7 降级版 | llm_cite_mode | — | — |
| Q38 | 领域→非领域迁移份额 | 4.6% → 8.9% | W6 | — | authors_flow.json | — |
| Q39 | 净流动比（2015 后） | ~1.6× | W6 | — | authors_flow.json | — |
| Q41 | 基金子群体外部主题份额 | 4.29% → 15.94% | W8 | — | funding_agenda | — |
| Q43 | 多目标方向份额 | 13.9% → 31.6% | P5 | terms.py | terms.json | share |
| Q44 | 自引率 | 30.7% → 10.1% | P5 | authors.py | authors.json | self_citation |
| Q45 | 语料份额 2000 / 2005 峰 / 2025 | 28.8% / 49.9% / 20.4% | R3-O | r3o_register.py | r3o_quantities.json | ec_corpus_share_paper_weight |
| Q46 | 语料份额（槽位权重）同三点 | 31.0% / 51.2% / 19.0% | R3-O | 同上 | 同上 | ec_corpus_share_slot_weight |
| Q47 | 非领域池膨胀 2020 → 2025 | 5,021 → 10,954（+118%） | P2 | trade.py | trade.json | flow[].pool_NON |
| Q48 | **EC→非 EC** 绝对边数 2017 / 2021 / 2025（balance_stable 派生；2026-10-05 方向指认更正：原标"领域被引"系方向标反，正确口径见 NUMBERS.md R3-O 派生量补登记节） | 2,123 / 2,654 / 1,931 | R3-O 派生量补登记 | r3b_dims.py 派生 | r3b_dims.json | balance_stable.2021.rate_EC_papers_cite_NON (edges derived as N_EC * rate) |
| Q48b | **非 EC→EC（双端分子）**绝对边数 2021 / 2025 | 2,964 / 2,749（−7.3%） | R3-O 派生量补登记 | r3b_dims.py 派生 | r3b_dims.json | balance_stable.2021.rate_NON_papers_cite_EC (edges derived as N_NON * rate) |
| Q49 | 施引池免疫差距占比 | 原始差距的 36%–51% | R3-B 派生 | r3b 复算 | r3b_cd.json | cd5_NONciter 派生 |
| Q50 | 同格差距占未分层差距比值 | 约 15%–68% | R3-O 派生 | stability/disruption 派生 | stability.json + disruption.json | 派生 |
| Q51 | 基线集合规模 | 611 篇 | R3-F | r3f | r3f_results.json | — |
| Q52 | 跨库口径秩相关 | 0.086 | W1/W2 | — | tevc_crosscheck.json | — |
| **Q53** | 三维同格存活率（cohort 2018/19/20 × Rp 桶 × Rq 桶） | 23 格中 21 格为负（91.3%）；中位点差 −0.166 | R3-P1 三项欠登记读数重跑与对账 | r3p1_rereg.py | r3p1_recon.json | t1_3d_strata.neg_share |
| **Q53b** | 三维同格仅有的 2 个翻正格 | 2018 年 10-19\|20-29 为 +0.045；2018 年 20-29\|10-19 为 +0.034 | R3-P1 三项欠登记读数重跑与对账 | r3p1_rereg.py | r3p1_recon.json | t1_3d_strata.positive_cells |
| **Q54** | 回归控制 EC 主效应（规格 A，n=11,134 / EC 3,891） | −0.1596（HC1 se 0.0127）；\|Rp\| −0.0172、\|Rq\| −0.0278 | R3-P1 三项欠登记读数重跑与对账 | r3p1_rereg.py | r3p1_recon.json | t2_regression_variants[0].beta |
| **Q54b** | 回归 \|Rq\| 规格敏感性（全池均值版） | EC −0.2939 | R3-P1 三项欠登记读数重跑与对账 | r3p1_rereg.py | r3p1_recon.json | t2_regression_variants[2].beta |
| **Q55** | 库内解析参考文献中位数 EC 2010 / 2020 / 2025 | 3 / 9 / 13 | R3-P1 三项欠登记读数重跑与对账 | r3p1_rereg.py | r3p1_recon.json | t3_median_resolved_refs.series.EC |
| **Q55b** | 库内解析参考文献中位数 非 EC 2010 / 2020 / 2025 | 3 / 5 / 4 | R3-P1 三项欠登记读数重跑与对账 | r3p1_rereg.py | r3p1_recon.json | t3_median_resolved_refs.series.NON_EC |
| **Q56** | 解析参考文献中位数分段均值 EC / 非 EC | EC 1.56→7.93（2002–2010→2011–2025）；非 EC 0.67→4.00 | R3-P1 三项欠登记读数重跑与对账 | r3p1_rereg.py | r3p1_recon.json | t3_median_resolved_refs.summary.seg_means |
| **Q57** | C2 期刊构成重加权（2021 构成固定，2021→2025）：E1 篇均跨域边数 / E2 参与率 | E1 0.830→0.642（−22.7%）；E2 0.291→0.232（−20.2%） | C2 构成敏感性更正（2026-10-17，v2.0.0；勘误见根目录 ERRATA.md） | c2_composition_sensitivity.py | c2_composition_sensitivity.json | source_standardized.endpoints |
| **Q58** | C2 主题构成重加权（同上） | E1 0.830→0.520（−37.4%）；E2 0.291→0.203（−30.3%） | 同上 | c2_composition_sensitivity.py | c2_composition_sensitivity.json | topic_standardized.endpoints |

---

## 待补编号（装配批次一）

以下 Q 编号已在 `paper/plan/01_narrative_and_outline.md` 中按段位预留，具体分配待对应登记行确认后填入：

| 段 | 预留 | 用途 | 阻塞 |
|---|---|---|---|
| Q25–Q30 | 6 个 | 校准层补充（逐案例命中年份、模糊逻辑产业口径敏感性、两个负例领域的触发年份） | 出图时按 Fig 5 泳道实际标注补 |
| Q33–Q34 | 2 个 | 引用年龄三源分源（oc / s2 / 全源）的数值 | 现行 ED 图不含此件（2026-10-06 引用序重排后），出图时再定位 |
| Q37 | 1 个 | 议程模式的三组分份额（方法词 / 理论词 / 外部主题词） | ED-6（议程热图）出图时补 |
| Q40 | 1 个 | 留存率剪刀差（领域侧下降 vs 非领域侧上升） | Fig 4 定稿时补 |
| Q42 | 1 个 | 基金议程的滞后期相关（lag 0 占优） | Methods 撰写时补 |
| Q52 后续 | — | 反证层余项（新人参与率 76–80%、多目标三锚等） | 反证段撰写时补 |

## 维护工序

1. 新增数字：先在 `NUMBERS.md` 加登记行 → 在本文件分配 Q 编号 → 再写入正文/图注/表。
2. 每轮装配后：由扩展后的 `verify_numbers.py` 以 Q 编号为键复跑三方核对，输出到 `paper/build/`。
3. SI 表 13 由本文件生成，**不手工维护**。
