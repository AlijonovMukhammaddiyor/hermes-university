# RFC-004 — Faculty Handbook, Researched Professors & the Mastery Model

Status: **ACCEPTED — implementing** · Owner: the maintainer · Date: 2026-07-07
Supersedes the per-course-professor design in RFC-003. Builds on RFC-001/002/003.

## 0. The mission (owner's words, binding)
> A course must make the learner **truly one of the best in that field** — able to work with the best
> people. Beyond domain knowledge it must teach **how to be the best and how to keep evolving** in the
> field. Every course is authored by **deep, multi-source research** — **we do not trust the model's
> knowledge.** Nothing superficial or mediocre.

This makes three things first-class, for **every** course:
1. **Deep research** — verified, cited, primary-source; never the LLM's memory.
2. **A mastery model** — the excellence bar + how the best practice + the frontier + how to stay
   current + the signature work that earns a seat with the best. Not just topics: *how to become and
   remain excellent*.
3. **A researched professor** — the teaching character for the field is itself researched, as data.

## 1. What a "professor" is (the decomposition)
A great professor = **universal pedagogy** (domain-independent, encode once) + **domain teaching
character** (data, researched) + **the course** (data) + **the learner** (data, engine-owned) + the
model's reasoning at runtime. Per-course professor *skills* were the shared template + a name — an
accidental design. So:

- **Faculty Handbook** — ONE canonical `professor` skill: universal pedagogy + the authoring protocol
  + grading discipline. Improve it once; every course gets better. Never regenerated.
- **Professor is instantiated, not generated.** "Professor of CS400" = Faculty Handbook **bound to**
  CS400's module (syllabus + professor profile + mastery model) + the learner model, at runtime.
- **Creating a new course's professor = authoring data.** Zero code generation, zero redeploy, zero
  cron surgery. Exactly parallel to the syllabus. Specialized grading (LeetCode/Judge0/tools) stays in
  the engine's proof-gate layer, referenced by name in the module — no bespoke professor code, ever.

## 2. Deep-research mandate (we do not trust the LLM)
Authoring MUST perform genuine research with the real tools (`web-search-plus`, browser,
`read_extract`), not recall:
- **Fan-out** queries per research target (below); open **primary sources** (top-university course
  pages/OCW, expert talks/blogs, papers, practitioner write-ups, hiring rubrics).
- **Cross-verify** any non-obvious claim across ≥2 independent sources; drop what can't be corroborated.
- **Cite everything** in `courses/<CODE>/research/dossier.md` (title · url · why · what it corroborated).
- If a tool fails, **say so** and degrade to uploads + explicitly-flagged model knowledge — never fake it.

**Research targets (every course):** (a) canonical curriculum of the field; (b) the **excellence bar**
— what distinguishes the best / the hiring bar for top roles; (c) **expert practices** — how top people
actually work and practice; (d) the **frontier** — state of the art + trajectory; (e) **staying
current** — the people, communities, papers, feeds, conferences to keep evolving; (f) the **best
materials** per unit (regardless of cost).

## 3. Schema additions (`engine/course.py`) — additive, non-breaking
```python
class ProfessorProfile(BaseModel):
    persona: str                        # voice/character calibrated to the field + learner
    teaching_stance: str                # the pedagogical approach for this domain
    common_misconceptions: list[str] = []   # what trips learners; the professor preempts these
    assessment_philosophy: str = ""     # what "excellent" looks like + how to grade it rigorously
    hint_style: str | None = None

class MasteryModel(BaseModel):
    excellence_bar: str                 # what the best in this field can DO (the target to design back from)
    expert_practices: list[str] = []    # how top practitioners work/practice/think
    frontier: str = ""                  # state of the art + where the field is heading
    staying_current: list[Resource] = []# people/communities/papers/feeds/confs to keep evolving
    signature_work: str = ""            # the portfolio/reputation that earns a seat with the best
    deliberate_practice: str = ""       # the regimen to reach the bar
```
`Course` gains `professor_profile: ProfessorProfile | None` and `mastery_model: MasteryModel | None`.
All optional/defaulted → existing courses + tests still validate.

## 4. Raised `authored` gate (deterministic quality floor)
A course is `authored: true` only when it is genuinely deep, not a stub:
- `description` present; **every teaching unit has ≥1 resource**;
- `professor_profile` present; `mastery_model` present (`excellence_bar` + `staying_current` non-empty);
- a **research dossier exists** at `courses/<CODE>/research/dossier.md` (non-trivial).

`hu-engine course validate` reports `authored` on these; the autonomous authoring loop keeps working
until it's true. You cannot mark a course live by cutting corners.

## 5. Rendering (`engine/docs.py`)
Syllabus gains, up top: **"What the best in this field can do"** (excellence_bar), **"How this course
makes you one of them"** (units mapped back from the bar), **"How to keep evolving"** (frontier +
staying-current resources), and **"How this course is taught"** (professor profile: stance +
preempted misconceptions). Resources.md unchanged. Dossier is browsable in the vault.

## 6. Skill/plumbing changes
- Collapse N per-course professor skills → one `professor` (Faculty Handbook) skill; it reads the
  module it's told to teach. Retire `cs*-professor` on the droplet.
- `render_skills.py`: render `registrar`, `examiner`, `professor` (once).
- Crons (`uni-assign`, `uni-audit`): attach `registrar` + `professor`.
- Registrar handoff: "Professor — author/teach course `<CODE>`" (single skill, code as parameter).

## 7. Acceptance
Re-author **CS270** to the new bar: dossier with cross-verified sources covering all six research
targets; `professor_profile` + `mastery_model` populated; `authored: true` under the raised gate; the
syllabus renders the mastery sections. Then the same pipeline makes *any* future course this deep,
self-serve.

## 8. Risks & mitigations
- **Research shallow/hallucinated** → raised `authored` gate + dossier requirement + cross-verify rule
  + cite-or-drop; co-design review. If the model can't corroborate, it must say so.
- **Runtime research depth vs a dedicated harness** → mandate fan-out + primary sources + min coverage;
  the dossier makes depth auditable.
- **Schema churn** → all additions optional/defaulted; full test run before deploy.
- **One skill = single point of change** → that's the point (quality compounds); guard with tests.
