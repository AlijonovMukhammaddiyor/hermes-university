"""Deterministic Registrar operations — the state mutations the skills call (RFC §3, §5).

Every number here is computed from the grade log. Skills orchestrate (teach/assign/grade-to-rubric)
and call these; they never mutate GPA/standing/position/promotion themselves.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from . import gradebook as gb
from .gradebook import BAND_POINTS, GradeRecord
from .state import SemesterRecord, State

PASS_BAND_POINTS = BAND_POINTS["B"]  # promotion/midterm gate = >= B


def register_courses(state: State, course_dir: str | Path) -> list[str]:
    """Populate state.courses from the course modules under `course_dir` (RFC §6).
    Idempotent: updates existing entries, preserves progress fields (unit_index)."""
    from .course import load_course
    from .state import Course as StateCourse

    added: list[str] = []
    for path in sorted(Path(course_dir).glob("*/course.yaml")):
        if path.parent.name == "_TEMPLATE":
            continue
        c = load_course(path)
        first_unit = c.units[0].id if c.units else None
        active = c.active_default and (c.activates_week is None or
                                       state.position.week_in_semester >= c.activates_week)
        existing = state.courses.get(c.id)
        state.courses[c.id] = StateCourse(
            title=c.title, credits=c.credits, runs_in=c.runs_in,
            active=active if existing is None else existing.active,
            unit=existing.unit if existing else first_unit,
            unit_index=existing.unit_index if existing else 0,
            activates_week=c.activates_week,
        )
        if existing is None:
            added.append(c.id)
    return added


def catalog(course_dir: str | Path) -> list[dict]:
    """List AVAILABLE courses (the modules) — does not touch state. For the enrollment menu."""
    from .course import load_course

    out: list[dict] = []
    for path in sorted(Path(course_dir).glob("*/course.yaml")):
        if path.parent.name == "_TEMPLATE":
            continue
        c = load_course(path)
        out.append({"code": c.id, "title": c.title, "credits": c.credits,
                    "domain": c.subject_domain, "units": len(c.units),
                    "activates_week": c.activates_week, "north_star": c.north_star.strip()})
    return out


def enroll(state: State, course_dir: str | Path, code: str) -> str:
    """Enroll the learner in ONE course from the catalog. Returns 'enrolled' or 'already'.
    Active immediately unless the module is dormant-until-week (e.g. PD101 wk 9)."""
    from .course import load_course
    from .state import Course as StateCourse

    if code in state.courses:
        return "already"
    path = Path(course_dir) / code / "course.yaml"
    if not path.exists():
        raise KeyError(f"no course module {code!r} in the catalog")
    c = load_course(path)
    active = c.active_default and (c.activates_week is None or
                                   state.position.week_in_semester >= c.activates_week)
    state.courses[code] = StateCourse(
        title=c.title, credits=c.credits, runs_in=c.runs_in, active=active,
        unit=(c.units[0].id if c.units else None), unit_index=0,
        activates_week=c.activates_week)
    return "enrolled"


def drop(state: State, code: str) -> bool:
    """Un-enroll a course. Returns True if it was enrolled."""
    return state.courses.pop(code, None) is not None


def active_courses(state: State) -> list[str]:
    return [k for k, c in state.courses.items() if c.active]


def refresh(state: State, records: list[GradeRecord]) -> State:
    """Recompute semester + cumulative GPA and standing from the grade log."""
    sem = state.position.semester
    state.gpa.semester = gb.semester_gpa(records, sem)
    state.gpa.cumulative = gb.cumulative_gpa(records)
    state.standing = gb.standing_for(state.gpa.cumulative)
    return state


def record_day(state: State, today: str, all_done: bool) -> State:
    c, l, last = gb.update_streak(state.streak.current, state.streak.longest,
                                  state.streak.last_completed_date, today, all_done)
    state.streak.current, state.streak.longest, state.streak.last_completed_date = c, l, last
    return state


def activate_due_courses(state: State) -> list[str]:
    """Activate courses whose semester is current and whose activation week has arrived.
    Returns the list of course codes newly activated."""
    newly: list[str] = []
    for code, course in state.courses.items():
        if state.position.semester not in course.runs_in:
            course.active = False
            continue
        due = course.activates_week is None or state.position.week_in_semester >= course.activates_week
        if due and not course.active:
            course.active = True
            newly.append(code)
        elif due:
            course.active = True
    return newly


def band_passes(band: str) -> bool:
    return BAND_POINTS.get(band, 0.0) >= PASS_BAND_POINTS


def promote_or_graduate(state: State, finals_band: str, on: str,
                        records: list[GradeRecord]) -> tuple[State, str]:
    """Apply a semester-finals result. Returns (state, status) where status is one of
    'promoted', 'graduated', 'remediation'. Deterministic; the Examiner supplies the band."""
    sem = state.position.semester
    passed = band_passes(finals_band)
    state.history.append(SemesterRecord(
        semester=sem, gpa=gb.semester_gpa(records, sem),
        standing=gb.standing_for(gb.semester_gpa(records, sem)),
        finals_grade=finals_band, completed_on=on,
    ))
    key = f"s{sem}_finals"
    setattr(state.assessments, key, finals_band)
    if not passed:
        return state, "remediation"
    if sem < state.program.total_semesters:
        state.position.semester = sem + 1
        state.position.week_in_semester = 1
        state.position.phase = "depth" if sem + 1 == 2 else "foundations"
        state.gpa.semester = None
        # activate S2 courses
        for course in state.courses.values():
            course.active = (sem + 1) in course.runs_in and course.activates_week is None
        return state, "promoted"
    return state, "graduated"


def advance_week(state: State) -> State:
    state.position.week_in_semester += 1
    state.position.absolute_week += 1
    return state


def write_dashboard(vault: str | Path, state: State, today: str) -> None:
    """Write engine-precomputed rollups to frontmatter notes the Obsidian Dashboard displays.
    The dashboard only reads these — it never computes numbers (RFC §9)."""
    reg = Path(vault) / "Registrar"
    reg.mkdir(parents=True, exist_ok=True)
    status = (
        "---\n"
        "type: status\n"
        f"semester: {state.position.semester}\n"
        f"week: {state.position.week_in_semester}\n"
        f"gpa_semester: {state.gpa.semester if state.gpa.semester is not None else ''}\n"
        f"gpa_cumulative: {state.gpa.cumulative if state.gpa.cumulative is not None else ''}\n"
        f"standing: {state.standing}\n"
        f"streak: {state.streak.current}\n"
        f"updated: {today}\n"
        "---\n\n"
        f"# Status — {state.learner.name}\n"
    )
    (reg / "status.md").write_text(status)
    snap = (
        "---\n"
        "type: gpa_snapshot\n"
        f"date: {today}\n"
        f"gpa_cumulative: {state.gpa.cumulative if state.gpa.cumulative is not None else ''}\n"
        f"semester: {state.position.semester}\n"
        "---\n"
    )
    (reg / f"gpa-{today}.md").write_text(snap)


def load_state(vault: str | Path) -> State:
    return State.load(Path(vault) / "Registrar" / "state.json")


def save_state(vault: str | Path, state: State) -> None:
    state.save(Path(vault) / "Registrar" / "state.json")
