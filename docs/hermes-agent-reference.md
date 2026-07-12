# Hermes Agent — internal reference

Canonical notes on the runtime we build on (`NousResearch/hermes-agent`, MIT). Compiled from deep
research against `main` (~July 2026, v0.18.2). **Confidence is marked; "verify directly" items at the
bottom are not yet source-confirmed.** Numbers that bite our design are called out; don't treat the
soft/marketing figures as contracts.

## What it is
A self-hosted, **single-primary-agent** runtime ("the agent that grows with you"). Every entry point —
interactive CLI, an always-on messaging **gateway** (~24 channels), a **cron** scheduler, batch runs,
an ACP/IDE adapter — funnels into one `AIAgent` orchestrator (`run_agent.py`). Identity, skills, and
memory are separated on disk under `HERMES_HOME` (default `~/.hermes`): `SOUL.md` (persona), `skills/`
(`SKILL.md` folders), `memories/` (`MEMORY.md` + `USER.md`), `state.db` (SQLite sessions), `cron/jobs.json`.

## Capabilities (surface is far bigger than we use)
- **Skills** — on-demand `SKILL.md` docs, 3-level progressive disclosure, `agentskills.io`-compatible;
  auto-exposed as slash commands; up to **5 chained per message**; ~72 ship bundled. A **curator** ages
  skills active→stale→archived (never auto-deletes).
- **Self-authoring** — the agent writes skills via `/learn` + `skill_manage` after real work.
- **~73 tools** across toggleable toolsets; **MCP client** built in (`hermes mcp install`).
- **`execute_code`** — agent writes Python calling Hermes tools in a child process (keeps intermediates
  out of context). **`delegate_task`** — spawns isolated **subagents** (native multi-agent).
- **Multimodality** (voice/vision/image/video, 10 TTS providers); **32 model providers**; provider
  **resilience** (fallback chains, credential-pool rotation, cost/speed routing, 1-hr Claude prompt cache).
- **Pluggable external memory** backends (Honcho, Mem0, Supermemory, …) beyond built-in memory.

## Architecture & request lifecycle
- **One orchestrator.** `AIAgent.run_conversation(prompt)`; thin entry layers per platform.
- **System prompt = stable → context → volatile tiers**, frozen for the session to keep the provider
  prefix-cache warm; a **date-only** timestamp keeps it byte-stable all day. Memory writes persist to
  disk immediately but **only re-enter the prompt next session** (frozen snapshot).
- **Context files** (`.hermes.md`/`HERMES.md` → `AGENTS.md` → `CLAUDE.md` → `.cursorrules`) load
  **first-match-wins** (only one). `SOUL.md` is independent/additive, loaded **only from `HERMES_HOME`**,
  and threat-scanned for prompt injection before injection.
- **Sessions** — `state.db` (SQLite, WAL, schema v20) with FTS5 full-text recall via `session_search`
  (returns real stored messages, no LLM summary).
- **Gateway** — self-managed daemon (`hermes gateway start`; `install` → systemd/launchd). **Cron**
  ticks every 60s; each due job runs a **fresh, history-less `AIAgent`** with a restricted toolset and
  delivers to a target. Cron jobs can't spawn more cron jobs.

## File & context limits ⭐ (the part that constrains us)
| File | Limit | Style | Over-limit |
|---|---|---|---|
| `SOUL.md` / context files (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`) | **20,000 chars** (scales to model window; ceiling 500K; `context_file_max_chars`) | **soft** | truncates — 70% head + 20% tail, middle → marker |
| Subdirectory-discovered context files | ~8,000 chars *(doc-only, unverified)* | soft | tighter cap |
| **`SKILL.md`** | **100,000 chars** (`MAX_SKILL_CONTENT_CHARS`); `name ≤64`; `description ≤1024` stored / **≤60 shown** | **hard** | **rejects** (validated in `skill_manage`) |
| `MEMORY.md` / `USER.md` | 2,200 / 1,375 chars | **hard** | rejects, **no auto-compact** |
| Single `read_file` | 100,000 chars | reject → use offset/limit |
| Terminal tool output | 50,000 bytes | cap |
| History compression | compresses at **~50%** of window (`threshold_percent=0.50`; ⚠️ DeepWiki says 85% — source shows 0.50) | protects first 3 / last 20 turns |

- `skills_list()` (Level 0, all skills' metadata) ≈ **~3k tokens**; the full body loads only on `skill_view`.
- The one **≤15KB** skill limit is a **GEPA self-evolution** guardrail in the *separate*
  `hermes-agent-self-evolution` repo — binds us **only if we adopt self-evolution**, not at runtime.

## Requirements & recommended setup
- **Python `>=3.11,<3.14`**; one-line installer bundles uv + Python 3.11 + Node 22 + ripgrep + ffmpeg
  (only non-Windows prereq: **git**).
- **Model must expose ≥64,000 tokens of context** — smaller is rejected at startup. Providers: Nous
  Portal (OAuth, recommended) / OpenAI / Anthropic / OpenRouter / any OpenAI-compatible endpoint.
- **Always-on:** `hermes gateway install` (systemd/launchd) or Docker
  (`nousresearch/hermes-agent`, `-v ~/.hermes:/opt/data -p 8642:8642`). **Never run two gateways on one
  data dir.** Host: a "$5 VPS" is called plenty (docs); 2–4 GB / 2 vCPU for comfort.
- **Security:** allowlist or DM-pairing; **never** `GATEWAY_ALLOW_ALL_USERS=true` with terminal access;
  authenticate the dashboard (an unauthenticated dashboard was a real June-2026 attack vector).

## Best-practice patterns
- **Three-level progressive disclosure** — tiny always-loaded surface (`description ≤60`), heavy content
  in the body / `references/` pulled on demand.
- **Fixed SKILL.md order:** *When to Use → Quick Reference → Procedure → Pitfalls → Verification*,
  most-common workflow first. **Wrap existing CLIs, never invent commands.**
- **"Files over hidden prompts":** `SOUL.md` = portable identity · `AGENTS.md` = project scope ·
  `MEMORY.md` = continuity.
- **#1 pitfall — prefix-cache invalidation.** Unstable prompts (timestamps, mid-session toolset changes)
  can **10× cost**. Guard: keep the system prompt byte-stable within a session; CI-assert
  turn-1 == turn-10 prompt.
- Other pitfalls: memory-file rot (hard caps force consolidation), skill sprawl dilutes the Level-0
  index, auxiliary-model misconfig fails silently, Ollama's 4k default context collides with the 64k floor.

## Implications for Hermes University
- **Our ~18KB `registrar.SKILL.md` is ~18% of the 100K cap** — no hard-cap risk now or with RFC-013.
- **Real cost is per-`skill_view` token load** (~5–6k tokens for an 18KB body every open) — so grow the
  body carefully and defer bulk to `references/`.
- **Our renderer bypasses `skill_manage`** (`render_skills.py` writes `SKILL.md` straight to disk), so
  Hermes never validates the 100K / description-length caps — **we must self-enforce** them.
- **Keep university content in *skills*, not context files** — the 20K `SOUL.md`/`AGENTS.md`
  soft-truncation silently eats the middle of anything large.
- **Don't route learner observations into `MEMORY.md`/`USER.md`** — tiny hard caps + next-session lag;
  keep the deep Learner Model in our engine. (See RFC-013 § "Fit with the Hermes runtime".)

## Verify directly (not yet source-confirmed)
1. Does `skill_view` truncate a large `SKILL.md` body at load, beyond the 100K authoring cap?
2. Confirm our renderer path and add the cap guards (100K body, 60-char description).
3. Compression threshold — source shows **0.50**, DeepWiki says **85%**; confirm the live default.
4. The 8,000-char subdirectory context-file cap (doc prose only).
5. Web-search backend — Firecrawl? (conflicting signals, unconfirmed).
6. Popularity metrics (~213K stars) are almost certainly a summarizer hallucination — ignore.
7. Code claims cite files, **not line numbers** — a `git clone` is needed for precise anchors.
