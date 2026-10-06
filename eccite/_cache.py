"""JSONL 追加式缓存 + 断点续传（移植自 p13，键从 pid 改为 ckey）。

ckey 约定：有 DOI 论文用规范化 DOI；无 DOI 论文用 "noDOI:<accession_no>"。
缓存按 DOI 键持久化是同库方案的安全网：主库被 build --rebuild 整库替换后，
init -> migrate -> load 可零 API 调用恢复全部引文表。
瞬时错误不写缓存，重跑自动补抓。
"""
import json
import threading
from pathlib import Path

from ecdb import _paths


def cache_dir() -> Path:
    d = _paths.project_root() / "cache_citations"
    d.mkdir(parents=True, exist_ok=True)
    return d


class JsonlSink:
    """追加式 JSONL 缓存 + 断点续传。"""

    def __init__(self, path: Path, key: str = "ckey"):
        self.path = Path(path)
        self.key = key
        self._lock = threading.Lock()
        self.done: set = set()
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    try:
                        self.done.add(json.loads(line)[key])
                    except Exception:
                        pass  # 容忍抓取中断产生的残缺行
        self._fh = open(self.path, "a", encoding="utf-8")

    def add(self, obj: dict):
        with self._lock:
            self._fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
            self._fh.flush()
            self.done.add(obj[self.key])

    def iter_records(self):
        """只读遍历（跳过残缺行）。"""
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def close(self):
        self._fh.close()

    def __len__(self):
        return len(self.done)
