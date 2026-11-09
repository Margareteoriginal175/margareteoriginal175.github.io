#!/usr/bin/env python3
"""Self-healing registry: per-source health scores, auto-skip with backoff,
translation-provider rotation. State lives in data/sources_health.json.

CLI:
  python3 selfheal.py should-skip <name>        exit 0 = skip, 1 = run
  python3 selfheal.py record <name> <ok|fail> [count] [error]
  python3 selfheal.py show
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
PATH = ROOT / "data" / "sources_health.json"
TZ = ZoneInfo("Asia/Shanghai")

FAIL_SKIP_AFTER = 3          # consecutive failures before auto-skip
BACKOFF_BASE_H = 1           # 1h, 2h, 4h ... capped
BACKOFF_CAP_H = 24
TRANSLATOR_SKIP_AFTER = 6

_state: dict | None = None


def now() -> datetime:
    return datetime.now(TZ)


def label(dt: datetime | None = None) -> str:
    return (dt or now()).strftime("%Y-%m-%d %H:%M Asia/Shanghai")


def load() -> dict:
    global _state
    if _state is None:
        try:
            _state = json.loads(PATH.read_text(encoding="utf-8"))
        except Exception:
            _state = {}
        _state.setdefault("sources", {})
        _state.setdefault("translators", {})
    return _state


def save() -> None:
    st = load()
    st["updated_at"] = now().isoformat(timespec="seconds")
    st["updated_at_label"] = label()
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _entry(kind: str, name: str) -> dict:
    st = load()
    e = st[kind].setdefault(name, {})
    e.setdefault("ok_total", 0)
    e.setdefault("fail_total", 0)
    e.setdefault("fail_streak", 0)
    e.setdefault("score", 100)
    return e


def should_skip(name: str, kind: str = "sources") -> bool:
    e = _entry(kind, name)
    until = e.get("skip_until")
    if not until:
        return False
    try:
        if now() < datetime.fromisoformat(until):
            return True
    except Exception:
        pass
    # backoff expired -> probe again (auto-retry)
    e["state"] = "retrying"
    return False


def record(name: str, ok: bool, count: int | None = None, error: str = "", kind: str = "sources") -> dict:
    e = _entry(kind, name)
    e["last_run"] = now().isoformat(timespec="seconds")
    e["last_run_label"] = label()
    if count is not None:
        e["last_count"] = int(count)
    if ok:
        e["ok_total"] += 1
        e["fail_streak"] = 0
        e["last_ok"] = e["last_run"]
        e["last_ok_label"] = e["last_run_label"]
        e["state"] = "healthy"
        e.pop("skip_until", None)
        e.pop("skip_until_label", None)
        e["score"] = min(100, int(e.get("score", 100)) + 10)
    else:
        e["fail_total"] += 1
        e["fail_streak"] += 1
        e["last_error"] = (error or "empty/failed")[:200]
        e["score"] = max(0, int(e.get("score", 100)) - 20)
        limit = TRANSLATOR_SKIP_AFTER if kind == "translators" else FAIL_SKIP_AFTER
        if e["fail_streak"] >= limit:
            hours = min(BACKOFF_CAP_H, BACKOFF_BASE_H * (2 ** (e["fail_streak"] - limit)))
            until = now() + timedelta(hours=hours)
            e["skip_until"] = until.isoformat(timespec="seconds")
            e["skip_until_label"] = label(until)
            e["state"] = "skipped"
        else:
            e["state"] = "degraded"
    return e


def translator_order(names: list[str]) -> list[str]:
    """Healthy providers first (by score), skipped ones last (still tried as last resort)."""
    def key(n):
        e = _entry("translators", n)
        skipped = should_skip(n, "translators")
        return (1 if skipped else 0, -int(e.get("score", 100)), names.index(n))
    return sorted(names, key=key)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "should-skip":
        skip = should_skip(argv[2])
        save()
        print(f"[selfheal] {argv[2]} skip={skip}")
        return 0 if skip else 1
    if cmd == "record":
        name, ok = argv[2], argv[3] == "ok"
        cnt = int(argv[4]) if len(argv) > 4 and argv[4].lstrip("-").isdigit() else None
        err = argv[5] if len(argv) > 5 else ""
        e = record(name, ok, cnt, err)
        save()
        print(f"[selfheal] {name} -> {e['state']} score={e['score']} streak={e['fail_streak']}")
        return 0
    if cmd == "show":
        print(json.dumps(load(), ensure_ascii=False, indent=2))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
