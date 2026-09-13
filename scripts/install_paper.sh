#!/usr/bin/env bash
# Install The Hermes Daily (RFC-010 v2): the edition format check + the vault's paper identity.
#
# The agent host only ever WRITES an edition — markdown into $VAULT/Paper/<date>/articles/ — and
# checks it. Rendering the broadsheet needs Node and happens on the reader's own machine, so
# nothing here installs a reader, a server, or npm.
#
# Idempotent; never fatal. A box without the check still writes editions, it just cannot gate on
# them, so this warns and exits 0 rather than failing the whole install.
set -uo pipefail
R="${1:-$HOME/hermes-university}"; V="${2:-$HOME/vault}"
ENGINE_URL="git+https://github.com/vaelkeep/vael-paper.git#subdirectory=server"
PV="$R/.venv-paper"   # kept out of the engine venv: vael-paper pins fastapi/uvicorn/pillow

# 1. each paper's identity — seeded once, then it is the owner's file and we never touch it again.
#    A paper is an editions root: paper.json beside date-named folders of articles.
for TPL in "$R"/vault-template/Papers/*/; do
  [ -d "$TPL" ] || continue
  NAME=$(basename "$TPL")
  mkdir -p "$V/Papers/$NAME"
  if [ ! -f "$V/Papers/$NAME/paper.json" ] && [ -f "$TPL/paper.json" ]; then
    cp "$TPL/paper.json" "$V/Papers/$NAME/paper.json"
    echo "  seeded $V/Papers/$NAME/paper.json — masthead and sections are yours to edit"
  fi
done

# 2. the rendered site is output, never source: it would add ~500 KB of PNG plates to the vault
#    every night, and git keeps every blob forever.
#    Chart plates are the same: the engine redraws <article-id>-chart.png from the article's own
#    `chart:` block whenever it scans, so committing ~200 KB of PNG a night buys nothing and can
#    never be reclaimed. Photographs are NOT ignored — only the generated plates.
GI="$V/.gitignore"
add_ignore() {
  grep -qxF "$1" "$GI" 2>/dev/null && return 0
  printf '%s\n' "$1" >> "$GI"
  echo "  added $1 to the vault .gitignore"
}
grep -q "^# The Hermes Daily" "$GI" 2>/dev/null || printf '\n# The Hermes Daily — rendered output, redrawn on demand, never source\n' >> "$GI"
add_ignore "Papers/*/.site/"
add_ignore "Papers/*/*/images/*-chart.png"
# The PDF is ~700 KB and regenerated from the same markdown on demand.
add_ignore "Papers/*/*/*.pdf"

# 3. the paper's typefaces. Without these the print build falls back to whatever
#    serif the host has — DejaVu on a plain Debian box — and the typography in the
#    stylesheet is decorative only.
if [ ! -f "$HOME/.hermes/fonts/fonts.css" ]; then
  echo "  fetching the paper's typefaces"
  python3 "$R/scripts/paper/fetch_fonts.py" >/dev/null 2>&1 \
    || echo "  couldn't fetch fonts — the PDF will set in the host's default serif"
fi

# 4. the format check — the only half of the engine the writer needs
if [ ! -x "$PV/bin/vael-paper-check" ]; then
  echo "  installing the vael-paper format check (no Node, check only)"
  python3 -m venv "$PV" >/dev/null 2>&1 || true
  "$PV/bin/pip" -q install --upgrade pip >/dev/null 2>&1 || true
  "$PV/bin/pip" -q install "vael-paper @ $ENGINE_URL" >/dev/null 2>&1 || true
fi
if [ -x "$PV/bin/vael-paper-check" ]; then
  echo "  edition check ready: $PV/bin/vael-paper-check"
else
  echo "  couldn't install the edition check — editions will still be written, but unchecked."
  echo "  retry: $PV/bin/pip install 'vael-paper @ $ENGINE_URL'"
fi
exit 0
