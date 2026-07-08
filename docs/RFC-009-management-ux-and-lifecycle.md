# RFC-009 — Manageable-by-anyone: course lifecycle, one control surface, working Anki

Status: **ACCEPTED — implementing** · Date: 2026-07-08
Canonical description: [`ARCHITECTURE.md`](../ARCHITECTURE.md). Builds on RFC-002/004/007/008.

## 0. Why
Managing the university still leaks into the shell. Deleting a course meant SSH + `rm` + reasoning
about git tracking — the opposite of "anyone can run this." Three concrete gaps surfaced from an audit
of the engine, the three skills, the vault renderer, and the Anki path:

1. **No course lifecycle.** `state.Course` has only `active: bool` (calendar). Nothing records that a
   course is *draft / awaiting research / authoring / awaiting placement / active / archived*. The
   `authored` gate is computed in the CLI and thrown away, so no surface can say what a course is
   waiting on. `drop()` just pops the dict — no files, no git, no audit.
2. **No safe management verbs.** There is no `delete` / `archive` / `restore` / `profile` command and
   **no confirm-before-destructive mechanism at all** (`drop` fires immediately). Profile identity
   lives in `profile.yaml` with no learner-facing way to view or change it.
3. **Anki is wired but dead.** Cards are never auto-generated (`cards.build_cards` is unused outside
   tests), nothing writes `SRS/pending.jsonl`, `anki_sync.py` is scheduled by nothing, review results
   never flow back, and no "cards due" number is exposed anywhere.

**Non-negotiable (unchanged):** the engine owns all truth. Surfaces read and propose; they never
compute. Every number on every surface traces to the gradebook / learner model / FSRS.

## 1. Principle: one backbone, three thin surfaces
The engine gains a **course lifecycle** and an **aggregate status**. Every surface renders the same
truth for its medium:

- **Telegram** — the *control + coach* surface. Every management action is a discoverable, confirmable
  verb. Zero setup, on the phone. This is where "anyone manages everything."
- **Obsidian** — the *manage/read/track* surface. A single engine-rendered **`Home.md`** control
  center mirrors the Telegram status; the Kanban `Board.md` (RFC-008) is the daily workspace.
- **Anki** — the *retention* surface. Cards are auto-generated from proven outcomes and pushed; the
  due count is surfaced back into Telegram + Home so it stops being a black box.

## 2. Course lifecycle (engine backbone)
Add `status` to `state.Course` (a `Literal`), owned and advanced only by the engine:

```
draft ──enroll──▶ researching ──report uploaded──▶ authoring ──authored:true──▶ placement
                      │ (blocked on you)                                            │
                      ▼                                                              ▼
                  (re-nudge)                                       active ◀──placement done──┘
                                                                     │
                                                        archive ◀────┴────▶ (drop = archive, not delete)
                                                          │ restore ▲
```

- **`researching`** is the *blocked-on-you* state — the single machine-readable signal every surface
  reads to say "waiting for your research report." Set when `authored:false` and no report under
  `Uploads/<CODE>/`; cleared when a report lands or the learner replies `done`.
- The **`authored` gate result is persisted** onto `state.Course` at transition time (it was ephemeral)
  so surfaces can show state without re-shelling `course validate`.
- **`drop` becomes `archive`** (soft, reversible; sets `EnrollmentRecord.dropped_on`, which is dead
  today). Archived courses hide from active views, keep their files, and `restore` brings them back.
- **`delete` is separate, hard, double-confirmed** — removes `courses/<CODE>/` (git-ignored instance
  data), the vault `Courses/<CODE>/` docs, and the state entry, atomically. This is the verb that
  replaces the SSH/`rm` dance.

Transitions live in `registrar.py` (one function per edge); the CLI exposes them; skills only call the
CLI. Initial `status` set in `register_courses`/`enroll`.

## 3. Management verbs + the confirm convention (Telegram)
Extend the existing context-aware quick-action menu (registrar:91-95) — do not invent a new UI. Full
grammar: `courses · create · enroll · drop(=archive) · delete · archive · restore · status · plan ·
research · profile · help`, all natural-phrasing tolerant, courses addressed by **name** not code.

**Confirm convention (new, reused everywhere):** any destructive verb replies with a one-line
consequence + a `yes` / `cancel` quick action and does nothing until `yes`. Two tiers:
- **Soft** (archive/drop, reschedule): single `yes`.
- **Hard** (delete, reset): names the exact loss ("deletes the syllabus, resources, and progress for
  *AI Agent Engineering* — this can't be undone") and requires an explicit `delete <NAME>` echo.
Archive is always offered as the safer default next to delete.

## 4. Obsidian control center (`Home.md`)
New `render_home(state, records, modules, board, srs_due)` in `docs.py`, written by `render_all` at the
vault root. It **aggregates already-computed truth** (no new numbers except SRS due): header
(semester/week · standing + hold warning · semester & cumulative GPA · streak), a **Courses** list with
status badge + mastery %, **Today** (from the Board's Today column), **Blocked on you** (researching
courses + Proof-Pending cards + probation hold), and **Cards due** (§5). The two duplicate
`Dashboard.md` notes collapse into `Home.md` (engine-rendered) + the Kanban `Board.md`; Dataview stays
display-only.

## 5. Anki, made real (forward pipeline)
Wire the missing connective step so the surface works end to end:

1. **Proof-passed → card.** When `grade add --passed` records mastery, the engine appends the
   professor-supplied front/back (or a proof-derived default) to `<vault>/SRS/pending.jsonl` via the
   existing `cards.build_cards` + `fsrs.new_card`. New CLI: `srs add` (emit) and `srs due` (count due
   from `OutcomeState.fsrs`).
2. **Sync on a schedule.** `anki_sync.py` (already push-capable) is invoked by a new cron; it uploads
   `pending.jsonl` and clears it only on a clean sync.
3. **Surface the number.** `srs due` feeds `Registrar/status.md`, `Home.md`, and the Telegram digest,
   so "cards due" is an engine number, not LLM prose.

**Deliberately deferred (own follow-up):** review results flowing *back* from Anki to update
`OutcomeState.fsrs` and lower live mastery on lapse (RFC-001's decay). That needs an Anki→engine read
path (AnkiConnect or collection read-back) and is scoped separately; §5 is the forward half and is
independently useful. This is stated loudly rather than half-built.

## 6. Onboarding + profile
- **First-contact wizard** (Telegram): name → goal → target level → daily cap → first course, writing
  the profile through a new `profile set` CLI (never hand-edited YAML). Unattended installs keep the
  generic `profile.example.yaml` defaults.
- **`profile`** verb: view; `profile set <field> <value>`: edit (goal, cap, level, timezone). Re-renders
  affected surfaces. Identity stays in the git-ignored `profile.yaml` (RFC-005).

## 7. Non-goals
Web UI (retired, RFC-008). Multi-learner/tenancy. Anki review-back (§5 defer). Renaming course codes
(cosmetic). Editing a course's curriculum by hand — authoring stays research-gated (RFC-007).

## 8. Verification
- Lifecycle unit tests: enroll→researching→authoring→placement→active; archive↔restore; delete removes
  files+state atomically; `status --all` reflects each.
- Confirm tests: destructive verbs no-op without `yes`; hard-delete needs the name echo.
- Anki tests: `grade add --passed` appends a well-formed `pending.jsonl` line; `srs due` counts FSRS
  due; sync clears only on success.
- `render_home` golden test: badges, blocked-on-you, cards-due present; no raw numbers invented.
- Full `pytest` green; ruff clean; end-to-end on the droplet (create→research→author→placement→active,
  then archive, then delete — all from Telegram, no shell).
