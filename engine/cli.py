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
    pi.add_argument("--name", required=True); pi.add_argument("--tz", default="Asia/Tashkent")
    pi.add_argument("--started", required=True); pi.add_argument("--out", required=True)
    psh = ps.add_parser("show"); psh.add_argument("--file", required=True)
    preg = ps.add_parser("register")
    preg.add_argument("--file", required=True); preg.add_argument("--courses", required=True)

    pg = sub.add_parser("gpa"); pg.add_argument("--records", required=True)
    pg.add_argument("--semester", type=int, default=None)

    # grade add — the audit records a proven grade; engine recomputes GPA/standing + dashboard
    pga = sub.add_parser("grade").add_subparsers(dest="sub", required=True).add_parser("add")
    for a in ("vault", "course", "outcome", "kind", "source"):
        pga.add_argument(f"--{a}", required=True)
    pga.add_argument("--score", type=float, required=True)
    pga.add_argument("--weight", type=float, required=True)
    pga.add_argument("--semester", type=int, required=True)
    pga.add_argument("--passed", action="store_true")
    pga.add_argument("--tier", default=None); pga.add_argument("--topic", default=None)
    pga.add_argument("--weak", default=""); pga.add_argument("--today", required=True)

    # day close — update the streak once the day's items are (or aren't) all proven
    pdc = sub.add_parser("day").add_subparsers(dest="sub", required=True).add_parser("close")
    pdc.add_argument("--vault", required=True); pdc.add_argument("--today", required=True)
    pdc.add_argument("--all-done", action="store_true")

    pv = sub.add_parser("proof").add_subparsers(dest="sub", required=True).add_parser("verify")
    pv.add_argument("--gate", required=True); pv.add_argument("--evidence", required=True)

    pl = sub.add_parser("learner").add_subparsers(dest="sub", required=True)
    plw = pl.add_parser("weak"); plw.add_argument("--records", required=True)
    plw.add_argument("--tz", default="Asia/Tashkent")

    args = p.parse_args(argv)

    if args.cmd == "state" and args.sub == "init":
        st = fresh_state(name=args.name, timezone=args.tz, started_on=args.started)
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
        val = gb.semester_gpa(recs, args.semester) if args.semester else gb.cumulative_gpa(recs)
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
            band=band, score=args.score, credits_weight=args.weight, semester=args.semester,
            proof=Proof(source=args.source, passed=args.passed),
            tier=args.tier, topic=args.topic,
            weak_areas=[w for w in args.weak.split(",") if w])
        append_record(recs_path, record)
        st = R.load_state(vault)
        R.refresh(st, load_records(recs_path))
        R.save_state(vault, st); R.write_dashboard(vault, st, args.today)
        print(json.dumps({"band": band, "gpa_cumulative": st.gpa.cumulative,
                          "standing": st.standing})); return 0
    if args.cmd == "day" and args.sub == "close":
        from pathlib import Path
        from . import registrar as R
        vault = Path(args.vault)
        st = R.load_state(vault)
        R.record_day(st, args.today, args.all_done)
        R.save_state(vault, st); R.write_dashboard(vault, st, args.today)
        print(json.dumps({"streak": st.streak.current})); return 0
    if args.cmd == "proof":
        res = get_gate(args.gate).verify(json.loads(args.evidence))
        print(res.model_dump_json()); return 0 if res.passed else 2
    if args.cmd == "learner" and args.sub == "weak":
        recs = gb.load_records(args.records)
        m = recompute(LearnerModel(), recs, tz=args.tz, now=_now())
        print(json.dumps({"weak_areas": weak_areas(m)})); return 0
    p.error("unknown command")


if __name__ == "__main__":
    sys.exit(main())
