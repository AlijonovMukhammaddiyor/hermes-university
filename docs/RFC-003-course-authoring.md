# RFC-003 — Research-Driven Course Authoring & World-Class Professors

Status: **HISTORICAL** — canonical description is [`ARCHITECTURE.md`](../ARCHITECTURE.md). Date: 2026-07-07
> Superseded where it disagrees with later RFCs: per-course professors → **one Faculty professor**
> (RFC-004); CS270/"4 seed courses" are gone → **empty catalog** (RFC-005); research is now
> **human-in-the-loop + placement-driven** (RFC-007). The research-as-data principle stands.

## 0. Why
Today a course is a static `course.yaml` I hand-authored, and its "syllabus" is a thin list of topics
+ proof gates. The learner asked for the one thing a real university does before anything else:
**design the course.** Course creation must become the single most important, most rigorous step —
a *world-class professor* who **researches the field deeply**, decides contents by **usefulness and
future prospects for this learner** (the learner's stated goal), and produces a **full university
syllabus with real materials** (specific textbooks/chapters, courses/lectures, papers, problem sets),
not just topic labels.

Decisions locked with the owner:
- **Self-serve System Professor** — the *runtime* Professor (on the droplet, with web-search +
  browser + extract tools) authors courses. We build the capability, not the content, so it's
  "perfect for any course" added later.
- **CS270 first**, end-to-end, as the reference course (anchored by the uploaded LLM book).
- **Best resource regardless of cost** — cite the single best resource even if paid (mark it).

Non-negotiables carried over: numbers are computed by code; **no outcome without a proof**; the course
module remains **data validated by the engine** — research authors it, the engine gates its structure.

## 1. The seam (where research meets determinism)
```
RESEARCH (Professor + web tools)  ──▶  a valid course.yaml  ──▶  engine VALIDATES  ──▶  rendered
  search · browse · extract · synthesize      (schema + resources)     (proof/DAG/rubric gate)   Syllabus.md
  calibrate to the learner's north star                                                          Resources.md
                         │                                                                            │
                         └────────────── co-design with the learner ──── approve ──── commit ────────┘
```
The Professor may write any prose it researches, but the **structure** (every outcome has a proof, the
prereq graph is acyclic, rubrics exist) is enforced by `engine/course.py` — unchanged rigor. Research
adds *content and materials*; it never bypasses the contract.

## 2. Course authoring pipeline (run by the Professor)
Invoked by the Registrar on `create course <goal>` (or the first enroll of a not-yet-authored course).

1. **Research** — with `web-search-plus` + browser + `read_extract`:
   - Map the field: canonical curricula (MIT/Stanford/CMU course pages, MIT OCW), standard textbooks,
     best courses/MOOCs, seminal + current papers, and the *industry bar* for the role.
   - **Future-prospects lens:** rank topics by ROI for the learner's north star; cut vanity topics.
   - Cache every source to `courses/<code>/research/dossier.md` (title · url · why it mattered) so the
     syllabus is transparent and reproducible. If web tools fail, **say so** and fall back to
     model-knowledge + uploaded materials — never silently pretend research happened.
2. **Design (backward)** — enduring understandings → measurable A-SMART outcomes (Bloom-tagged) →
   prereq DAG → unit sequence → assessments + rubrics → proof gates. One proof per outcome.
3. **Resource map** — for each unit, the **single best resource regardless of cost** (mark paid),
   mapped to a **specific locator** (e.g. "ch. 3–4", "Lectures 5–7"), plus why *this* one for *this*
   learner; add strong alternatives. Anchor the course to a `primary_text`.
4. **Co-design → approve → commit** — send the draft syllabus as a *file* (`hermes send -f`, never a
   Telegram table), take pacing/depth/interest adjustments, revise, validate, commit, register.

## 3. Schema additions (`engine/course.py`) — additive, non-breaking
```python
class Resource(BaseModel):
    type: Literal["textbook","course","paper","docs","video","problemset","reference"]
    title: str
    author: str | None = None
    url: str | None = None
    locator: str | None = None      # "ch. 3–4" | "Lectures 5–7" | "§2.1"
    why: str | None = None          # why THIS resource for THIS topic/learner
    tier: Literal["core","supplementary"] = "core"
    cost: Literal["free","paid"] = "free"
```
- `Course` gains: `description: str = ""`, `primary_text: Resource | None`,
  `resources: list[Resource] = []` (course-level library).
- `Unit` gains: `summary: str | None`, `resources: list[Resource] = []` (unit reading list),
  `est_weeks: int = 1` (schedule span).
- **All optional/defaulted** → existing 4 courses and every current test still validate. The
  *quality bar* (resources REQUIRED, research done) is enforced by the **authoring protocol**, not by
  breaking the schema. New optional validator warning if a unit has zero resources — non-fatal.

## 4. Engine CLI addition
- `hu-engine course validate --file courses/<code>/course.yaml` → `ok` or the exact validation error.
  This is the **structural gate** the runtime Professor calls to self-check its authored YAML before
  commit; it loops until valid. No new numbers, no state writes.

## 5. Rendering (`engine/docs.py`)
- `render_syllabus` → a real syllabus: description · credits/domain/prereqs · enduring understandings ·
  **primary text + course library** · **weekly schedule** (unit → week range via `term_calendar` +
  `est_weeks`) · per-unit summary + outcomes + **readings** + proof · assessment plan · grading policy.
- New `render_resources` → `Courses/<code>/Resources.md`: the curated library grouped by unit
  (title · locator · why · tier · cost + link). `render_all` writes it per course.
- Catalog gains a one-line description + the anchoring text.
- (Vault docs may use Markdown tables — Obsidian/WebUI render them. Telegram messages may **not**;
  that rule lives in the registrar skill, per the table-banner incident.)

## 6. The world-class Professor (`skills/professor.template.md`)
Add, above teaching: an **Authoring protocol** section = §2 above, with a hard research mandate, the
resource-curation standard (best-regardless-of-cost, specific locators, calibrated to the north star),
the emit-valid-YAML + `course validate` loop, and the co-design/commit steps. Teaching method stays.

## 7. Authoring flow in the Registrar (`skills/registrar.template.md`)
New verbs, backed by the Professor:
- **`create course <goal>`** — Registrar assigns a code, hands the goal to the owning Professor to run
  the pipeline, presents the draft syllabus file for co-design, and on approval commits + adds to the
  catalog.
- First **`enroll <CODE>`** of a not-yet-authored code triggers authoring first, then placement.

## 8. Reference course & acceptance
The **system** (runtime Professor) authors **CS270** end-to-end with real research, anchored by
`Uploads/CS270/`. Acceptance: `course validate` passes; `Syllabus.md` + `Resources.md` render with a
weekly schedule and per-unit best-in-class materials with locators; a cached `research/dossier.md`
exists; the owner reviews and approves. Then the same pipeline is available for any future course.

## 9. Risks & mitigations
- **Runtime research variance** → strong protocol + engine `validate` gate + co-design approval +
  cached dossier for audit.
- **Web-tool failure / rate limits (Serper/Brave)** → cache; degrade to model + uploads and say so.
- **Professor emits invalid YAML** → `course validate` loop before commit.
- **Link rot / paywall** → mark `cost`/`tier`; prefer durable when quality is equal.
- **Schema churn** → every field optional/defaulted; full test run before deploy.
```
```
