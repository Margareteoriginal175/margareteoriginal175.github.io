#!/usr/bin/env bash
# Idempotent installer for Engine B on the Simular server. Safe to re-run (also run at login/boot).
set -uo pipefail
U="${SUDO_USER:-$(id -un)}"; H="$(getent passwd "$U" | cut -d: -f6)"
E="$H/engine"
chmod +x "$E/engine/engine_b.sh" "$E/engine/pipeline.sh" 2>/dev/null || true
grep -qxF 'logs/' "$E/.git/info/exclude" 2>/dev/null || printf 'logs/\n.lock\n' >> "$E/.git/info/exclude"

# 1) systemd timer (primary): hourly :25 Asia/Shanghai + 4 min after boot, catch-up after sleep
sudo -n tee /etc/systemd/system/engine-b.service >/dev/null <<UNIT
[Unit]
Description=aiym168 Engine B (self-updating site, takeover when GitHub is stale)
Wants=network-online.target
After=network-online.target
[Service]
Type=oneshot
User=$U
Environment=HOME=$H
ExecStart=$E/engine/engine_b.sh
TimeoutStartSec=55min
Nice=5
UNIT
sudo -n tee /etc/systemd/system/engine-b.timer >/dev/null <<'UNIT'
[Unit]
Description=Run aiym168 Engine B hourly
[Timer]
OnCalendar=*-*-* *:25:00 Asia/Shanghai
OnBootSec=4min
Persistent=true
AccuracySec=30s
[Install]
WantedBy=timers.target
UNIT
sudo -n systemctl daemon-reload && sudo -n systemctl enable --now engine-b.timer

# 2) cron (secondary, same minute; the lock file prevents double runs) + @reboot
if ! command -v crontab >/dev/null 2>&1; then
  sudo -n DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cron >/dev/null 2>&1 || true
fi
if command -v crontab >/dev/null 2>&1; then
  sudo -n systemctl enable --now cron >/dev/null 2>&1 || true
  ( crontab -l 2>/dev/null | grep -v 'engine/engine_b.sh' ; \
    echo "CRON_TZ=Asia/Shanghai"; \
    echo "25 * * * * $E/engine/engine_b.sh >/dev/null 2>&1"; \
    echo "@reboot sleep 240 && $E/engine/engine_b.sh >/dev/null 2>&1" ) | awk '!seen[$0]++' | crontab -
fi

# 3) self-reinstall at desktop login (home dir persists even if /etc is reset by an image upgrade)
mkdir -p "$H/.config/autostart"
cat > "$H/.config/autostart/engine-b.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Engine B self-install
Exec=bash -c "sleep 30; bash $E/engine/install_box.sh >> $E/logs/install.log 2>&1"
X-GNOME-Autostart-enabled=true
NoDisplay=true
DESK
echo "[install] done"; systemctl list-timers engine-b.timer --no-pager | head -3; crontab -l 2>/dev/null | grep -E 'engine_b|CRON_TZ' || true
