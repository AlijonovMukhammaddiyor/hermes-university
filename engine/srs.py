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


def queue_cards(vault: str | Path, course: str, deck_prefix: str, unit: str,
                items: list[dict], now: datetime) -> int:
    """Append professor-supplied [{front,back,tags?}] cards for a proven outcome. Writes the
    push queue (pending.jsonl: deck/front/back/tags) and the ledger (full card + fsrs). Returns count."""
    built = C.build_cards(prefix=deck_prefix or DECK_PREFIX, course_code=course,
                          items=items, unit=unit or None, now=now)
    d = _srs_dir(vault)
    with (d / "pending.jsonl").open("a") as pend, (d / "ledger.jsonl").open("a") as led:
        for card in built:
            pend.write(json.dumps({"deck": card.deck, "front": card.front,
                                   "back": card.back, "tags": card.tags}) + "\n")
            led.write(json.dumps({"course": course, "deck": card.deck, "front": card.front,
                                  "fsrs": card.fsrs, "created": now.isoformat()}) + "\n")
    return len(built)


def _lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def due_count(vault: str | Path, now: datetime) -> dict:
    """queued = cards waiting to sync to Anki (the actionable number); created = all-time;
    due = cards whose FSRS schedule says due (from the ledger — see the review-back caveat above)."""
    d = _srs_dir(vault)
    ledger = _lines(d / "ledger.jsonl")
    return {"queued": len(_lines(d / "pending.jsonl")),
            "created": len(ledger),
            "due": sum(1 for c in ledger if fsrs.is_due(c.get("fsrs", {}), now))}
