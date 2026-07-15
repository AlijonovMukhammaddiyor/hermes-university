"""FSRS spaced-repetition wrapper (py-fsrs). Isolates the library so storage is plain dicts.

Cards are stored as JSON-able dicts in the Learner Model. Ratings: 1=Again 2=Hard 3=Good 4=Easy.
All functions take an explicit `now` (no hidden clock) so scheduling is deterministic/testable.
RFC §4.4 / §15.
"""
# The one place py-fsrs is touched: it converts the library's typed CardDict to/from the plain
# JSON-able dicts the engine stores, and scopes the library's attribute noise to this wrapper.
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from fsrs import Card, Rating, Scheduler

_scheduler = Scheduler()

RATING = {1: Rating.Again, 2: Rating.Hard, 3: Rating.Good, 4: Rating.Easy}


def new_card(now: datetime | None = None) -> dict:
    card = Card()
    if now is not None:  # fresh card is due at now, not real time (explicit-clock contract)
        card.due = _aware(now)
    return dict(card.to_dict())


def review(card_dict: dict, rating: int, now: datetime) -> dict:
    """Return the updated card dict after a review at `now` with `rating` (1..4)."""
    if rating not in RATING:
        raise ValueError(f"rating must be 1..4, got {rating!r}")
    card = Card.from_dict(cast(Any, card_dict))
    card, _log = _scheduler.review_card(card, RATING[rating], review_datetime=_aware(now))
    return dict(card.to_dict())


def due(card_dict: dict) -> datetime:
    return Card.from_dict(cast(Any, card_dict)).due


def is_due(card_dict: dict, now: datetime) -> bool:
    return due(card_dict) <= _aware(now)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
