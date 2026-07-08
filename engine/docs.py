"""Rendering layer — the *visible* university (RFC-002 §3).

Deterministic, read-only projections generated from the canonical data (course modules + state +
grade log) into human-readable Markdown the WebUI file-browser and Obsidian display, and the agent
can render on request. Numbers come from the engine; nothing here is hand-typed or LLM-invented.
"""

from __future__ import annotations

from pathlib import Path

from .course import Course, load_course
from .gradebook import GradeRecord, band_meets, course_gpa, load_records
from .state import State


# ---------------------------------------------------------------- catalog
def render_catalog(courses: list[Course]) -> str:
    out = ["# 📚 Course Catalog", "",
           "> [!tip] Add or start a course",
           "> Message the bot **`create course <goal>`** to research + build a new one, or "
           "**`enroll <name>`** to begin one below.", ""]
    if not courses:
        out += ["> [!note] Your catalog is empty",
                "> Nothing here yet — say **`create course <your goal>`** and it builds one for you."]
        return "\n".join(out).rstrip() + "\n"
    out += ["| Course | Credits | You'll be able to… | Units | Enroll |",
            "|---|---|---|---|---|"]
    for c in sorted(courses, key=lambda x: x.id):
        goal = _cell(c.north_star.strip().rstrip("."))
        out.append(f"| **{c.title}** | {c.credits} | {goal} | {len(c.units)} | `enroll {c.id}` |")
    return "\n".join(out).rstrip() + "\n"


def grading_line(c: Course) -> str:
    w = getattr(c, "grade_weights", None) or {}
    if not w:
        return "per syllabus"
    return " · ".join(f"{k} {int(round(v*100))}%" for k, v in w.items() if v)


def _res_line(r) -> str:
    """One Markdown bullet for a Resource (single line so it nests cleanly under readings)."""
    head = f"**{r.title}**"
    if r.author:
        head += f" · {r.author}"
    if r.locator:
        head += f" — {r.locator}"
    tags = r.type + (", paid" if getattr(r, "cost", "free") == "paid" else "")
    head += f" _({tags})_"
    if r.url:
        head += f" — {r.url}"
    if r.why:
        head += f"  · _{r.why}_"
    return "- " + head


def _cell(s: str) -> str:
    return (s or "").replace("|", "/").replace("\n", " ").strip()


def _unit_spans(c) -> dict[str, tuple[int, int, int]]:
    """The one calendar spine (RFC-006): unit.id -> (semester, start_week, end_week), from est_weeks
    accumulated per semester. Both the week-by-week table and the Units section read this, so they
    can never disagree."""
    spans: dict[str, tuple[int, int, int]] = {}
    cursor: dict[int, int] = {}
    for u in sorted(c.units, key=lambda x: (x.semester, x.order_index)):
        start = cursor.get(u.semester, 1)
        end = start + max(1, getattr(u, "est_weeks", 1)) - 1
        cursor[u.semester] = end + 1
        spans[u.id] = (u.semester, start, end)
    return spans


def _assessment_marks(c) -> dict[tuple[int, int], str]:
    """The assessment calendar (RFC-009): which (semester, week) carries a quiz/midterm/finals. Derived
    from the unit spine + semester length so it always lines up with the week-by-week plan and matches
    what the Examiner administers — a quiz at each unit's end, a midterm mid-semester, finals last week."""
    spans = _unit_spans(c)
    marks: dict[tuple[int, int], str] = {}
    by_sem: dict[int, list[int]] = {}
    for sem, _start, end in spans.values():
        by_sem.setdefault(sem, []).append(end)
        marks[(sem, end)] = "📝 Unit quiz"
    for sem, ends in by_sem.items():
        sem_end = max(ends)
        # midterm at the UNIT boundary nearest the semester mid-point (after a completed unit — never
        # mid-unit), never the final week; falls back to the mid-point if there's only one unit
        inner = [e for e in sorted(set(ends)) if e < sem_end]
        mid = min(inner, key=lambda e: abs(e - sem_end / 2)) if inner else max(1, (sem_end + 1) // 2)
        marks[(sem, mid)] = "🎯 Midterm exam"                          # overrides that unit's quiz
        marks[(sem, sem_end)] = "🏁 Finals"                            # last week of the semester
    return marks


def _grading_section(c) -> list[str]:
    """Full grading breakdown + how assessment works — so the syllabus is a complete academic plan."""
    labels = {"hw": "Assignments (take-home)", "quiz": "Quizzes", "exam": "Unit exams",
              "midterm": "Midterm", "finals": "Finals"}
    w = getattr(c, "grade_weights", None) or {}
    if not w:
        return []
    parts = [f"**{labels.get(k, k.title())}** {int(round(v * 100))}%" for k, v in w.items() if v]
    return ["## Assessment & grading", " · ".join(parts), "",
            "How it works: every week ships a **take-home assignment** (the deliverable in the plan "
            "below). Each unit closes with a **quiz**; there's a **midterm** at the semester mid-point "
            "and **finals** in the last week. Every graded item maps to an outcome and is scored "
            "against its rubric — no grade without a proof.", ""]


def _week_plan_table(c) -> list[str]:
    """Ivy-grade week-by-week academic calendar (RFC-006/009): Week · Focus · Readings · Assignment
    (take-home) · Assessment (quiz/midterm/finals slots). Absolute weeks come from the same spine as
    the Units section (_unit_spans), so everything lines up. Markdown table — Obsidian renders it."""
    spans = _unit_spans(c)
    marks = _assessment_marks(c)
    rows = []
    for u in sorted(c.units, key=lambda x: (x.semester, x.order_index)):
        sem, start, _ = spans[u.id]
        for i, s in enumerate(sorted(getattr(u, "sessions", []) or [], key=lambda s: s.week)):
            reads = "; ".join(
                _cell(r.title + (f" {r.locator}" if r.locator else "")) for r in s.readings) or "—"
            wk = start + i
            rows.append((sem, wk, _cell(s.focus), reads, _cell(s.deliverable) or "—",
                         marks.get((sem, wk), "—")))
    if not rows:
        return []
    covered = {(sem, wk) for sem, wk, *_ in rows}      # show exam weeks even without a weekly session
    for (sem, wk), label in marks.items():
        if (sem, wk) not in covered:
            rows.append((sem, wk, "Assessment week", "—", "—", label))
    out = ["## Week-by-week plan", "",
           "| Week | Focus | Readings | Assignment (take-home) | Assessment |",
           "|---|---|---|---|---|"]
    for sem, wk, focus, reads, deliv, assess in sorted(rows, key=lambda r: (r[0], r[1])):
        out.append(f"| S{sem} W{wk} | {focus} | {reads} | {deliv} | {assess} |")
    return out + [""]


# ---------------------------------------------------------------- syllabus
def render_syllabus(c: Course) -> str:
    out = [f"# {c.id} — {c.title}", "", f"> {c.north_star.strip()}", ""]
    if getattr(c, "description", ""):
        out += [c.description.strip(), ""]
    out += [f"**Credits:** {c.credits}  ·  **Domain:** {c.subject_domain}  ·  "
            f"**Prereqs:** {', '.join(c.prerequisites) or 'none'}", ""]
    aud = getattr(c, "audience", None)
    if aud and (aud.good_fit or aud.not_a_fit):
        out += ["## Who this course is for"] + [f"- {x}" for x in aud.good_fit]
        if aud.not_a_fit:
            out += ["", "**Not for — look elsewhere if:**"] + [f"- {x}" for x in aud.not_a_fit]
        out += [""]
    if getattr(c, "primary_text", None):
        out += ["## Primary text", _res_line(c.primary_text), ""]
    mm = getattr(c, "mastery_model", None)
    if mm:
        out += ["## What the best in this field can do", mm.excellence_bar.strip(), ""]
        if mm.expert_practices:
            out += ["**How the best practice:**"] + [f"- {p}" for p in mm.expert_practices] + [""]
        if mm.signature_work:
            out += [f"**Signature work that earns a seat with the best:** {mm.signature_work.strip()}", ""]
        if mm.frontier or mm.staying_current:
            out += ["## How to keep evolving"]
            if mm.frontier:
                out += [mm.frontier.strip(), ""]
            if mm.staying_current:
                out += [_res_line(r) for r in mm.staying_current] + [""]
        if mm.deliberate_practice:
            out += [f"**Deliberate-practice regimen:** {mm.deliberate_practice.strip()}", ""]
    pp = getattr(c, "professor_profile", None)
    if pp:
        out += ["## How this course is taught", f"*{pp.teaching_stance.strip()}*", ""]
        if pp.common_misconceptions:
            out += ["**Misconceptions the professor preempts:**"] + \
                   [f"- {m}" for m in pp.common_misconceptions] + [""]
    if c.enduring_understandings:
        out += ["## Enduring understandings"] + [f"- {e}" for e in c.enduring_understandings] + [""]
    out += _grading_section(c)
    out += _week_plan_table(c)
    out += ["## Units, outcomes & proofs"]
    assess = {a.id: a for a in c.assessments}
    spans = _unit_spans(c)
    for u in sorted(c.units, key=lambda x: (x.semester, x.order_index)):
        _, start, end = spans[u.id]
        span = f"Week {start}" if start == end else f"Weeks {start}–{end}"
        out.append(f"\n### Sem {u.semester} · {span} · {u.title}")
        if getattr(u, "summary", None):
            out.append(f"_{u.summary.strip()}_")
        for o in u.outcomes:
            a = assess.get(o.proof)
            proof = (a.proof_gate if a else "—")
            out.append(f"- **{o.bloom_level}** — {o.statement}")
            out.append(f"  - *proof:* {proof}")
        if getattr(u, "resources", None):
            out.append("- *readings:*")
            for r in u.resources:
                out.append("  " + _res_line(r))
    if getattr(c, "resources", None):
        out += ["", "## Course library"] + [_res_line(r) for r in c.resources]
    out += ["", "## Assessment plan"]
    for a in c.assessments:
        out.append(f"- **{a.id}** ({a.type}, {a.modality}, ≥{a.bloom_target}) — {a.proof_gate}")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- resources (curated library)
def render_resources(c: Course) -> str:
    out = [f"# 📖 Resources — {c.id} {c.title}", ""]
    if getattr(c, "primary_text", None):
        out += ["## Primary text", _res_line(c.primary_text), ""]
    if getattr(c, "resources", None):
        out += ["## Course library"] + [_res_line(r) for r in c.resources] + [""]
    out += ["## By unit"]
    for u in sorted(c.units, key=lambda x: (x.semester, x.order_index)):
        out.append(f"\n### Sem {u.semester} · {u.title}")
        if getattr(u, "resources", None):
            out += [_res_line(r) for r in u.resources]
        else:
            out.append("_(no unit-specific resources yet)_")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- personalized plan (RFC-007)
def render_my_plan(c: Course, mastered: set[str]) -> str:
    """The learner's personalized track: placed-out units (all outcomes mastered) are skipped and the
    remaining weeks are renumbered. The canonical full A–Z course stays in Syllabus.md."""
    placed, rows, week = [], [], 1
    for u in sorted(c.units, key=lambda x: (x.semester, x.order_index)):
        outs = [o.id for o in u.outcomes]
        if outs and all(o in mastered for o in outs):
            placed.append(u.title)
            continue
        for s in (getattr(u, "sessions", []) or []):
            reads = "; ".join(
                _cell(r.title + (f" {r.locator}" if r.locator else "")) for r in s.readings) or "—"
            rows.append((week, _cell(u.title), _cell(s.focus), reads, _cell(s.deliverable) or "—"))
            week += 1
    out = [f"# 🎯 My Plan — {c.id} · {c.title}", "",
           "Your personalized track — placed-out units skipped, weeks renumbered. "
           "The full A–Z course is in `Syllabus.md`.", ""]
    if placed:
        out += ["**Placed out (tested):** " + ", ".join(placed), ""]
    if rows:
        out += ["| Week | Unit | Focus | Readings | Deliverable |", "|---|---|---|---|---|"]
        out += [f"| {w} | {unit} | {focus} | {reads} | {deliv} |"
                for w, unit, focus, reads, deliv in rows]
    else:
        out += ["_All units placed out — nothing left to schedule._"]
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
    # an outcome counts as achieved only at its mastery threshold (default ≥B), matching promotion
    thr = {o.id: o.mastery_threshold for m in modules.values() for o in m.all_outcomes()}
    passed = {r.outcome for r in records if band_meets(r.band, thr.get(r.outcome, 0.8))}
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
    out = [f"# 🧭 Degree Progress — {state.degree.name}", "",
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


# ---------------------------------------------------------------- schedule (academic calendar)
def term_calendar(started_on: str | None, total_semesters: int, wps: int) -> dict:
    """Key dates per semester derived from the start date. Week N of semester S begins
    `started_on + ((S-1)*wps + (N-1))` weeks."""
    from datetime import date, timedelta
    if not started_on:
        return {}
    start = date.fromisoformat(started_on)

    def wk(sem: int, w: int) -> str:
        return (start + timedelta(weeks=(sem - 1) * wps + (w - 1))).isoformat()

    cal = {}
    for s in range(1, total_semesters + 1):
        cal[s] = {"start": wk(s, 1), "add_drop_deadline": wk(s, 2),
                  "midterm": wk(s, 6), "finals": wk(s, wps)}
    cal["graduation"] = (start + timedelta(weeks=total_semesters * wps)).isoformat()
    return cal


def render_schedule(state: State) -> str:
    p, pr = state.position, state.program
    cal = term_calendar(pr.started_on, pr.total_semesters, pr.weeks_per_semester)
    out = ["# 🗓️ Academic Schedule", "",
           f"- **Program:** {pr.total_semesters} semesters × {pr.weeks_per_semester} weeks "
           f"· started {pr.started_on}",
           f"- **Now:** Semester {p.semester}, week {p.week_in_semester}", ""]
    for s in range(1, pr.total_semesters + 1):
        c = cal.get(s, {})
        out += [f"## Semester {s}",
                f"- Term start: {c.get('start','?')}  ·  Add/drop deadline: {c.get('add_drop_deadline','?')}",
                f"- Midterm (wk 6): {c.get('midterm','?')}  ·  **Finals (wk {pr.weeks_per_semester}): {c.get('finals','?')}**",
                f"- Cadence: biweekly unit exams (wk 2,4,8,10), quiz on other Sundays", ""]
    out.append(f"🎓 **Projected graduation:** {cal.get('graduation','?')}")
    return "\n".join(out).rstrip() + "\n"


def render_diploma(state: State) -> str:
    d = state.degree
    return (f"# 🎓 Diploma\n\n"
            f"This certifies that **{state.learner.name or 'the learner'}** has completed\n\n"
            f"## {d.name}\n\n"
            f"- **Requirement met:** {d.requirement}\n"
            f"- **Cumulative GPA:** {_fmt(state.gpa.cumulative)}\n"
            f"- **Awarded:** {d.awarded_on}\n\n"
            f"Congratulations. 🎉\n")


# ---------------------------------------------------------------- control center (RFC-009)
_STATUS_BADGE = {
    "draft": "📝 draft",
    "researching": "🔬 researching — waiting on you",
    "authoring": "✍️ authoring",
    "placement": "🎯 placement",
    "active": "🟢 active",
    "archived": "🗄️ archived",
}


def status_snapshot(vault: str | Path, courses_dir: str | Path, now=None) -> dict:
    """The one aggregate every surface reads (RFC-009): standing/GPA/streak, each course + lifecycle
    status + mastery %, today's board items, what's blocked on the learner, and SRS counts. Pure
    reaggregation of engine truth — no number is invented here."""
    from datetime import datetime, timezone

    from . import board as B
    from . import srs as S
    vault, courses_dir = Path(vault), Path(courses_dir)
    modules = {c.id: c for c in
               (load_course(p) for p in sorted(courses_dir.glob("*/course.yaml"))
                if p.parent.name != "_TEMPLATE")}
    state = State.load(vault / "Registrar" / "state.json")
    records = load_records(vault / "records" / "grades.jsonl")
    thr = {o.id: o.mastery_threshold for m in modules.values() for o in m.all_outcomes()}
    passed = {r.outcome for r in records if band_meets(r.band, thr.get(r.outcome, 0.8))}

    courses = []
    for code, sc in state.courses.items():
        outs = [o.id for o in modules[code].all_outcomes()] if code in modules else []
        pct = int(round(100 * sum(1 for o in outs if o in passed) / len(outs))) if outs else 0
        courses.append({"code": code, "title": sc.title, "status": sc.status,
                        "active": sc.active, "mastery_pct": pct})

    bpath = vault / "Board.md"
    cols = B.parse_board(bpath.read_text()) if bpath.exists() else {}
    today = [c.title for c in cols.get("Today", [])]
    blocked = []
    for c in courses:
        if c["status"] == "researching":
            blocked.append({"code": c["code"], "title": c["title"],
                            "reason": "waiting for your research report"})
    for card in cols.get("Proof Pending", []):
        blocked.append({"code": card.course, "title": card.title, "reason": "proof needs rework"})
    if state.hold:
        blocked.append({"code": None, "title": None, "reason": f"hold: {state.hold}"})

    # review-back (RFC-009 §5): outcomes that lapsed in Anki → surface for review (transcript stands)
    o2c = {o.id: (code, o.statement) for code, m in modules.items() for o in m.all_outcomes()}
    review = [{"outcome": oid, "course": o2c.get(oid, (None, None))[0],
               "statement": o2c.get(oid, (None, None))[1]} for oid in S.review_due(vault)]

    return {"learner": state.learner.name, "semester": state.position.semester,
            "week": state.position.week_in_semester,
            "weeks_per_semester": state.program.weeks_per_semester,
            "standing": state.standing, "hold": state.hold,
            "gpa_semester": state.gpa.semester, "gpa_cumulative": state.gpa.cumulative,
            "streak": state.streak.current, "courses": courses, "today": today,
            "blocked": blocked, "review": review,
            "srs": S.due_count(vault, now or datetime.now(timezone.utc))}


def render_home(snap: dict) -> str:
    """The Obsidian control center `Home.md` — structured to match the Board: callout boxes + a course
    table (Obsidian renders both richly). The visual mirror of the Telegram status surface."""
    active = [c for c in snap["courses"] if c["status"] != "archived"]
    where = (f"Semester {snap['semester']} · Week {snap['week']}/{snap['weeks_per_semester']} · "
             f"Standing: {snap['standing']}")
    if snap["gpa_cumulative"] is not None:
        where += f" · GPA {_fmt(snap['gpa_semester'])} (cum {_fmt(snap['gpa_cumulative'])})"
    if snap["streak"]:
        where += f" · 🔥 {snap['streak']}-day streak"
    out = [f"# 🏛️ Home — {snap['learner'] or 'Hermes University'}", "",
           "> [!abstract] Where you are", f"> {where}", ""]
    if snap["hold"]:
        out += [f"> [!warning] On hold: {snap['hold']}",
                "> New material is paused until it clears.", ""]

    out += ["## 📚 Courses"]
    if active:
        out += ["| Course | Status | Mastery |", "|---|---|---|"]
        for c in active:
            badge = _STATUS_BADGE.get(c["status"], c["status"])
            m = f"{c['mastery_pct']}%" if c["status"] == "active" else "—"
            out.append(f"| **{c['title']}** | {badge} | {m} |")
    else:
        out += ["> [!note] No courses yet",
                "> Message the bot **`create course <your goal>`** to begin."]
    out.append("")

    if snap["blocked"]:
        out += ["> [!todo] Blocked on you"]
        for b in snap["blocked"]:
            who = f"**{b['title']}** — " if b.get("title") else ""
            hint = (f" → open `Uploads/{b['code']}/RESEARCH-PROMPT.md`, run it in Claude, drop the "
                    "report back") if b["reason"].startswith("waiting for your research") else ""
            out.append(f"> - {who}{b['reason']}{hint}")
    else:
        out += ["> [!success] You're all caught up", "> Nothing is waiting on you right now."]
    out.append("")

    if snap["today"]:
        out += ["## ✅ Today"] + [f"- [ ] {t}" for t in snap["today"]] + [""]

    if snap.get("review"):
        out += ["> [!question] To review — proven before, refresh it"]
        out += [f"> - {r['statement'] or r['outcome']}" for r in snap["review"]] + [""]

    srs = snap["srs"]
    if srs["queued"] or srs["created"]:
        line = f"> [!note] Anki: **{srs['queued']}** queued · {srs['created']} created"
        if srs.get("review_due"):
            line += f" · {srs['review_due']} to review"
        out += [line, ""]

    out += ["---", "[[Board]] · [[Catalog]] · [[Guide]] · [[Registrar/Transcript|Transcript]] · "
            "[[Registrar/DegreeProgress|Degree Progress]] · [[Registrar/Schedule|Schedule]]"]
    return "\n".join(out).rstrip() + "\n"


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
        w(f"Courses/{code}/Resources.md", render_resources(m))
    w("Registrar/Transcript.md", render_transcript(state, records))
    w("Registrar/Schedule.md", render_schedule(state))
    enrolled_modules = {k: modules[k] for k in state.courses if k in modules}
    w("Registrar/DegreeProgress.md", render_degree_progress(state, records, enrolled_modules))
    if state.degree.awarded_on:
        w("Registrar/Diploma.md", render_diploma(state))
    w("Home.md", render_home(status_snapshot(vault, courses_dir)))   # the control center (RFC-009)
    return written


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:.2f}"
