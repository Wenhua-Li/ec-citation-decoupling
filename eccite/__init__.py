"""eccite —— EC_MAP_2026 引文数据子系统（参考文献列表 + 被引列表）。

数据流：
    EC_History/ec_corpus.db --migrate--> db/ec_papers.db 四张 cit_* 表
    Crossref / Semantic Scholar / OpenCitations --fetch--> cache_citations/*.jsonl --load--> 同表

用法（项目根目录）：python -m eccite <stage>，见 cli.py。
"""
__version__ = "1.0.0"
