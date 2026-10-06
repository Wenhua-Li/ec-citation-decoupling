# EC 文献数据库使用说明（DATA_USAGE.md）

数据库：`db/ec_papers.db`（SQLite，5.1 GB）｜ 访问接口：`ecdb` Python 包（零第三方依赖）
规模：**146,785 篇**（2000–2025 年，核心字段零缺失）｜ 其中 **EC（进化计算）47,834 篇**
数据怎么来的（获取途径与清洗操作）见：[DATA_PIPELINE.md](DATA_PIPELINE.md)

## 30 秒速览

- 一篇论文一行存在 `papers` 主表；作者、机构、关键词在关联表；每篇另有 EC/非EC 标签（`paper_domain`）和引文数据（参考文献列表 + 被引列表，4 张表）。
- 查询一律通过 `ecdb`（命令行或 Python），全库带 FTS5 全文检索（一种 SQLite 内置的按相关度排序的搜索方式）。
- 最常用的三条命令：

```bash
python -m ecdb info                                        # 库状态
python -m ecdb search "large-scale optimization" --year-range 2023:2025
python -m ecdb sql "SELECT label, COUNT(*) FROM paper_domain GROUP BY label"
```

---

## 1. 快速开始

所有命令在**项目根目录**运行（Python API 同理）：

```bash
# 全文检索（覆盖标题/摘要/作者/关键词），支持过滤
python -m ecdb search '"multi-objective optimization" AND survey' --count
python -m ecdb search "pso" --venue swevc --doctype JA --json

# 单篇详情（按 DOI 或 EI 编号）
python -m ecdb get --doi 10.1109/tevc.2025.3613238 --json

# 结构化过滤（不走全文索引）
python -m ecdb papers --author "Kalyanmoy Deb" --year-range 2024:2025 --has-abstract 1

# 文献计量统计
python -m ecdb stats --by year
python -m ecdb stats --by term --kind controlled --top 30
python -m ecdb stats --by venue --doctype CA

# EC 子集（论文研究的主要分析对象）：SQL 联表 paper_domain
python -m ecdb sql "SELECT p.pub_year, COUNT(*) FROM papers p JOIN paper_domain d ON d.accession_no=p.accession_no WHERE d.label='EC' GROUP BY 1"

# 来源一览 / 任意只读 SQL
python -m ecdb venues
python -m ecdb sql "SELECT venue_tag, COUNT(*) FROM papers WHERE pub_year>=2024 GROUP BY venue_tag ORDER BY 2 DESC"
```

Python API 返回普通 dict/list，可自由后处理：

```python
import ecdb

res = ecdb.search("estimation of distribution algorithm", year_range=(2020, None), limit=50)
res["total"], res["rows"][0]["title"]

paper = ecdb.get_paper(accession="20254219328246")   # 或 doi=...
paper["authors"]       # [{position, name_raw, name_display, affil_refs}, ...]
paper["affiliations"]  # [{idx, affiliation}, ...]  idx 与 authors.affil_refs 对应
paper["terms"]         # [{kind: controlled|uncontrolled, term}, ...]

ecdb.find_papers(venue="tevc", year=2025, order_by="pub_year DESC, title", limit=100)
ecdb.stats(by="term", kind="uncontrolled", top=50)
ecdb.export(res["rows"], "结果.csv")           # 或 fmt="json"
ecdb.raw_sql("SELECT COUNT(*) FROM papers WHERE abstract IS NULL")   # 大结果集传 max_rows
```

---

## 2. 库结构（Schema）

### papers 主表（146,785 行）

| 字段 | 来源（EI 原始列） | 说明 |
|---|---|---|
| `accession_no` ★主键 | Accession number | EI 唯一编号 |
| `doi` | DOI | 已小写化、剥离 URL 前缀；约 99.1% 有值（含标题匹配回写的部分，见 DATA_PIPELINE §1.2） |
| `title` / `abstract` | Title / Abstract | 标题空白折叠；摘要保留内部换行 |
| `authors_raw` / `affiliations_raw` | Author / Author affiliation | 原始字符串保底留存 |
| `corresponding_authors` | Corresponding author(s) | |
| `source` / `source_abbr` | Source / Abbreviated source title | 刊名/会议名（全/缩写） |
| `venue_tag` | —— 由导出文件名推导 | **导出批次标签**（如 `tevc`、`gecco_21_25`），不是刊名 |
| `publisher` | Publisher/Repository | 部分为增强回填的推导值 |
| `volume` / `issue` / `pages` / `article_number` | 同名 | |
| `pub_year` | Publication year | 整数；**可靠的年份字段**（`issue_date` 是自由文本，未清洗） |
| `issue_date` / `language` | Issue date / Language | 原样保留 |
| `issn` / `e_issn` / `coden` / `isbn` / `isbn13` | 同名 | |
| `doc_type` | Document type | `JA`（期刊论文）/ `CA`（会议论文），仅此两类 |
| `num_references` | Number of references | 整数 |
| `main_heading` / `classification_code` / `treatment` | 同名 | EI 学科分类 |
| `funding_details` / `funding_text` | Funding details / Funding text | 基金信息（含编号变体列合并） |
| `open_access` | Open Access type(s) | |
| `conf_name` / `conf_date` / `conf_location` / `conf_code` / `sponsor` / `editor` | 会议信息 | 仅会议记录有值 |
| `extra` | —— | JSON：不在上表中的其他 EI 列（兜底） |
| `quality_flags` | —— | JSON 数组：缺失字段标签（见 §4 注意事项） |
| `added_at` / `updated_at` | —— | 导入时间戳 |

### 关联表

| 表 | 内容 |
|---|---|
| `paper_authors` | (编号, 位置, 原始姓名, 展示姓名, 机构引用)；`name_display` 是 "名 姓" 格式，按作者查询用它 |
| `paper_affiliations` | (编号, 机构序号, 机构名)；序号与作者行的 `affil_refs`（如 "1;2"）对应 |
| `paper_terms` | (编号, 类别, 词)；类别 ∈ `controlled`（EI 受控词，可比性好）/ `uncontrolled`（作者自由词，噪声多） |
| `paper_sources` | (编号, 文件名)：每篇来自哪些导出 CSV（跨文件重复溯源） |
| `paper_domain` | (编号, 标签, 层级, 置信度, 证据, 模型, 规则版本, 判定时间)；`label` ∈ `EC` / `NON_EC`；`tier` ∈ `venue`（按刊源判定）/ `rule`（按规则）/ `llm`（大语言模型判定）/ `human`（人工）。当前分布：EC = venue 26,603 + llm 21,231；非EC = rule 79,595 + llm 19,356 |
| `domain_meta` | 打标运行的元信息（规则版本、模型、范围） |
| `db_meta` | 构建元信息（时间、剔除统计等），`info` 命令会展示 |

### 引文表（4 张，由 `eccite` 子系统维护，`ecdb build` 不触碰）

| 表 | 内容 |
|---|---|
| `paper_refs_out` | **出边**（这篇论文的参考文献列表）：(编号, 来源, 被引键, 序号, 被引DOI, 被引题名, 被引年份)。来源 ∈ crossref / s2 / oc；去重键为 DOI 或杂凑值；`seq` 仅 Crossref 有（存缴顺序） |
| `paper_cited_in` | **入边**（谁引了这篇）：(编号, 来源, 施引键, 施引DOI, 施引年份) |
| `paper_cit_meta` | 每篇的抓取状态与真实计数：DOI、DOI 来源（`ei` 原始 / `title_match` 标题匹配找回）、S2 编号、Crossref/S2 被引总数、参考文献/被引抓取状态、是否旧库迁移 |
| `paper_cit_edges` | **派生表**（`python -m eccite edges` 随时重建）：库内引文网络，两端均为本库论文，附支持来源数。⚠️ 当前行数与验收口径不一致（见 §4 第 10 条） |

### 索引与视图

- `papers_fts`（FTS5 全文索引）：标题、摘要、作者（拼接）、关键词（拼接）四列，`search()` 默认走它，按 bm25 相关度排序。
- `v_papers_flat` 视图：papers + 聚合好的作者串/关键词串，一行一篇，便于直接导出。
- 常规索引：doi / pub_year / source / doc_type / venue_tag / 展示姓名 / 关键词。

---

## 3. 检索说明

- 全文检索模式下查询词按空格分词后**隐式 AND**；`"短语"`（引号）做相邻匹配；支持 `AND / OR / NOT / NEAR` 与 `*` 前缀通配。含连字符的词自动按短语处理（`multi-objective` ≈ 短语匹配，因分词器同样把连字符切开，效果等价）。
- `--mode like` 强制子串匹配（全文检索不可用时的回退，较慢）。
- 过滤参数对所有查询命令通用：`--year`、`--year-range 2020:2025`、`--venue`（匹配批次标签/刊名缩写/刊名，不分大小写）、`--doctype JA|CA`、`--author`（子串匹配两种姓名格式）、`--source`、`--term`。

---

## 4. 注意事项（做统计前必读）

1. **作者同名无法消歧**：`paper_authors` 按姓名字符串聚合，"Wei Zhang" 这类常见名会是多人的合计。作者维度结论需人工复核或结合机构。
2. **DOI 缺失约 0.9%**：主要是会议前言类/早期记录；用 DOI 判重或关联外部数据时会漏这部分。
3. **`pub_year` 个别为 NULL**（极少数脏行）；`issue_date` 是自由文本（"2025"、"July 13, 2025"），不要拿它当年份。
4. **清洗规则是启发式的**：可能存在极少数漏网（标题不规则的编者按等）与理论上的误伤（已用佐证条件压低）。精细统计前建议抽样人工核对，样例见 `archive/db_cleaning_report.md`。
5. **无摘要 ≠ 噪声**：带 `no_abstract` 标签的记录多为 EI 未收录摘要的早期会议论文，是正经研究文献。做摘要文本分析前用 `--has-abstract 1` 过滤；做发文量统计不必排除。
6. **venue_tag 是批次标签**：同一期刊/会议可能有多个标签（如 `eswa_26_1` / `eswa_26_2`）。按"刊源"聚合统计请用 `source`（351 个不同值）；按"导出批次"过滤才用 `venue_tag`。
7. **关键词两种类别性质不同**：controlled 是 EI 统一受控词表（跨年可比）；uncontrolled 是作者自由词（同义变体多）。趋势分析建议用 controlled，且受 EI 标引政策漂移影响——强结论用标题+摘要文本匹配复核。
8. **领域标签的口径**：`paper_domain` 是"广义进化计算"口径（含遗传算法、进化策略、群体智能等），LLM 判定层的低置信 2,528 篇尚未人工复核（队列在 `archive/labeling/low_confidence_review.csv`）；金标准 200 篇人工评估准确率 97%。对边界敏感的结论建议剔除低置信样本做稳健性检验。
9. **引用统计口径**：无 DOI 论文默认无引用边；超高被引论文（如 NSGA-II）的 Semantic Scholar 被引**列表**被截断在约 1 万条且只留最近的——逐年被引曲线必须用 `oc` 来源行或 `cr_cit_count` / `s2_cit_count` **总数**字段，不能用行数统计。
10. **`paper_cit_edges` 行数待核对**：当前 990,612 行 ≠ 验收时的 1,908,020（疑似对账收尾时重建所致）。分析脚本的标准做法是**从 `paper_refs_out.cited_doi` 回连 `papers.doi` 自行计算库内边**（跨源去重），不依赖此表；投稿前应重跑 `python -m eccite edges` 对账。
11. **撤稿/勘误/评论/编者按已物理剔除**：回看被剔除内容须查原始 CSV（`archive/data_from_EI/`）或清洗报告。
12. **`raw_sql` 默认最多返回 1,000 行**：大批量查询显式传 `max_rows`。

---

## 5. 运维约定

- **并发**：SQLite 多读单写。查询可并发；任何写库操作（build / enrich / eccite 写入）必须串行、一次一个，且仅用户明确要求时执行。
- **移动**：文件夹整体移动/重命名不影响任何功能（路径基于 `ecdb` 包位置解析）；库未开 WAL 模式，单文件即全部，无附属文件。
- **写库前快照**：任何修改数据库的操作之前，先复制 `db/ec_papers.db` 为带日期快照放入 `archive/db_backup/`。
- **缓存勿删**：`cache_citations/`（引文抓取断点缓存）与 `cache_domain/`（打标断点缓存）是重建与恢复的安全网。
- **引文子系统的命令**：`python -m eccite status / report / validate / edges / reconcile / load`（说明见 DATA_PIPELINE.md 第 4 节）。
- **环境变量**（一般用不到）：`ECDB_ROOT` 项目根、`ECDB_DATA` CSV 目录、`ECDB_DB` 库文件路径、`ECCITE_OLD_DB` 旧项目库位置。
