"""The Anki forward pipeline (RFC-009 §5).

Turns a proven outcome into review cards: appends to `<vault>/SRS/pending.jsonl` (the queue
`scripts/anki_sync.py` uploads to AnkiWeb, then clears on a clean sync) and to an append-only
`ledger.jsonl` (so a due/created count can be surfaced without reading Anki back).

Review results flowing *back* from Anki to update live mastery is a deferred follow-up (RFC-009 §5);
until then `due` is derived from the initial FSRS schedule in the ledger.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import cards as C
from . import fsrs

DECK_PREFIX = "Hermes"


def _srs_dir(vault: str | Path) -> Path:
    d = Path(vault) / "SRS"
    d.mkdir(parents=True, exist_ok=True)
    return d


def outcome_tag(outcome: str) -> str:
    """The Anki tag that links a card back to its engine outcome (survives sync → the review-back
    reader parses it). Anki tags are space-free; outcome ids (e.g. 'f1.apply') are fine."""
    return f"hu-o::{outcome}"


def queue_cards(
    vault: str | Path,
    course: str,
    deck_prefix: str,
    unit: str,
    items: list[dict],
    now: datetime,
    outcome: str = "",
) -> int:
    """Append professor-supplied [{front,back,tags?}] cards for a proven outcome. Writes the push
    queue (pending.jsonl: deck/front/back/tags) and the ledger (full card + fsrs). When `outcome` is
    given, every card is tagged so its Anki reviews map back to that outcome (RFC-009 review-back)."""
    built = C.build_cards(
        prefix=deck_prefix or DECK_PREFIX,
        course_code=course,
        items=items,
        unit=unit or None,
        now=now,
    )
    d = _srs_dir(vault)
    with (d / "pending.jsonl").open("a") as pend, (d / "ledger.jsonl").open("a") as led:
        for card in built:
            tags = list(card.tags)
            if outcome and outcome_tag(outcome) not in tags:
                tags.append(outcome_tag(outcome))
            pend.write(
                json.dumps(
                    {"deck": card.deck, "front": card.front, "back": card.back, "tags": tags}
                )
                + "\n"
            )
            led.write(
                json.dumps(
                    {
                        "course": course,
                        "outcome": outcome,
                        "deck": card.deck,
                        "front": card.front,
                        "fsrs": card.fsrs,
                        "created": now.isoformat(),
                    }
                )
                + "\n"
            )
    return len(built)


# ---- review-back: Anki reviews → retention signal (RFC-009 §5) ----
# retention.json: {outcome: {reviews, lapses, last_ease, last_ts, review_due}}. GPA/transcript are
# NOT touched — a lapse only marks an outcome review-due so it re-enters the teaching rotation.
def _retention_path(vault: str | Path) -> Path:
    return _srs_dir(vault) / "retention.json"


def load_retention(vault: str | Path) -> dict:
    p = _retention_path(vault)
    return json.loads(p.read_text()) if p.exists() else {}


def ingest_reviews(vault: str | Path, events: list[dict]) -> dict:
    """Fold Anki review events into per-outcome retention. Each event: {outcome, ease(1-4), ts}.
    ease 1 = Again → a lapse → review-due; ease ≥ 3 (Good/Easy) → recovered. Returns a summary."""
    ret = load_retention(vault)
    ingested = 0
    for ev in sorted(events, key=lambda e: e.get("ts") or ""):  # a present-but-null ts sorts first
        o = ev.get("outcome")
        ease = ev.get("ease")
        if not o or ease not in (1, 2, 3, 4):
            continue
        r = ret.setdefault(
            o, {"reviews": 0, "lapses": 0, "last_ease": None, "last_ts": None, "review_due": False}
        )
        r["reviews"] += 1
        r["last_ease"], r["last_ts"] = ease, ev.get("ts")
        if ease == 1:
            r["lapses"] += 1
            r["review_due"] = True
        elif ease >= 3:
            r["review_due"] = False  # a good/easy review clears the flag
        ingested += 1
    _retention_path(vault).write_text(json.dumps(ret, indent=1) + "\n")
    return {"ingested": ingested, "review_due": review_due(vault)}


def review_due(vault: str | Path) -> list[str]:
    """Outcomes currently flagged for review (recently lapsed and not yet recovered)."""
    return sorted(o for o, r in load_retention(vault).items() if r.get("review_due"))


def _lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def due_count(vault: str | Path, now: datetime) -> dict:
    """queued = cards waiting to sync to Anki (the actionable number); created = all-time;
    due = cards whose FSRS schedule says due (from the ledger — see the review-back caveat above)."""
    d = _srs_dir(vault)
    ledger = _lines(d / "ledger.jsonl")
    return {
        "queued": len(_lines(d / "pending.jsonl")),
        "created": len(ledger),
        "due": sum(1 for c in ledger if fsrs.is_due(c.get("fsrs", {}), now)),
        "review_due": len(review_due(vault)),
    }
