#!/usr/bin/env python3
"""Data desk: what the learner model believes, and on what evidence.

Reads records/learner_model.json and writes the belief page: the hours the
record was actually made in, the observed pace, the weak topics, and whatever
the engine currently holds as a preference (quoted verbatim — the desk never
paraphrases a belief into something firmer than it is).

Note on `best_hours`: the engine derives it in learner_model.py by counting
GRADED RECORDS by the hour slot of their timestamp — not by when study blocks
were booked or worked. With few records those timestamps are largely the night
audit's own clock, so this desk reports the count it is and says how thin the
evidence is rather than calling it an energy window.

Data desk, deliberately code, never a model.

Usage:
    model_desk.py <edition_dir> [--vault PATH]

Writes <edition_dir>/articles/04-what-the-model-believes.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import DeskError, clip, load_json, resolve_vault, write_article  # noqa: E402

FILENAME = "04-what-the-model-believes.md"

# The paper's label ceiling is twelve characters (docs/WRITING.md).
LABEL_LIMIT = 12


def gather(vault: Path) -> dict:
    model = load_json(vault / "records" / "learner_model.json")
    routine = model.get("routine") or {}
    pace = model.get("pace") or {}

    slots = {str(k): int(v) for k, v in (routine.get("adherence_by_slot") or {}).items()}

    topics = []
    for name, topic in (model.get("topics") or {}).items():
        topics.append({
            "name": str(name),
            "proficiency": topic.get("proficiency"),
            "ceiling": topic.get("difficulty_ceiling"),
            "attempts": topic.get("attempts", 0),
        })
    topics.sort(key=lambda t: (t["proficiency"] if t["proficiency"] is not None else 1.0, -t["attempts"]))

    outcomes = []
    for name, outcome in (model.get("outcomes") or {}).items():
        outcomes.append({
            "name": str(name),
            "band": outcome.get("mastery_band"),
            "attempts": outcome.get("attempts", 0),
        })

    prefs = []
    for key, pref in (model.get("preferences") or {}).items():
        prefs.append({
            "aspect": str(pref.get("aspect") or key),
            "value": str(pref.get("value") or ""),
            "evidence": str(pref.get("evidence") or ""),
            "confidence": pref.get("confidence"),
            "source": pref.get("source"),
        })

    return {
        "slots": slots,
        "best_hours": [str(h) for h in (routine.get("best_hours") or [])],
        "task_cap": pace.get("task_cap_observed"),
        "rest_day": pace.get("rest_day"),
        "topics": topics,
        "outcomes": outcomes,
        "prefs": prefs,
        "window_days": model.get("trend_window_days"),
    }


def build_body(facts: dict) -> str:
    slots, total = facts["slots"], sum(facts["slots"].values())
    paras = []

    if total:
        busiest = max(slots.items(), key=lambda kv: kv[1])
        paras.append(
            f"Every belief below is drawn from {total} recorded outcome"
            f"{'s' if total != 1 else ''}. The hours in the chart are the hours those "
            f"records were written in — most often {busiest[0]}, {busiest[1]} of "
            f"{total} — which is a record of when work was marked, not proof of when "
            "it was done. On a handful of records the two are easy to confuse."
        )
    else:
        paras.append(
            "Nothing has been recorded yet, so the model holds no view about your "
            "hours. The first graded outcome starts it."
        )

    if facts["task_cap"]:
        pace = f"The busiest day on record carried {facts['task_cap']} tasks."
        if facts["rest_day"]:
            pace += f" The quietest weekday is {facts['rest_day']}."
        paras.append(pace)

    for pref in facts["prefs"]:
        if not pref["value"]:
            continue
        confidence = pref["confidence"]
        stated = f"On **{pref['aspect'].replace('_', ' ')}** the model currently holds: *{pref['value']}*."
        if confidence is not None:
            stated += f" It holds this at {float(confidence):.0%} confidence"
            if pref["source"]:
                stated += f", from {pref['source']}"
            stated += "."
        paras.append(stated)
        if pref["evidence"]:
            paras.append(f"> {pref['evidence']}")

    rows = []
    if facts["topics"]:
        rows += ["### Topics, weakest first", "", "| Topic | Ceiling | Tries |", "|:---|:---|---:|"]
        for topic in facts["topics"][:6]:
            ceiling = clip(str(topic["ceiling"] or "—"), 10)
            rows.append(f"| {clip(topic['name'])} | {ceiling} | {topic['attempts']} |")

    if facts["outcomes"]:
        rows += ["", "### Outcomes", "", "| Outcome | Band | Tries |", "|:---|:---|---:|"]
        for outcome in facts["outcomes"]:
            rows.append(
                f"| {clip(outcome['name'])} | {clip(str(outcome['band'] or '—'), 6)} "
                f"| {outcome['attempts']} |"
            )

    body = "\n\n".join(paras)
    if rows:
        body += "\n\n" + "\n".join(rows)
    return body


def build_article(edition_dir: Path, vault: Path) -> Path:
    facts = gather(vault)
    slots = facts["slots"]

    fields = {
        "id": FILENAME[:-3],
        "headline": "What the Model Believes About You",
        "deck": "Drawn from the record, with the evidence attached",
        "section": "standing",
        "byline": "The Registrar",
        "priority": 3,
        "span": "1col",
    }

    # Only chart real variation: one bar is not a distribution, and the check
    # wants at least two values.
    if len(slots) >= 2:
        ordered = sorted(slots.items(), key=lambda kv: kv[1], reverse=True)
        fields["chart"] = {
            "kind": "bars",
            "values": [count for _, count in ordered],
            "labels": [clip(slot, LABEL_LIMIT) for slot, _ in ordered],
            "show_values": True,
        }
        fields["caption"] = (
            "Recorded outcomes by the hour slot they were written in. "
            "These are marking times, not a measured energy window."
        )

    return write_article(edition_dir, FILENAME, fields, build_body(facts))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edition_dir", type=Path)
    parser.add_argument("--vault", default=None)
    args = parser.parse_args(argv)

    try:
        target = build_article(args.edition_dir, resolve_vault(args.vault))
    except DeskError as exc:
        print(f"model desk: {exc} — dropping the story", file=sys.stderr)
        return 1
    print(f"wrote {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
