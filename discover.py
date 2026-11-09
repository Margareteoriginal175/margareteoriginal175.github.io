#!/usr/bin/env python3
"""Self-discovery (runs at most once per ~20h; FORCE_DISCOVER=1 to force).

Finds NEW free LLM / AI / dev resources from keyless or free feeds:
  * GitHub repository search (seed queries + topics learned from previous hits)
  * Hacker News Algolia extra queries (well-upvoted only)
  * V2EX node feeds (share / create / programmer) via RSS-like JSON
Filters to scope (AI / LLM / dev freebies; no finance/crypto/coupons),
dedupes against everything already on the site, translates to Chinese and
writes data/auto/discovered.json. fetch_auto.py merges these items.
Learned topics are kept in data/auto/discovery_state.json (self-expanding).
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fetch_auto as fa
import selfheal

ROOT = Path(__file__).resolve().parent
AUTO = ROOT / "data" / "auto"
OUT = AUTO / "discovered.json"
STATE = AUTO / "discovery_state.json"
UTC = timezone.utc
MIN_INTERVAL_H = 20
MAX_KEEP = 60
MAX_AGE_DAYS = 45

SEED_QUERIES = [
    "free llm api",
    "free ai api",
    "free gpt api",
    "free openai api",
    "free claude api",
    "free deepseek api",
    "free gpu",
    "awesome free llm",
    "free inference api",
    "免费 大模型 api",
    "免费 api key",
]
SEED_TOPICS = ["free-api", "llm-api", "free-llm", "openai-api", "gpt-free", "ai-tools"]
TOPIC_ALLOW = re.compile(r"(llm|gpt|claude|gemini|deepseek|qwen|openai|inference|gpu|free-api|ai-api|kimi|glm)", re.I)
GENERIC_TOPICS = {"llm", "ai", "llms", "api", "apis", "free", "agents", "agent", "gpt", "openai", "claude", "chatgpt",
                  "gemini", "deepseek", "qwen", "python", "machine-learning", "deep-learning", "artificial-intelligence"}
FREE_WORDS = ("free", "免费", "白嫖", "credits", "no api key", "without api key", "无需", "gratis", "零成本", "公益")


def looks_free(text: str) -> bool:
    low = (text or "").lower()
    return any(w in low for w in FREE_WORDS)
EXTRA_BLOCK = ["stock", "trading", "forex", "bitcoin", "btc", "crypto", "token sale", "coupon", "cashback",
               "金融", "股票", "比特币", "加密货币", "优惠券", "信用卡", "贷款"]
HN_QUERIES = ["free inference", "free tier LLM", "open source LLM API free", "free credits AI", "free GPU notebook"]


def in_scope(text: str) -> bool:
    low = (text or "").lower()
    if fa.looks_blocked(low) or any(b in low for b in EXTRA_BLOCK):
        return False
    return fa.looks_ai_tech(low)


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def known_urls() -> set[str]:
    urls = set()
    for f in list((ROOT / "data").glob("????-??-??.json")) + list(AUTO.glob("????-??-??.json")) + [AUTO / "github_hot.json"]:
        for it in (load(f, {}) or {}).get("items") or []:
            u = (it.get("url") or "").rstrip("/")
            if u:
                urls.add(u)
    return urls


def gh_search(q: str, tok: str, days: int = 180) -> list[dict]:
    since = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    pushed = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
        {"q": f"{q} created:>{since} pushed:>{pushed} stars:>=15", "sort": "stars", "order": "desc", "per_page": 15}
    )
    hdr = {"Accept": "application/vnd.github+json"}
    if tok:
        hdr["Authorization"] = f"Bearer {tok}"
    st, data = fa.safe_get(url, headers=hdr)
    time.sleep(2.2 if tok else 6.5)
    return (data or {}).get("items") or []


def main() -> int:
    AUTO.mkdir(parents=True, exist_ok=True)
    prev = load(OUT, {}) or {}
    state = load(STATE, {}) or {}
    force = os.environ.get("FORCE_DISCOVER", "").strip() in ("1", "true", "yes")
    last = prev.get("updated_at")
    if last and not force:
        try:
            age_h = (datetime.now(fa.TZ) - datetime.fromisoformat(last)).total_seconds() / 3600
            if age_h < MIN_INTERVAL_H:
                print(f"[discover] skip — last run {age_h:.1f}h ago (<{MIN_INTERVAL_H}h)")
                return 0
        except Exception:
            pass
    if selfheal.should_skip("Discovery"):
        print("[discover] auto-skipped by selfheal backoff")
        selfheal.save()
        return 0

    tok = fa.github_token()
    seen = known_urls()
    learned = state.get("learned_topics") or []
    topics = list(dict.fromkeys(SEED_TOPICS + learned))[:24]
    found: dict[str, dict] = {}
    topic_counter: Counter = Counter()
    errors = 0

    queries = [f"{q} in:name,description" for q in SEED_QUERIES] + [f"topic:{t} free" for t in topics]
    for q in queries:
        try:
            repos = gh_search(q, tok)
        except Exception as e:
            errors += 1
            print(f"[discover] gh error {q}: {e}")
            continue
        for r in repos:
            desc = r.get("description") or ""
            text = f"{r.get('full_name')} {desc} {' '.join(r.get('topics') or [])}"
            if not in_scope(text) or not looks_free(text) or r.get("archived") or r.get("fork"):
                continue
            url = (r.get("html_url") or "").rstrip("/")
            for t in r.get("topics") or []:
                if TOPIC_ALLOW.search(t) and t.lower() not in GENERIC_TOPICS and not any(b in t.lower() for b in EXTRA_BLOCK):
                    topic_counter[t] += 1
            if not url or url in seen or url in found:
                continue
            pushed = datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")).astimezone(fa.TZ)
            found[url] = {
                "id": fa.slug_id("disc", r.get("full_name", "")),
                "source": "GitHub 自动发现",
                "_title": r.get("full_name") or "",
                "_repo": True,
                "_raw": desc or r.get("full_name") or "",
                "author": (r.get("owner") or {}).get("login") or "github",
                "url": url,
                "posted_at": pushed.strftime("%Y-%m-%d %H:%M Asia/Shanghai"),
                "engagement": {"stars": r.get("stargazers_count") or 0},
            }

    since = int((datetime.now(UTC) - timedelta(days=3)).timestamp())
    for q in HN_QUERIES:
        url = "https://hn.algolia.com/api/v1/search_by_date?" + urllib.parse.urlencode(
            {"query": q, "tags": "story", "hitsPerPage": 20, "numericFilters": f"created_at_i>{since},points>=15"}
        )
        st, data = fa.safe_get(url)
        time.sleep(0.5)
        if not data:
            errors += 1
            continue
        for h in data.get("hits") or []:
            title = h.get("title") or ""
            u = (h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}").rstrip("/")
            if not in_scope(title) or not looks_free(title) or u in seen or u in found:
                continue
            created = datetime.fromtimestamp(h.get("created_at_i") or 0, tz=UTC).astimezone(fa.TZ)
            found[u] = {
                "id": fa.slug_id("dischn", str(h.get("objectID"))),
                "source": "Hacker News 自动发现",
                "_title": title,
                "_raw": f"{title} {h.get('story_text') or ''}"[:1500],
                "author": h.get("author") or "hn",
                "url": u,
                "posted_at": created.strftime("%Y-%m-%d %H:%M Asia/Shanghai"),
                "engagement": {"points": h.get("points") or 0},
            }

    # translate + classify new finds
    new_items = []
    for it in sorted(found.values(), key=lambda x: -sum((x.get("engagement") or {}).values()))[:30]:
        raw_title, raw, is_repo = it.pop("_title"), it.pop("_raw"), it.pop("_repo", False)
        cat, _, _ = fa.keyword_classify(raw)
        zh_sum = fa.free_translate(raw) if not fa.has_cjk(raw) else raw
        if is_repo:
            zh_title = f"GitHub 开源：{raw_title}"  # repo names are kept as-is (proper nouns)
        else:
            zh_title = fa.free_translate(raw_title) if not fa.has_cjk(raw_title) else raw_title
        if not fa.has_cjk(zh_sum) or not fa.has_cjk(zh_title):
            print(f"[discover] translation unavailable — retry next run: {raw_title[:60]}")
            continue  # all-Chinese rule: never publish untranslated text
        it.update({
            "category": cat if cat != "其他科技" else "大模型 API 免费额度",
            "title": zh_title,
            "summary": zh_sum,
            "how": "打开来源链接查看项目说明与领取/使用方式；参与前请自行核实。",
            "deadline": None,
            "original_title": raw_title,
            "original_summary": raw,
            "translated_by": "free-translate",
            "discovered_at": datetime.now(fa.TZ).strftime("%Y-%m-%d %H:%M Asia/Shanghai"),
        })
        new_items.append(it)

    # merge with previous discoveries, expire old ones
    cutoff = datetime.now(fa.TZ) - timedelta(days=MAX_AGE_DAYS)
    merged, urls = [], set()
    for it in new_items + list(prev.get("items") or []):
        u = it.get("url")
        if not u or u in urls or not fa.has_cjk(it.get("summary") or "") or not looks_free(f"{it.get('original_title')} {it.get('original_summary')} {it.get('summary')}"):
            continue
        try:
            if datetime.strptime((it.get("discovered_at") or "")[:16], "%Y-%m-%d %H:%M").replace(tzinfo=fa.TZ) < cutoff:
                continue
        except Exception:
            pass
        urls.add(u)
        merged.append(it)
    merged = merged[:MAX_KEEP]

    # self-expansion: learn new topics that keep appearing
    learned_new = [t for t, c in topic_counter.most_common(40) if c >= 2 and t not in SEED_TOPICS]
    learned = [t for t in learned if t.lower() not in GENERIC_TOPICS and TOPIC_ALLOW.search(t)]
    state["learned_topics"] = list(dict.fromkeys(learned + learned_new))[:20]
    state["last_run_label"] = datetime.now(fa.TZ).strftime("%Y-%m-%d %H:%M Asia/Shanghai")
    state["queries"] = len(queries) + len(HN_QUERIES)
    state["new_found"] = len(new_items)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    now = datetime.now(fa.TZ)
    OUT.write_text(json.dumps({
        "updated_at": now.isoformat(timespec="seconds"),
        "updated_at_label": now.strftime("%Y-%m-%d %H:%M Asia/Shanghai"),
        "new_this_run": len(new_items),
        "items": merged,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = errors < (len(queries) + len(HN_QUERIES)) // 2
    selfheal.record("Discovery", ok, len(new_items), "" if ok else f"{errors} query errors")
    fa.save_translate_cache()
    selfheal.save()
    print(f"[discover] new={len(new_items)} kept={len(merged)} learned_topics={state['learned_topics']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
