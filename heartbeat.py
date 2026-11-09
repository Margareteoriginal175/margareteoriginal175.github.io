#!/usr/bin/env python3
"""Write data/heartbeat.json so scheduled Actions stay active.

By default updates at most once per Asia/Shanghai calendar day to avoid
noisy hourly commits. Set HEARTBEAT_FORCE=1 to always rewrite.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo("Asia/Shanghai")
OUT = ROOT / "data" / "heartbeat.json"


def main() -> int:
    now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")
    force = os.environ.get("HEARTBEAT_FORCE", "").strip() in ("1", "true", "yes")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists() and not force:
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
            prev_day = (prev.get("updated_at_label") or prev.get("updated_at") or "")[:10]
            if prev_day == today:
                print(f"[heartbeat] skip — already updated today ({prev.get('updated_at_label')})")
                return 0
        except Exception as exc:  # noqa: BLE001
            print(f"[heartbeat] could not read previous ({exc}); rewriting")

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
