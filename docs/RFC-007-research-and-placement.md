# RFC-007 — Human-in-the-loop Research, Placement-Driven Curriculum & Coherence Cleanup

Status: **ACCEPTED — implemented** · Date: 2026-07-07
Canonical description: [`ARCHITECTURE.md`](../ARCHITECTURE.md). This RFC records the change.

## 0. Why
Two defects surfaced reviewing a real course: (1) research rested on the model's memory (the multi-round
"harness" was prose only; the engine merely checked a dossier *file existed*), and (2) the professor
pruned fundamentals by **assumption** ("you have a CS background"). A full audit then found coherence
debt (a live `gpa` bug, dead schema fields, a dual-canon docs conflict, stale cron prompts).

## 1. Research is human-in-the-loop; everything else is web-searched
- The professor **writes a deep-research prompt** to `Courses/<CODE>/research/PROMPT.md`, hands it to the
  owner to run in **Claude (Deep Research)**, and **pauses** until the cited report is uploaded to
  `Uploads/<CODE>/`. It never authors from memory. (Chosen over deploying `open_deep_research` — simpler,
  and Claude's deep research is strong.)
- For everything the report doesn't cover, the professor does **mandatory web search (Serper via
  `web-search-plus`)** and cites the URL.
- **Machine-enforced:** the `authored` gate (`hu-engine course validate`) now parses the dossier and
  requires **≥5 distinct source URLs + `confidence` tags + an "Open questions" section** — a from-memory
  dossier cannot pass. (Replaces the old size-only check.)

## 2. Full A–Z curriculum, then placement (never assume level)
- The professor builds the **complete curriculum starting from fundamentals** — early units are marked
  `foundational: true` — and **must not skip anything by assumption**.
- **Placement decides what to skip.** The learner self-reports or sits a rigorous placement exam per
  unit; a "yes" is verified at **≥ B** (the `Outcome.mastery_threshold`, now wired) before it counts.
  Passed outcomes are recorded via `grade add --source placement`.
- **Personalized track:** `hu-engine render-my-plan` writes `Courses/<CODE>/MyPlan.md` — the week-by-week
  plan with mastered units placed-out and weeks renumbered. The full course stays in `Syllabus.md`.

## 3. Coherence cleanup (same pass)
- **Bug:** `hu-engine gpa` no longer TypeErrors (passes `courses`; equal-weight when no `--state`).
- **Mastery bar unified at ≥ B:** `band_meets()` drives `mastered` (plan) and degree-progress, matching
  the promotion gate; `mastery_threshold` is honored.
- **Module-driven proof gate:** `hu-engine plan` returns the outcome's `gate`/`gate_args`; the Examiner
  uses those, not a hardcoded `leetcode`/username. Cron prompts de-personalized + course-agnostic.
- **Activation wired:** `hu-engine advance` advances the week and runs `activate_due_courses`.
- **Skills:** Registrar hands off to the Examiner; both call `hu-engine plan`; stale example course +
  "coding interview" framing removed; duplicate "pull first" de-duped; examiner uses `{{ENGINE}}` +
  `{{COURSES_DIR}}`.
- **Docs:** RFC-001 demoted to historical (resolving the dual-canon conflict with `ARCHITECTURE.md`);
  RFC-002/003 bannered; dead schema gate-fields pruned; deleted-course comments scrubbed.

## 4. Acceptance
`hu-engine gpa` runs; `course validate` rejects a memory dossier and accepts a cited one; a course
authored under this flow includes `foundational` units, pauses for the research report, and personalizes
`MyPlan.md` after placement. Full `pytest` green; `grep` for personal/stale course literals in
`engine/ skills/ courses/_TEMPLATE/ *.md` is clean.
