#!/usr/bin/env python3
"""Data desk: where the learner stands — standing, GPA, streak, courses.

Reads Registrar/state.json and records/grades.jsonl and writes the Record page.

Data desk, deliberately code, never a model. If a figure here is wrong, fix
this script; do not have a model "improve" the numbers.

Usage:
    standing_desk.py <edition_dir> [--vault PATH]

Writes <edition_dir>/articles/03-where-you-stand.md
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    DeskError,
    clip,
    load_json,
    load_jsonl,
    resolve_vault,
    write_article,
)

FILENAME = "03-where-you-stand.md"

# How the engine's standing vocabulary reads in a sentence.
STANDING_PROSE = {
    "good": "in good standing",
    "honors": "on the honours list",
    "probation": "on probation",
}


def _days_since(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        when = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return (datetime.now(UTC) - when).days


def gather(vault: Path) -> dict:
    state = load_json(vault / "Registrar" / "state.json")
    grades = load_jsonl(vault / "records" / "grades.jsonl")

    position = state.get("position") or {}
    program = state.get("program") or {}
    gpa = state.get("gpa") or {}
    streak = state.get("streak") or {}

    bands: dict[str, int] = {}
    for row in grades:
        band = str(row.get("band") or "?")
        bands[band] = bands.get(band, 0) + 1

    last_ts = max((row.get("ts") or "" for row in grades), default="")

    return {
        "semester": position.get("semester"),
        "week": position.get("week_in_semester"),
        "weeks_total": program.get("weeks_per_semester"),
        "phase": position.get("phase"),
        "gpa_semester": gpa.get("semester"),
        "gpa_cumulative": gpa.get("cumulative"),
        "standing": state.get("standing"),
        "hold": state.get("hold"),
        "streak": streak.get("current"),
        "streak_best": streak.get("longest"),
        "graded": len(grades),
        "bands": bands,
        "days_since_grade": _days_since(last_ts),
        "courses": state.get("courses") or {},
    }


def build_body(facts: dict) -> str:
    standing = str(facts["standing"] or "unknown")
    standing_prose = STANDING_PROSE.get(standing, standing)
    week, weeks_total = facts["week"], facts["weeks_total"]
    graded = facts["graded"]
    passed = graded - facts["bands"].get("F", 0)

    paras = [
        f"You are in week {week} of {weeks_total} of semester {facts['semester']}, "
        f"{standing_prose}, with a semester grade-point average of "
        f"{facts['gpa_semester']:.2f} and a cumulative average of "
        f"{facts['gpa_cumulative']:.2f}."
    ]

    if graded:
        recorded = (
            f"{graded} outcome{'s' if graded != 1 else ''} "
            f"{'have' if graded != 1 else 'has'} been graded so far, "
            f"of which {passed} cleared the bar."
        )
        if facts["days_since_grade"] is not None:
            recorded += (
                f" The most recent went into the record "
                f"{facts['days_since_grade']} days ago."
            )
        paras.append(recorded)
    else:
        paras.append(
            "Nothing has been graded yet, so the average is an opening balance "
            "rather than a verdict."
        )

    if facts["hold"]:
        paras.append(
            f"A hold is in force — *{facts['hold']}* — which means no new material is "
            "assigned until an outcome is graded at B or better. The work that clears "
            "it is remediation on what is already open, not anything new."
        )

    streak, best = facts["streak"], facts["streak_best"]
    if streak:
        paras.append(f"The current streak is {streak} days; the longest on record is {best}.")
    elif best:
        paras.append(f"The streak is at zero. The longest on record is {best} days.")
    else:
        paras.append("No streak has been set yet, so the first completed day sets the record.")

    rows = ["### The record", "", "| Measure | Standing |", "|:---|---:|"]
    rows.append(f"| Semester | {facts['semester']} |")
    rows.append(f"| Week | {week} of {weeks_total} |")
    rows.append(f"| GPA, semester | {facts['gpa_semester']:.2f} |")
    rows.append(f"| GPA, cumulative | {facts['gpa_cumulative']:.2f} |")
    rows.append(f"| Standing | {clip(standing)} |")
    if facts["hold"]:
        rows.append(f"| Hold | {clip(str(facts['hold']))} |")
    rows.append(f"| Streak | {streak} |")
    rows.append(f"| Outcomes graded | {graded} |")

    courses = facts["courses"]
    if courses:
        # Four columns, and every cell under the paper's 26-character ceiling:
        # the code and the title get their own so neither has to be cut.
        rows += ["", "### Courses", "", "| Course | Title | Cr | Status |", "|:---|:---|---:|:---|"]
        for code, course in courses.items():
            title = clip(str(course.get("title") or code))
            credits = course.get("credits", "—")
            status = clip(str(course.get("status") or "—"), 12)
            rows.append(f"| {clip(str(code), 10)} | {title} | {credits} | {status} |")

    return "\n\n".join(paras) + "\n\n" + "\n".join(rows)


def build_article(edition_dir: Path, vault: Path) -> Path:
    facts = gather(vault)
    standing = str(facts["standing"] or "unknown")

    deck = (
        f"Week {facts['week']} of {facts['weeks_total']}, "
        f"GPA {facts['gpa_semester']:.2f}, streak {facts['streak']}"
    )
    headline = {
        "probation": "The Record, and the Hold on It",
        "honors": "The Record, and the Honours on It",
    }.get(standing, "Where You Stand")

    fields = {
        "id": FILENAME[:-3],
        "headline": headline,
        "deck": deck,
        "section": "standing",
        "byline": "The Registrar",
        "priority": 2,
        "span": "2col",
    }
    return write_article(edition_dir, FILENAME, fields, build_body(facts))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edition_dir", type=Path)
    parser.add_argument("--vault", default=None)
    args = parser.parse_args(argv)

    try:
        target = build_article(args.edition_dir, resolve_vault(args.vault))
    except DeskError as exc:
        print(f"standing desk: {exc} — dropping the story", file=sys.stderr)
        return 1
    print(f"wrote {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
