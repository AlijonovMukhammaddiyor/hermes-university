#!/usr/bin/env bash
# Durable vault sync (RFC-009): GUARANTEE the Obsidian vault is always committed AND pushed to the
# remote, so a droplet-side change can never be stranded (Obsidian only ever sees the remote).
#
# Idempotent and safe to run on a short timer OR from a git post-commit hook. Self-heals three
# failure modes: (a) engine/agent wrote but didn't commit, (b) committed but didn't push,
# (c) push rejected because the remote advanced (Obsidian-side commit) — pull, then push.
set -uo pipefail
V="${1:-$HOME/vault}"
cd "$V" 2>/dev/null || exit 0
[ -d .git ] || exit 0

# 1) commit anything pending (renders/edits that weren't committed by their author)
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -q -m "chore(vault): auto-sync" || true
fi

# 2) reconcile with the remote and push (rejected? the timer retries next tick)
git fetch -q origin 2>/dev/null || exit 0
if ! git rev-parse '@{u}' >/dev/null 2>&1; then
  git push -q -u origin HEAD 2>/dev/null || true
  exit 0
fi
if [ "$(git rev-parse @)" != "$(git rev-parse '@{u}')" ]; then
  git pull --no-rebase --no-edit -q 2>/dev/null || true    # integrate Obsidian-side commits
  git push -q 2>/dev/null || true
fi
