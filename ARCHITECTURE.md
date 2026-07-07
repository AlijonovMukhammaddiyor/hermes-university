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
- **the vault** — a git-synced Obsidian folder: rendered Catalog/Syllabus/Resources/Transcript/
  Schedule/DegreeProgress docs, daily notes, exams, uploads, SRS. What you read; also the WebUI browses it.

## The course module (`course.yaml`)
`Course → Unit → Outcome → Assessment → Rubric`, plus researched `description`, `primary_text`,
per-unit `resources` (best materials, specific locators), a `professor_profile` (the teaching character
for the field), and a `mastery_model` (excellence bar · expert practices · frontier · how to stay
current · signature work). The validator enforces: every outcome has a proof, Bloom target ≥ outcome,
prereqs form a DAG, rubrics exist. `hu-engine course validate` also reports `authored` — true only when
the course has a description, per-unit resources, a professor profile, a mastery model, and a research
dossier. Nothing shallow ships.

## Lifecycle
```
Catalog → Registration (prereqs, credit-load, holds) → Syllabus → Academic Calendar
  → Instruction (daily, concept-first) → Assessment (weighted policy) → Grading → Transcript → GPA
  → Standing (probation/good/honors + consequences) → Progression (unit gates)
  → Promotion (finals ≥B) → Graduation (credential + diploma)   ·   throughout: Advising · SRS
```

## Autonomous course authoring
When you enroll a course that isn't authored yet — or the daily loop finds one — the Professor runs its
authoring protocol: (optional intake interview) → **deep research as a multi-round harness** (fan-out
sweep → deep read of primary sources → adversarial verification, ≥2 corroborating sources and no strong
refutation → a completeness critic that loops until no material gaps → a cited dossier) → backward
design from the excellence bar → resource map → validate to `authored: true` → render → co-design →
persist. Zero code, zero redeploy: a new course's professor is the Faculty Handbook bound to the module.

## Install & run
See the [README](README.md) quickstart and [PREREQUISITES.md](PREREQUISITES.md). `install.sh` is
idempotent: profile + config → engine venv → vault scaffold → state init → render skills → verify.
