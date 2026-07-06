# RFC-001 — Hermes University v2 Architecture

Status: **DRAFT — awaiting sign-off** · Owner: the maintainer · Date: 2026-07-06

This is the canonical spec. Every doc, engine module, skill, cron, and template in this repo
points at the definitions here. "In sync" is enforced structurally: **the deterministic engine is
the single source of truth for all numbers**, and **one config renders everything**. If an artifact
disagrees with this RFC, the artifact is wrong.

---

## 1. What we're building

A **general, course-agnostic learning engine** that runs an autonomous "university" on top of the
Hermes Agent: scheduled professors teach concept-first, assign proof-gated work, grade to rubrics,
and a deterministic Registrar tracks a durable GPA/transcript across **two rigorous 3-month
semesters**. Cards flow to the learner's phone via Anki (FSRS). It must be **perfect for any
course** (a course is a data-defined module) and shippable as a **single installable repo**
(bring your own API keys).

Non-goals (locked earlier): multi-tenancy/multi-user (single instance per install), a custom web
dashboard (management is via the Hermes WebUI chat + an Obsidian dashboard).

---

## 2. Decisions log (locked with the user)

| # | Decision | Rationale |
|---|---|---|
| D1 | **Single instance**, rebuilt clean; designed generally but no tenancy machinery | User is sole learner |
| D2 | **Two rigorous 3-month semesters** (12 weeks each); S1 finals ≥B → promote to S2; S2 finals → graduation | "very rigorous 2 semesters" |
| D3 | Manage via **existing Hermes WebUI chat** (no custom dashboard) + Obsidian dashboard for viewing | |
| D4 | **Rewrite the logic layer; keep verified plumbing** | Kill drift, keep what works |
| D5 | **Single installable repo** (`config.env` + `install.sh`); curriculum shipped as a git **tap** | "people install at once, given API keys" |
| D6 | **Research-first** for everything before hand-rolling | User directive |
| D7 | **Deterministic engine computes all numbers**; LLM only teaches/grades-to-rubric/nudges | Prior-art + pedagogy + Obsidian threads converge; transcript must be trustworthy |
| D8 | **Anki via `genanki` → AnkiWeb** (headless); retire the live xvfb-Anki+AnkiMCP stack | Robust + installable; no live desktop-Anki dependency |
| D9 | **Proof-gate is a pluggable interface**; **LeetCode adapter now, Judge0 adapter later** | Ship now, no rework later |
| D10 | **Assignments on Hermes `kanban`** (prereq links, block-on-submission, dispatch) | Ready-made pipeline, no build |
| D11 | Course-module template = the **evidence-based pedagogy schema** (backward design) | Research-backed rigor |

---

## 3. Core architecture — two layers, hard boundary

```
┌─────────────────────────── LLM layer (skills, per-role, non-authoritative) ──────────────────────────┐
│  Registrar-agent   Examiner-agent   Professor-agents (one per course)                                  │
│  - teach concept-first, assign, grade a submission AGAINST A RUBRIC → {band, weak_areas, reasoning}    │
│  - explain, nudge, converse (WebUI/Telegram). NEVER computes GPA/streak/mastery/intervals.             │
└───────────────────────────────────────────┬───────────────────────────────────────────────────────────┘
                                             │ calls (RPC / CLI)         ▲ reads (context)
                                             ▼                           │
┌─────────────────────── Deterministic engine (Python, authoritative, tested) ─────────────────────────┐
│  registrar.py  gradebook.py  fsrs.py  proofgate/  scheduler.py  state.py                                │
│  - owns ALL numbers: GPA (semester+cumulative), standing, streak, mastery, FSRS due dates              │
│  - verifies proofs (proofgate adapters), records grades, computes promotion/graduation                 │
│  - writes state.json (schema-validated) + transcript + Dashboard frontmatter + genanki decks           │
└───────────────────────────────────────────┬───────────────────────────────────────────────────────────┘
                                             ▼
        Git vault (records)      AnkiWeb (cards→phone)      Google Calendar (Mentor)      Kanban (assignments)
```

**Invariant:** the LLM may *propose* a rubric band for a free-form artifact; the engine decides
whether the proof-gate passed, converts band→GPA, and updates state. The LLM cannot write a number
into the transcript. This is the habit-sprint pattern (deterministic engine + conversational coach)
and the reason the GPA can be trusted.

---

## 4. Canonical data model

### 4.1 `state.json` (engine-owned; schema-validated on every write)
```jsonc
{
  "schema_version": 3,
  "program": { "total_semesters": 2, "weeks_per_semester": 12, "started_on": "YYYY-MM-DD" },
  "position": { "semester": 1, "week_in_semester": 1, "absolute_week": 1, "phase": "foundations" },
  "gpa": { "semester": null, "cumulative": null },      // computed, never LLM-written
  "standing": "good",                                     // good | honors(≥3.7) | probation(<2.5)
  "streak": { "current": 0, "longest": 0, "last_completed_date": null },
  "learner": { "name": null, "timezone": "Asia/Tashkent", "persona_stage": "guide" },
  "courses": {
    "<CODE>": { "title": "...", "credits": 4, "runs_in": [1,2], "active": true,
                "unit": "<unit-id>", "unit_index": 0, "activates_week": null }
  },
  "assessments": { "s1_midterm": null, "s1_finals": null, "s2_midterm": null, "s2_finals": null },
  "history": []   // per completed semester: {semester, gpa, standing, finals_grade, completed_on}
}
```

### 4.2 Grade & mastery records (append-only, engine-owned)
`records/grades.jsonl` — one line per graded proof:
```jsonc
{ "ts": "...", "course": "CS250", "outcome": "two-pointers.apply", "kind": "hw|quiz|exam|midterm|finals",
  "band": "A|B|C|F", "score": 0.0-1.0, "credits_weight": 0.3, "proof": {"source":"leetcode","passed":true,"ref":"..."} }
```
The engine derives GPA/mastery/standing from this log — the log is the truth, `state.json` is a
cached projection the engine rewrites.

### 4.3 Course-module schema (the pedagogy template — course-agnostic)
Adopted verbatim from the methodology research. A course = data, not code:
```
Course:  id, title, subject_domain, north_star, prerequisites[], enduring_understandings[],
         units[] (ordered, each gates the next), mastery_policy, grading_scale
Unit:    id, title, order_index, outcomes[], prereq_outcomes[], entry_gate, summative, exit_gate
Outcome: id, statement (A-SMART), bloom_level, depends_on[], proof (assessment_id), spaced_items[],
         mastery_threshold          # RULE: no outcome may exist without a proof
Assessment: id, outcome_id, type(formative|summative), modality, bloom_target(≥outcome), rubric_id,
            proof_gate (explicit pass condition, may require performance AND self-explanation),
            scaffold_stage (worked_example|completion|independent)
Rubric:  id, shape(analytic|single_point), criteria[] (3–8 atomic/orthogonal/non-hackable),
         score_to_grade (band→letter→GPA points)
```
Stored per course as `courses/<CODE>/course.yaml` (+ `units/`, `rubrics/`, `resources/`).

---

## 5. Semester model (D2)

- **2 semesters × 12 weeks.** `position` tracks semester + week_in_semester + absolute_week.
- **Cadence each semester (rigorous):** daily ≤4 proof-gated tasks · weekly quiz (Sun) · biweekly
  unit exams (wk 2,4,8,10; gate next unit ≥C) · **midterm wk 6** (cumulative, ≥B or remediation) ·
  **semester finals wk 12** (cumulative).
- **Transitions:** S1 finals **≥B → promote to S2** (roll semester GPA into `history`, load S2
  units); fail → remediation week + one retake. S2 finals → **graduation / readiness verdict**.
- **Mastery gating:** engine never unlocks a unit whose `entry_gate` (prereq mastery) is unmet, nor
  advances past a unit whose `exit_gate` is unmet. Time flexes; thresholds don't.
- **Live mastery:** a lapsed (FSRS-decayed) outcome lowers current mastery/GPA until refreshed — the
  transcript reflects *current* competence, not a one-time peak.

---

## 6. Course-registration workflow (repeatable, per course)

To add ANY course (this is what "register a course" runs, research-first):
1. **Research** the domain's canonical curriculum (community-vetted; cite sources).
2. **Co-design** the `Course → Units → Outcomes` (A-SMART + Bloom) and, per outcome, its
   **proof-gate + rubric** — backward design, enforced (no outcome without a proof).
3. **Author the module**: `courses/<CODE>/course.yaml`, unit lessons, rubrics, resources; the
   **professor skill** (rendered from `skills/professor.template.md` + course values); register the
   proof-gate adapter mapping; derive FSRS spaced-items.
4. **Wire**: add to `state.courses`, curriculum, kanban board template; add to the assign/exam crons.
5. **Verify**: engine unit-tests (schema valid, every outcome has a reachable proof, gates form a
   DAG) + a dry-run assign.
6. **Commit** (repo) — the course is now a self-contained, shippable module.

Seed curricula from research (per-course, co-designed): **CS250** NeetCode-150 pattern order ·
**CS301** Hello-Interview delivery framework + case studies · **CS270** Anthropic building-blocks →
context → RAG → evals · **PD101** interviewing.io story-selection + LP dimensions. Exact week-by-week
is co-designed at registration time, not pre-baked here.

---

## 7. Integrations

| Concern | Mechanism | Notes |
|---|---|---|
| Spaced repetition | `py-fsrs` (scheduling) + **`genanki`** decks → **AnkiWeb** (D8) | headless; learner reviews on phone; retire live-Anki stack |
| Coding proof | **proofgate interface** `verify(evidence)→{passed,score,source}`; **LeetCode adapter now** (session cookie, best-effort), **Judge0 adapter later** (D9) | swappable; LLM never decides "passed" |
| Free-form proof | rubric-graded by LLM → band; engine records; above "apply" requires self-explanation | can't fabricate: band alone ≠ pass |
| Calendar | Google Calendar MCP — read primary / write **Mentor** only | kept from v1 |
| Assignments | **Hermes `kanban`** (D10): card=assignment, link=prereq, block=awaiting submission, complete=graded, `dispatch` progresses | ready-made |
| Interface | Telegram gateway (push/quick replies) + **Hermes WebUI chat** (manage) | kept |

---

## 8. Hermes primitives we exploit

Curriculum = **skills + bundles**, shipped as a private **tap** (git skill registry) → this *is*
the installable distribution. Professor runs = **cron** (+ **MoA** for hard grading, **fallback**
chains for unattended reliability). Teach vs grade separated via **multi-profile** or MoA to avoid
leniency bias. Learner model = **USER.md** + optional external memory (Mem0/Honcho) as a long-term
mastery graph. Vault auto-commit via **hooks**; curriculum hygiene via **curator** (pin
hand-authored lessons). Secrets via **Bitwarden** (keys out of plaintext in the shipped repo).

---

## 9. Surfaces (view & manage)

- **Hermes WebUI chat** (localhost:8787) — the management console: `status`, `transcript`, `day
  off`, `reschedule`, `edit curriculum`, `pause/resume <course>`, `explain grade`, `what's next`.
  These are Registrar verbs gated on interactive (vs cron) sessions.
- **Obsidian `Dashboard.md`** — read-only view: GPA-over-time chart (obsidian-charts), transcript
  table (Bases/Dataview), streak, today's plan (Tasks), upcoming exams. **Engine precomputes all
  rollups into YAML frontmatter** so the dashboard only displays (fast, Bases-compatible, no live
  LLM math). Agent writes frontmatter-only; ownership partitioned (engine owns state/transcript,
  human owns free-text notes) to keep git two-way sync conflict-free.

---

## 10. Packaging (single installable repo)

```
hermes-university/
  README.md  PREREQUISITES.md  docs/RFC-001-architecture.md
  config.env.example              # ALL identity + secrets/IDs; nothing hardcoded elsewhere
  install.sh                      # idempotent: deps → render skills → register MCPs → crons → scaffold vault → interactive OAuth/cookie → verify
  engine/                         # deterministic Registrar (Python, tested): registrar, gradebook, fsrs, scheduler, state, proofgate/
  skills/                         # templates: registrar, examiner, professor.template.md (rendered against config + course)
  crons/                          # cron definitions (assign, audit, week[midterm/finals], monthly, cookie-check)
  courses/<CODE>/                 # per-course modules (course.yaml, units/, rubrics/, resources/)  + _TEMPLATE/
  vault-template/                 # scaffold for the learner's data vault (Dashboard.md, Registrar/, ...)
```
`config.env` keys (user brings these): `LEARNER_NAME`, `TIMEZONE`, `DEEPSEEK_API_KEY`,
`TELEGRAM_BOT_TOKEN`+chat, `LEETCODE_SESSION`, `ANKIWEB_EMAIL`(+interactive pw),
`GOOGLE_OAUTH_CREDENTIALS`(path), calendar IDs (auto-derived at install). Everything else = templates
rendered against these → mechanical "complete sync." Prereqs enumerated in `PREREQUISITES.md`.

---

## 11. Migration from v1 (the running droplet)

v1 (day-1 state) migrates cleanly: `install.sh` run against the droplet renders v2 in place →
rewrite `state.json`→v3, replace skills/crons, scaffold `courses/` + Dashboard, **retire the
anki-headless service + AnkiMCP** (switch to genanki→AnkiWeb), keep gcal/leetcode/webui/git/swap.
Archive the v1 Daily note. `install.sh` re-runnable = upgrade path.

---

## 12. Build phases (each verified before the next)

1. **Repo + engine core**: `config.env`, `install.sh` skeleton, deterministic engine
   (state schema+validation, gradebook GPA/standing, fsrs via py-fsrs, proofgate interface +
   leetcode adapter) with unit tests.
2. **Skills/crons templates**: registrar (+management verbs), examiner (midterm/finals/promotion),
   professor.template; cron definitions. Rendered by install.sh.
3. **Course-module template + registration workflow**; author **CS250** first end-to-end
   (co-designed) as the reference module.
4. **Integrations**: genanki→AnkiWeb, kanban assignment pipeline, calendar, Obsidian Dashboard.
5. **Register CS301, CS270, PD101** (each: research → co-design → author → commit).
6. **Deploy to droplet via install.sh** (migration) + end-to-end verify incl. a **simulated wk-12
   finals→promotion** before it matters.

---

## 13. Coherence matrix (the "in sync" guarantee — filled as we build)

| Artifact | Reads | Writes | Authoritative? |
|---|---|---|---|
| engine/registrar | grades.jsonl, course.yaml | state.json, transcript, Dashboard frontmatter | **yes** |
| skill: professor | course.yaml, state.position | a submission + proposed rubric band | no (proposes) |
| skill: examiner | course.yaml, records | proposed bands; calls engine to gate/promote | no |
| cron: assign/audit/week | — | invoke skills + engine | no |
| Obsidian Dashboard | state/transcript frontmatter | — (display only) | no |

Every future change is checked against this table; nothing invents its own fields or numbers.

---

## 14. Open (co-design) items — NOT decided here
- Exact **week-by-week curriculum content** per course (done at registration, together).
- Rubric criteria wording per course.
- Whether teach/grade separation uses multi-profile vs MoA (decide at phase 2).
- External memory provider choice (optional; decide at phase 3).
