"""限速 / 重试 HTTP 工具（移植自 EC_History/scripts/p13_citations.py，实战验证过）。"""
import http.client
import json
import threading
import time
import urllib.error
import urllib.request


class RateLimiter:
    """线程安全的最小请求间隔限速器，支持 429 自适应降速。"""

    def __init__(self, min_interval: float, floor: float = 0.05):
        self.min_interval = min_interval
        self.floor = floor
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self):
        with self._lock:
            now = time.time()
            t = max(self._next, now)
            self._next = t + self.min_interval
            sleep = t - now
        if sleep > 0:
            time.sleep(sleep)

    def slowdown(self, factor: float = 1.5, cap: float = 10.0):
        with self._lock:
            self.min_interval = min(self.min_interval * factor, cap)

    def speedup(self, factor: float = 0.97):
        with self._lock:
            self.min_interval = max(self.min_interval * factor, self.floor)


def http_json(url: str, headers: dict, limiter: RateLimiter | None = None,
              max_tries: int = 6, method: str = "GET", body: bytes | None = None,
              timeout: int = 90):
    """GET/POST JSON，带 429/5xx 退避重试。返回 (status, obj)。"""
    delay = 2.0
    last_err = None
    for _attempt in range(max_tries):
        if limiter:
            limiter.wait()
        req = urllib.request.Request(url, headers=headers, data=body, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if limiter:
                    limiter.speedup()
                return resp.status, json.loads(raw)
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code == 404:
                return 404, None
            if e.code == 429 or e.code >= 500:
                if limiter:
                    limiter.slowdown()
                retry_after = e.headers.get("Retry-After") if e.headers else None
                sleep = float(retry_after) if retry_after and retry_after.isdigit() else delay
                time.sleep(min(sleep, 60))
                delay = min(delay * 2, 60)
                continue
            if e.code == 400:
                return 400, None
            raise
        except (OSError, TimeoutError, json.JSONDecodeError,
                http.client.HTTPException) as e:
            # 含 URLError / RemoteDisconnected / IncompleteRead 等
            last_err = str(e)
            time.sleep(delay)
            delay = min(delay * 2, 60)
    raise RuntimeError(f"failed after {max_tries} tries: {url} ({last_err})")
