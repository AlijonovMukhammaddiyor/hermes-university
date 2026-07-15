#!/usr/bin/env bash
# Hermes University — one-command RESTORE on a fresh droplet (RFC-011).
# Prereqs: Hermes Agent installed (hermes CLI + ~/.hermes) as your normal user; git + openssl; and
# your BACKUP PASSPHRASE (~/.hermes/backup.key from the old box). Anki desktop optional (SRS sync).
# Usage:  bootstrap.sh <code-repo-url> <vault-repo-url>
#   e.g.  bootstrap.sh git@github.com:you/hermes-university.git git@github.com:you/hermes-vault.git
set -euo pipefail
CODE_URL="${1:?usage: bootstrap.sh <code-repo-url> <vault-repo-url>}"
VAULT_URL="${2:?usage: bootstrap.sh <code-repo-url> <vault-repo-url>}"
R="$HOME/hermes-university"; V="$HOME/vault"; HR="$HOME/.hermes"

echo "== 1/6 clone code + vault =="
[ -d "$R/.git" ] || git clone "$CODE_URL" "$R"
[ -d "$V/.git" ] || git clone "$VAULT_URL" "$V"

echo "== 2/6 restore encrypted secrets =="
ENC="$V/_source/secrets.tar.gz.enc"
if [ -f "$ENC" ]; then
  read -rsp "  Backup passphrase: " PASS; echo
  TMP=$(mktemp -d)
  if ! openssl enc -d -aes-256-cbc -pbkdf2 -in "$ENC" -out "$TMP/b.tar.gz" -pass pass:"$PASS" 2>/dev/null; then
    echo "  WRONG PASSPHRASE — aborting (nothing changed)."; rm -rf "$TMP"; exit 1
  fi
  tar -xzf "$TMP/b.tar.gz" -C "$TMP"
  cp "$TMP/profile.yaml" "$R/" 2>/dev/null || true
  cp "$TMP/config.env"   "$R/" 2>/dev/null || true
  mkdir -p "$HR/cron" "$HOME/.config/google-calendar-mcp"
  cp "$TMP/hermes/.env"          "$HR/"       2>/dev/null || true
  cp "$TMP/hermes/config.yaml"   "$HR/"       2>/dev/null || true
  cp "$TMP/hermes/auth.json"     "$HR/"       2>/dev/null || true
  cp "$TMP/hermes/cron/jobs.json" "$HR/cron/" 2>/dev/null || true
  cp "$TMP/gcal/tokens.json" "$HOME/.config/google-calendar-mcp/" 2>/dev/null || true
  # the restored config.yaml points the calendar MCP at this path, so it has to come back too
  cp "$TMP/gcal/gcp-oauth.keys.json" "$HR/" 2>/dev/null || true
  echo "$PASS" | tr -d '\n' > "$HR/backup.key"; chmod 600 "$HR/backup.key"   # future backups reuse
  rm -rf "$TMP"
  echo "  secrets + config + crons restored"
else
  echo "  no secrets bundle in the vault — supply profile.yaml + config.env + ~/.hermes/.env manually."
fi

echo "== 3/6 restore course sources =="
if [ -d "$V/_source/courses" ]; then
  mkdir -p "$R/courses"
  cp -r "$V/_source/courses/." "$R/courses/"
  echo "  restored: $(ls "$R/courses" | grep -v _TEMPLATE | tr '\n' ' ')"
fi

echo "== 4/6 run install.sh (venv · skills · systemd · sync/backup/anki timers · hooks) =="
# pass the restored vault path explicitly, else install.sh would scaffold a fresh empty vault
( cd "$R" && HERMES_UNIVERSITY_VAULT="$V" bash install.sh ) || echo "  install.sh reported issues — review above."

echo "== 5/6 re-auth externals (only what can't be restored) =="
echo "  - AnkiWeb: collection re-syncs on first push (creds already restored)."
echo "  - Google Calendar: token restored; if expired, re-run its OAuth flow once."

echo "== 6/6 verify + start =="
"$R/.venv/bin/hu-engine" status --vault "$V" --courses "$R/courses" 2>/dev/null | head -c 500 || true
echo; echo "Start the gateway:  systemctl --user restart hermes-gateway"
echo "DONE — prior state (courses, GPA, streak, crons, config) restored from the vault."
