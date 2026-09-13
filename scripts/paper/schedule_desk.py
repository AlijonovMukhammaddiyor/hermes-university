#!/usr/bin/env python3
"""Data desk: today's booked study blocks, from Google Calendar.

Reads the OAuth client and token the agent already holds, finds the Mentor
calendar by name, and writes the day's blocks as a table. Needs network; if
the token will not refresh or the calendar is missing, the desk exits nonzero
and the story is dropped — it never prints a block it did not read.

Data desk, deliberately code, never a model.

Usage:
    schedule_desk.py <edition_dir> [--vault PATH] [--calendar Mentor] [--date YYYY-MM-DD]

Writes <edition_dir>/articles/02-todays-blocks.md
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date as date_cls
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import DeskError, clip, load_json, resolve_vault, write_article  # noqa: E402

FILENAME = "02-todays-blocks.md"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/calendar/v3"
TIMEOUT = 25


def _get_json(url: str, token: str) -> dict:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DeskError(f"calendar API unreachable: {exc}") from exc


def access_token(keys_path: Path, tokens_path: Path) -> str:
    """Mint a fresh access token from the stored refresh token."""
    client = load_json(keys_path)
    node = client.get("installed") or client.get("web")
    if not node:
        raise DeskError(f"{keys_path} is not a Desktop OAuth client")

    stored = load_json(tokens_path)
    # The MCP nests its tokens under an account key ("normal" for the default).
    leaf = stored if "refresh_token" in stored else next(
        (v for v in stored.values() if isinstance(v, dict) and "refresh_token" in v), None
    )
    if not leaf:
        raise DeskError(f"no refresh_token in {tokens_path}")

    payload = urllib.parse.urlencode({
        "client_id": node["client_id"],
        "client_secret": node["client_secret"],
        "refresh_token": leaf["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=payload), timeout=TIMEOUT) as response:
            return json.load(response)["access_token"]
    except urllib.error.HTTPError as exc:
        raise DeskError(f"token refresh refused ({exc.code}) — re-authorise the calendar") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DeskError(f"token endpoint unreachable: {exc}") from exc


def find_calendar(token: str, name: str) -> str:
    listing = _get_json(f"{API}/users/me/calendarList", token)
    for item in listing.get("items", []):
        if str(item.get("summary", "")).strip().lower() == name.strip().lower():
            return item["id"]
    raise DeskError(f"no calendar named {name!r}")


def events_on(token: str, calendar_id: str, day: date_cls, zone: ZoneInfo) -> list[dict]:
    start = datetime.combine(day, datetime.min.time(), tzinfo=zone)
    query = urllib.parse.urlencode({
        "timeMin": start.isoformat(),
        "timeMax": (start + timedelta(days=1)).isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
    })
    calendar = urllib.parse.quote(calendar_id, safe="")
    payload = _get_json(f"{API}/calendars/{calendar}/events?{query}", token)

    out = []
    for item in payload.get("items", []):
        if item.get("status") == "cancelled":
            continue
        start_raw = (item.get("start") or {}).get("dateTime")
        end_raw = (item.get("end") or {}).get("dateTime")
        if not start_raw:  # an all-day entry is not a study block
            continue
        begin = datetime.fromisoformat(start_raw).astimezone(zone)
        finish = datetime.fromisoformat(end_raw).astimezone(zone) if end_raw else None
        out.append({
            "start": begin,
            "end": finish,
            "title": str(item.get("summary") or "Untitled"),
            "minutes": int((finish - begin).total_seconds() // 60) if finish else None,
        })
    return out


def learner_zone(vault: Path) -> ZoneInfo:
    state = load_json(vault / "Registrar" / "state.json")
    name = ((state.get("learner") or {}).get("timezone")) or "UTC"
    try:
        return ZoneInfo(str(name))
    except ZoneInfoNotFoundError as exc:
        raise DeskError(f"unknown learner timezone {name!r}") from exc


def build_body(blocks: list[dict], day: date_cls, calendar: str) -> str:
    pretty_day = day.strftime("%A %-d %B")

    if not blocks:
        return (
            f"Nothing is booked on the {calendar} calendar for {pretty_day}. "
            f"The {calendar} calendar is where the registrar places study against "
            "real hours, kept separate from your own commitments so that neither "
            "crowds the other. An empty day is not a rest day unless it was "
            "assigned as one; it is a day the work has to find its own time, "
            "which is the arrangement that has historically failed. If something "
            "is outstanding, the night audit will still look for a proof of it."
        )

    total = sum(block["minutes"] or 0 for block in blocks)
    opens = blocks[0]["start"].strftime("%H:%M")
    last_end = next((b["end"] for b in reversed(blocks) if b["end"]), None)
    closes = last_end.strftime("%H:%M") if last_end else None

    first = (
        f"{len(blocks)} block{'s are' if len(blocks) != 1 else ' is'} booked on the "
        f"{calendar} calendar for {pretty_day}, {total} minutes in all. "
        f"The first opens at {opens}"
    )
    first += f" and the last closes at {closes}." if closes else "."

    paras = [
        first,
        f"The {calendar} calendar is the study calendar, separate from your own "
        "commitments: anything on it was placed by the registrar against the hours "
        "the record suggests, not entered by you. A block is a booking rather than "
        "a reminder — the time is already spoken for.",
        # Only what the calendar itself supports — this desk never read the
        # audit log, so it states the rule and not a claim about the record.
        "The night audit reads each block against its proof. A block that passes "
        "without one is recorded as a miss, and the task rolls forward as debt "
        "into the next assigned day.",
    ]

    rows = ["### The day", "", "| Time | Block | Mins |", "|:---|:---|---:|"]
    for block in blocks:
        when = block["start"].strftime("%H:%M")
        rows.append(f"| {when} | {clip(block['title'])} | {block['minutes'] or '—'} |")

    return "\n\n".join(paras) + "\n\n" + "\n".join(rows)


def build_article(edition_dir: Path, vault: Path, calendar: str,
                  keys_path: Path, tokens_path: Path, day: date_cls) -> Path:
    zone = learner_zone(vault)
    token = access_token(keys_path, tokens_path)
    blocks = events_on(token, find_calendar(token, calendar), day, zone)

    deck = (
        f"{len(blocks)} booked for {day.strftime('%A')}"
        if blocks else f"Nothing booked for {day.strftime('%A')}"
    )
    fields = {
        "id": FILENAME[:-3],
        "headline": "Today's Blocks",
        "deck": deck,
        "section": "today",
        "byline": "The Registrar",
        "priority": 2,
        "span": "1col",
    }
    return write_article(edition_dir, FILENAME, fields, build_body(blocks, day, calendar))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edition_dir", type=Path)
    parser.add_argument("--vault", default=None)
    parser.add_argument("--calendar", default="Mentor")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument("--oauth-keys", default="~/.hermes/gcp-oauth.keys.json")
    parser.add_argument("--tokens", default="~/.config/google-calendar-mcp/tokens.json")
    args = parser.parse_args(argv)

    try:
        day = date_cls.fromisoformat(args.date) if args.date else date_cls.today()
        target = build_article(
            args.edition_dir,
            resolve_vault(args.vault),
            args.calendar,
            Path(args.oauth_keys).expanduser(),
            Path(args.tokens).expanduser(),
            day,
        )
    except DeskError as exc:
        print(f"schedule desk: {exc} — dropping the story", file=sys.stderr)
        return 1
    print(f"wrote {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
