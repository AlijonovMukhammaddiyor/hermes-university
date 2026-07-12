#!/usr/bin/env bash
# Disaster-recovery backup (RFC-011): mirror course sources + an encrypted secrets bundle into the
# vault so its git remote is the single durable store. Idempotent, rewrites only when inputs change;
# vault-sync (RFC-009) then commits + pushes. Safe on a timer.
set -uo pipefail
R="${HERMES_UNIVERSITY_ROOT:-$HOME/hermes-university}"
V="${HERMES_UNIVERSITY_VAULT:-$HOME/vault}"
HR="$HOME/.hermes"
SRC="$V/_source"
KEY="$HR/backup.key"
GCT="$HOME/.config/google-calendar-mcp/tokens.json"
mkdir -p "$SRC/courses"

# 1) course sources → vault/_source/courses/<CODE>/ (course.yaml + research/)
if [ -d "$R/courses" ]; then
  for d in "$R"/courses/*/; do
    code=$(basename "$d"); [ "$code" = "_TEMPLATE" ] && continue
    [ -f "$d/course.yaml" ] || continue
    mkdir -p "$SRC/courses/$code"
    cp "$d/course.yaml" "$SRC/courses/$code/course.yaml"
    [ -d "$d/research" ] && { mkdir -p "$SRC/courses/$code/research"; \
      rsync -a --delete "$d/research/" "$SRC/courses/$code/research/" 2>/dev/null \
      || cp -r "$d/research/." "$SRC/courses/$code/research/" 2>/dev/null || true; }
  done
fi

# 2) encrypted secrets bundle → vault/_source/secrets.tar.gz.enc (only if inputs changed)
[ -f "$KEY" ] || {
  umask 077; head -c 32 /dev/urandom | base64 | tr -d '\n' > "$KEY"
  echo "════════════════════════════════════════════════════════════════════════"
  echo " NEW BACKUP PASSPHRASE generated at $KEY — SAVE IT in a password manager."
  echo " It is the ONLY key that decrypts your redeploy backup."
  if [ -t 1 ]; then  # print the secret only to an interactive terminal…
    echo "     $(cat "$KEY")"
  else  # …never from the timer, where stdout is the journal
    echo "     (read it on the server with:  cat $KEY   — kept out of logs)"
  fi
  echo "════════════════════════════════════════════════════════════════════════"
}
FILES=("$R/profile.yaml" "$R/config.env" "$HR/.env" "$HR/config.yaml" "$HR/auth.json" \
       "$HR/cron/jobs.json" "$GCT")
present=(); for f in "${FILES[@]}"; do [ -f "$f" ] && present+=("$f"); done
HASH=$(cat "${present[@]}" 2>/dev/null | sha256sum | cut -d' ' -f1)
if [ "$(cat "$HR/.backup.hash" 2>/dev/null)" != "$HASH" ]; then
  STAGE=$(mktemp -d); mkdir -p "$STAGE/hermes/cron" "$STAGE/gcal"
  cp "$R/profile.yaml" "$STAGE/" 2>/dev/null || true
  cp "$R/config.env" "$STAGE/" 2>/dev/null || true
  for f in .env config.yaml auth.json; do cp "$HR/$f" "$STAGE/hermes/" 2>/dev/null || true; done
  cp "$HR/cron/jobs.json" "$STAGE/hermes/cron/" 2>/dev/null || true
  [ -f "$GCT" ] && cp "$GCT" "$STAGE/gcal/" 2>/dev/null || true
  TAR=$(mktemp); tar -czf "$TAR" -C "$STAGE" . 2>/dev/null
  openssl enc -aes-256-cbc -pbkdf2 -salt -in "$TAR" -out "$SRC/secrets.tar.gz.enc" -pass file:"$KEY"
  echo "$HASH" > "$HR/.backup.hash"
  rm -f "$TAR"; rm -rf "$STAGE"
  enc_status="rewritten"
else
  enc_status="unchanged"
fi

cat > "$SRC/README.md" <<EOF
# Hermes University — disaster-recovery backup (RFC-011)
This folder is the durable backup that rides the vault's git remote.
- \`courses/<CODE>/\` — authored course sources (course.yaml + research dossier).
- \`secrets.tar.gz.enc\` — profile.yaml, config.env, ~/.hermes/{.env,config.yaml,cron/jobs.json,auth.json},
  Google-Calendar token — AES-256 encrypted. Decrypt only with your passphrase (~/.hermes/backup.key).
To restore on a fresh droplet: run \`bootstrap.sh <code-repo> <vault-repo>\`.
EOF
echo "backup ok: courses=[$(ls "$SRC/courses" 2>/dev/null | tr '\n' ' ')] secrets=$enc_status"
