"""Rendering layer — the *visible* university (RFC-002 §3).

Deterministic, read-only projections generated from the canonical data (course modules + state +
grade log) into human-readable Markdown the WebUI file-browser and Obsidian display, and the agent
can render on request. Numbers come from the engine; nothing here is hand-typed or LLM-invented.
"""

from __future__ import annotations

from pathlib import Path

from .course import Course, load_course
from .gradebook import GradeRecord, course_gpa, load_records
from .state import State

DEGREE_NAME = "B.S. Interview Readiness"


# ---------------------------------------------------------------- catalog
def render_catalog(courses: list[Course]) -> str:
    out = ["# 📚 Course Catalog — Hermes University", ""]
    for c in sorted(courses, key=lambda x: x.id):
        prereqs = ", ".join(c.prerequisites) if c.prerequisites else "none"
        out += [f"## {c.id} — {c.title}  ·  {c.credits} credits",
                f"*{c.north_star.strip()}*", "",
                f"- **Prerequisites:** {prereqs}",
                f"- **Units ({len(c.units)}):** " + " → ".join(u.title for u in c.units),
                f"- **Grading:** " + grading_line(c),
                f"- **Enroll:** reply `enroll {c.id}`", ""]
    return "\n".join(out).rstrip() + "\n"


def grading_line(c: Course) -> str:
    w = getattr(c, "grade_weights", None) or {}
    if not w:
        return "per syllabus"
    return " · ".join(f"{k} {int(round(v*100))}%" for k, v in w.items() if v)


# ---------------------------------------------------------------- syllabus
def render_syllabus(c: Course) -> str:
    out = [f"# {c.id} — {c.title}", "", f"> {c.north_star.strip()}", "",
           f"**Credits:** {c.credits}  ·  **Domain:** {c.subject_domain}  ·  "
           f"**Prereqs:** {', '.join(c.prerequisites) or 'none'}", ""]
    if c.enduring_understandings:
        out += ["## Enduring understandings"] + [f"- {e}" for e in c.enduring_understandings] + [""]
    out += ["## Grading policy", grading_line(c), "",
            "## Units & outcomes (the schedule)"]
    assess = {a.id: a for a in c.assessments}
    for u in sorted(c.units, key=lambda x: (x.semester, x.order_index)):
        out.append(f"\n### Sem {u.semester} · Unit {u.order_index}: {u.title}")
        for o in u.outcomes:
            a = assess.get(o.proof)
            proof = (a.proof_gate if a else "—")
            out.append(f"- **{o.bloom_level}** — {o.statement}")
            out.append(f"  - *proof:* {proof}")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- transcript
def _course_records(records: list[GradeRecord], code: str) -> list[GradeRecord]:
    return [r for r in records if r.course == code]


def render_transcript(state: State, records: list[GradeRecord]) -> str:
    out = [f"# 🎓 Transcript — {state.learner.name or ''}".rstrip(), "",
           f"**Standing:** {state.standing}  ·  **Semester GPA:** "
           f"{_fmt(state.gpa.semester)}  ·  **Cumulative GPA:** {_fmt(state.gpa.cumulative)}", ""]
    if not state.courses:
        return "\n".join(out) + "\n_Not enrolled in any course yet._\n"
    out += ["| Course | Credits | Records | Course GPA |", "|---|---|---|---|"]
    for code, c in sorted(state.courses.items()):
        recs = _course_records(records, code)
        cg = course_gpa(recs, getattr(c, "grade_weights", None) or {})
        out.append(f"| {code} — {c.title} | {c.credits} | {len(recs)} | {_fmt(cg)} |")
    if state.history:
        out += ["", "## Completed semesters"]
        for h in state.history:
            out.append(f"- Semester {h.semester}: finals {h.finals_grade}, GPA {_fmt(h.gpa)} "
                       f"({h.standing}) — {h.completed_on}")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- degree progress
def render_degree_progress(state: State, records: list[GradeRecord],
                           modules: dict[str, Course]) -> str:
    passed = {r.outcome for r in records if r.band != "F"}
    total = req = 0
    for code, c in state.courses.items():
        m = modules.get(code)
        if not m:
            continue
        outs = [o.id for o in m.all_outcomes()]
        total += len(outs)
        req += sum(1 for o in outs if o in passed)
    pct = int(round(100 * req / total)) if total else 0
    credits_enrolled = sum(c.credits for c in state.courses.values())
    out = [f"# 🧭 Degree Progress — {DEGREE_NAME}", "",
           f"**Requirement:** pass finals of both 3-month semesters (≥B).", "",
           f"**Outcomes mastered:** {req}/{total}  ({pct}%)",
           f"**Semester:** {state.position.semester}/{state.program.total_semesters} · "
           f"week {state.position.week_in_semester}/{state.program.weeks_per_semester}",
           f"**Credits enrolled:** {credits_enrolled}  ·  **Cumulative GPA:** "
           f"{_fmt(state.gpa.cumulative)}  ·  **Standing:** {state.standing}", ""]
    if state.degree.awarded_on:
        out.append(f"🏆 **Degree awarded {state.degree.awarded_on}.**")
    else:
        remaining = total - req
        out.append(f"**What's left:** {remaining} outcomes across your enrolled courses, then the "
                   f"semester finals (≥B) to promote/graduate.")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- schedule (calendar filled in P1)
def render_schedule(state: State) -> str:
    p = state.position
    return (f"# 🗓️ Academic Schedule\n\n"
            f"- **Program:** {state.program.total_semesters} semesters × "
            f"{state.program.weeks_per_semester} weeks\n"
            f"- **Started:** {state.program.started_on}\n"
            f"- **Now:** Semester {p.semester}, week {p.week_in_semester}\n"
            f"- **This semester:** biweekly exams (wk 2,4,8,10) · midterm wk 6 · finals wk 12\n")


# ---------------------------------------------------------------- orchestrator
def render_all(vault: str | Path, courses_dir: str | Path) -> list[str]:
    """(Re)generate every visible document. Returns the list of paths written."""
    vault, courses_dir = Path(vault), Path(courses_dir)
    modules = {c.id: c for c in
               (load_course(p) for p in sorted(courses_dir.glob("*/course.yaml"))
                if p.parent.name != "_TEMPLATE")}
    state = State.load(vault / "Registrar" / "state.json")
    records = load_records(vault / "records" / "grades.jsonl")

    written: list[str] = []

    def w(rel: str, text: str):
        path = vault / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        written.append(rel)

    w("Catalog.md", render_catalog(list(modules.values())))
    for code, m in modules.items():
        w(f"Courses/{code}/Syllabus.md", render_syllabus(m))
    w("Registrar/Transcript.md", render_transcript(state, records))
    w("Registrar/Schedule.md", render_schedule(state))
    enrolled_modules = {k: modules[k] for k in state.courses if k in modules}
    w("Registrar/DegreeProgress.md", render_degree_progress(state, records, enrolled_modules))
    return written


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:.2f}"
