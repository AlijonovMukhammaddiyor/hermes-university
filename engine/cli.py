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

    pg = sub.add_parser("gpa"); pg.add_argument("--records", required=True)
    pg.add_argument("--semester", type=int, default=None)

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
    if args.cmd == "gpa":
        recs = gb.load_records(args.records)
        val = gb.semester_gpa(recs, args.semester) if args.semester else gb.cumulative_gpa(recs)
        print(json.dumps({"gpa": val, "standing": gb.standing_for(val)})); return 0
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
