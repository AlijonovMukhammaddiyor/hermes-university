#!/usr/bin/env bash
# Hermes University — one-command setup wizard. Prompts for keys, writes them to config.env and
# into the Hermes agent (~/.hermes), installs the web-search plugin, then runs install.sh.
# Prereq: the Hermes Agent must already be installed (the `hermes` CLI on PATH):
#     curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
# See PREREQUISITES.md for the accounts/keys to get first.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="$ROOT/config.env"

log() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
die() {
  printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2
  exit 1
}

command -v hermes >/dev/null 2>&1 || die "the Hermes Agent isn't installed (no 'hermes' on PATH).
  Install it first:  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
  then re-run ./setup.sh"

[ -f "$CFG" ] || {
  cp "$ROOT/config.env.example" "$CFG"
  log "created config.env from the example"
}
set -a
. "$CFG"
set +a

# in-place upsert KEY=value into config.env; shell-quoted so odd values round-trip (quotes $ ` \)
set_key() {
  python3 - "$CFG" "$1" "$2" <<'PY'
import shlex
import sys
path, key, val = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(path).read().splitlines()
line = f"{key}={shlex.quote(val)}"
for i, l in enumerate(lines):
    if l.startswith(key + "="):
        lines[i] = line
        break
else:
    lines.append(line)
open(path, "w").write("\n".join(lines) + "\n")
PY
}

# ask NAME "prompt" required[0/1] secret[0/1] — reads into $NAME and persists to config.env
ask() {
  local name="$1" prompt="$2" required="${3:-0}" secret="${4:-0}" cur="${!1:-}" ans=""
  while :; do
    if [ "$secret" = 1 ]; then
      printf '%s%s: ' "$prompt" "${cur:+ [keep current]}"
      read -rs ans || true
      echo
    else
      printf '%s%s: ' "$prompt" "${cur:+ [$cur]}"
      read -r ans || true
    fi
    ans="${ans:-$cur}"
    if [ -n "$ans" ] || [ "$required" = 0 ]; then break; fi
    echo "  (required)"
  done
  printf -v "$name" '%s' "$ans"
  [ -n "$ans" ] && set_key "$name" "$ans"
  return 0
}

log "Let's set up Hermes University. Blank keeps the current value / skips an optional one."
echo "── Required ──────────────────────────────────────────────"
ask DEEPSEEK_API_KEY "DeepSeek API key" 1 1
ask LLM_MODEL "LLM model (deepseek-v4-flash / deepseek-v4-pro)" 0 0
ask TELEGRAM_BOT_TOKEN "Telegram bot token (@BotFather)" 1 1
ask TELEGRAM_ALLOWED_USERS "Your Telegram numeric user id (@userinfobot)" 1 0
ask SERPER_API_KEY "Serper API key (serper.dev — web search)" 1 1
echo "── Optional (press Enter to skip) ────────────────────────"
ask TELEGRAM_HOME_CHANNEL "Telegram chat id for scheduled digests" 0 0
ask ANKIWEB_USERNAME "AnkiWeb username (spaced repetition)" 0 0
ask ANKIWEB_PASSWORD "AnkiWeb password" 0 1
ask GOOGLE_OAUTH_CREDENTIALS "Google Calendar OAuth client json — path (books your study routine)" 0 0

# wire into the agent — config set auto-routes: secrets → .env, settings → config.yaml
log "wiring keys into the Hermes agent (~/.hermes)"
hermes config set DEEPSEEK_API_KEY "$DEEPSEEK_API_KEY"
hermes config set model.provider deepseek
hermes config set model.base_url https://api.deepseek.com/v1   # native DeepSeek — else Hermes routes deepseek via OpenRouter and 401s
hermes config set model.default "${LLM_MODEL:-deepseek-v4-flash}"
hermes config set TELEGRAM_BOT_TOKEN "$TELEGRAM_BOT_TOKEN"
hermes config set TELEGRAM_ALLOWED_USERS "$TELEGRAM_ALLOWED_USERS"
hermes config set SERPER_API_KEY "$SERPER_API_KEY"
[ -n "${TELEGRAM_HOME_CHANNEL:-}" ] && hermes config set TELEGRAM_HOME_CHANNEL "$TELEGRAM_HOME_CHANNEL"
[ -n "${BRAVE_API_KEY:-}" ] && hermes config set BRAVE_API_KEY "$BRAVE_API_KEY"

# web search — multi-provider plugin; registers the web_search_plus tool the skills use
log "installing the web-search plugin"
hermes plugins install robbyczgw-cla/hermes-web-search-plus --enable \
  || log "plugin install skipped — run later: hermes plugins install robbyczgw-cla/hermes-web-search-plus --enable"

# Google Calendar — we register the MCP; Google has no headless consent flow, so the one-time browser
# approval stays manual. Tokens are portable: authorize anywhere, copy tokens.json to a headless box.
if [ -n "${GOOGLE_OAUTH_CREDENTIALS:-}" ]; then
  KEYS="${GOOGLE_OAUTH_CREDENTIALS/#\~/$HOME}"
  [ -f "$KEYS" ] || die "Calendar: no file at $KEYS (PREREQUISITES.md § Google Calendar)"
  python3 -c 'import json,sys; sys.exit(0 if "installed" in json.load(open(sys.argv[1])) else 1)' "$KEYS" \
    || die "Calendar: $KEYS is not a Desktop OAuth client — recreate it as 'Desktop app', not 'Web application'"
  log "registering the google-calendar MCP"
  hermes mcp remove google-calendar >/dev/null 2>&1 || true   # re-register cleanly when re-run
  # `mcp add` asks "Enable all N tools?" and cancels on EOF — answer it, we want the whole toolset.
  printf 'y\n' | hermes mcp add google-calendar --command npx \
    --env "GOOGLE_OAUTH_CREDENTIALS=$KEYS" --args -y @cocal/google-calendar-mcp \
    || log "calendar MCP registration failed — see PREREQUISITES.md"
  if [ -f "$HOME/.config/google-calendar-mcp/tokens.json" ]; then
    log "Calendar: already authorized"
  else
    log "Calendar: authorize once — opens a browser:"
    printf '      GOOGLE_OAUTH_CREDENTIALS=%s npx -y @cocal/google-calendar-mcp auth\n' "$KEYS"
    log "  no browser here? run it on your laptop, then copy ~/.config/google-calendar-mcp/tokens.json over"
  fi
else
  log "Calendar: skipped, no OAuth client json (PREREQUISITES.md § Google Calendar to add it later)"
fi

# engine · vault · skills · crons · timers · preflight
log "running install.sh"
bash "$ROOT/install.sh"

echo
log "Setup done. Start the agent:  hermes gateway install && hermes gateway start"
log "Then message your bot:  create course <what you want to become>"
