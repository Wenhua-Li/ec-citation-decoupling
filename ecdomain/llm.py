"""LLM 层：MiniMax 批量判定规则层未决论文（todo）。

- 直连 API（cn 区），key 复用本机 mmx 配置 ~/.mmx/config.json，无第三方依赖。
- 按 accession+model 键缓存到 cache_domain/<model>.jsonl（断点续跑、改判不重扣）。
- MiniMax 错误藏在 HTTP 200 的 base_resp 里（2056=Token Plan 窗口用量到顶）。
"""
import json
import random
import re
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import LABEL_EC, LABEL_NON
from . import _db

API_URL = "https://api.minimaxi.com/v1/text/chatcompletion_v2"
DEFAULT_MODEL = "MiniMax-M3"
TEMPERATURE = 0.1
CONCURRENCY = 12       # 用户确认套餐无调用次数限制；12 并发实测可持续
MAX_RETRY = 8          # 2062 速率限制按指数退避等待，总耐心约 9 分钟
CONF_ACCEPT = 0.75     # 低于此置信进二次复核队列（llm2/人工）
RUBRIC_VER = "v1"      # rubric 改动时递增，缓存文件名随之切换，旧判定不误用

RUBRIC = """You are a meticulous bibliometric classifier building a literature map of Evolutionary Computation (EC).

TASK: Decide whether the paper's PRIMARY method belongs to the metaheuristic family, defined as:
- Evolutionary algorithms: genetic algorithms, differential evolution, evolution strategies, genetic programming, estimation-of-distribution algorithms, coevolutionary algorithms, neuroevolution, memetic and hybrid evolutionary algorithms.
- Swarm intelligence: particle swarm optimization, ant colony optimization, artificial bee colony, and other population-based swarm methods.
- Other nature-inspired metaheuristics (grey wolf, whale, firefly, cuckoo, bat, etc.).
- Single-point metaheuristics: simulated annealing, tabu search, variable neighborhood search, GRASP.
- Any hybrid method whose core includes one of the above.

Answer "EC" if the primary method (the one the paper proposes, improves, or applies as its core solution approach) belongs to that family — including applications of such methods to domain problems.
Answer "NON_EC" otherwise. NON_EC includes:
- Pure exact/mathematical methods (MILP, branch-and-bound, dynamic programming, convex optimization).
- Pure machine learning / deep learning / statistics; pure fuzzy logic or fuzzy control.
- Papers whose primary method is ML or exact optimization, where a metaheuristic appears only as a comparison baseline or only as a hyperparameter-tuning tool.
- Evolutionary biology, evolutionary game theory, phylogenetics (similar words, unrelated field).

Respond with ONE JSON object and nothing else:
{"label": "EC" or "NON_EC", "confidence": <float 0..1>, "evidence": "<=25 words naming the paper's primary method>"}"""

_USER_TMPL = "TITLE: {title}\n\nABSTRACT: {abstract}\n\nKEYWORDS: {keywords}"


class QuotaError(RuntimeError):
    pass


def _key():
    cfg = Path.home() / ".mmx" / "config.json"
    return json.loads(cfg.read_text(encoding="utf-8"))["api_key"]


def call_model(messages, model=DEFAULT_MODEL, temperature=TEMPERATURE, timeout=180):
    """单次调用；返回 choices[0].message.content 字符串。非 0 base_resp 抛异常。"""
    body = {"model": model, "messages": messages, "temperature": temperature}
    req = urllib.request.Request(
        API_URL, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + _key(), "Content-Type": "application/json"})
    last = None
    for attempt in range(MAX_RETRY):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resp = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                last = f"HTTP {e.code}"
                time.sleep(min(150, 2 ** attempt * 4))
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read()[:200]}")
        except urllib.error.URLError as e:
            last = str(e.reason)
            time.sleep(min(150, 2 ** attempt * 4))
            continue
        base = resp.get("base_resp") or {}
        if base.get("status_code", 0) != 0:
            msg = base.get("status_msg", "")
            if base.get("status_code") == 2056:
                raise QuotaError(f"Token Plan 窗口用量到顶：{msg}")
            last = f"base_resp {base.get('status_code')}: {msg}"
            time.sleep(min(150, 2 ** attempt * 4))
            continue
        choices = resp.get("choices")
        if not choices:
            last = "empty choices"
            time.sleep(min(30, 2 ** attempt * 2))
            continue
        usage = resp.get("usage") or {}
        return choices[0]["message"]["content"], usage
    raise RuntimeError(f"重试 {MAX_RETRY} 次仍失败：{last}")


_JSON_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def parse_verdict(content):
    """从模型输出中稳健地取 JSON 判定。"""
    if not content:
        raise ValueError("空输出")
    try:
        obj = json.loads(content)
    except json.JSONDecodeError:
        m = _JSON_RE.search(content)
        if not m:
            raise ValueError(f"无 JSON：{content[:120]}")
        obj = json.loads(m.group(0))
    label = str(obj.get("label", "")).strip().upper()
    if label not in (LABEL_EC, "NON_EC"):
        raise ValueError(f"非法 label：{label!r}")
    try:
        conf = max(0.0, min(1.0, float(obj.get("confidence", 0.5))))
    except (TypeError, ValueError):
        conf = 0.5
    ev = str(obj.get("evidence", ""))[:250]
    return label, conf, ev


def _cache_path(model):
    root = Path(_db.db_path()).parent.parent
    d = root / "cache_domain"
    d.mkdir(exist_ok=True)
    return d / f"{model}.{RUBRIC_VER}.jsonl"


def _load_cache(model):
    cache = {}
    p = _cache_path(model)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(line)
                cache[o["accession_no"]] = o
            except (json.JSONDecodeError, KeyError):
                continue
    return cache


_LOCK = threading.Lock()


def _append_cache(model, rec):
    with _LOCK:
        with open(_cache_path(model), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def fetch_papers(accs):
    """取论文文本（title/abstract/keywords 拼串）。"""
    conn = _db.connect_ro()
    out = {}
    try:
        for j in range(0, len(accs), 500):
            ph = ",".join("?" * len(accs[j:j + 500]))
            for r in conn.execute(
                    f"SELECT accession_no, title, abstract FROM papers "
                    f"WHERE accession_no IN ({ph})", accs[j:j + 500]):
                out[r["accession_no"]] = {"title": r["title"] or "",
                                          "abstract": r["abstract"] or ""}
        kw = {a: [] for a in out}
        for j in range(0, len(accs), 500):
            ph = ",".join("?" * len(accs[j:j + 500]))
            for r in conn.execute(
                    f"SELECT accession_no, term FROM paper_terms "
                    f"WHERE accession_no IN ({ph})", accs[j:j + 500]):
                if r["accession_no"] in kw:
                    kw[r["accession_no"]].append(r["term"])
        for a, v in out.items():
            v["keywords"] = "; ".join(kw[a])
    finally:
        conn.close()
    return out


def todo_accessions(limit=None, seed=20260927):
    """规则层未决（B/C 档且无 rule 行）的论文 accession 列表。"""
    conn = _db.connect_ro()
    try:
        rows = conn.execute(
            "SELECT p.accession_no FROM papers p "
            "JOIN venue_tier vt ON vt.venue_tag = p.venue_tag "
            "AND vt.tier IN ('B_ci_broad','C_mixed_appl') "
            "LEFT JOIN paper_domain pd ON pd.accession_no = p.accession_no "
            "WHERE pd.accession_no IS NULL").fetchall()
    finally:
        conn.close()
    accs = [r[0] for r in rows]
    if limit is not None and limit < len(accs):
        rng = random.Random(seed)
        rng.shuffle(accs)
        accs = accs[:limit]
    return accs


def gold_accessions():
    """金标准 CSV 里的 accession 顺序列表（试点集）。"""
    import csv
    root = Path(_db.db_path()).parent.parent
    p = root / "labeling" / "gold_set_200.csv"
    if not p.exists():
        raise SystemExit("金标准 CSV 不存在：先 python -m ecdomain gold")
    with open(p, encoding="utf-8-sig") as f:
        return [(r["gold_id"], r["accession_no"], r["stratum"])
                for r in csv.DictReader(f)]


# 受控词含这些（方法/优化类）的 auto-非EC 论文有"藏EC"风险，需要 LLM 复核
RISKY_CTL = (
    "Multiobjective optimization", "Combinatorial optimization",
    "Constrained optimization", "Heuristic algorithms", "Heuristic methods",
    "Integer programming", "Global optimization", "Optimization",
    "Optimization algorithms", "Local search (optimization)",
    "Convex optimization", "Structural optimization", "Shape optimization",
)


def full_run_scope():
    """全量 LLM 范围 = todo + 规则EC复核 + 风险非EC复核 + A档跑题论文。"""
    accs = todo_accessions()
    conn = _db.connect_ro()
    try:
        rule_ec = [r[0] for r in conn.execute(
            "SELECT accession_no FROM paper_domain WHERE tier='rule' AND label=?", (LABEL_EC,))]
        ph = ",".join("?" * len(RISKY_CTL))
        risky = [r[0] for r in conn.execute(
            "SELECT DISTINCT pd.accession_no FROM paper_domain pd "
            "WHERE pd.tier='rule' AND pd.label=? AND EXISTS ("
            "  SELECT 1 FROM paper_terms t WHERE t.accession_no = pd.accession_no "
            f"  AND t.kind='controlled' AND t.term IN ({ph}))",
            (LABEL_NON,) + RISKY_CTL)]
    finally:
        conn.close()
    # A 档（venue 直接判 EC）里被规则判为 NON_EC 的"跑题论文"，也送 LLM 复核
    from . import rules
    venue_non = [a for a, _, dec, _, _ in rules.classify_venue_a() if dec == LABEL_NON]
    seen, out = set(accs), list(accs)
    for a in rule_ec + risky + venue_non:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out, {"todo": len(accs), "rule_ec_recheck": len(rule_ec),
                 "risky_non_recheck": len(risky), "venue_a_offtopic": len(venue_non)}


def write_llm_rows(accs, model=DEFAULT_MODEL):
    """把缓存中这些论文的判定全部入库（tier='llm'，幂等覆盖 rule/venue 行）。"""
    cache = _load_cache(model)
    rows = [(a, cache[a]["label"], cache[a]["confidence"],
             cache[a]["evidence"], model, _db.utcnow())
            for a in accs if a in cache]
    if not rows:
        return 0
    conn = _db.connect_rw()
    try:
        _db.ensure_schema(conn)
        for j in range(0, len(rows), 3000):
            conn.executemany(
                "INSERT OR REPLACE INTO paper_domain"
                "(accession_no, label, tier, confidence, evidence, model, rule_ver, judged_at) "
                "VALUES(?,?,'llm',?,?,?,NULL,?)", rows[j:j + 3000])
        _db.set_meta(conn, "llm_run", json.dumps(
            {"model": model, "rubric": RUBRIC_VER, "rows_in_db": len(rows),
             "ts": _db.utcnow()}))
        conn.commit()
    finally:
        conn.close()
    return len(rows)


def run_batch(accs, model=DEFAULT_MODEL, concurrency=CONCURRENCY, tag=""):
    """批量判定，结果写 JSONL 缓存。返回 [(acc, errmsg), ...]；QuotaError 会中止本批。"""
    papers = fetch_papers(accs)
    cache = _load_cache(model)
    todo = [a for a in accs if a in papers and a not in cache]
    print(f"[llm{tag}] 目标 {len(accs):,}，缓存命中 {len(accs)-len(todo):,}，待调 {len(todo):,}"
          f"（并发 {concurrency}，模型 {model}）", flush=True)
    if not todo:
        return []
    usage_sum = Counter()
    done = [0]
    errors = []
    stop = threading.Event()
    t0 = time.time()

    def work(a):
        p = papers[a]
        prompt = _USER_TMPL.format(title=p["title"][:600],
                                   abstract=p["abstract"][:4000],
                                   keywords=p["keywords"][:400])
        content, usage = call_model(
            [{"role": "system", "content": RUBRIC},
             {"role": "user", "content": prompt}], model=model)
        label, conf, ev = parse_verdict(content)
        rec = {"accession_no": a, "model": model, "rubric": RUBRIC_VER,
               "label": label, "confidence": conf, "evidence": ev, "ts": _db.utcnow()}
        _append_cache(model, rec)
        return a, label, conf, ev, usage

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = {ex.submit(work, a): a for a in todo}
        for fut in as_completed(futs):
            a = futs[fut]
            try:
                _, label, conf, ev, usage = fut.result()
                usage_sum["in"] += usage.get("prompt_tokens", 0) or 0
                usage_sum["out"] += usage.get("completion_tokens", 0) or 0
            except QuotaError as e:  # 窗口硬上限：中止整批，缓存已保住完成的
                errors.append((a, f"{e}（已中止本批）"))
                stop.set()
                for f2 in futs:
                    f2.cancel()
                break
            except Exception as e:  # noqa: BLE001 —— 记错继续，收尾汇总
                errors.append((a, str(e)[:150]))
                continue
            done[0] += 1
            if done[0] % 50 == 0:
                rate = done[0] / (time.time() - t0)
                print(f"[llm{tag}] {done[0]}/{len(todo)}  {rate:.1f} 篇/s  "
                      f"in={usage_sum['in']:,} out={usage_sum['out']:,}  "
                      f"err={len(errors)}", flush=True)

    dt = time.time() - t0
    print(f"[llm{tag}] 本轮完成 {done[0]:,} / 失败 {len(errors):,}  耗时 {dt/60:.1f} min  "
          f"tokens in={usage_sum['in']:,} out={usage_sum['out']:,}", flush=True)
    if errors:
        for a, msg in errors[:5]:
            print(f"    err {a}: {msg}")
    return errors


def pilot():
    """试点：对金标准 200 篇跑 LLM（不入库），产出成本/耗时/一致性的原始数据。"""
    gold = gold_accessions()
    accs = [a for _, a, _ in gold]
    errors = run_batch(accs, tag=":pilot")
    # 缓存 -> 试点摘要（与金标准标签的对比等用户标完后在 eval 里算）
    cache = _load_cache(DEFAULT_MODEL)
    dist = Counter(cache[a]["label"] for _, a, _ in gold if a in cache)
    print(f"[llm:pilot] 金标准 {len(gold)} 篇的 LLM 判定分布：{dict(dist)}；"
          f"准确率等用户标注回传后由 eval 计算")
    return errors


def full_run(limit=None):
    from . import venues
    n_add, _ = venues.write_venue_labels()
    if n_add:
        print(f"[llm] A档 venue 标签落库 {n_add:,} 篇")
    if limit is not None:
        accs = todo_accessions(limit=limit)
        print(f"[llm] todo 抽样 {len(accs):,} 篇")
    else:
        accs, bd = full_run_scope()
        print(f"[llm] 全量范围 {len(accs):,} 篇 = todo {bd['todo']:,} + "
              f"规则EC复核 {bd['rule_ec_recheck']:,} + 风险非EC复核 "
              f"{bd['risky_non_recheck']:,} + A档跑题 {bd['venue_a_offtopic']:,}")
    # 先把缓存里已完成的判定落库（断点续跑场景下可能积压）
    written = write_llm_rows(accs)
    print(f"[llm] 缓存回写 {written:,} 行")
    # 循环模式：窗口用量到顶(2056)则休眠 30 分钟自动续跑，直到全部完成
    for rnd in range(200):
        errors = run_batch(accs, tag=f":full r{rnd}")
        n_db = write_llm_rows(accs)
        print(f"[llm r{rnd}] 入库进度 {n_db:,}/{len(accs):,}", flush=True)
        if not errors:
            print("[llm] 全部完成")
            break
        if all("窗口用量" in m for _, m in errors):
            print(f"[llm r{rnd}] Token Plan 用量限制，等 5 分钟重试"
                  "（进度在缓存，不重扣）...", flush=True)
            time.sleep(300)
            continue
        # 非配额错误：只重试失败的子集，最多再试 3 轮
        accs = [a for a, _ in errors]
        if rnd >= 3:
            print(f"[llm] 仍有 {len(errors):,} 篇反复失败，放弃（可重跑续传）")
            break
