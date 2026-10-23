# doc-id 索引（Q 编号 ↔ 登记行 ↔ 输出字段路径）— 双向不对称稿

**建立**：2026-10-16（NC 重构·双向不对称稿专用；旧稿 Q 表随 `archive/2026-10_nc_reboot/paper/build/doc_ids.md` 归档）。
**权威处**：本文件是 Q 编号的分配处；投稿件 SI 的 Q 表从本文件生成。
**用途**：让正文的每一个数字都能被审稿人（以及内部的核验脚本）追到可复算的源头。

## 使用规则

1. **先登记后使用**：任何数字进正文前，须在 `research/nature/NUMBERS.md` 有登记行；本文件为它分配 Q 编号。
2. **正文标注方式**：Markdown/LaTeX 中用 `\qid{Qn}` 在数字后就近标注（内部校对可见，终稿可关）。
3. **核验脚本的复核键**：`research/drafts/verify_numbers.py` 以 Q 编号为索引键，检查本文件每行的"输出文件 + 字段路径"在 `research/nature/out/`（或 `research/` 下）可解析（存在性核对；数值估计规范以 `NUMBERS.md` 与输出文件为准）。
4. **不手工维护数字列**：本文件的 Value 列仅作人工阅读参考。

## 冻结证据边界（本稿，2026-10-16 用户裁定）

- 主结果证据 = `paper_bootstrap_asymmetry.json`、`asymmetry_sensitivity.json`、`bidirectional_asymmetry.json`；测量框架 = `U1_formalization.md`（配 `u1_contributions.json`）；背景与限制数字一律回 `NUMBERS.md`。
- 写作纪律（脚本外人工复核项，违反即返工）：不得出现"首次提出"类优先权断言；不得把宽度/不对称写成"普遍定律"；不得给聚合读数指派行为因果主语；不得称筛查规则为"已验证仪器"；不得把当前证据写成无条件的"单向脱钩"结论；2025 端点为右删失，须与 2024 并读；q 分位是该重抽设计下的分布描述，不自动称 95% 置信区间；gap 为正向与反向池的非配对描述性比较。

## 编号方案

| 段 | 范围 | 用途 |
|---|---|---|
| 设计与支持 | Q1–Q6 | 支持集、支持池规模、右删失端点、重抽规格、矩阵范围 |
| 论文级重抽分布 | Q7–Q15 | 2024/2025 双端点 × E1/E2/E3 点估计、分位、正值比例 |
| 源级不确定性与留一 | Q16–Q18 | 来源级聚类重抽、逐源留一范围与极小值 |
| 敏感性与覆盖诊断 | Q19–Q22 | 低置信队列两变体、队列占比、DOI 解析行率 |
| 测量框架（U1） | Q23–Q28 | 精确宽度、交互项估计规范分离、关键源、within-source 端点、双向点估计 |
| 可移植性与筛查边界 | Q29–Q32 | U2 跨语料试点、第二多源面板、U3、control |
| 语料背景 | Q33–Q34 | 库规模、全库右删失行数 |

## Q 编号表

| Q | 含义 | 值 | 登记位置 | 脚本 | 输出文件 | 字段路径 |
|---|---|---|---|---|---|---|
| Q1 | 主结果支持集（2019/2021/2024/2025 双向皆在场） | 7 源 | 双向不对称 gap 矩阵与源级不确定性 | bidirectional_asymmetry.py | bidirectional_asymmetry.json | support |
| Q2 | 2021 基期 7 源支持池论文数（正向 NON→EC / 反向 EC→NON） | 4,426 / 1,038 | 0-6 全序列固定构成阶梯 | paper_bootstrap_asymmetry.py | paper_bootstrap_asymmetry.json | support.coverage.forward.2021.n_papers_in_support / support.coverage.reverse.2021.n_papers_in_support |
| Q3 | 2021 全支持池论文数（含 C&IE 离场源；正向 / 反向） | 4,985 / 1,205 | 0-6 全序列固定构成阶梯 | paper_bootstrap_asymmetry.py | paper_bootstrap_asymmetry.json | support.coverage.forward.2021.n_papers_stable8_pool / support.coverage.reverse.2021.n_papers_stable8_pool |
| Q4 | 论文级分层 bootstrap 规格与右删失端点 | 4,000 次；2025 | 双向不对称论文级分层 bootstrap | paper_bootstrap_asymmetry.py | paper_bootstrap_asymmetry.json | spec.reps / endpoint_censoring.censored_endpoint_years |
| Q5 | 源级 来源级聚类重抽 规格 | 2,000 次 | 双向不对称 gap 矩阵与源级不确定性 | bidirectional_asymmetry.py | bidirectional_asymmetry.json | spec.bootstrap_reps |
| Q6 | 18 格 gap 矩阵范围（三个构成权重基期 × 两个固定窗口端点 × E1/E2/E3） | 5.16–33.97pp | 双向不对称 gap 矩阵与源级不确定性 | bidirectional_asymmetry.py | bidirectional_asymmetry.json | summary.matrix_gap_min_pp / summary.matrix_gap_max_pp |
| Q7 | 2021→2024 E1 gap 点估计 | 16.53pp | 双向不对称论文级分层 bootstrap | paper_bootstrap_asymmetry.py | paper_bootstrap_asymmetry.json | point_estimates.2021->2024.E1.gap_pp |
| Q8 | 2021→2024 E2 gap 点估计 | 9.20pp | 双向不对称论文级分层 bootstrap | paper_bootstrap_asymmetry.py | paper_bootstrap_asymmetry.json | point_estimates.2021->2024.E2.gap_pp |
| Q9 | 2021→2024 E3 gap 点估计 | 19.42pp | 双向不对称论文级分层 bootstrap | paper_bootstrap_asymmetry.py | paper_bootstrap_asymmetry.json | point_estimates.2021->2024.E3.gap_pp |
| Q10 | 2024 端点论文级重抽分布（E1：分位与正值比例） | −0.57/16.57/33.14pp；97.18% | 双向不对称论文级分层 bootstrap | paper_bootstrap_asymmetry.py | paper_bootstrap_asymmetry.json | bootstrap.2021->2024\|E1.gap_pp.q025 / bootstrap.2021->2024\|E1.gap_pp.q975 / bootstrap.2021->2024\|E1.positive_share |
| Q11 | 2024 端点论文级重抽分布（E2） | 1.31/9.32/17.01pp；98.85% | 双向不对称论文级分层 bootstrap | paper_bootstrap_asymmetry.py | paper_bootstrap_asymmetry.json | bootstrap.2021->2024\|E2.gap_pp.q025 / bootstrap.2021->2024\|E2.gap_pp.q975 / bootstrap.2021->2024\|E2.positive_share |
| Q12 | 2024 端点论文级重抽分布（E3） | 5.27/19.21/33.67pp；99.60% | 双向不对称论文级分层 bootstrap | paper_bootstrap_asymmetry.py | paper_bootstrap_asymmetry.json | bootstrap.2021->2024\|E3.gap_pp.q025 / bootstrap.2021->2024\|E3.gap_pp.q975 / bootstrap.2021->2024\|E3.positive_share |
| Q13 | 2025 端点（右删失）论文级重抽分布（E1） | 25.25pp；10.33/25.25/39.79pp；99.98% | 双向不对称论文级分层 bootstrap | paper_bootstrap_asymmetry.py | paper_bootstrap_asymmetry.json | point_estimates.2021->2025.E1.gap_pp / bootstrap.2021->2025\|E1.gap_pp.q025 / bootstrap.2021->2025\|E1.positive_share |
| Q14 | 2025 端点（右删失）论文级重抽分布（E2） | 24.62pp；16.82/24.69/32.45pp；100% | 双向不对称论文级分层 bootstrap | paper_bootstrap_asymmetry.py | paper_bootstrap_asymmetry.json | point_estimates.2021->2025.E2.gap_pp / bootstrap.2021->2025\|E2.gap_pp.q975 / bootstrap.2021->2025\|E2.positive_share |
| Q15 | 2025 端点（右删失）论文级重抽分布（E3） | 24.25pp；11.10/24.44/37.64pp；99.98% | 双向不对称论文级分层 bootstrap | paper_bootstrap_asymmetry.py | paper_bootstrap_asymmetry.json | point_estimates.2021->2025.E3.gap_pp / bootstrap.2021->2025\|E3.gap_pp.q975 / bootstrap.2021->2025\|E3.positive_share |
| Q16 | 源级 来源级聚类重抽（2021 基期，E1，2024 / 2025 端点） | −8.83/17.73/38.84pp 与 6.70/25.25/44.54pp；90.8% / 99.4% | 双向不对称 gap 矩阵与源级不确定性 | bidirectional_asymmetry.py | bidirectional_asymmetry.json | bootstrap.2021\|2021->2024\|E1.q025 / bootstrap.2021\|2021->2024\|E1.positive_share / bootstrap.2021\|2021->2025\|E1.q975 / bootstrap.2021\|2021->2025\|E1.positive_share |
| Q17 | 2021→2024 逐源留一 gap 范围（E1 / E2 / E3） | 11.75–28.69pp；7.03–14.16pp；14.83–27.02pp | 双向不对称 gap 矩阵与源级不确定性 | bidirectional_asymmetry.py | bidirectional_asymmetry.json | loo.Applied Soft Computing\|2021\|2021->2024\|E1.gap_pp / loo.European Journal of Operational Research\|2021\|2021->2024\|E3.gap_pp |
| Q18 | 留一极小值（共同来源逐源留一 / 剔 TFS，18 格仍全正） | 2.49pp；3.27–32.66 个百分点 | 双向不对称敏感性分析 | asymmetry_sensitivity.py | asymmetry_sensitivity.json | s3_reverse_loo.by_source.Expert Systems with Applications.cells.2019\|2021->2024\|E2.gap_pp / s3_reverse_loo.focus_tfs.cells.2024\|2021->2025\|E1.gap_pp |
| Q19 | 低置信队列剔除 gap（2024 / 2025，E1/E2/E3） | 16.36/9.65/19.25pp；19.14/24.25/20.19pp | 双向不对称敏感性分析 | asymmetry_sensitivity.py | asymmetry_sensitivity.json | s2_low_confidence_queue.variants.unit_excluded.point_estimates.2021->2024.E1.gap_pp / s2_low_confidence_queue.variants.unit_excluded.point_estimates.2021->2025.E3.gap_pp |
| Q20 | 低置信队列与指向其的边同时剔除（2024 / 2025） | 17.01/10.15/20.32pp；17.97/22.36/18.47pp | 双向不对称敏感性分析 | asymmetry_sensitivity.py | asymmetry_sensitivity.json | s2_low_confidence_queue.variants.full_excluded.point_estimates.2021->2024.E1.gap_pp / s2_low_confidence_queue.variants.full_excluded.point_estimates.2021->2025.E3.gap_pp |
| Q21 | 低置信队列占支持池比例（正向 / 反向） | 0.77% / 7.04% | 双向不对称敏感性分析 | asymmetry_sensitivity.py | asymmetry_sensitivity.json | s2_low_confidence_queue.queue.inventory.forward.share_of_pool_2021_24_25 / s2_low_confidence_queue.queue.inventory.reverse.share_of_pool_2021_24_25 |
| Q22 | DOI 行率（正向 / 反向，2019/2021/2024/2025） | 0.634/0.668/0.649/0.609；0.700/0.719/0.746/0.744 | 双向不对称敏感性分析 | asymmetry_sensitivity.py | asymmetry_sensitivity.json | s5_reference_doi_diagnostics.pooled_by_direction_year_support_only.forward\|2019.doi_row_rate / s5_reference_doi_diagnostics.pooled_by_direction_year_support_only.reverse\|2025.doi_row_rate |
| Q23 | U1 精确宽度（Laspeyres / Paasche / 宽度） | −1.83% / −14.60%；12.7766 个百分点 | U1 精确宽度与交互项分离复核 | u1_contributions.py | u1_contributions.json | aggregates.laspeyres_change / aggregates.paasche_change / aggregates.exact_width_percentage_points |
| Q24 | U1 交互项和与 pairwise 宽度和（估计规范分离，不得混称） | −0.095238 与 −0.127766 | U1 精确宽度与交互项分离复核 | u1_contributions.py | u1_contributions.json | horizontal_interaction_sum / pairwise_width_sum |
| Q25 | 关键源交互项（EAAI / EJOR）与占比 | 95.5% / 70.8% | U1 精确宽度与交互项分离复核 | u1_contributions.py | u1_contributions.json | horizontal_interaction[2].interaction / horizontal_interaction[3].interaction |
| Q26 | 剔除关键源后的宽度（剔 EJOR 实测） | 6.63 个百分点 | 循环论证风险检验 | decirc.py | decirc.json | loo[3].width_pp |
| Q27 | within-source 阶梯端点（2021→2024 / 2025，前向 E1） | −1.8% / −16.1% | 0-6 反向阶梯与 within-source 矩阵 | stable8_merged.py | stable8_merged.json | same_support.2024.fixed_2021_weights.E1.rel_change / same_support.2025.fixed_2021_weights.E1.rel_change |
| Q28 | 论文级重抽下的双向点估计（E1，2021→2024 / 2025） | 前向 −1.8% / −16.1%；反向 +14.7% / +9.2% | 双向不对称论文级分层 bootstrap | paper_bootstrap_asymmetry.py | paper_bootstrap_asymmetry.json | point_estimates.2021->2024.E1.forward_rel_change / point_estimates.2021->2024.E1.reverse_rel_change / point_estimates.2021->2025.E1.reverse_rel_change |
| Q29 | 跨语料宽度（U2 预注册试点：OR→ML / OR→evo） | 143.9 / 2.96 个百分点 | U2 跨语料阶梯试点 | pilot_ladder.py | pilot_ladder.json | pairs.OR<->ML.OR->ML.fixed_composition.E1_width_pp / pairs.OR<->evo.OR->evo.fixed_composition.E1_width_pp |
| Q30 | 第二多源语料宽度（economics↔psychology） | 34.6 / 32.1 个百分点 | 多源面板宽度检验 | panels_ladder.py | panels_ladder.json | directions.economics->psychology.width_pp / directions.psychology->economics.width_pp |
| Q31 | U3 独立验证的覆盖度与检验功效筛查边界（TP / FN） | 5,397 / 4,203；56.22% / 43.78% | U3 独立性能验证 | defect_injection_validation.py | defect_injection_validation.json | scoring.confusion_all.TP / scoring.confusion_all.FN |
| Q32 | control 长期共趋势（水平 / 一阶差分 / 去趋势 rho） | 0.9124 / 0.6359 / 0.3263 | control_theory 边界规范化重跑 v2 | control_boundary_v2.py | control_boundary_v2.json | verdict.modes.rho_level / verdict.modes.rho_first_diff / verdict.modes.rho_detrended |
| Q33 | 语料与库背景（总量 / EC 标注子集 / 非 EC 对照 / 金标准准确率） | 146,785；47,834；98,951；97% | 库概况 | — | — | — |
| Q34 | 全库右删失剔除行数（施引年 >2025） | 607,204 | 总估计规范 | memory.py | memory.json | truncated_rows_gt_2025 |
| Q42 | 合成校准：离散度/迁移→宽度（84 万面板；Spearman、R²、校准带） | 0.584 / 0.605；R² 0.183 / 0.218 / 0.395 | 阶段 B 硬化分析 | synth_width_dispersion.py | synth_width_dispersion.json | global.spearman_width_dispersion / global.r2_width_on_dispersion_migration |
| Q43 | 符号判据合成核验（一致符号零失配 / 混号 4.02%） | 0 / 4.02% | 阶段 B 硬化分析 | synth_width_dispersion.py | synth_width_dispersion.json | sign_diagnostics |
| Q44 | DOI 解析暴露括号与翻零份额（2021→2024 E3 gap） | 23.68 / 19.42 / −8.71pp；翻零 λ=0.239 | 阶段 B 硬化分析 | doi_bracket.py | doi_bracket.json | gap.2021->2024 / tipping_point.2021->2024.diagonal_flip_lambda |
| Q35 | Fig2a 逐源 (Δw, Δm) 展示值（7 源，前向 E1，2021→2024） | 见 SI S5 表（EAAI +0.154/−0.298；EJOR −0.069/+0.650 等） | U1 精确宽度与交互项分离复核 | u1_contributions.py | u1_contributions.json | horizontal_interaction |
| Q36 | Fig1a 前向 E1 基期摆幅与反向符号稳健区间（2021→2024） | +7.1% / −1.8% / −14.6%；反向 +13.3%~+18.3% | U0 构成权重基期选择全表 | stable8_merged.py | stable8_merged.json | baseline_table_forward_2124 / baseline_table_reverse_2124 |
| Q37 | ED2 逐源符号记分卡（前向混号 / 反向 E1 全正） | 前向 E1 −45.8%~+71.0%；反向 +1.6%~+66.0% | 符号一致判据全量核验 | stable8_merged.py | stable8_merged.json | per_source_e1 / per_source_e1_reverse |
| Q38 | ED3 源级重抽 18 格分位与正值比例 | 见 SI S2 与图内标注 | 双向不对称 gap 矩阵与源级不确定性 | bidirectional_asymmetry.py | bidirectional_asymmetry.json | bootstrap |
| Q39 | ED1 前向阶梯各层（S1 单端锚 / pooled / 固定 2021，双端点 × 三估计量） | S1 E1 −24.3%/−36.8%；pooled E1 −18.5%/−32.0%；固定 E1 −1.8%/−16.1% | 0-6 合并名稳定集重算 | stable8_merged.py | stable8_merged.json | s1_single_end_anchor / same_support |
| Q40 | ED1 反向各层（全支持 / pooled / 固定 2021，双端点 × 三估计量） | 全支持 E1 +4.6%/+1.2%（图内按冻结 JSON 直算；NUMBERS 3 位小数派生为 +4.7%，舍入差已登记 FIG_SOURCES）；固定 E1 +14.7%/+9.2% | 0-6 反向阶梯与 within-source 矩阵 | stable8_merged.py | stable8_merged.json | s1_reverse_full / same_support_reverse |
| Q45 | fieldmap 地图总览（20 方向/12 对；三档 full 8 / e1 10 / refused 2；阈值 100 边/窗） | full 8 / e1 10 / refused 2 | B 广度层地图 | fieldmap.py | fieldmap.json | design.tier_edges_threshold / directions.physics->materials.tier |
| Q46 | physics→materials E1 pooled 相对变化与重抽 | +56.2%（q +49.9/+56.1/+62.8，100% 正） | B 广度层地图 | fieldmap.py | fieldmap.json | directions.physics->materials.aggregates.E1.pooled_rel / directions.physics->materials.bootstrap_pooled_e1.q025 |
| Q47 | biology→medicine E1 pooled | +171.8% | B 广度层地图 | fieldmap.py | fieldmap.json | directions.biology->medicine.aggregates.E1.pooled_rel |
| Q48 | chemical_engineering→chemistry E1 pooled | +113.4% | B 广度层地图 | fieldmap.py | fieldmap.json | directions.chemical_engineering->chemistry.aggregates.E1.pooled_rel |
| Q49 | electrical_engineering→computer_science E1 pooled | +144.4% | B 广度层地图 | fieldmap.py | fieldmap.json | directions.electrical_engineering->computer_science.aggregates.E1.pooled_rel |
| Q50 | 双向齐跌对（sociology→polisci / polisci→sociology） | −9.6% / −19.3% | B 广度层地图 | fieldmap.py | fieldmap.json | directions.sociology->political_science.aggregates.E1.pooled_rel / directions.political_science->sociology.aggregates.E1.pooled_rel |
| Q51 | economics→business L/P 宽度（构成敏感性示例） | 宽度 −44.4pp（L +113.1% / P +68.7%） | B 广度层地图 | fieldmap.py | fieldmap.json | directions.economics->business.aggregates.E1.width_pp |
| Q52 | mechanical_engineering→materials 低基数示例 | pooled +600.2%、宽度 −399.1pp、早窗 151 边 | B 广度层地图 | fieldmap.py | fieldmap.json | directions.mechanical_engineering->materials.aggregates.E1.pooled_rel / directions.mechanical_engineering->materials.pooled_edges.early |
| Q53 | refused 档如实执行例（statistics→cs） | 记分卡全正、pooled +113.0%，池化 71/171 边 < 100 → refused | B 广度层地图 | fieldmap.py | fieldmap.json | directions.statistics->computer_science.aggregates.E1.pooled_rel |
| Q54 | 配对 gap 方向分布（正 2 / 负 4 / 不稳 2；正值占比 18.9%/29.4%） | 正 2 / 负 4 / 不稳 2 | B 广度层地图 | fieldmap.py | fieldmap.json | pair_gap_bootstrap_e1.physics<->materials.q50 / pair_gap_bootstrap_e1.economics<->business.pos_share |
| Q55 | 支持变化例（physics 新 PRB 记录早窗 0 篇） | 早窗 0 篇、modern 14,894 篇不入聚合 | B 广度层地图 | fieldmap.py | fieldmap.json | directions.physics->materials.per_source.S164566984.early.n_articles |
| Q56 | 三档阈值泊松校准（100 边/窗 = 20% 变化 9.2% 符号错率） | 100 边/窗；9.2% | B 广度层采集前闸门 | tier_calibration.py | tier_calibration.json | readings.per_source_edges_for_10pct_sign_error_at_20pct_change |
| Q57 | R3a：GA 资格族降幅 | −76.7% | R3-A 子方向拆分 | r3a_execute.py | r3a_results.json | subfamilies[family=ga].rel_decline |
| Q58 | R3a：遗传规划降幅 | −70.1% | R3-A 子方向拆分 | r3a_execute.py | r3a_results.json | subfamilies[family=genetic_programming].rel_decline |
| Q59 | R3a：粒子群显著上升（唯一上升资格族） | +31.5%（z=−5.33） | R3-A 子方向拆分 | r3a_execute.py | r3a_results.json | subfamilies[family=particle_swarm].rel_decline |
| Q60 | R3a：EMO 降幅不足（<25% 线） | −21.3% | R3-A 子方向拆分 | r3a_execute.py | r3a_results.json | subfamilies[family=emo].rel_decline |
| Q61 | R3a：深跌资格族区间（7 族 48–77%） | 48–77% | R3-A 子方向拆分 | r3a_execute.py | r3a_results.json | subfamilies[family=other_metaheuristic].rel_decline |
| Q62 | R3a：两期分母 | G1 18,031 / G2 53,184 | R3-A 子方向拆分 | r3a_execute.py | r3a_results.json | denominators.N_G1 |
| Q63 | R3a：非资格上升族（swarm ×4.8 / DE 143→868） | other_swarm_bio 119→1,697；DE 143→868 | R3-A 子方向拆分 | r3a_execute.py | r3a_results.json | subfamilies[family=other_swarm_bio].share_G1 |
| Q64 | P4：LLM/GPT A 类份额 2025 | 2.66%（2023 0.28%） | P4 研究议程 | terms.py | terms.json | share.LLM/GPT.2025.a |
| Q65 | R3b：EC 外部主题份额（EC_any） | 1.1%(2000)→15.4%(2025) | R3-B 三维对照与 CD 桥接 | r3b_dims.py | r3b_dims.json | agenda_external_sum.EC_any.2025.external_sum |
| Q66 | 0-2：CD5 差距 raw / JA-only（2018–20 与 2005–07） | raw −0.443 → JA −0.368；2005–07 raw −0.035 → JA +0.059 | 阶段 0 前置测量节点 | doctype_cd.py | doctype_cd.json | window_summary.raw_gap_2018_20 / window_summary.JA_gap_2018_20 |
| Q67 | R3-P1：三维同格 21/23 为负 | 91.3%；中位 −0.166 | R3-P1 三项欠登记读数重跑 | r3p1_rereg.py | r3p1_recon.json | t1_3d_strata.neg_share |
| Q68 | R3-P1：HC1 回归 EC 主效应 | −0.1596（HC1 se 0.0127，t=−12.6，n=11,134） | R3-P1 三项欠登记读数重跑 | r3p1_rereg.py | r3p1_recon.json | t2_regression_variants[0].beta |
| Q69 | W4a：8/8 刊源内 EC CD5 全降 | 8/8（TEVC +0.012→−0.477 等） | W4a 稳健性扩展 | w4a.py | w4a.json | source_within_decline.Expert Systems with Applications.delta |
| Q70 | P1：≥5 岁份额序列（2006/2019 峰/2025） | 27.9% / 53.2% / 41.2% | P1 引用记忆 | memory.py | memory.json | by_citing_year_oc[year=2019].share_age_ge_5 |
| Q71 | P1：偏好比 2024（附 2006/2016） | 1.607（0.472 / 1.092） | P1 引用记忆 | memory.py | memory.json | youth_bias_oc[year=2024].I1_over_I6 |
| Q72 | R3o：构成校正首择比 2025（论文权重；槽位版 0.714） | 0.663（2003 0.930） | R3-O 叙事定稿新量登记 | r3o_register.py | r3o_quantities.json | corrected_first_choice_ratio_paper_weight.2025 |
| Q73 | R3o：原始首择份额（44.8 峰→13.5；构成解释 55.2%） | 44.8%→13.5% | R3-O 叙事定稿新量登记 | r3o_register.py | r3o_quantities.json | first_choice_share.2025 |
| Q74 | W6：稳健留存序列（EC 63.4→41.6；NON 57.3→65.8） | 63.4%→41.6% | W6 作者流动 | author_flow.py | authors_flow.json | ec_attrition_series_robust[0].EC |
| Q75 | W6：EC→非 EC 迁移（4.6→8.9）与净流动比 0.95→1.62 | 4.6%→8.9% | W6 作者流动 | author_flow.py | authors_flow.json | flow_full[0].EC->NON |
| Q76 | W8：基金子集外部份额 2025（2016 1.63%） | 15.94% | W8 基金议程 | funding_agenda.py | funding_agenda.json | funded_subset_share.2025.external_sum |
| Q77 | W8：与论文议程 lag-0 同步（一阶差分 r；精确置换 9!=362,880 次单侧 p=0.0003） | +0.926 | W8 基金议程 + 深审批次3 置换复核 | funding_permutation.py | funding_permutation.json | observed_r_lag0_first_difference（登记值 0.926 = 复核值 0.9258 舍入；原 funding_agenda.json 字段系水平相关 0.996，2026-10-20 勘误改指） |
| Q78 | W8：基金覆盖率（总 44.0%；2025 79.3%） | 44.0% / 79.3% | W8 基金议程 | funding_agenda.py | funding_coverage.json | 2025.coverage |
| Q79 | P5：自引率 2025（2002 30.74%） | 10.14% | P5 反直觉证据束 | authors.py | authors.json | self_citation[year=2025].rate |
| Q80 | P5：NSGA-II 年被引（2020→2025） | 2,636→4,518 | P5 反直觉证据束 | checks.py | checks.json | c3_nsga2_series.oc.2025 |
| Q81 | W1：记忆方向分裂（≥5 岁首末，按系列） | CV 0.59→0.49、NLP 0.60→0.44 vs OR 0.73→0.76、evo 0.71→0.79、ML 0.49→0.69 | W1/W2 外部轮廓 | w1_panels.py (archived) | age_w1.json | operations_research__S103321696.2025.share_ge5 |
| Q82 | 0-6：EAAI/ESWA 池膨胀（构成迁移载体） | EAAI 284→1,859；ESWA 1,209→3,282 | 0-6 合并名稳定集重算 | stable8_merged.py | stable8_merged.json | per_source_e1.2021\|Engineering Applications of Artificial Intelligence.n_non |
| Q83 | 0-6：反向全支持 E1 水平（3.010→3.150→3.046） | 3.010 / 3.150 / 3.046 | 0-6 反向阶梯与 within-source 矩阵 | stable8_merged.py | stable8_merged.json | s1_reverse_full.2021.E1_mean_edges_to_non |
| Q84 | U0：2019→2024 窗口三基期摆幅 | +14.3% / −0.4% / −20.8%（摆幅 35.1pp） | U0 构成权重基期选择全表 | stable8_merged.py | stable8_merged.json | baseline_table_forward_1924 |
| Q85 | A2：Fig1a 反向 E1 三基期区间 | +13.3%~+18.3% | A2 图组展示值 | stable8_merged.py | stable8_merged.json | baseline_table_reverse_2124 |
| Q86 | 配对 gap 明细（econ↔bus −22.2pp/E3 +22.4 翻正；soc↔poli −9.7pp；neuro 正值占比 12.2%；phys↔mat L/P −110.5/−121.3） | 见登记行 | v3 双引擎稿增补登记 | fieldmap.py | fieldmap.json | pair_gaps_pp.economics<->business.E1.pooled_rel / pair_gap_bootstrap_e1.sociology<->political_science.q50 |
| Q87 | 锚源换新计数（PRB 14,892/14,894 双报；BMJ 9,474；NEJM 3,266） | 见登记行 | v3 双引擎稿增补登记 | prescreen_source_lookup.py | source_health.json | S4210237713.articles_2021_2023 |
| Q88 | U3 判定分解（9,600 缺陷 + 1,000 清洁 + 200 void = 10,800） | 见登记行 | v3 双引擎稿增补登记 | defect_injection_validation.py | defect_injection_validation.json | cells |
| Q89 | PRB 分裂源不剔除反事实（physics→materials pooled E1 不剔除 +59.5% 对剔除 +56.2%，失真 +3.36pp；现代窗边 17,979→31,820） | 见登记行 | 录用级整改增补登记 | prb_counterfactual.py | prb_counterfactual.json | included.pooled_e1_rel_change / distortion_pp / included.modern_edges |
| Q90 | E3 零解析参考文献分母暴露（七源共同支持；fwd ≤0.16% / rev ≤0.11%，双向千分位近对称） | 见登记行 | 批次 1 增补登记（2026-10-20） | probe_zero_resolved_share.py | zero_resolved_share.json | years.2021.forward_non_ec.share / years.2024.reverse_ec.share |
| Q91 | 子族首秀作者双口径（EC 首秀分母 M1=7,365/M2=12,946；EMO +32.1%/PSO +120.7%/GA −60.9%/GP −49.8%/GenEC −35.7%；5 族过 25% 线裁定不翻转；与 r3a 存档 exact 一致） | 见登记行 | 批次 2 增补登记（2026-10-20） | subfamily_dual_share.py | subfamily_dual_share.json | denominators.M1_ec_debuts / denominators.M2_ec_debuts / trigger_recheck.n_pass |
| Q92 | 批次3 P1-2：金标准混淆矩阵与逐类精度（200 篇；精度 EC 0.98/非EC 0.97；一致率 0.97 与 Q33 一致） | 0.97（194/200） | 批次 3 增补登记（2026-10-20） | gold_label_audit.py | gold_label_audit.json | gold_confusion |
| Q93 | 批次3 P1-2：0.03/0.05/0.10 对称翻转噪声下双向 E1 间隙稳健（三档 P(gap>0)=1.000；中位 19.54/21.24/22.79pp） | P(gap>0)=1.000 | 批次 3 增补登记（2026-10-20） | gold_label_audit.py | gold_label_audit.json | flip_noise |
| Q94 | 批次3 P1-3：逐源重抽分位数（反向七源点估计全正、区间 q025 均穿零；合并反向 q025=+0.039） | 逐源 q025 −0.316~−0.028 | 批次 3 增补登记（2026-10-20） | persource_bootstrap.py | persource_bootstrap.json | per_source_quantiles |
| Q95 | 批次3 P1-4：λ 分母双版（E1 两版同 0.206；E3 A 版 0.239=B 版 0.041 之上更宽暴露界） | 0.206 / 0.239 / 0.041 | 批次 3 增补登记（2026-10-20） | flip_lambda_dual.py | flip_lambda_dual.json | windows |
| Q96 | 批次3 P1-9：Poisson 池化=4 源合计（与单源同分布）；精确 0.0941；登记 MC 值均在 MC 误差内不改动 | 0.0941 | 批次 3 增补登记（2026-10-20） | poisson_pooled_check.py | poisson_pooled_check.json | cells |
| Q97 | 批次3 P1-11：资助差分 lag-0 r 全置换零分布（362,880 重排；精确单侧 p=0.0003） | p=0.0003（N=362,880） | 批次 3 增补登记（2026-10-20） | funding_permutation.py | funding_permutation.json | exact_p_one_sided |
| Q98 | 终读修复：S5.1 within-EC-debut 列三格补值（EDA −42.0%/LCS −84.0%/Genetic fuzzy −61.5%，描述性未检验） | −42.0% / −84.0% / −61.5% | 批次 3b 增补登记（2026-10-20） | subfamily_dual_share.py | subfamily_dual_share.json | subfamilies |

---

## 待补编号（装配批次，暂不参与硬核对）

本批 Q35–Q40 已于 2026-10-17 A2 图组装配时补入主表（Fig1a/Fig2a 展示值、ED1–ED3 数据源）。Q41（命题 2 核对表逐源记号）未分配：其展示已由 ED2 承担、数据源登记于 Q37，Q41 保留为 SI 表定稿（A3）备用。

## 维护工序

1. 新增数字：先在 `NUMBERS.md` 加登记行 → 在本文件分配 Q 编号 → 再写入正文/图注/表。
2. 每轮装配后：由 `verify_numbers.py` 以 Q 编号为键复跑三方核对，输出到 `paper/build/`。
3. 本文件与 `research/drafts/numbers_checklist.csv`（数字白名单）同步维护；正文出现未登记数字即视为未通过。
