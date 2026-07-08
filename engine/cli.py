"""Thin CLI so skills/crons invoke the engine (they never compute numbers themselves).

Examples:
  hu-engine state init --name "..." --tz Asia/Tashkent --started 2026-07-06 --out state.json
  hu-engine gpa --records records/grades.jsonl
  hu-engine proof verify --gate leetcode --evidence '{"username":"u","slug":"two-sum","since_ts":0}'
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from . import gradebook as gb
from .learner_model import LearnerModel, recompute, weak_areas
from .proofgate import get_gate
from .state import State, fresh_state


def _now() -> datetime:
    return datetime.now(timezone.utc)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="hu-engine")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("state").add_subparsers(dest="sub", required=True)
    pi = ps.add_parser("init")
    pi.add_argument("--name", default=None); pi.add_argument("--tz", default=None)
    pi.add_argument("--started", required=True); pi.add_argument("--out", required=True)
    psh = ps.add_parser("show"); psh.add_argument("--file", required=True)
    preg = ps.add_parser("register")
    preg.add_argument("--file", required=True); preg.add_argument("--courses", required=True)

    pg = sub.add_parser("gpa"); pg.add_argument("--records", required=True)
    pg.add_argument("--semester", type=int, default=None)
    pg.add_argument("--state", default=None)   # for credit/kind weights; else equal-weight

    # grade add — the audit records a proven grade; engine recomputes GPA/standing + dashboard
    pga = sub.add_parser("grade").add_subparsers(dest="sub", required=True).add_parser("add")
    for a in ("vault", "course", "outcome", "kind", "source"):
        pga.add_argument(f"--{a}", required=True)
    pga.add_argument("--score", type=float, required=True)
    pga.add_argument("--semester", type=int, required=True)
    pga.add_argument("--passed", action="store_true")
    pga.add_argument("--tier", default=None); pga.add_argument("--topic", default=None)
    pga.add_argument("--weak", default=""); pga.add_argument("--today", required=True)

    # day close — update the streak once the day's items are (or aren't) all proven
    pdc = sub.add_parser("day").add_subparsers(dest="sub", required=True).add_parser("close")
    pdc.add_argument("--vault", required=True); pdc.add_argument("--today", required=True)
    pdc.add_argument("--all-done", action="store_true")

    # promote — apply a semester-finals result (engine gates promotion/graduation)
    ppr = sub.add_parser("promote")
    ppr.add_argument("--vault", required=True); ppr.add_argument("--band", required=True)
    ppr.add_argument("--today", required=True); ppr.add_argument("--courses", default=None)

    # enrollment — catalog / enroll / drop
    pcat = sub.add_parser("catalog"); pcat.add_argument("--courses", required=True)
    pen = sub.add_parser("enroll")
    pen.add_argument("--vault", required=True); pen.add_argument("--courses", required=True)
    pen.add_argument("--code", required=True); pen.add_argument("--today", default=None)
    pdr = sub.add_parser("drop")
    pdr.add_argument("--vault", required=True); pdr.add_argument("--code", required=True)

    # render-docs — regenerate the visible university documents
    prd = sub.add_parser("render-docs")
    prd.add_argument("--vault", required=True); prd.add_argument("--courses", required=True)

    # advance — move the calendar forward a week and activate any now-due courses (weekly cron)
    padv = sub.add_parser("advance")
    padv.add_argument("--vault", required=True); padv.add_argument("--weeks", type=int, default=1)

    # render-my-plan — the learner's personalized (placement-pruned) track → Courses/<CODE>/MyPlan.md
    prm = sub.add_parser("render-my-plan")
    prm.add_argument("--vault", required=True); prm.add_argument("--course-file", required=True)
    prm.add_argument("--tz", default="UTC")

    # board — the two-way Obsidian Kanban surface (RFC-008): read current, write from a JSON spec
    pbd = sub.add_parser("board").add_subparsers(dest="sub", required=True)
    pbr = pbd.add_parser("read"); pbr.add_argument("--vault", required=True)
    pbw = pbd.add_parser("write"); pbw.add_argument("--vault", required=True)
    pbw.add_argument("--json", required=True)

    # course validate — structural gate for professor-authored YAML (RFC-003 §4)
    pcv = sub.add_parser("course").add_subparsers(dest="sub", required=True).add_parser("validate")
    pcv.add_argument("--file", required=True)

    pv = sub.add_parser("proof").add_subparsers(dest="sub", required=True).add_parser("verify")
    pv.add_argument("--gate", required=True); pv.add_argument("--evidence", required=True)

    pl = sub.add_parser("learner").add_subparsers(dest="sub", required=True)
    plw = pl.add_parser("weak"); plw.add_argument("--records", required=True)
    plw.add_argument("--tz", default="Asia/Tashkent")

    # plan — the engine's per-course "what to teach next + at what difficulty" (drives assign)
    pp = sub.add_parser("plan")
    pp.add_argument("--vault", required=True); pp.add_argument("--course-file", required=True)
    pp.add_argument("--tz", default="Asia/Tashkent")

    args = p.parse_args(argv)

    if args.cmd == "state" and args.sub == "init":
        from pathlib import Path as _P
        from .profile import load_profile
        prof = load_profile(_P(__file__).resolve().parents[1])
        st = fresh_state(name=args.name or prof.name, timezone=args.tz or prof.timezone,
                         started_on=args.started, credential_name=prof.credential_name)
        st.save(args.out); print(f"wrote {args.out}"); return 0
    if args.cmd == "state" and args.sub == "show":
        print(State.load(args.file).model_dump_json(indent=2)); return 0
    if args.cmd == "state" and args.sub == "register":
        from .registrar import register_courses
        st = State.load(args.file)
        added = register_courses(st, args.courses)
        st.save(args.file)
        print(json.dumps({"registered": added, "courses": sorted(st.courses)})); return 0
    if args.cmd == "gpa":
        recs = gb.load_records(args.records)
        if args.state:
            courses = State.load(args.state).courses
        else:                                   # no state: each course equal-weight (credits 1, no policy)
            from types import SimpleNamespace
            courses = {c: SimpleNamespace(credits=1, grade_weights={}) for c in {r.course for r in recs}}
        val = (gb.semester_gpa(recs, courses, args.semester) if args.semester
               else gb.cumulative_gpa(recs, courses))
        print(json.dumps({"gpa": val, "standing": gb.standing_for(val)})); return 0
    if args.cmd == "grade" and args.sub == "add":
        from pathlib import Path
        from . import registrar as R
        from .gradebook import GradeRecord, Proof, append_record, load_records, score_to_band
        vault = Path(args.vault)
        recs_path = vault / "records" / "grades.jsonl"
        recs_path.parent.mkdir(parents=True, exist_ok=True)
        band = score_to_band(args.score)
        record = GradeRecord(
            ts=_now().isoformat(), course=args.course, outcome=args.outcome, kind=args.kind,
            band=band, score=args.score, semester=args.semester,
            proof=Proof(source=args.source, passed=args.passed),
            tier=args.tier, topic=args.topic,
            weak_areas=[w for w in args.weak.split(",") if w])
        append_record(recs_path, record)
        st = R.load_state(vault)
        all_recs = load_records(recs_path)
        R.refresh(st, all_recs)
        R.save_state(vault, st); R.write_dashboard(vault, st, args.today)
        R.persist_learner_model(vault, all_recs, st.learner.timezone, _now())
        print(json.dumps({"band": band, "gpa_cumulative": st.gpa.cumulative,
                          "standing": st.standing, "hold": st.hold})); return 0
    if args.cmd == "day" and args.sub == "close":
        from pathlib import Path
        from . import registrar as R
        vault = Path(args.vault)
        st = R.load_state(vault)
        R.record_day(st, args.today, args.all_done)
        R.save_state(vault, st); R.write_dashboard(vault, st, args.today)
        print(json.dumps({"streak": st.streak.current})); return 0
    if args.cmd == "catalog":
        from . import registrar as R
        print(json.dumps(R.catalog(args.courses), indent=2)); return 0
    if args.cmd == "enroll":
        from pathlib import Path
        from . import docs
        from . import registrar as R
        vault = Path(args.vault)
        st = R.load_state(vault)
        try:
            result = R.enroll(st, args.courses, args.code, today=args.today)
        except R.EnrollError as e:
            print(json.dumps({"code": args.code, "result": "refused", "reason": str(e)}))
            return 2
        R.save_state(vault, st)
        docs.render_all(vault, args.courses)     # refresh the visible docs
        print(json.dumps({"code": args.code, "result": result,
                          "enrolled": sorted(st.courses)})); return 0
    if args.cmd == "drop":
        from pathlib import Path
        from . import registrar as R
        vault = Path(args.vault)
        st = R.load_state(vault); dropped = R.drop(st, args.code); R.save_state(vault, st)
        print(json.dumps({"code": args.code, "dropped": dropped,
                          "enrolled": sorted(st.courses)})); return 0
    if args.cmd == "render-docs":
        from . import docs
        written = docs.render_all(args.vault, args.courses)
        print(json.dumps({"rendered": written})); return 0
    if args.cmd == "advance":
        from pathlib import Path
        from . import registrar as R
        vault = Path(args.vault)
        st = R.load_state(vault)
        for _ in range(max(0, args.weeks)):
            R.advance_week(st)
        activated = R.activate_due_courses(st)
        R.save_state(vault, st)
        print(json.dumps({"semester": st.position.semester,
                          "week": st.position.week_in_semester, "activated": activated})); return 0
    if args.cmd == "board" and args.sub == "read":
        from pathlib import Path
        from . import board as B
        p = Path(args.vault) / "Board.md"
        cols = B.parse_board(p.read_text() if p.exists() else "")
        print(json.dumps({k: [c.model_dump() for c in v] for k, v in cols.items()})); return 0
    if args.cmd == "board" and args.sub == "write":
        from pathlib import Path
        from . import board as B
        spec = json.loads(args.json)
        cols = {k: [B.Card.model_validate(c) for c in v] for k, v in spec.items()}
        (Path(args.vault) / "Board.md").write_text(B.render_board(cols))
        print(json.dumps({"written": "Board.md",
                          "columns": {k: len(v) for k, v in cols.items()}})); return 0
    if args.cmd == "render-my-plan":
        from pathlib import Path
        from . import docs
        from .course import load_course
        c = load_course(args.course_file)
        recs = [r for r in gb.load_records(Path(args.vault) / "records" / "grades.jsonl")
                if r.course == c.id]
        m = recompute(LearnerModel(), recs, tz=args.tz, now=_now())
        mastered = {oid for oid, st in m.outcomes.items() if st.mastery_band and gb.band_meets(
            st.mastery_band, (c.outcome(oid).mastery_threshold if c.outcome(oid) else 0.8))}
        rel = f"Courses/{c.id}/MyPlan.md"
        path = Path(args.vault) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(docs.render_my_plan(c, mastered))
        print(json.dumps({"rendered": rel, "placed_out": sorted(mastered)})); return 0
    if args.cmd == "course" and args.sub == "validate":
        from .course import load_course
        try:
            c = load_course(args.file)
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)})); return 2
        import re as _re
        from pathlib import Path as _P
        n_res = len(c.resources) + sum(len(u.resources) for u in c.units)
        teaching = [u for u in c.units if not u.id.endswith("finals")]
        # Dossier gate (RFC-007): real cited research, not a memory dump. Require ≥5 distinct source
        # URLs + confidence tags + an "open questions / couldn't verify" section.
        dossier = _P(args.file).parent / "research" / "dossier.md"
        dtext = dossier.read_text() if dossier.exists() else ""
        n_urls = len(set(_re.findall(r"https?://[^\s)\]>]+", dtext)))
        has_dossier = (n_urls >= 5 and "confidence" in dtext.lower()
                       and any(s in dtext.lower() for s in
                               ("open question", "couldn't verify", "could not verify", "cannot verify")))
        mm = c.mastery_model
        has_mastery = bool(mm and mm.excellence_bar and mm.staying_current)
        missing = []
        if not c.description: missing.append("description")
        if not all(u.resources for u in teaching): missing.append("unit-resources")
        if not all(u.sessions for u in teaching): missing.append("weekly-plan")
        if not c.professor_profile: missing.append("professor_profile")
        if not has_mastery: missing.append("mastery_model")
        if not has_dossier:
            missing.append("research-dossier(needs ≥5 cited URLs + confidence + open-questions)")
        authored = not missing
        print(json.dumps({"ok": True, "id": c.id, "units": len(c.units),
                          "outcomes": len(c.all_outcomes()), "resources": n_res,
                          "authored": authored, "missing_for_authored": missing,
                          "no_resource_units": [u.id for u in c.units if not u.resources]}))
        return 0
    if args.cmd == "promote":
        from pathlib import Path
        from . import registrar as R
        from .gradebook import load_records
        vault = Path(args.vault)
        st = R.load_state(vault)
        records = load_records(vault / "records" / "grades.jsonl")
        st, status = R.promote_or_graduate(st, args.band, args.today, records)
        R.save_state(vault, st); R.write_dashboard(vault, st, args.today)
        if args.courses:
            from . import docs
            docs.render_all(vault, args.courses)   # refresh Transcript/DegreeProgress/Diploma
        print(json.dumps({"status": status, "semester": st.position.semester,
                          "degree_awarded": st.degree.awarded_on})); return 0
    if args.cmd == "proof":
        res = get_gate(args.gate).verify(json.loads(args.evidence))
        print(res.model_dump_json()); return 0 if res.passed else 2
    if args.cmd == "learner" and args.sub == "weak":
        recs = gb.load_records(args.records)
        m = recompute(LearnerModel(), recs, tz=args.tz, now=_now())
        print(json.dumps({"weak_areas": weak_areas(m)})); return 0
    if args.cmd == "plan":
        from pathlib import Path
        from .course import load_course
        from .learner_model import difficulty_for, next_topic
        c = load_course(args.course_file)
        recs = [r for r in gb.load_records(Path(args.vault) / "records" / "grades.jsonl")
                if r.course == c.id]
        m = recompute(LearnerModel(), recs, tz=args.tz, now=_now())

        def _thr(oid):                             # per-outcome mastery threshold (default 0.8 → ≥B)
            oc = c.outcome(oid)
            return oc.mastery_threshold if oc else 0.8
        mastered = {oid for oid, st in m.outcomes.items()
                    if st.mastery_band and gb.band_meets(st.mastery_band, _thr(oid))}
        nxt = next_topic(c.dag(), mastered)
        if nxt is None:
            print(json.dumps({"course": c.id, "next": None, "done": True})); return 0
        unit = c.unit_of(nxt)
        o = c.outcome(nxt)
        a = next((x for x in c.assessments if o and x.id == o.proof), None)   # module-driven gate
        tier = difficulty_for(m, unit.id if unit else nxt, baseline=c.starting_tier)
        print(json.dumps({"course": c.id, "next_outcome": nxt, "unit": unit.id if unit else None,
                          "statement": o.statement if o else None,
                          "proof_gate": a.proof_gate if a else None,
                          "gate": a.gate if a else None, "gate_args": a.gate_args if a else {},
                          "difficulty": tier})); return 0
    p.error("unknown command")


if __name__ == "__main__":
    sys.exit(main())
