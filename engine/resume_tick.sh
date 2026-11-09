#!/usr/bin/env bash
# Runs every 5 min on the box. If the previous tick is > 10 min old, the box was asleep/failed
# and was just woken (e.g. by the GitHub box guard) -> run Engine B right away instead of waiting for :25.
T="$HOME/engine/.tick"; now=$(date +%s); prev=$(cat "$T" 2>/dev/null || echo 0); echo "$now" > "$T"
if [ $((now - prev)) -gt 600 ]; then
  mkdir -p "$HOME/engine/logs"
  echo "[resume-tick] $(TZ=Asia/Shanghai date '+%F %T') gap $((now - prev))s — box was asleep, running engine B" >> "$HOME/engine/logs/resume.log"
  ENGINE_B_REASON=resume exec "$HOME/engine/engine/engine_b.sh"
fi
