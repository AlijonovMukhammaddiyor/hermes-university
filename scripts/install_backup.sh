#!/usr/bin/env bash
# Install disaster-recovery backup timer (RFC-011): runs hermes_backup.sh daily so course sources +
# the encrypted secrets bundle land in the vault (which auto-pushes). Idempotent.
set -euo pipefail
R="${1:-$HOME/hermes-university}"; V="${2:-$HOME/vault}"
chmod +x "$R/scripts/hermes_backup.sh"
UD="$HOME/.config/systemd/user"; mkdir -p "$UD"
cat > "$UD/hermes-backup.service" <<EOF
[Unit]
Description=Hermes University — disaster-recovery backup into the vault (RFC-011)
[Service]
Type=oneshot
Environment=HERMES_UNIVERSITY_ROOT=$R
Environment=HERMES_UNIVERSITY_VAULT=$V
ExecStart=$R/scripts/hermes_backup.sh
EOF
cat > "$UD/hermes-backup.timer" <<EOF
[Unit]
Description=DR backup, daily
[Timer]
OnCalendar=*-*-* 05:00:00
OnBootSec=3min
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now hermes-backup.timer >/dev/null 2>&1 || true
echo "  installed backup timer (daily 05:00) — first run also on boot"
