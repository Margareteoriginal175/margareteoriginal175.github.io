#!/usr/bin/env python3
"""Write data/heartbeat.json so scheduled Actions stay active."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo("Asia/Shanghai")
OUT = ROOT / "data" / "heartbeat.json"


def main() -> int:
    now = datetime.now(TZ)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": True,
        "purpose": "keepalive for GitHub Actions schedule (avoid 60-day disable)",
        "updated_at": now.isoformat(timespec="seconds"),
        "updated_at_label": now.strftime("%Y-%m-%d %H:%M:%S Asia/Shanghai"),
        "unix": int(now.timestamp()),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[heartbeat] wrote {OUT} @ {payload['updated_at_label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
