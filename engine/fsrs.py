"""FSRS spaced-repetition wrapper (py-fsrs). Isolates the library so storage is plain dicts.

Cards are stored as JSON-able dicts in the Learner Model. Ratings: 1=Again 2=Hard 3=Good 4=Easy.
All functions take an explicit `now` (no hidden clock) so scheduling is deterministic/testable.
RFC §4.4 / §15.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fsrs import Card, Rating, Scheduler

_scheduler = Scheduler()

RATING = {1: Rating.Again, 2: Rating.Hard, 3: Rating.Good, 4: Rating.Easy}


def new_card(now: datetime | None = None) -> dict:
    card = Card()
    if now is not None:                       # honor the explicit clock (module contract) — a fresh
        card.due = _aware(now)                # card is due at `now`, not at import/real time
    return card.to_dict()


def review(card_dict: dict, rating: int, now: datetime) -> dict:
    """Return the updated card dict after a review at `now` with `rating` (1..4)."""
    if rating not in RATING:
        raise ValueError(f"rating must be 1..4, got {rating!r}")
    card = Card.from_dict(card_dict)
    card, _log = _scheduler.review_card(card, RATING[rating], review_datetime=_aware(now))
    return card.to_dict()


def retrievability(card_dict: dict, now: datetime) -> float:
    """Current recall probability (0..1)."""
    card = Card.from_dict(card_dict)
    return float(_scheduler.get_card_retrievability(card, current_datetime=_aware(now)))


def due(card_dict: dict) -> datetime:
    return Card.from_dict(card_dict).due


def is_due(card_dict: dict, now: datetime) -> bool:
    return due(card_dict) <= _aware(now)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
