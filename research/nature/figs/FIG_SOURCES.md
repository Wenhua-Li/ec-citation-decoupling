# FIG_SOURCES.md — 当前图组数据来源与图注义务（2026-10-22 精简版）

**范围**：当前有效图组 = NC v3 双引擎图组（`research/nature/figs/reconstruction/`，6 主图 + 8 ED）。生成脚本：`make_masterplan_figs.py`（数据只读 `research/nature/out/`、`research/panels/out/` 冻结 JSON，不触库、不改锁定输出）。
**历史登记**：旧 NHB 图组、A2 图组、旧 ED 表与逐轮修复记录已移入 `archive/history/FIG_SOURCES_20261022.md`；旧图文件在 `archive/`。本文件只保留当前图组。
**数字登记**：`research/nature/NUMBERS.md`；Q 编号三向索引见 SI 表 13 与 `paper/build/doc_ids.md`。

## 版式与验收

- 画布 182.9mm（≤183mm 双栏上限）；Arial（fallback DejaVu Sans）；面板标签 9–10pt 粗体；PDF 文本层最小字号 ≥6.5pt（`audit_pdf_fonts.py` FLOOR=7.0pt 设计线，×0.7148≥5pt）。
- 方向语义色全组统一：EC→外部（reverse/扩张）= 蓝 `#0072B2`/青 `#009E73`；外部→EC（forward/构成敏感）= 赭 `#D55E00`/琥珀 `#E69F00`；档位 full=浅青绿 / e1=暖灰蓝 / refused=斜纹灰；2025 右删失一律斜纹。
- 验收：双跑 PNG+PDF sha256 字节一致；字号审计 ALL PASS；图级 visual-judge 14/14；页面级主图/ED 页验收全过；`check_figure_caption_contract.py` 0 FAIL（Fig4 图内端点标注为已知 WARN）。

## 主图

| 图名（文件） | 数据文件（字段路径） | 图内内容 | 图注义务（最低要求） |
|---|---|---|---|
| Fig1 `fig1_asymmetry_illusion` | `stable8_merged.json`（s1_single_end_anchor / s2_double_end / same_support.pooled / same_support.fixed_2021_weights.E1 / baseline_table_forward_2124 / baseline_table_reverse_2124 / per_source_e1_reverse）；`u1_contributions.json`（aggregates）；`bidirectional_asymmetry.json`（matrix / summary） | a 前向 E1 估计规范阶梯（S1 −24.3/−36.8 → S2 −26.7/−41.0 → pooled −18.5/−32.0 → 固定 −1.8/−16.1，2025 斜纹）；b 三基期符号翻转（+7.1/−1.8/−14.6）；c 两世界示意（聚合同 1.20→0.92）；d 反向七源全正记分卡（+1.6~+66.0，聚合三基期 +13.3~+18.3）；e 18 格 gap 热图（2025 列红虚框） | 四条件随图（7 源共同支持/固定构成/非配对/2025 右删失）；a 是估计规范阶梯非控制链；c 为命题 4 构造示意（限 E1）；e 为描述性 gap |
| Fig2 `fig2_decomposition_engine` | `u1_contributions.json`（horizontal_interaction / aggregates）；`bidirectional_asymmetry.json`（loo）；`doi_bracket.json`（tipping_point.frontier / diagonal_flip_lambda） | a 7 源 (Δw,Δm) 风险定位（EAAI/EJOR 高亮，净交互 95.5%）；b 逐源水平交互项条形（Σ=−9.52pp，与 L −1.83%/P −14.60%/宽度 12.78pp 分离并呈）；c 逐源留一 gap（三估计量，全正）；d λ 翻零前沿（对角 0.239、观测 ≈2%/≈8%） | 交互项≠精确宽度归因（估计规范分离义务）；λ 是暴露括号非校正；LOO 非独立重复 |
| Fig3 `fig3_internal_ecology` | `r3a_results.json`（subfamilies）；`terms.json`（share.LLM/GPT.a 等）；`r3b_dims.json`（agenda_external_sum.EC_any）；`disruption.json`（rows[].EC/NON_EC.mean）；`doctype_cd.json`（window_summary）；`memory.json`（by_citing_year_oc.share_age_ge_5） | a 亚族哑铃（GA −76.7/GP −70.1 沉降 vs PSO +31.5/swarm ×4.8/DE 上升，EMO −21.3）；b 外部议程与 LLM 轨迹（≈1.9→≈17%；0→2.66%）；c CD5 双轨与 JA-only 差距（raw −0.443→JA −0.368；2005–07 −0.035→+0.059）；d ≥5 岁份额 27.9→53.2→41.2 | 亚族两期窗（G1/G2 非逐年）；词份额为受控词模式（精度见 ED5）；CD5 队列止 2020（cd2 桥接见 ED3）；不承担跨机制因果 |
| Fig4 `fig4_people_money` | `r3o_quantities.json`（first_choice_share / corrected_first_choice_ratio_paper_weight）；`authors_flow.json`（ec_attrition_series_robust / flow_full）；`funding_agenda.json`（funded_subset_share / leadlag_funded_vs_full_ec）；`authors.json`（self_citation）；`checks.json`（c3_nsga2_series.oc） | a 首秀份额与校正比（44.8→13.5 对 0.930→0.663，构成解释 55.2%）；b 留存对比+迁移（净外流 ≈1.6×）；c 基金外部议程同步（lag-0 r=+0.93）；d 反直觉束（自引 30.7→10.1、NSGA-II 2,636→4,518） | 姓名串估计=上界；基金覆盖 44.0%（2020 后 79.3%）；相关不作因果；留存/迁移主口径全量版（稳健版随 SI） |
| Fig5 `fig5_cross_science_atlas` | `fieldmap.json`（directions/*/tier / aggregates.E1 / scorecard.E1 / pooled_edges / per_source / pair_gap_bootstrap_e1）；`tier_calibration.json`（per_source_table / readings） | a 12 对×双向矩阵（档位底色+E1 相对变化+●符号一致+◦共享领域；4 个未采方向 not collected）；b 8 对配对 gap 森林（正2/负4/不稳2+正值占比）；c 泊松功效校准曲线（100 边阈值=9.2% 错率）；d PRB 新记录支持变化（早窗 0 篇拒入） | 案例非独立（cs/physics/medicine/materials 共享）；无频率推断；端点窗 2011–13 vs 2021–23 与 EC 主窗不同构；raw 档位 9/9/2 与登记 8/10/2 的口径差异（biomedical→medicine 归 e1）在 SI 声明 |
| Fig6 `fig6_portability_calibration` | `age_w1.json`（各系列 share_ge5 首末）；`u1_contributions.json`；`panels_ladder.json`（width_pp）；`pilot_ladder.json`（fixed_composition.E1_width_pp）；`synth_width_dispersion.json`（decile_calibration / global）；`defect_injection_validation.json`（scoring.confusion_all） | a W1 记忆分裂哑铃（CV/NLP 降 vs OR/控制/evo/ML 升）；b 跨语料宽度（EC 12.78/econ↔psych 34.6/32.1/OR→ML 143.9/OR→evo 2.96pp）；c 84 万合成面板十分位校准带（log 轴，R² 0.183→0.395→0.703）；d U3 混淆计数+申报表六字段 | "宽度定律"否决、只写联合校准；U3 为覆盖度与功效筛查（检出 56.22%/漏检 43.78%）；W1 各系列首末年份随面板而异（图内标注） |

## Extended Data

| 图名 | 数据文件 | 图内内容 | 图注义务 |
|---|---|---|---|
| ED1 `ed1_spec_ladders` | `stable8_merged.json`（s1_single_end_anchor / s1_reverse_full / same_support* / same_support_reverse*） | 双向 E1 三层阶梯（2024 实心/2025 斜纹） | 正向 pooled 仅存 E1；列表层差异随图 |
| ED2 `ed2_uncertainty_loo` | `bidirectional_asymmetry.json`（bootstrap / loo） | 源级重抽 18 格森林 + LOO 散点 | q 分位=设计内分布描述；2024 跨零格如实 |
| ED3 `ed3_cd5_robustness` | `w4a.json`（team_size / cd5_no_self）；`r3b_cd.json`（cd5 / cd3 / cd2 / cd5_NONciter） | 团队桶/窗口桥接（无反弹至 2023）/非 EC 施引免疫 | 自引剔除与基线边剔除（T2=False）见 SI S5.3 文字 |
| ED4 `ed4_memory_detail` | `memory.json`（cohort_windows）；`age_w2.json`（三案例 share_ge5） | 队列前置加载 26.1→37.0 + 历史案例记忆轨迹 | W2 三案例 PASS 判据见 SI S7 |
| ED5 `ed5_subfamily_terms_audit` | `r3a_results.json`（subfamilies / migration_by_subfamily_descriptive）；terms 精度登记行 | 资格族降幅条形（−25% 裁定线）+ 词模式精度与撤回注记 | EMO −21.3% 未过 25% 线；PSO 唯一上升族；迁移率族间近常数 |
| ED6 `ed6_fieldmap_sources` | `fieldmap.json`（full 档 directions/*/per_source.early/modern.E1） | 9 个 full 档方向逐源 E1 哑铃 | source id 与锚源字典对照见 SI S6；零基源单列 |
| ED7 `ed7_u3_validation` | `defect_injection_validation.json`（scoring / dose_response） | 混淆摘要 + 六场景剂量-检出曲线 | 独立验证设计（10,800 次判定）见 SI S8 |
| ED8 `ed8_reporting_card` | 申报表协议（U1_formalization.md §4/§10）；已申报读数取自上述 JSON | 六字段申报卡 + 已申报读数汇总行 | 两世界构造仅 E1；阈值语义随 SI S8 |

## 最新重构记录（2026-10-20~21）

- 14 图按规格书重排/重绘（k3-256k 四组施工 + 修复轮）；P0 修正：ED7a 混淆矩阵 4,203/68 归位、Fig4b 灰柱改真非 EC 留存、ED5a 有符号变化、ED2a 补 18 格森林、ED4a 截断至 2022、Fig2b 7×7 下三角 21 项矩阵、Fig5 图注 b/c/d 重配、Fig6 删申报通栏、ED1–7 图注补字母、Fig6a 换真刊名、ED6 duplicate record 标注。
- 版式体系：语义色三分法、Fig1 四条件徽章带、Fig5 c 降 inset / d 右窄条、标题描述化；字号门升级 7.0pt。
- 就近排版（2026-10-21 用户裁定）：主图落位 p3/5/9/12/14/16；SI ED 逐图插至首个引用段后（ED2 回退文末）；页面级验收 16/16。
- 2026-10-22 重建：`main.pdf` 20 页 / `si.pdf` 41 页（150×240mm 版面）；图件与数据未变。

## 历史入口

- 旧图组登记与逐轮修复记录：`archive/history/FIG_SOURCES_20261022.md`。
- 旧 NHB/旧图组文件：`archive/`；当前论文只引用 `figs/reconstruction/` 成品。
