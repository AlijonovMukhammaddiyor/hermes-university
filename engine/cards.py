"""Spaced-repetition card generation (RFC §7, D8).

Builds card records with an initial FSRS state; the professor supplies front/back. Pushed to
AnkiWeb by `engine.anki_sync` at deploy-time. Pure/testable — no network, no Anki runtime.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from . import fsrs


class Card(BaseModel):
    deck: str
    front: str
    back: str
    tags: list[str] = []
    fsrs: dict  # engine.fsrs card dict (initial schedule)


def deck_name(prefix: str, course_code: str, unit: str | None = None) -> str:
    parts = [prefix, course_code] + ([unit] if unit else [])
    return "::".join(parts)


def build_card(
    *,
    prefix: str,
    course_code: str,
    front: str,
    back: str,
    unit: str | None = None,
    tags: list[str] | None = None,
    now: datetime | None = None,
) -> Card:
    return Card(
        deck=deck_name(prefix, course_code, unit),
        front=front.strip(),
        back=back.strip(),
        tags=list(tags or []),
        fsrs=fsrs.new_card(now or datetime.now(UTC)),
    )


def build_cards(
    *,
    prefix: str,
    course_code: str,
    items: list[dict],
    unit: str | None = None,
    now: datetime | None = None,
) -> list[Card]:
    """items: [{front, back, tags?}] supplied by the professor for a proven outcome."""
    return [
        build_card(
            prefix=prefix,
            course_code=course_code,
            unit=unit,
            now=now,
            front=it["front"],
            back=it["back"],
            tags=it.get("tags", []),
        )
        for it in items
    ]
