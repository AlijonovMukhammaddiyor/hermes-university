#!/usr/bin/env bash
# Render The Hermes Daily on THIS machine and open it.
#
# The agent writes editions as markdown into the vault; git carries those. The broadsheet itself is
# output — ~500 KB of plates a night — so it is never committed. This builds it locally, into the
# vault's gitignored Paper/.site/, and opens it.
#
# First run clones the engine and builds its reader (needs Node); after that it is about a second.
#
# Usage: paper_render.sh [vault] [--paper NAME] [--no-open] [--port N]
#
# A vault can hold several papers under Papers/<name>/. With one, it is picked
# automatically; with more, name it.
set -euo pipefail

VAULT="${HERMES_UNIVERSITY_VAULT:-$HOME/vault}"
ENGINE="${VAEL_PAPER_HOME:-$HOME/vael-paper}"
OPEN=1
PORT=8791
PAPER=""

while [ $# -gt 0 ]; do
  case "$1" in
    --paper) PAPER="$2"; shift 2 ;;
    --no-open) OPEN=0; shift ;;
    --port) PORT="$2"; shift 2 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) VAULT="$1"; shift ;;
  esac
done
VAULT="${VAULT/#\~/$HOME}"
PAPERS="$VAULT/Papers"

die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }
log() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }

[ -d "$PAPERS" ] || die "no papers at $PAPERS — has the agent written an edition yet?"

# One paper needs no naming; several do.
if [ -z "$PAPER" ]; then
  found=$(find "$PAPERS" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort)
  count=$(printf '%s\n' "$found" | grep -c . || true)
  [ "$count" = 1 ] || die "which paper? $PAPERS holds: $(printf '%s ' $found)
    name one:  $(basename "$0") --paper <name>"
  PAPER="$found"
fi
EDITIONS="$PAPERS/$PAPER"
OUT="$EDITIONS/.site"
[ -f "$EDITIONS/paper.json" ] || die "no paper.json in $EDITIONS — is $PAPER a paper?"
command -v node >/dev/null 2>&1 || die "Node 20+ is needed to build the reader once (brew install node)"

# 1. the engine — cloned once, updated quietly after
if [ ! -d "$ENGINE/.git" ]; then
  log "cloning the vael-paper engine into $ENGINE"
  git clone -q https://github.com/vaelkeep/vael-paper.git "$ENGINE"
else
  git -C "$ENGINE" pull -q --ff-only 2>/dev/null || true
fi

# 2. the reader — a Vite build, needed only when it is missing or the engine moved on
if [ ! -f "$ENGINE/reader/dist/index.html" ] || [ "$ENGINE/reader/package.json" -nt "$ENGINE/reader/dist/index.html" ]; then
  log "building the reader (once; takes a minute)"
  npm --prefix "$ENGINE/reader" install --silent >/dev/null 2>&1 \
    || die "npm could not install the reader's dependencies"
  npm --prefix "$ENGINE/reader" run build --silent >/dev/null 2>&1 \
    || die "the reader failed to build — run: npm --prefix $ENGINE/reader run build"
fi

# 3. the exporter's own venv — uv when it is here because it is much faster
BIN="$ENGINE/server/.venv/bin"
if [ ! -x "$BIN/vael-paper-export" ]; then
  log "installing the engine's python side"
  if command -v uv >/dev/null 2>&1; then
    ( cd "$ENGINE/server" && uv sync --quiet ) || die "uv sync failed in $ENGINE/server"
  else
    python3 -m venv "$ENGINE/server/.venv" >/dev/null 2>&1
    "$BIN/python" -m pip install --quiet -e "$ENGINE/server" || die "pip install failed"
  fi
fi

# 4. export — every response the server would give, written out ahead of time
log "printing the edition"
"$BIN/vael-paper-export" --editions "$EDITIONS" --reader "$ENGINE/reader/dist" --out "$OUT" >/dev/null
rm -f "$OUT"/assets/*.map          # dev-only, and a third of the bundle

LATEST=$(ls -d "$EDITIONS"/2*/ 2>/dev/null | sort | tail -1 | xargs -I{} basename {})
log "printed $PAPER ${LATEST:-archive} → $OUT"

[ "$OPEN" = 1 ] || exit 0

# 5. serve it: the reader fetches api/*.json, which file:// will not allow
command -v python3 >/dev/null 2>&1 || die "python3 is needed to serve the pages"
( cd "$OUT" && exec python3 -m http.server "$PORT" >/dev/null 2>&1 ) &
sleep 1
log "reading at http://localhost:$PORT  (arrow keys turn the pages; ctrl-c here when done)"
if command -v open >/dev/null 2>&1; then open "http://localhost:$PORT"; fi
wait
