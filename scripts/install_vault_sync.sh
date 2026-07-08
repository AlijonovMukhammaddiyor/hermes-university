#!/usr/bin/env bash
# Install the durable vault-sync guarantee (RFC-009): a git post-commit hook that auto-pushes every
# commit, plus a systemd --user timer that reconciles every 2 minutes. Idempotent — safe to re-run.
# Usage: install_vault_sync.sh [VAULT_DIR] [REPO_DIR]
set -euo pipefail
VAULT="${1:-$HOME/vault}"
REPO="${2:-$HOME/hermes-university}"
SYNC="$REPO/scripts/vault_sync.sh"
chmod +x "$SYNC"

# 1) post-commit hook — push immediately after ANY commit (pull-then-retry on rejection).
#    A recursion guard stops the pull's merge-commit from re-triggering the hook.
HOOK="$VAULT/.git/hooks/post-commit"
mkdir -p "$VAULT/.git/hooks"
cat > "$HOOK" <<EOF
#!/usr/bin/env bash
[ -n "\${HU_VAULT_HOOK:-}" ] && exit 0
export HU_VAULT_HOOK=1
cd "$VAULT" || exit 0
git push -q 2>/dev/null || { git pull --no-rebase --no-edit -q 2>/dev/null; git push -q 2>/dev/null; } || true
EOF
chmod +x "$HOOK"
echo "installed post-commit hook -> $HOOK"

# 2) systemd --user timer — the backstop reconciler (every 2 min).
UD="$HOME/.config/systemd/user"
mkdir -p "$UD"
cat > "$UD/hermes-vault-sync.service" <<EOF
[Unit]
Description=Hermes University — keep the Obsidian vault committed + pushed
After=network-online.target

[Service]
Type=oneshot
ExecStart=$SYNC $VAULT
EOF
cat > "$UD/hermes-vault-sync.timer" <<EOF
[Unit]
Description=Reconcile the vault every 2 minutes (never leave a commit unpushed)

[Timer]
OnBootSec=1min
OnUnitActiveSec=2min
Persistent=true

[Install]
WantedBy=timers.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now hermes-vault-sync.timer
echo "enabled hermes-vault-sync.timer (every 2 min)"
