# RFC-008 — Obsidian-native surfaces (Kanban board + dashboard) & WebUI retirement

Status: **ACCEPTED — implementing** · Date: 2026-07-08
Canonical description: [`ARCHITECTURE.md`](../ARCHITECTURE.md).

## 0. Why
The vault is currently a *read* surface. Obsidian (with community plugins) can be the learner's actual
**workspace** — a Kanban board they track work on, and a live dashboard — while Telegram stays the
*coach/push* surface and Anki stays *retention*. The public WebUI is now redundant (Obsidian sync +
Telegram cover reading, tracking, chat, upload) and is a security exposure, so it is retired.

**Non-negotiable:** the engine still owns all truth (mastery, GPA, streak, standing). The board is a
**two-way view**, not the source — engine-authoritative on conflict.

## 1. Surfaces (one source, the right tool for each job)
- **Telegram** — coaching, nudges, quick-actions, voice, file handoff. The push surface.
- **Obsidian** — read (Syllabus/Resources/MyPlan/Transcript) + **track** (Kanban board) + **see**
  (Dataview dashboard). The pull/workspace surface. Requires the **Kanban** and **Dataview** community
  plugins (documented in PREREQUISITES + the vault README; the vault ships pre-configured).
- **Anki** — spaced repetition to the phone.
- ~~WebUI~~ — **retired** (disabled on the droplet).

## 2. The Kanban board (`{{VAULT}}/Board.md`) — two-way, engine-authoritative
Obsidian-kanban markdown: `kanban-plugin: board` frontmatter + `## Column` headings + `- [ ] card`
items. Columns: **This Week · Today · Doing · Proof Pending · Done**.

- **Card format:** `- [ ] **<human title>** — <one-liner> <!--hu:o=<outcome>;c=<course>;d=<tier>-->`
  The HTML comment carries the machine mapping (outcome/course/tier) and is invisible in Obsidian; the
  learner sees only the clean title + line.
- **Engine primitives** (`engine/board.py`, deterministic + tested):
  - `render_board(columns) -> md` — always-valid kanban markdown.
  - `parse_board(md) -> columns` — robust read (checked state, column, outcome).
- **CLI:** `hu-engine board read --vault …` (→ JSON columns) and `hu-engine board write --vault …
  --json <spec>` (→ writes `Board.md`).
- **Flow:**
  - **Assign (morning):** registrar reads the board, adds the day's picked tasks to **Today** (dedupe
    by outcome), preserves other columns, writes. Cards mirror the Daily note + calendar.
  - **Learner:** drags a card to **Done** (or checks it) in Obsidian; git-sync carries it back.
  - **Audit (night):** `board read` → outcomes in **Done**/checked that aren't graded → **verify the
    proof via the engine** → `grade add`. Verified → stays Done. **Unverified → bounced to Proof
    Pending with a one-line note** (engine-authoritative). Then re-write the board (roll incomplete
    Today → tomorrow, add nothing the learner didn't earn).
- **Conflict rule:** the board is re-rendered from engine truth each cycle; a card the learner marked
  Done without real proof does not become mastery — it bounces. No number ever comes from the board.

## 3. Dashboard (`{{VAULT}}/Dashboard.md`) — Dataview
The skills already write YAML frontmatter to `Daily/*.md`. Ship a `Dashboard.md` with Dataview queries:
this-week focus, today's tasks + done state, streak/GPA (from the engine-written `Registrar/status.md`
frontmatter), upcoming exams. Read-only; no numbers computed in the note.

## 4. WebUI retirement
Stop + disable the WebUI service on the droplet; close the public port. Document the removal. (If a
browser view is ever wanted, bind localhost + SSH-tunnel — not public.)

## 5. Open-source polish (worth starring)
- **README**: a compelling one-liner + the three-surface story + a quickstart + a "screenshots" section
  (Kanban board, Telegram flow, a rendered syllabus). Visuals sell it.
- **PREREQUISITES / vault README**: the required Obsidian plugins (Kanban, Dataview) + how the vault
  syncs (obsidian-git).
- Everything lands with tests; `pytest` green; no personal data.

## 6. Acceptance
`board write`/`board read` round-trip in tests; a Done card with a passing proof records mastery and a
Done card without proof bounces to Proof Pending; `Board.md` renders as a real board in Obsidian; the
WebUI service is disabled; README reads like a repo you'd star.
