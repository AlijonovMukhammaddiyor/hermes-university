#!/usr/bin/env bash
# Hermes University installer — idempotent; re-run to upgrade. Usually invoked by setup.sh (which
# collects keys first).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT="${HERMES_UNIVERSITY_VAULT:-$HOME/vault}"   # canonical path shared by bootstrap/sync scripts
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

log() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# 1. profile + config
[ -f "$ROOT/config.env" ] || die "config.env missing — cp config.env.example config.env and fill it in (see PREREQUISITES.md)"
set -a; . "$ROOT/config.env"; set +a
if [ ! -f "$ROOT/profile.yaml" ]; then
  cp "$ROOT/profile.example.yaml" "$ROOT/profile.yaml"
  log "created profile.yaml from the example — edit it with your name + goals before first run"
fi
log "config + profile loaded"

# 2. engine venv + install
# On Debian/Ubuntu the venv bootstrapper (ensurepip) ships as a SEPARATE package, so `python3 -m
# venv` dies half-way through a fresh install. Check up front: self-heal when we're root on apt,
# otherwise stop with the exact command to run rather than a traceback mid-install.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  PYV="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  if [ "$(id -u)" = 0 ] && command -v apt-get >/dev/null 2>&1; then
    log "python3-venv missing — installing python${PYV}-venv"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq >/dev/null 2>&1 || true
    apt-get install -y -qq "python${PYV}-venv" >/dev/null 2>&1 \
      || apt-get install -y -qq python3-venv >/dev/null 2>&1 || true
  fi
  python3 -c "import ensurepip" >/dev/null 2>&1 \
    || die "python3 cannot create virtualenvs (no ensurepip). Install it, then re-run:
    apt install python${PYV}-venv"
fi

log "installing deterministic engine"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" -q install --upgrade pip >/dev/null
"$ROOT/.venv/bin/pip" -q install -e "$ROOT[dev]" >/dev/null   # [dev] = pytest for the verify step
ENGINE="$ROOT/.venv/bin/hu-engine"

# 3. vault scaffold + git
log "scaffolding vault at $VAULT"
mkdir -p "$VAULT"
cp -rn "$ROOT/vault-template/." "$VAULT/" 2>/dev/null || true
if [ ! -d "$VAULT/.git" ]; then git -C "$VAULT" init -q -b main; fi
mkdir -p "$VAULT/Registrar" "$VAULT/records"
# durable sync: a vault commit can never stay unpushed (hook + 2-min reconciler timer)
if git -C "$VAULT" remote get-url origin >/dev/null 2>&1; then
  bash "$ROOT/scripts/install_vault_sync.sh" "$VAULT" "$ROOT" || log "vault-sync install skipped"
else
  log "vault has no 'origin' remote yet — run scripts/install_vault_sync.sh after adding one"
fi

# disaster-recovery backup: course sources + encrypted secrets into the vault, daily (RFC-011)
log "installing DR backup timer"
bash "$ROOT/scripts/install_backup.sh" "$ROOT" "$VAULT" || log "backup install skipped"

# Anki push + review-back sync (needs the bundled Anki desktop python; warns + skips if absent)
log "installing Anki sync timer"
bash "$ROOT/scripts/install_anki_sync.sh" "$ROOT" "$VAULT" || log "anki-sync install skipped"

# 4. engine state — init once; never clobber existing records
STATE="$VAULT/Registrar/state.json"
if [ ! -f "$STATE" ]; then
  log "initialising state.json (identity + goals from profile.yaml)"
  "$ENGINE" state init --started "$(date +%F)" --out "$STATE"
else
  log "state.json exists — leaving records intact (upgrade mode)"
fi
# No auto-enrollment: the catalog starts empty; you author + enroll courses on demand.

# 5. render skills (registrar, examiner, professor — one each)
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

# 6. crons — RESTORE brings them back via bootstrap.sh; first install creates from crons/crons.yaml
if command -v hermes >/dev/null 2>&1; then
  log "creating cron jobs (idempotent)"
  "$ROOT/.venv/bin/python" "$ROOT/scripts/install_crons.py" --vault "$VAULT" \
    || log "cron creation skipped — run scripts/install_crons.py once the gateway is set up"
else
  log "hermes CLI not found — create crons later: scripts/install_crons.py --vault $VAULT"
fi

# 7. externals — restored from the bundle where possible; re-auth only if expired.
[ -d /usr/local/share/anki ] || log "Anki desktop not installed — SRS sync disabled until you install it"
log "Google Calendar / AnkiWeb — tokens restored from backup if present; re-auth if expired"

# 9. verify
log "verifying engine"
"$ROOT/.venv/bin/python" -m pytest "$ROOT" -q
"$ENGINE" state show --file "$STATE" >/dev/null && log "state OK"

# integrations preflight (RFC-012) — informational; never blocks the engine install
log "checking integrations"
"$ENGINE" doctor --env "$ROOT/config.env" || log "some integrations need config (see above) — optional ones are fine to skip"

log "done. Vault: $VAULT"
