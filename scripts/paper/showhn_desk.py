#!/usr/bin/env python3
"""Data desk: what one person shipped that an audience actually showed up for.

The revenue desk counts money. This counts the other currency — attention — from
Show HN via Algolia's keyless API: points and comments on things people launched
in the last couple of days.

Points are not users. The desk says so, because the whole discipline of this paper
is that a number is quoted as the thing it measures and nothing else.

Needs network. If the fetch fails or nothing clears the bar, the desk exits nonzero
and the story is dropped — it never prints a launch it did not read.

Data desk, deliberately code, never a model.

Usage:
    showhn_desk.py <edition_dir> [--hours 48] [--min-points 20] [--limit 8]

Writes <edition_dir>/articles/03-what-shipped.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import DeskError, clip, write_article  # noqa: E402

FILENAME = "03-what-shipped.md"
API = "https://hn.algolia.com/api/v1/search_by_date"
TIMEOUT = 30
CHART_BARS = 6


def _project_name(title: str) -> str:
    """The project's name out of a Show HN title.

    "Toast, a by default in-terminal IDE" is Toast; "Hacker News, Without AI" is the
    whole thing. A dash or colon always separates name from pitch; a comma only does
    when what follows reads like prose rather than part of the name.
    """
    for sep in (" – ", " — ", " - ", ": "):
        if sep in title:
            return title.split(sep, 1)[0].strip()
    head, comma, tail = title.partition(",")
    if comma and tail.strip()[:1].islower():
        return head.strip()
    return title.strip()


def fetch(hours: int, min_points: int, limit: int) -> list[dict]:
    since = int(time.time()) - hours * 3600
    query = urllib.parse.urlencode({
        "tags": "show_hn",
        "numericFilters": f"points>={min_points},created_at_i>{since}",
        "hitsPerPage": max(limit * 3, 30),
    })
    request = urllib.request.Request(f"{API}?{query}",
                                     headers={"User-Agent": "hermes-daily-desk/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise DeskError(f"Show HN search unreachable: {exc}") from exc

    collected: dict[str, dict] = {}
    for hit in payload.get("hits") or []:
        title = str(hit.get("title") or "").strip()
        if not title:
            continue
        stripped = title[len("Show HN:"):].strip() if title.lower().startswith("show hn:") else title
        name = _project_name(stripped)

        # The same launch is often posted twice — sometimes with the capitalisation changed,
        # sometimes to a different URL. Key on the flattened title and keep the better-scored copy.
        key = re.sub(r"[^a-z0-9]+", "", stripped.lower())

        row = {
            "title": stripped,
            "name": name or stripped,
            "points": int(hit.get("points") or 0),
            "comments": int(hit.get("num_comments") or 0),
            "url": str(hit.get("url") or ""),
            "discussion": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
            "author": str(hit.get("author") or ""),
            "when": str(hit.get("created_at") or "")[:10],
        }
        if key not in collected or row["points"] > collected[key]["points"]:
            collected[key] = row

    rows = sorted(collected.values(), key=lambda r: r["points"], reverse=True)
    return rows[:limit]


def build_body(rows: list[dict], hours: int, min_points: int) -> str:
    total_points = sum(row["points"] for row in rows)
    talked_about = max(rows, key=lambda row: row["comments"])

    paras = [
        f"{len(rows)} things one person launched on Show HN in the last {hours} hours cleared "
        f"{min_points} points, {total_points:,} between them. The most argued-over is "
        f"*{talked_about['name']}*, at {talked_about['comments']} comments against "
        f"{talked_about['points']} points.",
        "**Points are attention, not adoption.** They say a title landed with a technical audience on "
        "one morning; they say nothing about users, retention or revenue. A high comment count against "
        "modest points usually means an argument rather than a hit. Treat this board as evidence that "
        "an idea can find an audience — the other kind of proof is on the revenue board.",
    ]

    rows_out = [
        "### What shipped",
        "",
        "| # | Project | Points | Comments |",
        "|---:|:---|---:|---:|",
    ]
    for index, row in enumerate(rows, 1):
        rows_out.append(f"| {index} | {clip(row['name'], 20)} | {row['points']} | {row['comments']} |")

    rows_out += ["", "### What they are", ""]
    for row in rows:
        link = row["url"] or row["discussion"]
        rows_out.append(
            f"- **[{row['name']}]({link})** — {clip(row['title'], 90)} "
            f"([discussion]({row['discussion']}))."
        )

    return "\n\n".join(paras) + "\n\n" + "\n".join(rows_out)


def build_article(edition_dir: Path, hours: int, min_points: int, limit: int) -> Path:
    rows = fetch(hours, min_points, limit)
    if not rows:
        raise DeskError(f"nothing on Show HN cleared {min_points} points in {hours}h")

    fields = {
        "id": FILENAME[:-3],
        "headline": "What Shipped, and Who Turned Up",
        "deck": f"{len(rows)} launches from the last {hours} hours, by attention",
        "section": "projects",
        "byline": "The Launch Desk",
        "priority": 3,
        "span": "2col",
    }

    charted = rows[:CHART_BARS]
    if len(charted) >= 2:
        fields["chart"] = {
            "kind": "bars",
            "values": [row["points"] for row in charted],
            # Labels are measured in rendered pixels against the gap between bars: six bars
            # leave room for about four characters, so the bars are numbered.
            "labels": [str(i) for i in range(1, len(charted) + 1)],
            "show_values": True,
        }
        fields["caption"] = (
            "Show HN points in the last two days. Attention on the morning it launched, "
            "not users. Numbered as in the table below."
        )

    return write_article(edition_dir, FILENAME, fields, build_body(rows, hours, min_points))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edition_dir", type=Path)
    parser.add_argument("--hours", type=int, default=48)
    parser.add_argument("--min-points", type=int, default=20)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args(argv)

    try:
        target = build_article(args.edition_dir, args.hours, args.min_points, args.limit)
    except DeskError as exc:
        print(f"show hn desk: {exc} — dropping the story", file=sys.stderr)
        return 1
    print(f"wrote {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
