# -*- coding: utf-8 -*-
"""OpenAlex API 客户端（W1/W2 工作包共用）。

约定（SOP 与 ACCEPTANCE 的依据）：
  - 礼貌池：所有请求带 mailto；全局速率 <= ~4.5 请求/秒；
  - 重试：429/5xx 指数退避，最多 5 次，超限抛 RuntimeError（调用方记录并跳过）；
  - 年份缓存：out/year_cache.json（OpenAlex id -> publication_year），batch_years 自动读写。
自检：python oa_client.py  -> 打印 TEVC 2020 年计数（约 90）。
"""
import json
import os
import time
import urllib.parse
import urllib.request

MAILTO = "ecmap.project@outlook.com"
BASE = "https://api.openalex.org"
# 默认不使用密钥；可通过环境变量 ECOA_API_KEYS（逗号分隔）提供。
# 提供多个 key 时轮换使用：当前 key 预算耗尽（429 含 "Insufficient budget"）自动切换下一个；
# 全部耗尽后回退礼貌池；未提供密钥时走礼貌池（不带 api_key）。
_DEFAULT_KEYS = ""
API_KEYS = [k.strip() for k in os.environ.get("ECOA_API_KEYS", _DEFAULT_KEYS).split(",") if k.strip()]
# 高级池上限 100 req/s，保守取 ~8 req/s；礼貌池模式（无密钥）建议 >=0.22
MIN_INTERVAL = float(os.environ.get("ECOA_MIN_INTERVAL", "0.12" if API_KEYS else "0.22"))  # 兼容保留；_get 用动态间隔

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(HERE, "out", "year_cache.json")

_last = [0.0]
_year_cache = {}

# 显式代理 opener（2026-10-18）：环境代理在此解析一次，绕开 urlopen 的代理解析歧义
_PROXY_URL = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
              or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or "").strip()
if _PROXY_URL:
    _OPENER = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": _PROXY_URL, "https": _PROXY_URL}))
    print(f"  [oa_client] 显式代理: {_PROXY_URL}", flush=True)
else:
    _OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    print("  [oa_client] 无代理环境变量，直连", flush=True)


def _strip_api_key(url):
    """从 URL 中移除 api_key 参数（预算耗尽回退礼貌池时用）"""
    import re
    return re.sub(r"[?&]api_key=[^&]*", lambda m: "?" if m.group(0).startswith("?") else "", url, count=1)


# —— key 管理（2026-10-01 主会话重写：滚动预算窗口下的逐请求轮转）——
# 实测：key 预算为分钟级滚动窗口（单发探针 200，数秒后连发即 429 "Insufficient budget"，
# 片刻后恢复）。策略：每个请求挑一个"未冷却"的 key 轮转使用；预算 429 只冷却该 key 65s，
# 不整链降级；全部 key 冷却时走一次礼貌池探路，若礼貌池也 429 则等到最早的 key 复活。
_KEY_COOLDOWN = float(os.environ.get("ECOA_KEY_COOLDOWN", "65"))
_KEYED_IV = float(os.environ.get("ECOA_MIN_INTERVAL", "0.12"))
_POLITE_IV = max(0.22, _KEYED_IV)
_key_dead_until = {}


def _pick_key():
    now = time.time()
    avail = [i for i in range(len(API_KEYS)) if _key_dead_until.get(i, 0) <= now]
    if not avail:
        return None
    # 轮转：取"最久没用"的可用 key（冷却到期最早者），避免连续打同一 key
    return min(avail, key=lambda i: -_key_dead_until.get(i, 0))


def _append_key(url, idx):
    url = _strip_api_key(url)
    return url + ("&" if "?" in url else "?") + f"api_key={API_KEYS[idx]}"


def _get(url):
    last_err = None
    for attempt in range(12):
        # 1) 选 key：有可用 key 则带 key（走独立预算），否则礼貌池
        ki = _pick_key() if API_KEYS else None
        if ki is None and API_KEYS:
            # 全部冷却：先试一次礼貌池（免费池偶有余量），失败则睡到最早复活
            now = time.time()
            wake = min(_key_dead_until.values())
            try:
                return _fetch(_strip_api_key(url), polite=True)
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    sleep = min(90, max(5, wake - now))
                    print(f"  [oa_client] 全 key 冷却且礼貌池 429，睡 {sleep:.0f}s 等 key 复活", flush=True)
                    time.sleep(sleep)
                    continue
                raise
        use_url = _append_key(url, ki) if ki is not None else _strip_api_key(url)
        try:
            return _fetch(use_url, polite=ki is None)
        except urllib.error.HTTPError as e:
            last_err = e
            body = ""
            try:
                body = e.read().decode(errors="replace")[:500]
            except Exception:
                pass
            if e.code == 429 and ki is not None:
                # 一切 429（预算体或纯限速体）一律：冷却该 key、立即换下一个；绝不长睡
                _key_dead_until[ki] = time.time() + _KEY_COOLDOWN
                print(f"  [oa_client] key#{ki} 429（{'预算' if 'Insufficient budget' in body else '限速'}），冷却 {_KEY_COOLDOWN:.0f}s", flush=True)
                continue
            if e.code in (401, 403) and ki is not None:
                # key 失效/未授权（2026-10-19 实测：预算耗尽期偶发 401）——同 429 处理：冷却换 key，不中断长跑
                _key_dead_until[ki] = time.time() + _KEY_COOLDOWN
                print(f"  [oa_client] key#{ki} HTTP {e.code}（key 未授权/失效），冷却 {_KEY_COOLDOWN:.0f}s", flush=True)
                continue
            if e.code in (401, 403) and ki is None:
                # 礼貌池 401/403：2026-10-19 实测 = 免费 IP 池分钟级滚动预算耗尽的信号（单发可过、
                # 持续流被掐、下一分钟恢复）。策略：耐心等 75s 重试，最多 20 次（约 25 分钟），
                # 仍失败才放弃——调用方 manifest 会登记 error 供 sweep 补漏。
                _POLITE_401_TRIES = getattr(_get, "_polite401", 0) + 1
                _get._polite401 = _POLITE_401_TRIES
                if _POLITE_401_TRIES <= 20:
                    print(f"  [oa_client] 礼貌池 HTTP {e.code}（分钟预算/边缘拦截，第 {_POLITE_401_TRIES} 次），等 75s", flush=True)
                    time.sleep(75)
                    if _POLITE_401_TRIES == 20:
                        _get._polite401 = 0
                    continue
                _get._polite401 = 0
                raise
            if e.code in (429,):
                # 礼貌池 429：睡到最早 key 复活（有界 ≤90s），避免 300s 长退避
                wake = min(_key_dead_until.values()) if _key_dead_until else time.time() + 30
                sleep = min(90, max(5, wake - time.time())) if API_KEYS else 45
                print(f"  [oa_client] 礼貌池 429，睡 {sleep:.0f}s", flush=True)
                time.sleep(sleep)
                continue
            if e.code in (500, 502, 503, 504):
                retry_after = e.headers.get("Retry-After") if e.headers else None
                sleep = min(int(retry_after), 120) if (retry_after and retry_after.isdigit()) else min(120, 15 * (1 + attempt))
                print(f"  [oa_client] HTTP {e.code}, backoff {sleep}s", flush=True)
                time.sleep(sleep)
                continue
            raise
        except Exception as e:  # 网络抖动/超时
            last_err = e
            time.sleep(3 * (min(attempt, 4) + 1))
    raise RuntimeError(f"OpenAlex 请求失败（重试 12 次）: {_strip_api_key(url)} :: {last_err}")


def _fetch(url, polite=False):
    """实际发起请求（含限速间隔），只做一次尝试，异常原样抛给 _get 处理。

    2026-10-18 补丁：代理显式化——用导入时从环境解析的 _PROXY_URL 构造专用 opener，
    不再依赖 urlopen 的环境代理解析（实测部分进程环境下默认解析不生效，
    请求直连外网被 OpenAlex 401/掐断，同机显式代理路径正常）。
    """
    iv = _POLITE_IV if polite else _KEYED_IV
    wait = _last[0] + iv - time.time()
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": f"ecmap-w1w2 ({MAILTO})"})
    with _OPENER.open(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _works_url(filter_str, select, cursor, search=None, extra=""):
    url = (f"{BASE}/works?filter={filter_str}&select={select}&per-page=200"
           f"&cursor={urllib.parse.quote(cursor)}&mailto={MAILTO}")
    if search:
        url += f"&search={urllib.parse.quote(search)}"
    return url + extra


def iter_works(filter_str, select, search=None, max_pages=None):
    """游标分页生成器；返回前打印进度。

    服务器毛刺防护：2026-09-29 高负载时段两次出现"meta.count>0 但 results 为空"的
    假空页（会令调用方误记 0 条），此处按可重试错误抛出，交由调用方的重试机制消化。
    """
    cursor, page_i, n = "*", 0, 0
    while True:
        page = _get(_works_url(filter_str, select, cursor, search))
        results = page.get("results", [])
        meta = page.get("meta") or {}
        if not results and meta.get("count", 0) > n:
            raise RuntimeError(
                f"empty-page glitch: meta.count={meta.get('count')} but 0 results "
                f"(page {page_i + 1}, yielded {n})")
        yield from results
        n += len(results)
        page_i += 1
        if page_i % 5 == 0:
            print(f"    ... {n} works (page {page_i})", flush=True)
        cursor = meta.get("next_cursor")
        if not cursor or (max_pages and page_i >= max_pages):
            return


def group_by_year(filter_str, search=None):
    url = f"{BASE}/works?filter={filter_str}&group_by=publication_year&per-page=200&mailto={MAILTO}"
    if search:
        url += f"&search={urllib.parse.quote(search)}"
    return {int(b["key"]): b["count"] for b in _get(url)["group_by"]}


def batch_years(ids):
    """解析一批 OpenAlex id（<=50/请求）的发表年；本地缓存优先。-> {id: year|None}

    每 40 次 API 批解析自动落盘一次年份缓存（metrics_age 单面板可达数小时，
    避免中途失败丢失全部解析成果）。
    """
    out, todo = {}, []
    for i in dict.fromkeys(ids):  # 去重：同一样本年内重复引用的参考文献只解析一次
        if i in _year_cache:
            out[i] = _year_cache[i]
        else:
            todo.append(i)
    if not todo:
        return out
    for k in range(0, len(todo), 50):
        batch = todo[k:k + 50]
        url = (f"{BASE}/works?filter=openalex:{'|'.join(batch)}"
               f"&select=id,publication_year&per-page=50&mailto={MAILTO}")
        got = set()
        for r in _get(url).get("results", []):
            rid = r["id"].rsplit("/", 1)[-1]
            y = r.get("publication_year")
            _year_cache[rid] = y
            out[rid] = y
            got.add(rid)
        for sid in batch:  # 死 id 缓存为 None，防止反复重查（2026-10-01 堵漏）
            if sid not in got:
                _year_cache[sid] = None
                out.setdefault(sid, None)
        batch_years._calls = getattr(batch_years, "_calls", 0) + 1
        if batch_years._calls % 40 == 0:
            save_year_cache()
            print(f"  [oa_client] 年份缓存自动落盘（第 {batch_years._calls} 批）", flush=True)
    return out


def load_year_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            _year_cache.update(json.load(f))
    return len(_year_cache)


def save_year_cache():
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(_year_cache, f)
    return len(_year_cache)


if __name__ == "__main__":
    c = group_by_year("primary_location.source.id:S93787993,from_publication_date:2020-01-01,to_publication_date:2020-12-31")
    print("TEVC 2020 works:", c.get(2020), "（预期约 90；差异大请检查网络/过滤）")
    print("cache entries:", load_year_cache())
