#!/usr/bin/env python3
"""Keyless X/Twitter freebie fetch for GitHub Actions.

Primary route: Twitter syndication timeline embed
  https://syndication.twitter.com/srv/timeline-profile/screen-name/<user>
Fallbacks: Google News RSS / Bing News RSS for site:x.com queries.
Nitter / xcancel / RSSHub are probed but usually fail from cloud IPs.

Fail-safe: on total failure, leave previous data untouched and exit 0.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
AUTO = DATA / "auto"
TZ = ZoneInfo("Asia/Shanghai")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# ~40 curated AI/tech freebie accounts
ACCOUNTS = [
    # labs / products
    "OpenAI", "AnthropicAI", "GoogleDeepMind", "GoogleAIStudio", "DeepMind",
    "deepseek_ai", "Alibaba_Qwen", "xai", "cursor_ai", "GitHub", "huggingface",
    "midjourney", "StabilityAI", "MetaAI", "MistralAI", "CohereAI", "perplexity_ai",
    "nvidia", "replicate", "togethercompute", "fireworksai_", "vercel", "netlify",
    "Cloudflare", "awscloud", "Azure", "GroqInc", "lmstudio", "ollama",
    # Chinese / freebie sharers seen in prior site data
    "linbai489068", "Jonnyhlkw", "chichu187", "AWG48488", "Stargridcompass",
    "Super_Nius", "vampire2g", "KOF97AI", "natboxio", "GeekCatX", "FirstInFeed",
    "NianEn_Ai", "0x_chaoran", "jhl880617", "mingzi206", "Leo_zhang2018",
    "fanfankp", "404latitude", "cyberde05", "tutuqi88", "BonoDJblack",
]

KEYWORDS = re.compile(
    r"(free\b|freemium|credits?|trial|giveaway|promo|coupon|open[\s-]?source|"
    r"开源|免费|额度|试用|限免|羊毛|赠送|福利|零成本|不收费|免费版|免费额度|"
    r"GPU|API\s*key|token\s*pack|student|education|hobby)",
    re.I,
)
BLOCK = re.compile(r"(crypto|nft|forex|赌博|博彩|色情|成人)", re.I)

STATUS_PATH = AUTO / "x_fetch_status.json"
FEED_PATH = AUTO / "x_feed.json"


def now_label() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M Asia/Shanghai")


def today() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def http_get(url: str, timeout: int = 18) -> tuple[int | None, bytes | None]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except Exception as e:
        code = getattr(e, "code", None)
        print(f"[x] GET fail {code or type(e).__name__}: {url[:90]}")
        return code, None


def slug_id(prefix: str, raw: str) -> str:
    h = abs(hash(raw)) % (10**10)
    return f"{prefix}-{h}"


def looks_freebie(text: str) -> bool:
    if not text or BLOCK.search(text):
        return False
    return bool(KEYWORDS.search(text))


def parse_syndication(screen: str) -> list[dict]:
    url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{urllib.parse.quote(screen)}"
    st, body = http_get(url)
    if not body or st != 200:
        return []
    text = body.decode("utf-8", "replace")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
        entries = (
            data.get("props", {})
            .get("pageProps", {})
            .get("timeline", {})
            .get("entries")
            or []
        )
    except Exception as e:
        print(f"[x] syndication parse {screen}: {e}")
        return []
    out = []
    for ent in entries:
        tw = ((ent or {}).get("content") or {}).get("tweet") or {}
        tid = str(tw.get("id_str") or tw.get("id") or "")
        full = (tw.get("full_text") or tw.get("text") or "").strip()
        if not tid or not full:
            continue
        user = tw.get("user") or {}
        handle = user.get("screen_name") or screen
        created = tw.get("created_at") or ""
        out.append(
            {
                "id": f"x-{tid}",
                "source": "X",
                "author": handle,
                "url": f"https://x.com/{handle}/status/{tid}",
                "title": full.split("\n", 1)[0][:120],
                "summary": full[:600],
                "_raw": full,
                "posted_at": created,
                "engagement": {
                    "likes": int(tw.get("favorite_count") or 0),
                    "bookmarks": 0,
                    "impressions": 0,
                    "replies": int(tw.get("conversation_count") or 0),
                    "retweets": int(tw.get("retweet_count") or 0),
                },
                "_route": "syndication",
            }
        )
    return out


def parse_rss_items(xml_bytes: bytes, route: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return []
    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = re.sub(r"<[^>]+>", " ", item.findtext("description") or "")
        desc = re.sub(r"\s+", " ", desc).strip()
        if not title:
            continue
        # Prefer real x.com links
        m = re.search(r"https?://(?:x|twitter)\.com/[A-Za-z0-9_]+/status/\d+", link + " " + desc)
        url = m.group(0) if m else link
        if "x.com" not in url and "twitter.com" not in url:
            # Google News wraps links — keep if title mentions X
            if not re.search(r"\bX\b|twitter", title, re.I):
                continue
        author = ""
        am = re.search(r"(?:x|twitter)\.com/([A-Za-z0-9_]+)", url)
        if am:
            author = am.group(1)
        text = f"{title}\n{desc}"
        items.append(
            {
                "id": slug_id("xrss", url or title),
                "source": "X",
                "author": author or "news",
                "url": url or link,
                "title": title[:120],
                "summary": (desc or title)[:600],
                "_raw": text[:800],
                "posted_at": item.findtext("pubDate") or "",
                "engagement": {"likes": 0, "bookmarks": 0, "impressions": 0},
                "_route": route,
            }
        )
    return items


def fetch_google_news() -> list[dict]:
    q = 'site:x.com (free OR credits OR trial OR giveaway OR 免费 OR 额度 OR 试用) (AI OR LLM OR GPT OR Claude OR GPU)'
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    )
    st, body = http_get(url)
    if not body or st != 200:
        return []
    return parse_rss_items(body, "google-news-rss")


def fetch_bing_news() -> list[dict]:
    q = "site:x.com free AI credits OR trial OR giveaway"
    url = "https://www.bing.com/news/search?" + urllib.parse.urlencode({"q": q, "format": "rss"})
    st, body = http_get(url)
    if not body or st != 200:
        return []
    return parse_rss_items(body, "bing-news-rss")


def probe_alt_routes() -> dict:
    """Probe alternate routes once; report only (do not rely on them)."""
    probes = {
        "nitter.net": "https://nitter.net/OpenAI/rss",
        "xcancel": "https://xcancel.com/OpenAI/rss",
        "rsshub.app": "https://rsshub.app/twitter/user/OpenAI",
    }
    out = {}
    for name, url in probes.items():
        st, body = http_get(url, timeout=10)
        out[name] = {"status": st, "ok": bool(body and st == 200 and len(body) > 200)}
        time.sleep(0.2)
    return out


def translate_items(items: list[dict]) -> list[dict]:
    """Reuse fetch_auto free translate when available."""
    try:
        from fetch_auto import batch_translate, enrich_deal  # type: ignore
    except Exception as e:
        print(f"[x] cannot import fetch_auto translate: {e}")
        for it in items:
            it.setdefault("category", "其他科技")
            it.setdefault("how", "打开来源链接按页面说明领取/试用；参与前自行核实。")
        return items

    batch = [
        {"id": it["id"], "title": it.get("title") or "", "text": it.get("_raw") or it.get("summary") or ""}
        for it in items
    ]
    tr = batch_translate(batch, kind="deal", batch_size=8)
    out = []
    for it in items:
        t = tr.get(it["id"]) or {}
        raw_t = it.get("title") or ""
        raw_b = it.get("_raw") or it.get("summary") or ""
        if t:
            it["category"] = t.get("category") or "其他科技"
            it["original_title"] = t.get("original_title") or raw_t
            it["original_summary"] = t.get("original_summary") or raw_b
            it["title"] = t.get("title") or raw_t
            it["summary"] = t.get("summary") or raw_b
            it["how"] = t.get("how") or "打开来源链接按页面说明领取/试用；参与前自行核实。"
            it["translated_by"] = t.get("translated_by") or "free-translate"
        else:
            cat, title, summary, how = enrich_deal(raw_t, raw_b, "X")
            it["category"] = cat
            it["original_title"] = raw_t
            it["original_summary"] = raw_b
            it["title"] = title
            it["summary"] = summary
            it["how"] = how
            it["translated_by"] = "keyword-fallback"
        it.pop("_raw", None)
        it.pop("_route", None)
        it.setdefault("deadline", None)
        out.append(it)
    return out


def load_existing_urls() -> set[str]:
    urls: set[str] = set()
    for folder in (DATA, AUTO):
        if not folder.exists():
            continue
        for f in folder.glob("*.json"):
            if f.name in ("translations.json", "x_fetch_status.json", "baidu_pushed.json"):
                continue
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            items = d.get("items") if isinstance(d, dict) else d
            if not isinstance(items, list):
                continue
            for it in items:
                if isinstance(it, dict) and it.get("url"):
                    urls.add(it["url"].split("?")[0])
    return urls


def merge_into_day(new_items: list[dict]) -> int:
    """Merge into data/YYYY-MM-DD.json (Simular + Action shared day file)."""
    day = today()
    path = DATA / f"{day}.json"
    prev = {"date": day, "updated_at_label": now_label(), "source": "x-fetch+simular", "items": []}
    if path.exists():
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    items = list(prev.get("items") or [])
    seen = { (it.get("url") or "").split("?")[0] for it in items if it.get("url") }
    added = 0
    for it in new_items:
        u = (it.get("url") or "").split("?")[0]
        if not u or u in seen:
            continue
        seen.add(u)
        items.insert(0, it)
        added += 1
    # keep day file bounded
    prev["items"] = items[:120]
    prev["updated_at_label"] = now_label()
    prev["date"] = day
    prev["source"] = "x-fetch+simular"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prev, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added


def write_feed(items: list[dict], status: dict) -> None:
    AUTO.mkdir(parents=True, exist_ok=True)
    FEED_PATH.write_text(
        json.dumps(
            {
                "updated_at_label": now_label(),
                "route": status.get("primary_route"),
                "items": items,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    print("[x] start", now_label())
    status = {
        "updated_at_label": now_label(),
        "primary_route": None,
        "routes": {},
        "accounts_ok": 0,
        "raw": 0,
        "kept": 0,
        "added": 0,
        "alt_probes": {},
    }
    raw: list[dict] = []
    syn_ok = 0
    # Cap accounts per run to stay polite in Actions (~25)
    for i, screen in enumerate(ACCOUNTS[:36]):
        try:
            got = parse_syndication(screen)
        except Exception as e:
            print(f"[x] syndication error @{screen}: {e}")
            got = []
        if got:
            syn_ok += 1
            raw.extend(got)
            print(f"[x] syndication @{screen}: {len(got)}")
        time.sleep(0.35)
        if i and i % 10 == 0:
            time.sleep(1.0)

    status["routes"]["syndication"] = {"accounts_ok": syn_ok, "tweets": len(raw)}
    if syn_ok:
        status["primary_route"] = "syndication"

    # Always try news RSS as supplement (and primary if syndication died)
    g = []
    b = []
    try:
        g = fetch_google_news()
        status["routes"]["google-news-rss"] = {"items": len(g)}
        print(f"[x] google-news-rss: {len(g)}")
    except Exception as e:
        status["routes"]["google-news-rss"] = {"error": str(e)}
    try:
        b = fetch_bing_news()
        status["routes"]["bing-news-rss"] = {"items": len(b)}
        print(f"[x] bing-news-rss: {len(b)}")
    except Exception as e:
        status["routes"]["bing-news-rss"] = {"error": str(e)}

    if not status["primary_route"]:
        if g:
            status["primary_route"] = "google-news-rss"
        elif b:
            status["primary_route"] = "bing-news-rss"

    raw.extend(g)
    raw.extend(b)
    status["alt_probes"] = probe_alt_routes()
    status["accounts_ok"] = syn_ok
    status["raw"] = len(raw)

    if not raw:
        print("[x] all routes empty — skip silently, keep previous data")
        status["ok"] = False
        AUTO.mkdir(parents=True, exist_ok=True)
        STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0

    # keyword filter + dedupe
    existing = load_existing_urls()
    filtered = []
    seen = set()
    for it in raw:
        text = it.get("_raw") or f"{it.get('title')} {it.get('summary')}"
        if not looks_freebie(text):
            continue
        u = (it.get("url") or "").split("?")[0]
        if not u or u in seen or u in existing:
            continue
        seen.add(u)
        filtered.append(it)
        if len(filtered) >= 25:
            break

    status["kept"] = len(filtered)
    print(f"[x] filtered freebie candidates: {len(filtered)}")
    if not filtered:
        print("[x] no freebie-matching tweets — keep previous data")
        status["ok"] = True
        status["note"] = "route worked but no keyword matches"
        write_feed([], status)
        return 0

    translated = translate_items(filtered)
    added = merge_into_day(translated)
    status["added"] = added
    status["ok"] = True
    write_feed(translated, status)
    print(f"[x] done primary={status['primary_route']} added={added}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[x] FATAL {type(e).__name__}: {e} — skip silently")
        raise SystemExit(0)
