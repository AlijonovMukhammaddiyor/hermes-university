#!/usr/bin/env bash
# Hermes University installer — idempotent; re-run to upgrade. See docs/RFC-001-architecture.md §10.
# Phase 1: real steps = config, engine venv, vault scaffold, state init, verify.
# Later phases (marked [PHASE n]) are stubbed until built.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT="${HERMES_UNIVERSITY_VAULT:-$HOME/hermes-vault}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

log() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# 1. config ---------------------------------------------------------------
[ -f "$ROOT/config.env" ] || die "config.env missing — cp config.env.example config.env and fill it in (see PREREQUISITES.md)"
set -a; . "$ROOT/config.env"; set +a
: "${LEARNER_NAME:?set LEARNER_NAME in config.env}"
: "${TIMEZONE:?set TIMEZONE in config.env}"
log "config loaded for '$LEARNER_NAME' ($TIMEZONE)"

# 2. engine venv + install ------------------------------------------------
log "installing deterministic engine"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" -q install --upgrade pip >/dev/null
"$ROOT/.venv/bin/pip" -q install -e "$ROOT" >/dev/null
ENGINE="$ROOT/.venv/bin/hu-engine"

# 3. vault scaffold + git -------------------------------------------------
log "scaffolding vault at $VAULT"
mkdir -p "$VAULT"
cp -rn "$ROOT/vault-template/." "$VAULT/" 2>/dev/null || true
if [ ! -d "$VAULT/.git" ]; then git -C "$VAULT" init -q -b main; fi
mkdir -p "$VAULT/Registrar" "$VAULT/records"

# 4. engine state (init once; never clobber existing records) -------------
STATE="$VAULT/Registrar/state.json"
if [ ! -f "$STATE" ]; then
  log "initialising state.json"
  "$ENGINE" state init --name "$LEARNER_NAME" --tz "$TIMEZONE" \
    --started "$(date +%F)" --out "$STATE"
else
  log "state.json exists — leaving records intact (upgrade mode)"
fi

# 5. render skills (registrar, examiner, professor-per-course) ------------
log "rendering skills"
BUILD="$ROOT/.build/skills"; rm -rf "$BUILD"
"$ROOT/.venv/bin/python" "$ROOT/scripts/render_skills.py" \
  "$ROOT" "$ROOT/config.env" "$BUILD" "$VAULT" "$ENGINE"
if command -v hermes >/dev/null 2>&1; then
  DEST="$HERMES_HOME/skills/hermes-university"; mkdir -p "$DEST"
  cp -r "$BUILD/." "$DEST/"; log "installed skills -> $DEST"
else
  log "hermes CLI not found — rendered to $BUILD (install on the droplet to deploy)"
fi

# 6. [PHASE 4] register MCPs (leetcode, google-calendar; genanki needs none)
log "[PHASE 4] MCP registration — not yet implemented"

# 7. [PHASE 2] create cron jobs (assign/audit/week/monthly/cookie-check) ---
log "[PHASE 2] cron creation — not yet implemented"

# 8. [PHASE 4] interactive one-time setup (Google OAuth, AnkiWeb login) ----
log "[PHASE 4] interactive OAuth/AnkiWeb — not yet implemented"

# 9. verify ---------------------------------------------------------------
log "verifying engine"
"$ROOT/.venv/bin/python" -m pytest "$ROOT" -q
"$ENGINE" state show --file "$STATE" >/dev/null && log "state OK"

log "done (phase-1 scope). Vault: $VAULT"
