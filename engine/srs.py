"""Anki pipeline (RFC-009 §5): a proven outcome → review cards → retention back.

Writes the push queue `SRS/pending.jsonl` (anki_sync.py uploads, clears on a clean sync) and an
append-only `ledger.jsonl`. Reviews come back via anki_review_pull.py → `ingest_reviews` →
`retention.json`: that is the trustworthy retention signal. `due` here is only the engine's own
initial FSRS estimate and drifts from Anki's scheduler once a card is synced.
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
    """Tag linking a card back to its engine outcome; survives sync so the review-back reader can
    parse it. Anki tags are space-free — outcome ids (e.g. 'f1.apply') are fine."""
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
    """Append [{front,back,tags?}] cards for a proven outcome to the push queue (pending.jsonl) and
    the ledger. A given `outcome` tags each card so its Anki reviews map back (review-back)."""
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


# --- review-back: Anki reviews → retention signal (RFC-009 §5) ---
# retention.json: {outcome: {reviews, lapses, last_ease, last_ts, review_due}}.
# GPA/transcript are NOT touched — a lapse only marks an outcome review-due (re-enters teaching).
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
            r["review_due"] = False
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
    due = cards whose FSRS schedule says due (from the ledger — see review-back caveat above)."""
    d = _srs_dir(vault)
    ledger = _lines(d / "ledger.jsonl")
    return {
        "queued": len(_lines(d / "pending.jsonl")),
        "created": len(ledger),
        "due": sum(1 for c in ledger if fsrs.is_due(c.get("fsrs", {}), now)),
        "review_due": len(review_due(vault)),
    }
