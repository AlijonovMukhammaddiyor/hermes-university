# RFC-006 — Ivy-Grade Syllabus (week-by-week, everything prepared)

Status: **ACCEPTED — implementing** · Date: 2026-07-07
Builds on RFC-004/005. Raises a course from a topic outline to a **fully-prepared, week-by-week
university syllabus** where every week's readings and deliverable are already assigned.

## 0. Why
A real Ivy syllabus is not a topic list — it's a **calendar**: week N → this focus, *these exact
readings* (ch. 3–4, Lectures 5–7), *this assignment due*. Our courses defined resources but only
grouped them per multi-week unit; nothing was divided across the weeks with work attached. The learner
wants **everything prepared** upfront: open the syllabus and know exactly what to read and do each week.

## 1. Schema — a per-week session plan
```python
class Session(BaseModel):
    week: int                       # week number within the course (1..N)
    focus: str                      # the week's theme / what you do
    readings: list[Resource] = []   # the EXACT readings for the week, with locators
    deliverable: str = ""           # the assignment/artifact produced that week
```
`Unit` gains `sessions: list[Session] = []`. The unit's `resources` remain the pool; `sessions` divide
them across the weeks and attach a concrete deliverable to each.

## 2. Raised `authored` gate
A course is `authored: true` only if — in addition to RFC-004 (description, unit resources, professor
profile, mastery model, dossier) — **every teaching unit has `sessions`** (i.e. the whole term is
planned week by week). No vague courses ship.

## 3. Rendering — the syllabus reads like a real course
`render_syllabus` gains a **"Week-by-week plan"** table (Markdown table — vault docs render it in
Obsidian/WebUI; the Telegram no-table rule is unaffected): `Week · Focus · Readings · Deliverable`,
rows across all units in week order. `Resources.md` stays the full library.

## 4. Authoring protocol — plan the calendar, present the file
- New step after the resource map: **divide the researched resources into a week-by-week plan** — for
  each week set `focus`, the exact `readings` (specific locators), and a `deliverable`.
- Co-design **sends the full `Syllabus.md` file** (`hermes send -f …`) — never a topic summary in
  chat — then asks 2–3 calibration questions. The learner sees the *prepared* syllabus first.

## 5. Acceptance
Re-author CS270: `authored: true` under the raised gate; `Syllabus.md` shows a Week-by-week table with
specific readings + deliverables for each of the ~10 weeks; the bot delivers the file, not a topic list.
GEN101 fixture updated with sessions so `git clone && pytest` stays green.
