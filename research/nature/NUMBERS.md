# NUMBERS.md — 正文数字来源登记表

## 库概况（2026-09-29 增补，PKG-C OQ-2 裁定；来源 AGENTS.md 库概况节 + ecdb info）

| 数字 | 值 | 来源 |
|---|---|---|
| 库总量 | 146,785 篇（2000–2025，期刊/会议论文，核心字段零缺失） | AGENTS.md / ecdb info |
| EC 打标子集 | 47,834 篇（金标准 200 篇人工评估准确率 97%） | paper_domain |
| 非 EC 对照 | 98,951 篇 | paper_domain |
| 低置信标签待复核 | 2,528 篇（W4b 待执行） | archive/labeling |
| 参考文献列表 / 被引列表 | 735 万条 / 1,144 万条（三源） | eccite |
| 库内引用边（DISTINCT 回连） | 922,842 条 | disruption_run.log |

维护规则（PLAN.md v3 硬规则）：**REPORT/PLAN/论文正文引用任何统计数字，一律以本表为准**；本表每行登记 脚本 → 输出文件 → 字段路径，数字与 out/ 中间结果一一对应。脚本重跑后须同步更新本表（生成日期列）。登记表没有的数字不得写入正文。
生成：2026-09-29（W0 全量重跑：authors / checks / memory / terms / trade / beauty / disruption / stability，8 脚本，日志在同目录 `*_run.log`）。

## 总口径（全表适用）

- 库内引用边：`paper_refs_out.cited_doi` 回连 `papers.doi`，跨来源 DISTINCT（当前 922,842 条，disruption_run.log）；
- 右删失：施引年 >2025 的行一律剔除（全库 607,204 行，memory.json `truncated_rows_gt_2025`）；CD5 队列止于 2020；
- 左边界：库始于 2000 年，"从业 15 年以上资深作者"2015 年起才可测、"首次出现"类指标早期年份不可比——此类数字只报可测区间；
- 期刊聚合一律用 `papers.source`（venue_tag 是导出批次标签）。

## P1 引用记忆

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| 偏好比 2006（oc 主口径） | 0.472 | memory.py | memory.json | youth_bias_oc[year=2006].I1_over_I6 |
| 偏好比 2016（交叉点前后） | 1.092 | memory.py | memory.json | youth_bias_oc[2016].I1_over_I6 |
| 偏好比 2024（最新完整年） | 1.607（s2 1.669 / 全源 1.636） | memory.py | memory.json | youth_bias_oc/s2/all[2024] |
| 被引年龄中位数（oc） | 2006:3 → 2016:5 → 2025:4 | memory.py | memory.json | by_citing_year_oc[].median_age |
| ≤1 岁份额（oc） | 2006:21.4% → 2016:14.7% → 2025:21.5% | memory.py | memory.json | by_citing_year_oc[].share_age_le_1 |
| ≥5 岁份额（oc） | 2006:27.9% → 2019 峰 53.2% → 2025:41.2% | memory.py | memory.json | by_citing_year_oc[].share_age_ge_5 |
| 被引前置化 w01/(w01+w23) | 2000 队列 26.1% → 2019 队列 37.0% | memory.py | memory.json | cohort_windows[].early_share_01_of_0_3 |
| 记录量 | 剔除 >2025 行后 1,057.6 万条 | memory.py | memory_run.log | — |

## P2 知识流入流出

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| 流入/篇（全库） | 0.07(2005)→1.37(2023 峰)→1.17(2025) | trade.py | trade.json | flow[not a_tier_only].import_per_ec_paper |
| 流出/篇（全库） | 0.065(2005)→0.625(2019 峰)→0.447(2025) | trade.py | trade.json | flow[].export_per_non_paper |
| 篇均口径比 | 1.08(2005)→2.62(2025) | trade.py | trade.json | flow[].ratio_citing_side_pools |
| 原始边数比 | 1.18(2005)→0.99(2019)→0.67(2025) | trade.py | trade.json | flow[].ratio_raw_edges |
| 被引侧口径比 | 1.34(2005)→0.17(2025) | trade.py | trade.json | flow[].ratio_cited_side_pools |
| A 类流入/篇 | 0.05(2005)→1.10(2025)，约 22 倍 | trade.py | trade.json | flow[a_tier_only].import_per_ec_paper |
| C2 固定期刊集出口率 | 0.059(2005)→0.830(2021 峰)→0.503(2025)，−40% | checks.py | checks.json | c2_fixed_venue_export[].rate |
| C2 稳定刊源（8 家） | ASC/C&IE/C&OR/EAAI/EJOR/ESWA/IEEE TFS/InfSci | checks.py | checks.json | c2_stable_sources |
| 固定期刊集内三归一 | 2005: 1.16/7.40/0.18 → 2025: 0.59/6.62/0.05（raw/篇均/被引侧） | trade.py | trade.json | fixed_venue_flow[] |
| 非 EC 池膨胀 | 2020:5,021 → 2025:10,954 篇（+118%） | trade.py | trade.json | flow[].pool_NON |

## P3 颠覆指数

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| EC CD5 均值 | 2003:+0.34 → 2019:−0.248 → 2020:−0.243 | disruption.py | disruption.json | rows[].EC.mean |
| 非 EC CD5 均值 | 2002:+0.28 → 2010 低点:+0.044 → 2019:+0.201 → 2020:+0.278 | disruption.py | disruption.json | rows[].NON_EC.mean |
| A 类 CD5 | 2020 均值 −0.442 / 中位 −0.621 | disruption.py | disruption.json | rows[].A_pure_ec |
| 稳定对照组分化 | 2019：EC −0.248 vs 稳定非 EC +0.161 | stability.py | stability.json | b_stable_control_cd5.series |
| 二维同格差距（早期两格精确值） | 2005-07 可测两格：Rp5-10\|Rq5-10 为 **−0.027**（EC −0.177, n=151 vs 非 EC −0.150, n=98）、Rp5-10\|Rq11-20 为 **+0.074**（EC −0.311, n=50 vs 非 EC −0.385, n=58）——两格一负一正、量级均近零 | stability.py | stability.json | c_cd5_2d_strata |
| 二维同格差距 | 2005-07 可测两格 ≈0（−0.03～+0.07）→ **2018-20 全部 8 格一致为负（−0.08～−0.25）**；高 \|R\| 主格（Rp21-40）−0.08/−0.15，低 \|R\| 格更深至 −0.17～−0.25 | stability.py | stability.json | c_cd5_2d_strata（2026-09-29 全格复算，PKG-C OQ-1 裁定） |
| 解析率（≥5 条参考论文） | EC 0.124(2005)→0.406(2025)；非 EC 0.049→0.178(2020 峰)→0.151(2025) | stability.py | stability.json | a_resolution_rate |
| 分桶控制 C1（2018-20） | 5-10 桶：EC −0.11 vs 非 EC +0.20；21-40 桶：−0.56 vs −0.30 | checks.py | checks.json | c1_bucket_cd5 |

## P4 研究议程

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| LLM/GPT 份额（A 类口径） | 2013-22 全 0 → 2023:0.28% → 2025:2.66% | terms.py | terms.json | share["LLM/GPT"][y].a |
| LLM/GPT 份额（EC 口径） | 2023:0.11% → 2025:1.81% | terms.py | terms.json | share["LLM/GPT"][y].ec |
| prompt（A 类，收紧后） | 2024:0.37% → 2025:0.68%（原 `\bprompt` 口径 1.93%，精确率仅 72%，已弃用） | terms.py | terms.json | share.prompt[y].a |
| RL vs DL（EC 口径 2025） | 6.22% vs 3.80% | terms.py | terms.json | share["reinforcement learning"/"deep learning"][2025].ec |
| 外部主题合计（EC 口径） | 约 1.9%(2005) → 约 17%(2025) | terms.py | terms.json | share 各外部词 .ec 之和（五词有重叠，作量级） |
| genetic algorithm（EC 口径） | 31.4%(2005) → 14.4%(2025) | terms.py | terms.json | share["genetic algorithm"][y].ec |
| multi-objective（EC 口径） | 13.9%(2005) → 31.6%(2025) | terms.py | terms.json | share["multi-objective"][y].ec |
| 模拟退火（EC 口径） | 3.84%(2005) → 2.20%(2025)——唯一收缩的经典方法词 | terms.py | terms.json | share["simulated annealing"][y].ec |
| ~~受控词跨年比值~~ | **已撤回**（标引口径漂移，仅限同年内跨组比较） | terms.py | terms.json | term_tides_*（限用） |

## P5 反直觉证据束

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| 自引率 | 30.74%(2002) → 10.14%(2025) | authors.py | authors.json | self_citation[].rate |
| 互引率 | 2025 年 0.04% | authors.py | authors.json | reciprocity[].rate |
| NSGA-II 被引（oc 单源） | 2020:2,636 → 2025:4,518 | checks.py | checks.json | c3_nsga2_series.oc |
| 新人参与率 | 2015 年后稳定 76–80%（早期波动：2003:85.7%、2010:74.4%） | authors.py | authors.json | entrants[].share_papers_with_newcomer |
| 资深作者参与率 | 2015:6.6% → 2025:39.0%（仅此区间可测） | authors.py | authors.json | entrants[].share_papers_with_veteran15 |
| EC 份额 | 28.8%(2000) → 49.9%(2005 峰) → 20.4%(2025) | 复核 SQL | — | papers×paper_domain 按年 |

## 基础设施数字

| 数字 | 值 | 来源 |
|---|---|---|
| 库内引用边（DISTINCT） | 922,842 | disruption_run.log |
| 右删失剔除行（>2025） | 607,204 | memory_run.log |
| 高解析期刊子集（≥90%） | 不可行（解析率上限约 0.4，语料只覆盖 EC 及邻近） | stability.json d_highres_cd5（空集，保留作记录） |

## W4a 稳健性扩展（2026-09-29，w4a.py）

| 数字 | 值 | 输出 | 字段路径 |
|---|---|---|---|
| CD 窗口变体分化差（2019） | CD3 gap −0.440 / CD5 gap −0.449（2020：−0.522）；CD10 2013 gap −0.305 | w4a.json | cd_window_variants |
| 自引剔除版 CD5（2019） | EC −0.176 vs 非 EC +0.257（gap −0.43，分化保持） | w4a.json | cd5_no_self |
| 团队规模同桶 CD5（2018-20） | 1-2 人桶：EC −0.204 vs 非 EC +0.132；3-4 人桶：−0.236 vs +0.206；7+ 人桶：−0.337 vs +0.395 | w4a.json | team_size.buckets |
| EC 平均团队规模 | 2.52(2005) → 3.61(2020) | w4a.json | team_size.mean_team_size |
| 同 source 内 EC CD5 变化 | 8/8 家全部下滑：TEVC +0.012→−0.477（Δ−0.49）、InfSci +0.248→−0.204、ASC +0.392→−0.004、LNCS −0.105→−0.470、ESWA +0.363→+0.038、EJOR +0.012→−0.262、C&OR −0.023→−0.287、C&IE +0.054→−0.089 | w4a.json | source_within_decline |
| 姓名同名重合概率（随机论文对） | 0.00013(2005) → 0.00003(2023)，远小于观测自引率且反向——自引率下降非姓名伪影 | w4a.json | name_density |

## W5 维度相关（2026-09-29，vitality.py；公共区间 2006–2020，n=15）

| 数字 | 值 | 输出 | 字段路径 |
|---|---|---|---|
| 水平相关（Pearson） | D1~D2 −0.962、D1~D3 −0.907、D2~D3 +0.925、D1~D4 −0.514 | vitality.json | corr |
| 一阶差分相关（去趋势） | 全部 |Δr| ≤ 0.33（D1~D2 −0.330、其余 −0.18～+0.15） | vitality.json | corr_first_difference |
| 判定 | 四维共享长期趋势、逐年波动独立 → **不合成单一指数**，以多维面板+共线结构呈现 | — | PLAN v3 W5 |

## W1 mini-pilot（2026-09-29，openalex_pilot.py）

| 数字 | 值 | 输出 | 字段路径 |
|---|---|---|---|
| OpenAlex 可达性 | 可达（API 直连成功，polite pool） | openalex_pilot.json | — |
| TEVC 2020–25 works | 1,048 篇，100% 有 DOI，参考文献中位数 59 条（本库 49） | openalex_pilot.json | oa_total/ref_count_median_* |
| DOI 命中率（对本库） | 62.6%（656/1048）；未命中样本几乎全为编者按/目录/勘误等前置内容（本库清洗时已剔除）——研究论文层面对齐率约 90%+ | openalex_pilot.json | doi_hit_in_our_lib/oa_only_sample_titles |
| 判定 | **W1 全景路线可行**；对齐按 DOI 优先、需处理前置内容与研究论文的区分 | — | PLAN v3 W1 |

## W2 预实验（2026-09-29，w2_pilot.py；OpenAlex 硬标准检验）

| 案例 | 总 works（窗口内） | 带参考文献 | ≥50 篇/年达标 | 参考年份解析率（中位） | 中位被引年龄 | 判定 |
|---|---|---|---|---|---|---|
| 专家系统 1978–93 | 34,360（峰值 1990：4,854） | 16,178 | 13/16 年 | 0.84 | 2.0（可算） | **PASS** |
| 符号 AI 1980–95 | 21,022（峰值 1994：2,422） | 12,935 | 16/16 年 | 0.92 | 3.5（可算） | **PASS** |
| 模糊逻辑 1975–2000 | 22,633（峰值 2000：2,641） | 13,164 | 25/26 年 | 0.96 | 5.5（可算） | **PASS** |
| 感知机/控制论 1955–75 | 3,171（峰值 1970：341） | 1,023 | 10/21 年 | 1.00 | 5.0（可算） | 标准不满足，按预注册规则降级为定性补充 |

## W1 面板骨架（2026-09-29，w1_panels.py；1985–2025 年度曲线 + 参考文献可用率）

| 领域 | 锚定期刊（OpenAlex source） | 总 works | 参考文献可用率 |
|---|---|---|---|
| 运筹优化 | EJOR（S103321696）；Management Science（S33323087） | 22,693；9,767 | 89.0%；86.0% |
| 控制理论 | Automatica（S51360982）；IEEE TAC（S184954342） | 13,692；18,355 | 92.4%；88.6% |
| 机器人 | IJRR（S73484101）；RAS（S133768115） | 3,101；5,164 | 90.0%；81.0% |
| NLP | Computational Linguistics（S155526855） | 1,664 | 67.7%（偏低，需补锚点） |
| 计算机视觉 | IJCV（S25538012） | 3,617 | 93.9% |
| 演化生物学 | Journal of Theoretical Biology（S109682412） | 13,260 | 81.3% |
| 机器学习（牛市对照） | Machine Learning（S62148650） | 3,812 | 85.1% |

## W6 作者流动（2026-09-29，PKG-A 交回；archive/packages/w6_authors/out/authors_flow.json；详见包内 NUMBERS_W6.md）

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| 首秀方向（新人首篇选 EC 份额，全量主口径） | 2005 峰值 44.8% → 2020:26.3% → **2025:13.5%** | author_flow.py | authors_flow.json | first_dir_series.full |
| EC 留存份额（期段间） | 全量 28.7%→17.8%；稳健（≥3 篇）63.4%→41.6% | author_flow.py | 同上 | ec_attrition_series_full/robust |
| EC→非 EC 迁移份额 | 全量 4.6%→8.9%；稳健 9.4%→18.3%（两版首末均 ×1.95） | author_flow.py | 同上 | 同上 |
| 净流动比（EC→NON ÷ NON→EC） | 全量 0.95→1.62；稳健 0.93→1.66（2015 后稳定 ~1.6 倍流出） | author_flow.py | 同上 | flow_*/flow 行份额派生 |
| NON 侧对照（剪刀差） | NON 留存上升（稳健 57.3%→65.8%）而 EC 下降——非语料整体现象 | author_flow.py | 同上 | flow_robust |
| 人工核对 | 46/50 成立（8%<10% 阈值）；稳健版 2025 首秀 19.4% 系幸存者选择效应，主口径用全量版 | — | flow_sample_review.md | — |

## W8 基金议程（2026-09-29，PKG-B 交回；archive/packages/w8_funding/out/；详见包内 NUMBERS_W8.md）

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| 覆盖率（逐年权威） | 2020:64.6% → 2025:79.3%；总覆盖 44.0%（原 67% 锚系分箱误置，已更正） | funding_agenda.py | funding_coverage.json | coverage |
| 基金子群体外部主题份额 | 1.63%(2016) → 4.29%(2020) → 8.50%(2022) → **15.94%(2025)** | funding_agenda.py | funding_agenda.json | funded_subset_share[].external_sum |
| 与论文议程的先行/滞后 | 水平相关各 lag 0.979–0.996（最大 lag 0）；一阶差分诊断 lag 0 r=+0.926——**同步外部化，未见资金先行信号** | 同上 | 同上 | leadlag_funded_vs_full_ec |
| 基金 vs 全体份额差 | 2020–25 各年基金子群体外部份额低 0.50–1.37pp | 同上 | 同上 | 与 terms.json 对照派生 |

## W7 预研与降级版（2026-09-29，PKG-D 交回；archive/packages/w7_prep/out/；详见包内 NUMBERS_W7.md）

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| EC 论文引用 LLM 地标集的份额（修正口径） | 0.00%(2018–19) → 0.68%(2025)，八年合计 50 篇 | llm_cite_mode.py（bert 修为 `\bbert\b`） | llm_citation_mode.json | share_series |
| 标记组画像（2023–25，n 标记组） | A 类占比 42.4% vs 未标记 53.4%；篇均参考文献 90.3 vs 47.7；自身 LLM 主题份额 15.2% vs 1.0% | 同上 | 同上 | profile_2023_2025 |
| EoH 试运行成本 | 单次调用列表价折算约 0.02–0.06 元；全程消耗远低于 200 元帽 | run_eoh_trial.py | eoh_run.log（JSONL 记账） | — |
| 推理模型思考 token 占比 | 输出 token 的 60–85%（费用须按总 token 外推，低估 3–5 倍风险） | 同上 | eoh_trial_report.md | — |
| ~~bert 无边界匹配版~~ | 作废留存（184 标记中 136 系 ber**t**h/人名误中） | — | llm_citation_mode_v0_bert_contaminated.json | 不引用 |

## P4 模式校验（2026-09-29，p4_validate.py；详见 archive/research_20261005/p4_validation.md，2026-10-05 归档）

| 模式 | 精确率（人工复核） | 处置 |
|---|---|---|
| LLM/GPT | 50/50 ≈ 100% | 不改 |
| transformer（限定版） | 11/13 ≈ 85% | 保留（影响 <0.1pp） |
| prompt（原版） | 36/50 ≈ 72% | **收紧为复合形式**，份额 1.93%→0.68%（A 类 2025） |
| 负样本假阴性 | 0/50 | 模式族召回无可见问题 |

## W1/W2 外部轮廓（2026-10-01 交回收割；结果已并入 research/nature/out/；明细见 archive/packages/w1w2/NUMBERS_W1W2.md）

| 数字 | 值 | 输出（nature/out/） | 字段路径 |
|---|---|---|---|
| W1 面板 | 11 源 96,170 篇（10 预注册 + NLE 追加），完整率全 1.000 | w1_download_summary（包内） | — |
| W2 案例面板 | 42,277 篇（三案例，逐年对账 1.000） | 同上 | — |
| **W1 引用记忆方向分裂（Fig1 核心看点）** | ≥5 岁份额：DL 邻近领域下降（CV 0.59→0.49、NLP 0.60→0.44）vs 方法论领域上升（OR 0.73→0.76、控制 0.61→0.74、演化生物 0.71→0.79、ML 0.49→0.69） | age_w1.json | 各面板 share_ge5 首末 |
| 抽样 CD 覆盖 | n_valid≥20 口径 214/244=0.88（严格 ≥30 口径 0.61，65 个 low_valid 轮廓级） | cd_sampled.json | 各面板 meta |
| 预警提前量（主口径 2000 锚定） | **6/9 命中**，提前量 −1～−10 年（中位 −4.5）；产业口径 1991 敏感性 7/9 | early_warning_table.json | rows/summary |
| 负例假阳性 | 2 个未衰退领域同流程触发 **7 次**个体指标转折信号——单指标判据假阳性不低，多维协同判据区分力待 W3 §5 重算 | 同上 | negative_controls |
| TEVC 双口径对照 | **未过线**：Spearman ρ=0.086、均值差 −0.24（OA −0.52~−0.75 vs 库内 −0.33~−0.44）；归因：前 100 施引者截断（上界 35–50%）/噪声/施引池差异 | tevc_crosscheck.json + tevc_attribution.json | per_year/spearman_rho |
| 领域边界三口径一致性 | 通过（ρ≥0.8 判据；控制与演化生物两域） | boundary_consistency.json | 各域 |
| W2 案例记忆轨迹 | 专家系统/符号 AI：≥5 岁份额先降后回升；模糊逻辑同型 | age_w2.json | 各案例 share_ge5 |
| 多维协同判据区分力（W3 §5 重算，2026-10-01） | 口径 A（指标变体）：正例 3/3 触发（落窗 2/3：−5/−10；模糊逻辑 −22 超窗、产业口径 −13 命中）、负例假阳性 7→1——**但触发簇全部为引用记忆同维两变体共转（伪影）**；口径 B（独立维度）：0/3 触发（维度转折相距 6–18 年）——判据在历史面板不具评估条件，不作为能力主张 | w3s5_coturn.py | w3s5_coturn.json | conclusion + 两口径 summary |

## R3-O 叙事定稿新量登记（2026-10-01，r3o_register.py；叙事会话两新量 + 槽位权重版 + 格级表，先登记后使用规则兑现）

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| 构成校正首选比（论文权重版） | 0.930(2003) → 0.898(2005) → 0.791(2013) → 0.788(2022) → **0.663(2025)**；2013–22 无趋势，降幅集中 2023–25 | r3o_register.py | r3o_quantities.json | corrected_first_choice_ratio_paper_weight |
| 构成校正首选比（作者槽位权重版，两版并列） | 0.906(2003) → 0.875(2005) → 0.789(2013) → 0.823(2022) → **0.714(2025)**；2013–22 轻微上行、2023–25 下降——与论文版同向但更平缓（正文引用时两版并列） | 同上 | 同上 | corrected_first_choice_ratio_slot_weight |
| EC 语料份额（论文权重，Fig1b） | 28.8%(2000) → 49.9%(2005 峰) → 20.4%(2025) | 同上 | 同上 | ec_corpus_share_paper_weight |
| EC 语料份额（作者槽位权重） | 31.0%(2000) → 51.2%(2005) → 19.0%(2025)（槽位口径，作敏感性分母；2025 低于论文口径 20.4%——EC 论文篇均作者槽位更少） | 同上 | 同上 | ec_corpus_share_slot_weight |
| 二维同格覆盖度（2018–20） | **EC 84.1%**（3,271/3,891）、**非 EC 67.0%**（4,855/7,243）；定义=分层表该组全部格 n 之和 ÷ disruption.json 该组 2018–20 可算论文数——作"非全体无偏估计"限定语使用 | 同上 | 同上 | strata_coverage_2018_20 |
| 格级区间与 n（2018–20 八共有格） | gap **−0.245 ～ −0.079 全负**；EC n 108–716、非 EC n 108–1,426；逐格表（均值/点差/n）见输出文件 | 同上 | 同上 | strata_2018_20_matched_cells |

> 自检：首选份额与 PKG-A 全量序列逐年一致；八格区间与 NARRATIVE_v1 引值（−0.08～−0.25）一致；覆盖率与叙事会话引值（84.1%/67.0%）精确一致。槽位权重版系本表新增（NARRATIVE §2 腿 2 加固项），方向与论文版一致但幅度更平缓，正文两版并列呈现。

## R3-A 子方向拆分（2026-10-01，r3a_execute.py；规则=R3E_FREEZE.md，冻结者≠执行者；双轨裁决第一输入）

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| 分类有效性（OTHER 率复算） | **2.6%**（47,834 篇，门槛 ≤10% 通过，与设计期 v3 一致） | r3a_execute.py | archive/packages/r3a/out/r3a_results.json（包 2026-10-05 归档） | validity_other_rate |
| 两期分母 | N(G1 2003–07)=**18,031**；N(G2 2019–22)=**53,184**（与 PKG-A 逐年合计一致） | 同上 | 同上 | denominators |
| 资格族（两期各 n≥200） | **9/17**；不合格 8 族单独披露不参与判定 | 同上 | 同上 | subfamilies[].eligible |
| 深跌资格族 | ga **−76.7%**、遗传规划 **−70.1%**、通用进化 **−61.7%**、进化策略 **−55.1%**、模因 **−53.5%**、其他元启发式 **−52.4%**、其他 **−48.3%**（均 p_raw 与 p_BH <1e-6） | 同上 | 同上 | subfamilies[] |
| **EMO 降幅不足** | 0.0465→0.0366，**−21.3%**（显著下降但 <25% 门槛；n=839/1,948） | 同上 | 同上 | 同上 |
| **粒子群显著上升** | 0.0253→0.0333，**+31.5%**（z=−5.33，上升方向 p<1e-6；n=457/1,773） | 同上 | 同上 | 同上 |
| 非资格上升族（G1<200） | other_swarm_bio 119→1,697（份额 ×4.8）、differential_evolution 143→868、generic_heuristic 上升——群智能/差分进化族在涨 | 同上 | 同上 | subfamilies[] |
| **裁决条件 1 判定** | **不成立**：资格族 ≥3 ✓ 但"全部降幅 ≥25% 且双口径显著"✗（EMO 不足、PSO 反向） | 同上 | 同上 | trigger_input_A |
| 迁移率×族（描述，非裁决） | 各族 EC→NON 期段迁移率 7.0–7.9%，族间接近（末段不计分母，OQ-2 裁定） | 同上 | 同上 | migration_by_subfamily_descriptive |
| 自洽检验 | 首选份额逐年对 PKG-A PASS；Σ族份额 G1=0.4083/G2=0.2432（vs PKG-A 0.4085/0.2434，舍入差） | 同上 | 同上 | consistency |

| 子方向深跌族区间（Q17 派生表述） | 合格 9 族中 7 族降幅 **48–77%**（ga 76.7% / GP 70.1% / general_ec 61.7% / evolution_strategies 55.1% / memetic_hybrid 53.5% / other_metaheuristic 52.4% / OTHER 48.3%，均 p_BH=0.0）；emo 21.3%；粒子群 **升 31.5%**（唯一上升族） | r3a_execute.py | r3a_results.json | subfamilies[].rel_decline |

## R3-F 基线引用边剔除重算（2026-10-01，r3f_execute.py；规则=archive/packages/r3f/README.md 预注册，冻结者≠执行者；R3-H 判据 T2 交付；包 2026-10-05 归档）

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| 基线集合 B | \|B1 基准文化论文\|=562（题名模式）∪ \|B2 Top-50 经典\|=50（重叠 1）= **611**；锚点：NSGA-II∈B2（库内被引第 1，7,083 次）✓、CEC 2005 家族∈B1 ✓（原始技术报告不在库，OQ-1 裁定按家族在场义通过） | r3f_execute.py | archive/packages/r3f/out/r3f_results.json | baseline_set / anchor_check |
| 实现自检 | 不剔除版复现 8 格全负 −0.074～−0.245，与 stability.json 逐格偏差 ≤0.011 | 同上 | 同上 | strata_original |
| **剔除后 2018–20 逐格 gap'** | 5-10 端 4 格**存活**：−0.205（5-10\|5-10）/−0.150（11-20\|5-10）/−0.121（5-10\|21-40）/−0.113（5-10\|11-20）；21-40 端 4 格**机械解释**：−0.045/−0.036/+0.030/+0.014（两格翻正） | 同上 | 同上 | strata_removed / T2.gaps |
| **T2 判定（R3-H 输入）** | **False**——8 格中 4 格 \|gap'\|>0.05：CD 差距在低参考文献密度端存活、高 Rp 端可被基线引用规范机械解释；**腿 3 解释权排他性检验部分通过（差距非全机械）** | 同上 | 同上 | T2.all_within_0.05 |
| 两版可算论文数 | 原始 34,054 → 剔除后 33,688（−366） | 同上 | 同上 | cd5_computable |
| 被引集中度（B 吸走份额，非裁决） | 0.024(2002)→0.122(2010)→**峰值 0.147(2019)**→0.098(2025)——基准引用文化先强化后回落 | 同上 | 同上 | baseline_concentration_share |
| 参考文献重合度（Jaccard，非裁决） | 2003–25 平稳 0.002–0.004，未见上升 | 同上 | 同上 | reference_overlap_jaccard |

## R3-B 三维对照与 CD 桥接（2026-10-01，r3b_dims.py + r3b_cd.py；规则=archive/packages/r3b/README.md 预注册；轨 A 最小集收口件；包 2026-10-05 归档）

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| 锚定复现 | 记忆全库锚/CD 三年锚与 memory.json、disruption.json 差 0.0000；稳定集 8 家一致；收支单端复算精确复现 C2 锚（OQ-1 裁定：双端为对照口径、单端为腿 1 锚，并存） | r3b_dims/cd | archive/packages/r3b/out/*.json | 各锚定字段 |
| **收支双端口径（对照新量）** | NON→EC：0.018(2002)→**0.686(2021 峰)→0.358(2025)**（−48%，复现腿 1 回落形态）；EC→NON：0.128(2002)→3.22(2021)→2.80(2025) 持续高位——**单向脱钩**（EC 引非 EC 高企、非 EC 引 EC 回落） | r3b_dims.py | r3b_dims.json | balance_stable |
| 记忆分侧（≥5 岁份额，2006 起读） | EC_stable 0.251(2006)→0.553(2025)、NON_stable →0.421、EC_all →0.517、NON_all →0.245——**两侧同向上升，非 EC 亦老化**（2026-10-02 勘误：原登记 0.279 系误抄全库锚值，K3 对账发现，实测 0.2506） | 同上 | 同上 | memory_by_group |
| 议程分侧（external_sum） | EC_any 1.1%(2000)→**15.4%(2025)**、NON_any 0.9%→**28.9%**、NON_stable →30.9%——**两侧同向外部化，非 EC 更甚** | 同上 | 同上 | agenda_external_sum |
| **CD 桥接（gap=EC−NON）** | cd5 至 2020 −0.521；**cd3 2021 −0.525/2022 −0.562；cd2 2021 −0.531/2022 −0.585/2023 −0.616**——桥接年延续负值且加深，无反弹 | r3b_cd.py | r3b_cd.json | cd3/cd2[].gap |
| **施引池免疫差距** | cd5_NONciter（仅非 EC 施引者的共同标尺）gap 2018–20 −0.182/−0.182/−0.187，2009–2023 全负，2021–23 收窄至 −0.053——**差距非施引池构成伪影**，幅度约为原 1/3 | 同上 | 同上 | cd5_NONciter[].gap |
| 施引池构成（inbreeding） | EC 论文施引者 EC 份额 0.855(2002)→0.778(2023) 缓降（无内卷加深）；NON 论文施引者 EC 份额 0.158→0.061 持降——两文献体脱钩 | 同上 | 同上 | citing_pool_share_EC |

### R3-O 派生量补登记（2026-10-02，DIRECTION_MEMO 执行清单；K3 对账 r4 #5/#11/#16/#34 的处置）

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| 腿 1 分母序列（c2 集内非 EC 论文数） | 4,318(2021) → 7,608(2024) → **7,681(2025)**（+78% vs 2021） | checks.py | checks.json | c2_fixed_venue_export[].n_non |
| 腿 1 分子序列（c2 集内 EC 被引边数） | 3,584(2021) → 4,694(2024 顶点) → **3,864(2025)**（+8% vs 2021）——由 rate×n_non 导出（2021: 0.830×4,318；2025: 0.503×7,681，取整复核一致） | 同上 | 同上 | c2_fixed_venue_export[].rate×n_non（派生） |
| 腿 2 构成解释占比（论文权重版，2003→2025） | 原始首选份额降幅 64.1%（0.377→0.135），校正比降幅 28.7%（0.930→0.663）→ **构成解释 55.2%（约六成）** | r3o_register.py 派生 | r3o_quantities.json | first_choice_share / corrected_first_choice_ratio_paper_weight |
| 同格差距占未分层差距的比值 | 8 格差距绝对值（0.079/0.131/0.146/0.171/0.205/0.217/0.223/0.245）÷ 同期未分层 EC−NON 年差距（0.358(2018)/0.449(2019)/0.521(2020)）＝ **窄端 15.2%（0.079÷0.521）～宽端 68.4%（0.245÷0.358），即约 15%–68%（约 1/6–2/3）**——NARRATIVE"约 1/4 至 1/2"按此更正 | stability/disruption 派生 | stability.json + disruption.json | c_cd5_2d_strata（EC/NON 配对相减）与 rows[].EC.mean−rows[].NON_EC.mean |
| **收支边数序列（派生，非篇均）** | EC→NON 边数 2,123(2017) → **2,654(2021 峰)** → 1,931(2025)；NON→EC 边数 1,827(2017) → 2,964(2021) → 2,749(2025)。由 `balance_stable` 逐年 **N × rate** 实算（如 2021: 825×3.217≈2,654），非 `trade.json` 的 `EC_to_NON` 字段（该字段为全库口径，量级不同，两口径勿混算） | r3b_dims.py 派生 | r3b_dims.json | balance_stable[].N_EC×rate_EC_papers_cite_NON / N_NON×rate_NON_papers_cite_EC |
| 2025 共同截断效应（两流同向转弱） | EC→NON 2021→2025 **−27.2%**、NON→EC 同期 **−7.3%**——两条流在 2025 同时回落，提示 2025 年（数据末年）存在共同语料或截断层；Methods 须披露并给出排除处置 | 同上 | 同上 | 同上（派生比值） |
| 非 EC 池增长（稳定 8 刊集口径） | 2,747(2017) → 7,681(2025)，**+180%**（vs 2017；vs 2020 为 +118%，两起点并存勿混） | 同上 | 同上 | balance_stable[].N_NON |
| 施引池免疫差距占原始差距比值 | 2018–20：−0.1824/−0.1818/−0.1871 ÷ −0.3577/−0.4494/−0.5209 ＝ **50.9%/40.5%/35.9%，即约 36%–51%（登记原"约 1/3"系取整下沿，已更正）**；引用时须并呈 2021–23 收窄至 −0.053 | r3b_cd.py 派生 | r3b_cd.json | cd5_NONciter[].gap / cd5[].gap |

### H0 口径指认勘误（2026-10-05，内部对账确认并扩大）

| 勘误项 | 错误形态 | 正确口径（本表行号为准） | 处置 |
|---|---|---|---|
| fig1 底条分子方向 | 图内标注 "NON→EC edges (numerator) 2,123→2,654→1,931" | 该序列按 :263 为 **EC→NON** 边数；左轴双端率的分子应为 NON→EC 边数 2,964(2021)→2,749(2025)（:263，−7.3% 见 :264） | fig1 已重出（底条改稳定集 N_NON 池 + 集内 NON→EC 边数）；s21/讨论同款句已改 |
| fig1 底条分母 | "non-EC pool 5,021→10,954（+118%）"（全库池，:50） | 左轴率的分母是**稳定集**池：4,318(2021)→7,681(2025)（:259）；2,747(2017)→7,681（+180%，:265） | 同上 |
| `paper/plan/01` Q48 与 `doc_ids.md` Q48 标签 | "领域被引绝对边数 2,123/2,654/1,931"，源标 trade.json | 应为 **EC→非 EC** 绝对边数，源 `r3b_dims.json balance_stable` 派生（:263） | 两处已改，并增 doc_ids Q48b（双端分子 2,964/2,749） |
| s21 ¶2 分子分母 | 单端分子分母（3,584→3,864 / 4,318→7,681）挂在双端率（0.686→0.358）下，得出"分子微升" | 双端率分子 2,964→2,749（**降** 7.3%）；单端分子分母归单端率（0.830→0.503）自带 | s21 ¶2/¶3 与讨论 ¶1 已改 |
| s21 ¶3 "pool more than doubled" | 系在 2017–2021 窗口下表述 | 稳定集池 2017→2021 为 2,747→4,318（+57.2%，:259/:265 派生）；"翻倍以上"仅对 2017→2025（+180%，:265）成立 | 正文已改用 +180% 登记值表述 |

**教训留痕**：`verify_numbers.py` 查"数字是否登记"，查不到"数字挂错测量"——两处口径（双端 `balance_stable` vs 单端 `c2_fixed_venue_export`）并存时，引用必须自带口径标签（OQ-1 裁定并存以来首次系统性错位）。

### Fig1 重构补登记（2026-10-02，门面图数据）

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| EC 年发文量 | 早期约 1,400–1,600 → **2,995(2024 历史顶点) → 2,789(2025)** | trade.py | trade.json | flow[!a_tier].pool_EC |

## R3-P1 三项欠登记读数重跑与对账（2026-10-02，r3p1_rereg.py；写稿前置 ① 兑现）

**背景**：前期内部评审给出三条 CD 加固读数，但未附输出文件路径，须独立重跑验证后方可登记。本节为独立重跑结果，是正文引用的唯一权威版本。三条全部复现；③ 的两个具体数不成立，已按复算值更正。分桶口径：**整数十年桶**（`//10`），非分位十分位——分位口径下三维同格为 13/17 为负，是本会话的第一次误判。

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| **三维同格存活率**（cohort 2018/2019/2020 × Rp 桶 × Rq 中位桶，格内各 ≥30 篇） | **23 格中 21 格为负（91.3%）**；中位点差 **−0.166**、均 −0.159、最深 −0.364、最浅 +0.045 | r3p1_rereg.py | r3p1_recon.json | t1_3d_strata |
| 三维同格仅有的 2 个翻正格 | 2018\|10-19\|**20-29** +0.045（EC 121/非 EC 90）；2018\|**20-29**\|10-19 +0.034（EC 41/非 EC 71）——两格均为 Rq 高于 Rp 的组合，绝对 CD 值两侧同低 | 同上 | 同上 | t1_3d_strata.positive_cells |
| **回归控制：EC 主效应**（规格 A） | `cd5 ~ EC + \|Rp\| + \|Rq\| + 年FE`，n=**11,134**（EC **3,891**）→ **EC −0.1596**（OLS se 0.0119 / HC1 se 0.0127，t=−12.6）；\|Rp\| −0.0172、\|Rq\| **−0.0278**；年效应 2019 +0.0497、2020 +0.1146；R²=0.3118 | 同上 | 同上 | t2_regression_variants[A] |
| 回归口径说明（\|Rq\| 规格敏感性） | 正文主用规格 A（施引者**库内**参考列表中位数，与 stability.py cd5_detail 同口径）；若改用全池参考列表均值，EC 系数变 **−0.2939**——两个规格同号同显著，幅度差在口径说明中写明 | 同上 | 同上 | t2_regression_variants[B/C/D] |
| **库内解析参考文献中位数逐年**（参考文献 ≥5 条，每年 ≥100 篇） | EC **3→6→9→13**（2010 / 2016 / 2020 / 2025）；非 EC **3→3→5→4**；2010 年 3/3 持平，此后 EC 反超并拉开（2020 年 9 对 5） | 同上 | 同上 | t3_median_resolved_refs.series |
| 解析参考文献中位数分段均值 | EC 2002–2010 均值 1.56 → 2011–2025 均值 7.93；非 EC 0.67 → 4.00 | 同上 | 同上 | t3_median_resolved_refs.summary.seg_means |
| （受控说明）评审报值更正记录 | 评审报"2010 年 4/3 → 2025 年 13/5"与"2010 年前 EC 不高于非 EC"**部分不成立**：2025 年非 EC 中位为 **4** 不是 5；2010 年前 9 年中 EC ≤ 非 EC 的仅 **3 年**（2002/2003/2010）。机制方向（2010 年后反超拉开）成立 | 同上 | 同上 | t3_median_resolved_refs.summary.review_claim_check |

## 低置信打标队列剔除敏感性（2026-10-06，queue_sensitivity.py；WP5 SI 承诺兑现）

**背景**：分析管线（trade.py / r3b_dims.py）加载 paper_domain 全部标签，低置信队列（LLM 层 confidence<0.75，2,528 篇 = EC 1,318 + NON 1,210）实际包含在已登记读数内。Methods 旧表述"excluded from all analyses by default"与实际不符，已改为"retained in the corpus; effect of excluding reported in Supplementary Table 1"。下表为剔除队列后的头部读数复算（含队列版已校验复现登记值：2,995/2,789、0.686/0.358/3.217/2.803）。队列在稳定 8 刊集内占比偏高（912 EC + 870 NON，占该集 EC 的 6.1%），故水平值移动大于库均 1.7%——属预期，方向与降幅份额不变。

| 数字 | 值（含队列 → 剔除队列） | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| 双端率 outward（NON→EC 篇均） | 2021: 0.6864 → 0.5906；2025: 0.3579 → 0.3092；**自峰值回落 47.9% → 47.6%** | queue_sensitivity.py | queue_sensitivity.json | balance_with/without_queue |
| 双端率 inward（EC→NON 篇均） | 2021: 3.217 → 2.9428；2025: 2.8026 → 2.3813；2025/2021 比值 0.871 → 0.809（"接近峰值"两种口径均成立） | 同上 | 同上 | 同上 |
| 发文池 pool_EC（trade.py pool 口径） | 2024: 2,995 → 2,913（仍为序列峰值）；2025: 2,789 → 2,674 | 同上 | 同上 | pool_with/without_queue |
| 发文池 pool_NON | 2024: 10,968 → 10,880；2025: 10,954 → 10,870 | 同上 | 同上 | 同上 |
| 队列构成 | EC 1,318 + NON_EC 1,210 = 2,528；稳定 8 刊集内 912 EC + 870 NON | 同上 | 同上 | queue_composition |

## C2 构成敏感性更正（v2.0.0，2026-10-17；勘误见根目录 ERRATA.md）

| 数字 | 值 | 脚本 | 输出 | 字段路径 |
|---|---|---|---|---|
| **C2 期刊构成重加权（2021 构成固定，2021→2025）** | **E1 篇均跨域边数**：0.830(2021) → 0.642(2025)，**−22.7%**；**E2 至少一条跨域边的施引论文比例**：0.291 → 0.232，**−20.2%** | c2_composition_sensitivity.py | c2_composition_sensitivity.json | source_standardized.endpoints |
| **C2 主题构成重加权（同上）** | **E1**：0.830 → 0.520，**−37.4%**；**E2**：0.291 → 0.203，**−30.3%** | 同上 | 同上 | topic_standardized.endpoints |

> 勘误史：2026-10-14 内部评审发现原脚本计数单位缺陷（单列 DISTINCT），使 E2 值被标称为篇均率（E1）；同日修复重算。2025 层缺 Computers & Industrial Engineering（2021 权重 0.129），按覆盖份额 0.871 显式重加权。本分析为敏感性检验，不替换登记主估计规范。
