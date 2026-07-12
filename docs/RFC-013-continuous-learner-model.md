# RFC-013 — Continuous Learner Model (learn the learner, 24/7)

**Status:** Proposed (awaiting review before any schema change) · **Builds on:** RFC-002 §4.4 Learner
Model, RFC-012 integrations

## Problem
The system personalizes off a real **Learner Model** (`engine/learner_model.py`), but it learns from a
single signal — **graded work and its timestamps** — and only updates on grade events. So it knows what
you're good at, your misconceptions, and roughly when you study, but it never learns from the signals it
already produces every day: your **chat** with the bot, whether you actually **did the booked calendar
blocks**, or how **long tasks take**. The objective is that it learns you *in every learning-relevant
aspect, continuously* — while staying an honest, correctable picture, not a hidden dossier.

The schema already anticipated this: `LearnerModel.prefs` and `.goals` exist as empty placeholders
(`learner_model.py:53-54`). This RFC fills them, on a controlled contract.

## Signals (grades is here today; the other three are new)
| Signal | Learns | Source |
|---|---|---|
| **Grades** *(have)* | proficiency, mastery, misconceptions, difficulty ceiling | grade log → `recompute()` |
| **Chat preferences** | format (worked-examples vs lecture), energy, constraints, interests, motivation | the LLM records structured observations from Telegram |
| **Calendar adherence** | real energy windows, realistic capacity, procrastination | did/moved/skipped booked blocks (google-calendar, RFC-012) |
| **Task timing** | reading speed, difficulty calibration, over/under-load | booked-block duration vs. completion |

## Schema
One typed `Observation`, and three bounded stores on `LearnerModel` (plus adherence-refined routine/pace).

```python
class Observation(BaseModel):
    aspect: str        # format | energy_window | constraint | interest | motivation | pace  (controlled)
    value: str         # "prefers worked examples over lectures"
    evidence: str      # "said so 2026-07-12" · "skipped 4 of 5 morning blocks"
    confidence: float  # 0..1 — decays without reinforcement
    source: str        # chat | calendar | timing | grades
    first_seen: str
    last_seen: str

# on LearnerModel:
preferences: dict[str, Observation]   # keyed by aspect (latest wins, conflicts resolved on confidence)
constraints: list[Observation]        # hard limits (no mornings, ≤1h/day)
interests:   list[Observation]        # what engages you
# Routine/Pace gain adherence-derived fields (energy_by_slot, realistic_task_cap)
```

**Controlled vocabulary** (the `aspect` enum) is the guardrail against free-form surveillance: the LLM
must map what it hears to a learning-relevant aspect, or not record it.

## Continuous update + decay
- **Event-driven:** grades → `recompute()` (today); chat → `learner observe`; calendar sync → an
  adherence pass; task done → timing captured.
- **Nightly consolidation** (`uni-learn` cron, or folded into the audit): recompute grade aggregates,
  **decay** every observation (`confidence *= d^days_since_last_seen`, drop below a floor), merge
  duplicates, resolve conflicts (highest current confidence wins).
- Decay is why it's *continuous, not cumulative* — a current picture that forgets what's no longer true.
  It's both the UX property (stays right) and half the privacy story.

## How it's written + read
- **Write (LLM, bounded):** `hu-engine learner observe --aspect format --value "…" --evidence "…"
  --source chat [--confidence 0.6]`. Skills call it when you state or reveal a preference. Invalid aspect
  → rejected.
- **Read (personalize everything):** Registrar schedules at your real energy windows, honors constraints,
  sizes to realistic pace. Professor teaches in your preferred format, grounds examples in your interests,
  tunes tone to what motivates you. One file, one query API — no surface invents its own idea of you.

## Privacy & transparency (firm — a hidden permanent dossier is out of scope)
- **You can see all of it.** A `LearnerModel.md` surface (and a Home section) — "What I've learned about
  you," grouped by aspect with the evidence and confidence behind each belief.
- **You can correct/delete it.** Tell the bot "that's wrong, I prefer X" (→ overwrites) or `learner
  forget --aspect …`; a full `learner reset`. The visible surface is also the safety net for a bad
  LLM extraction.
- **It forgets.** Decay above; nothing is kept forever.
- **Bounded + private.** Learning-relevant aspects only (documented *what it does not track*). Lives in
  your **private vault** (`records/learner_model.json`) — versioned there for undo, **never** in the
  public code repo.

## Plan (phased; each lands behind the gates, TDD)
- **A — foundation:** `Observation` + the three stores; `learner observe` / `forget` / `reset` CLI;
  `render_learner_model` visible surface + Home section; decay in a consolidation function. *(No behavior
  change until signals feed it — safe to land first.)*
- **B — signals:** chat-observation prompts in the skills; a calendar-adherence pass → observations;
  task-timing capture at `done`.
- **C — close the loop:** the `uni-learn` consolidation cron; skills read the new fields to personalize
  format/timing/tone; measure that scheduling + teaching actually shift.

## Not in scope
Sentiment tracking beyond stated energy, anything off-platform, and any belief the learner can't see and
override. If it can't be shown on `LearnerModel.md`, it isn't recorded.
