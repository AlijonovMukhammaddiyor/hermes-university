# Architecture

The canonical description of how Hermes University works. The `docs/RFC-00*.md` files are the
historical design record; this document is the current source of truth.

## What it is
A **course-agnostic autonomous learning engine** on the [Hermes Agent](https://github.com/NousResearch/hermes-agent).
You give it a goal; it **researches and authors** a full university course for it — syllabus, real
materials, and a path to mastery — then teaches it daily with proof-gated work, tracks a durable
GPA/transcript across two rigorous 3-month semesters, and pushes spaced-repetition cards to your phone.

## Five principles (non-negotiable)
1. **Numbers are computed by code, not the model.** The deterministic engine owns GPA, streak,
   mastery, FSRS due dates, standing, promotion. The LLM teaches, proposes rubric bands, and nudges.
2. **No outcome without a proof.** Every outcome is measurable, Bloom-tagged, and gated by a concrete
   proof; above "apply", passing needs performance *and* a self-explanation.
3. **A course is data, not code.** Everything course-specific — units, outcomes, resources, rubrics,
   the teaching profile, the mastery model — lives in `courses/<CODE>/course.yaml`. The engine and the
   single professor skill never change per course.
4. **Personalize to the learner's goals, not their work.** Identity + goals live in one `profile.yaml`;
   applied projects advance who you want to become, never a job or employer.
5. **No hardcoded personal or organizational data** anywhere in code, skills, or shipped content.

## Components
- **`engine/`** — the deterministic authority (Python, pydantic). Owns state, gradebook (kind-weighted
  GPA), the FSRS/learner model, proof-gates, the course schema + validator, the document renderer, and
  the `hu-engine` CLI that skills/crons call for every number.
- **`skills/`** — three rendered Hermes skills:
  - **Registrar** — orchestrates the daily loop and is the interactive console (enroll, status,
    transcript, tailor, create/revise/delete course). Reads the engine for all numbers.
  - **Professor (Faculty Handbook)** — ONE skill that teaches *any* course by reading its module, and
    **authors** new courses by deep, cited, multi-source research (never the model's memory).
  - **Examiner** — runs quizzes, unit exams, midterm, and data-driven finals; calls the engine to gate
    advancement, promotion, and graduation.
- **`courses/`** — course modules (data). Ships with only `_TEMPLATE/`; the catalog starts empty and
  you author courses on demand. Authored courses are private instance data (git-ignored).
- **`profile.yaml`** — your identity + goals (git-ignored; ships as `profile.example.yaml`).
- **the vault** — a git-synced Obsidian folder and the learner's **workspace**: rendered
  Catalog/Syllabus/Resources/MyPlan/Transcript/Schedule/DegreeProgress docs, daily notes, exams,
  uploads, SRS, and a two-way **Kanban `Board.md`** (RFC-008) + a Dataview `Dashboard.md`. Plugins:
  Kanban, Dataview, Obsidian Git. (The old browser WebUI is retired — Obsidian + Telegram replace it.)

## Surfaces (one brain, the right tool per job — RFC-009)
**Telegram** is the *control + coach* surface: every management action is a discoverable, confirmable
verb (`courses · create · enroll · archive · restore · delete · status · profile · help`) — nobody
ever needs the shell. **Obsidian** is *manage + read + track*: an engine-rendered **`Home.md`** control
center (each course + its lifecycle status, what's blocked on you, today's work, cards due) plus the
two-way Kanban `Board.md` (the engine stays authoritative — a card marked Done without a real proof
bounces). **Anki** *retains*: cards are auto-generated from proven outcomes and pushed via FSRS to the
phone; the queued/created count is surfaced back into Telegram + Home.

## Course lifecycle & management (RFC-009)
Every course carries an engine-owned **status** — `draft → researching → authoring → placement →
active → archived` — that every surface reads. `researching` is the machine-readable *blocked on your
research upload* signal. Management is safe by construction: a **drop is a reversible archive**
(soft), `restore` brings it back, and a **hard `delete`** (files + state) requires an explicit
confirmation echo. The one confirm convention (consequence + `yes`/`cancel`, name-echo for deletes)
guards every destructive action. Identity + goals are edited through `profile set`, never hand-edited
YAML. The lifecycle, the aggregate `status` snapshot, and the SRS pipeline all live in the engine
(`engine/authoring.py`, `registrar.py`, `srs.py`); skills only call the CLI.

## The course module (`course.yaml`)
`Course → Unit → Outcome → Assessment → Rubric`, plus researched `description`, an `audience`
(who-it's-for / who-it's-**not**-for, so the learner self-selects), `primary_text`, per-unit
`resources` (best materials, specific locators), a `professor_profile` (the teaching character for the
field), and a `mastery_model` (excellence bar · expert practices · frontier · how to stay current ·
signature work). The rendered `Syllabus.md` is a **complete academic plan**: the week-by-week table
carries each week's readings, its take-home **assignment**, and the **assessment calendar** the engine
derives — a quiz at each unit's end, a midterm mid-semester, finals in the last week — alongside the
grading breakdown. The validator enforces: every outcome has a proof, Bloom target ≥ outcome, prereqs
form a DAG, rubrics exist. `hu-engine course validate` also reports `authored` — true only when the
course has a description, an audience, per-unit resources, a professor profile, a mastery model, and a
research dossier. Nothing shallow ships.

## Lifecycle
```
Catalog → Registration (prereqs, credit-load, holds) → Syllabus → Academic Calendar
  → Instruction (daily, concept-first) → Assessment (weighted policy) → Grading → Transcript → GPA
  → Standing (probation/good/honors + consequences) → Progression (unit gates)
  → Promotion (finals ≥B) → Graduation (credential + diploma)   ·   throughout: Advising · SRS
```

## Course authoring (research-driven, placement-personalized — RFC-007)
When you enroll a course that isn't authored yet — or the daily loop finds one — the Professor runs its
authoring protocol:
1. **Research is human-in-the-loop.** The Professor writes a deep-research **prompt**
   (`Courses/<CODE>/research/PROMPT.md`); you run it in **Claude (Deep Research)** and upload the cited
   report to `Uploads/<CODE>/`. Authoring **pauses** until it lands — the model never authors from
   memory. For everything the report doesn't cover, the Professor does **mandatory web search (Serper)**
   and cites it. A machine-checked `authored` gate rejects any dossier without ≥5 cited URLs +
   confidence tags + an open-questions section.
2. **Build the FULL A–Z curriculum** (fundamentals always included as `foundational` units), best
   materials, and a week-by-week plan → validate to `authored: true` → render the full `Syllabus.md`.
3. **Placement, not assumption.** The learner self-reports or sits a rigorous placement exam per unit;
   a "yes" is verified at **≥ B** before it counts. Passed outcomes are recorded and the engine renders
   a personalized `MyPlan.md` (mastered units skipped, weeks renumbered). The full course stays in
   `Syllabus.md`; `MyPlan.md` is the learner's track.

Zero code, zero redeploy: a new course's professor is the Faculty Handbook bound to the module.

## Install & run
See the [README](README.md) quickstart and [PREREQUISITES.md](PREREQUISITES.md). `install.sh` is
idempotent: profile + config → engine venv → vault scaffold → state init → render skills → verify.
