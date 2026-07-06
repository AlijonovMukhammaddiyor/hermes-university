"""Grades → GPA / standing / streak. The ONLY place these numbers are computed. RFC §4.2."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Literal

from pydantic import BaseModel

Band = Literal["A", "B", "C", "F"]
BAND_POINTS: dict[Band, float] = {"A": 4.0, "B": 3.0, "C": 2.0, "F": 0.0}
# Grade scale (RFC / program): A ≥0.90, B ≥0.80, C ≥0.70, else F.
BAND_CUTOFFS: list[tuple[float, Band]] = [(0.90, "A"), (0.80, "B"), (0.70, "C")]

HONORS_GPA = 3.7
PROBATION_GPA = 2.5


class Proof(BaseModel):
    source: str            # leetcode | judge0 | rubric | self-explain | ...
    passed: bool
    ref: str | None = None


class GradeRecord(BaseModel):
    ts: str                # ISO timestamp (UTC)
    course: str
    outcome: str           # "<topic>.<bloom>" e.g. "two-pointers.apply"
    kind: Literal["hw", "quiz", "exam", "midterm", "finals"]
    band: Band
    score: float           # 0..1
    credits_weight: float  # contribution weight
    semester: int
    proof: Proof
    # Learner-model signal (optional; set by the grader):
    topic: str | None = None            # defaults to outcome prefix if omitted
    tier: Literal["easy", "med", "hard"] | None = None
    weak_areas: list[str] = []          # misconception tags from grading

    def topic_of(self) -> str:
        return self.topic or self.outcome.rsplit(".", 1)[0]


def score_to_band(score: float) -> Band:
    for cutoff, band in BAND_CUTOFFS:
        if score >= cutoff:
            return band
    return "F"


def gpa(records: Iterable[GradeRecord]) -> float | None:
    """Credit-weighted GPA. None when there are no weighted records."""
    pts = wt = 0.0
    for r in records:
        pts += BAND_POINTS[r.band] * r.credits_weight
        wt += r.credits_weight
    if wt == 0:
        return None
    return round(pts / wt, 2)


def semester_gpa(records: Iterable[GradeRecord], semester: int) -> float | None:
    return gpa(r for r in records if r.semester == semester)


def cumulative_gpa(records: Iterable[GradeRecord]) -> float | None:
    return gpa(records)


def standing_for(gpa_value: float | None) -> Literal["good", "honors", "probation"]:
    if gpa_value is None:
        return "good"
    if gpa_value >= HONORS_GPA:
        return "honors"
    if gpa_value < PROBATION_GPA:
        return "probation"
    return "good"


def update_streak(current: int, longest: int, last_completed: str | None,
                  today: str, all_done: bool) -> tuple[int, int, str | None]:
    """Advance the daily streak. `today`/`last_completed` are YYYY-MM-DD.

    all_done False resets to 0. Consecutive calendar days extend; a gap resets to 1.
    Idempotent for a repeated same-day all_done call.
    """
    if not all_done:
        return 0, longest, last_completed
    td = date.fromisoformat(today)
    if last_completed == today:
        return current, longest, last_completed  # already counted today
    if last_completed is not None and date.fromisoformat(last_completed) == td - timedelta(days=1):
        new = current + 1
    else:
        new = 1
    return new, max(longest, new), today


def load_records(path: str | Path) -> list[GradeRecord]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[GradeRecord] = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(GradeRecord.model_validate_json(line))
    return out


def append_record(path: str | Path, record: GradeRecord) -> None:
    with Path(path).open("a") as f:
        f.write(record.model_dump_json() + "\n")
