"""Deterministic Registrar operations — the state mutations the skills call (RFC §3, §5).

Every number here is computed from the grade log. Skills orchestrate (teach/assign/grade-to-rubric)
and call these; they never mutate GPA/standing/position/promotion themselves.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from . import gradebook as gb
from .gradebook import BAND_POINTS, GradeRecord
from .state import EnrollmentRecord, SemesterRecord, State

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
        from .authoring import authored_report
        c = load_course(path)
        first_unit = c.units[0].id if c.units else None
        active = c.active_default and (c.activates_week is None or
                                       state.position.week_in_semester >= c.activates_week)
        existing = state.courses.get(c.id)
        status = (existing.status if existing else
                  ("placement" if authored_report(c, path.parent)["authored"] else "researching"))
        state.courses[c.id] = StateCourse(
            title=c.title, credits=c.credits, runs_in=c.runs_in,
            active=active if existing is None else existing.active,
            unit=existing.unit if existing else first_unit,
            unit_index=existing.unit_index if existing else 0,
            activates_week=c.activates_week, grade_weights=c.grade_weights,
            status=status, archived_on=existing.archived_on if existing else None,
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


class EnrollError(Exception):
    """Registration refused (prereq / credit-load / hold)."""


def enroll(state: State, course_dir: str | Path, code: str, today: str | None = None) -> str:
    """Enroll in ONE course, enforcing registrar rules (RFC-002 §4). Returns 'enrolled'/'already'.
    Raises EnrollError with a human reason on prereq/credit-load/hold violations."""
    from .course import load_course
    from .state import Course as StateCourse

    if code in state.courses:
        return "already"
    path = Path(course_dir) / code / "course.yaml"
    if not path.exists():
        raise KeyError(f"no course module {code!r} in the catalog")
    c = load_course(path)

    if state.hold:
        raise EnrollError(f"enrollment is on hold ({state.hold}); clear it before adding courses")
    for pre in c.prerequisites:                     # prereq must already be enrolled
        if pre not in state.courses:
            raise EnrollError(f"{code} requires {pre} first — enroll in {pre} before {code}")
    load = sum(sc.credits for sc in state.courses.values() if sc.active) + c.credits
    if load > state.enrollment.credit_cap:
        raise EnrollError(f"credit load {load} exceeds cap {state.enrollment.credit_cap}; "
                          f"drop a course before adding {code}")

    active = c.active_default and (c.activates_week is None or
                                   state.position.week_in_semester >= c.activates_week)
    from .authoring import authored_report
    status = "placement" if authored_report(c, path.parent)["authored"] else "researching"
    state.courses[code] = StateCourse(
        title=c.title, credits=c.credits, runs_in=c.runs_in, active=active,
        unit=(c.units[0].id if c.units else None), unit_index=0,
        activates_week=c.activates_week, grade_weights=c.grade_weights, enrolled_on=today,
        status=status)
    state.enrollment.records.append(EnrollmentRecord(code=code, enrolled_on=today or ""))
    return "enrolled"


def refresh_course_status(state: State, course_dir: str | Path, uploads_dir: str | Path,
                          code: str) -> str | None:
    """Re-derive a course's authoring-phase status from the filesystem (RFC-009). Only advances a
    course still in the authoring pipeline (researching/authoring/placement) — never overrides a
    live 'active' or an 'archived' course. Returns the new status, or None if unchanged/absent."""
    from .authoring import authoring_status
    sc = state.courses.get(code)
    if sc is None or sc.status not in ("researching", "authoring", "placement"):
        return None
    new = authoring_status(Path(course_dir) / code / "course.yaml", uploads_dir, code)
    if new != sc.status:
        sc.status = new
        return new
    return None


def activate_course(state: State, code: str) -> bool:
    """Placement done → the course goes live (RFC-009). Returns True if it transitioned."""
    sc = state.courses.get(code)
    if sc and sc.status in ("placement", "authoring"):
        sc.status = "active"
        sc.active = True
        return True
    return False


def archive(state: State, code: str, today: str | None = None) -> bool:
    """Soft-drop: keep the record + files, hide from active views, reversible (RFC-009).
    Returns True if the course was enrolled and not already archived."""
    sc = state.courses.get(code)
    if sc is None or sc.status == "archived":
        return False
    sc.status = "archived"
    sc.active = False
    sc.archived_on = today
    for rec in state.enrollment.records:                 # close the audit record (dropped_on)
        if rec.code == code and rec.dropped_on is None:
            rec.dropped_on = today or ""
    return True


def restore(state: State, course_dir: str | Path, uploads_dir: str | Path, code: str,
            today: str | None = None) -> bool:
    """Un-archive: re-derive the course's authoring status from the filesystem (RFC-009).
    Returns True if it was archived and is now restored."""
    from .authoring import authoring_status
    sc = state.courses.get(code)
    if sc is None or sc.status != "archived":
        return False
    sc.archived_on = None
    sc.status = authoring_status(Path(course_dir) / code / "course.yaml", uploads_dir, code)
    state.enrollment.records.append(EnrollmentRecord(code=code, enrolled_on=today or ""))
    return True


def drop(state: State, code: str, today: str | None = None) -> bool:
    """Back-compat alias — a drop is a soft archive (RFC-009), not a hard delete."""
    return archive(state, code, today)


def delete(state: State, code: str) -> bool:
    """Remove a course from state entirely (hard delete; the CLI also removes the files)."""
    return state.courses.pop(code, None) is not None


def active_courses(state: State) -> list[str]:
    return [k for k, c in state.courses.items() if c.active]


def refresh(state: State, records: list[GradeRecord]) -> State:
    """Recompute semester + cumulative GPA and standing from the grade log."""
    sem = state.position.semester
    state.gpa.semester = gb.semester_gpa(records, state.courses, sem)
    state.gpa.cumulative = gb.cumulative_gpa(records, state.courses)
    state.standing = gb.standing_for(state.gpa.cumulative)
    # standing consequence: probation places a hold (no new material); recovery clears it
    if state.standing == "probation":
        state.hold = "probation"
    elif state.hold == "probation":
        state.hold = None
    return state


def persist_learner_model(vault: str | Path, records: list[GradeRecord], tz: str,
                          now) -> None:
    """Recompute the Learner Model from the grade log and write records/learner_model.json
    (RFC-002 §2.5). Mastery/proficiency live here; per-card FSRS review state lives in Anki."""
    from .learner_model import LearnerModel, recompute
    p = Path(vault) / "records" / "learner_model.json"
    existing = LearnerModel.model_validate_json(p.read_text()) if p.exists() else LearnerModel()
    recompute(existing, records, tz=tz, now=now)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(existing.model_dump_json(indent=1) + "\n")


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
    sem_gpa = gb.semester_gpa(records, state.courses, sem)
    state.history.append(SemesterRecord(
        semester=sem, gpa=sem_gpa, standing=gb.standing_for(sem_gpa),
        finals_grade=finals_band, completed_on=on,
    ))
    if sem >= state.program.total_semesters and passed:
        state.degree.awarded_on = on             # graduation awards the degree
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
