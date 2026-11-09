#!/usr/bin/env python3
"""Daily dead-link pruning (FORCE_PRUNE=1 to force).

HEAD-checks (GET fallback) every item URL; 404/410 twice in a row (or once
for 410) => dead. Dead URLs are listed in data/link_health.json and build.py
drops them. X/Twitter URLs are skipped (they block bots).
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo("Asia/Shanghai")
OUT = ROOT / "data" / "link_health.json"
UA = "Mozilla/5.0 (compatible; aiym168-linkcheck/1.0; +https://aiym168.github.io/)"
CTX = ssl.create_default_context()
MIN_INTERVAL_H = 20
SKIP_HOSTS = ("x.com", "twitter.com", "news.google.com", "t.co")


def urls_to_check() -> set[str]:
    urls = set()
    files = list((ROOT / "data").glob("????-??-??.json")) + list((ROOT / "data" / "auto").glob("*.json"))
    for f in files:
        if f.name in ("translations.json", "x_fetch_status.json", "discovery_state.json"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for it in (d.get("items") or []) if isinstance(d, dict) else []:
            u = (it.get("url") or "").strip()
            if u.startswith("http") and not any(h in u for h in SKIP_HOSTS):
                urls.add(u)
    return urls


def check(url: str) -> int:
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
                return r.status
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 429, 400, 501):
                continue
            return e.code
        except Exception:
            if method == "HEAD":
                continue
            return -1
    return -1


def main() -> int:
    try:
        prev = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        prev = {}
    force = os.environ.get("FORCE_PRUNE", "").strip() in ("1", "true", "yes")
    if prev.get("checked_at") and not force:
        age_h = (datetime.now(TZ) - datetime.fromisoformat(prev["checked_at"])).total_seconds() / 3600
        if age_h < MIN_INTERVAL_H:
            print(f"[prune] skip — last check {age_h:.1f}h ago")
            return 0
    links = prev.get("links") or {}
    urls = sorted(urls_to_check())
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = dict(zip(urls, ex.map(check, urls)))
    now = datetime.now(TZ)
    dead = []
    for u, code in results.items():
        e = links.get(u) or {}
        bad = code in (404, 410)
        e["status"] = code
        e["checked"] = now.strftime("%Y-%m-%d %H:%M")
        e["bad_streak"] = (e.get("bad_streak", 0) + 1) if bad else 0
        e["dead"] = bool(code == 410 or e["bad_streak"] >= 2)
        links[u] = e
        if e["dead"]:
            dead.append(u)
    # forget URLs no longer referenced
    links = {u: links[u] for u in urls if u in links}
    out = {
        "checked_at": now.isoformat(timespec="seconds"),
        "checked_at_label": now.strftime("%Y-%m-%d %H:%M Asia/Shanghai"),
        "checked": len(urls),
        "dead_count": len(dead),
        "dead": sorted(dead),
        "links": links,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[prune] checked={len(urls)} dead={len(dead)} errors={sum(1 for c in results.values() if c == -1)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
