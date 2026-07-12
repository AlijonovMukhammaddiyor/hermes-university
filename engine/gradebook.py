"""Grades → GPA / standing / streak. The ONLY place these numbers are computed. RFC §4.2."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

Band = Literal["A", "B", "C", "F"]
# str-keyed (not Band-keyed) so band strings threaded through the code can index it without casts
BAND_POINTS: dict[str, float] = {"A": 4.0, "B": 3.0, "C": 2.0, "F": 0.0}
# Grade scale (RFC / program): A ≥0.90, B ≥0.80, C ≥0.70, else F.
BAND_CUTOFFS: list[tuple[float, Band]] = [(0.90, "A"), (0.80, "B"), (0.70, "C")]

HONORS_GPA = 3.7
PROBATION_GPA = 2.5


class Proof(BaseModel):
    source: str  # leetcode | judge0 | rubric | self-explain | ...
    passed: bool
    ref: str | None = None


class GradeRecord(BaseModel):
    ts: str  # ISO timestamp (UTC)
    course: str
    outcome: str  # "<topic>.<bloom>" e.g. "two-pointers.apply"
    kind: Literal["hw", "quiz", "exam", "midterm", "finals"]
    band: Band
    score: float  # 0..1
    semester: int
    proof: Proof
    # Learner-model signal (optional; set by the grader):
    topic: str | None = None  # defaults to outcome prefix if omitted
    tier: Literal["easy", "med", "hard"] | None = None
    weak_areas: list[str] = []  # misconception tags from grading

    def topic_of(self) -> str:
        return self.topic or topic_of_outcome(self.outcome)


def topic_of_outcome(outcome_id: str) -> str:
    """The learner-model topic key for an outcome id (`<topic>.<bloom>` → `<topic>`). The ONE place
    this mapping lives, so a record's `topic_of()` and any caller (e.g. the `plan` difficulty lookup)
    can never key the topics dict differently."""
    return outcome_id.rsplit(".", 1)[0]


def score_to_band(score: float) -> Band:
    for cutoff, band in BAND_CUTOFFS:
        if score >= cutoff:
            return band
    return "F"


def band_meets(band: str, threshold: float = 0.8) -> bool:
    """True if `band` clears an outcome's mastery threshold (mapped to a band cutoff). Default 0.8 → B.
    The single bar for 'mastered / placed-out / passed', consistent with the ≥B promotion gate."""
    return BAND_POINTS.get(band, 0.0) >= BAND_POINTS[score_to_band(threshold)]


def course_gpa(records: Iterable[GradeRecord], weights: dict[str, float] | None) -> float | None:
    """One course's GPA (0–4): kind-weighted mean of grade points, renormalized over the kinds that
    actually have records. Deterministic — the grading policy comes from the course, not the model."""
    from collections import defaultdict

    by_kind: dict[str, list[float]] = defaultdict(list)
    for r in records:
        by_kind[r.kind].append(BAND_POINTS[r.band])
    if not by_kind:
        return None
    means = {k: sum(v) / len(v) for k, v in by_kind.items()}
    w = weights or {}
    tw = sum(w.get(k, 0.0) for k in means)
    if tw == 0:  # no policy weight for present kinds → equal-weight
        return round(sum(means.values()) / len(means), 2)
    return round(sum(means[k] * w.get(k, 0.0) for k in means) / tw, 2)


def gpa(records: Iterable[GradeRecord], courses: dict) -> float | None:
    """Credit-weighted mean of course GPAs (courses that have records). `courses` maps code →
    an object with `.credits` and `.grade_weights` (state.Course)."""
    records = list(records)
    pts = cr = 0.0
    for code, c in courses.items():
        cg = course_gpa((r for r in records if r.course == code), getattr(c, "grade_weights", {}))
        if cg is None:
            continue
        pts += cg * c.credits
        cr += c.credits
    return round(pts / cr, 2) if cr else None


def semester_gpa(records: Iterable[GradeRecord], courses: dict, semester: int) -> float | None:
    return gpa((r for r in records if r.semester == semester), courses)


def cumulative_gpa(records: Iterable[GradeRecord], courses: dict) -> float | None:
    return gpa(records, courses)


def standing_for(gpa_value: float | None) -> Literal["good", "honors", "probation"]:
    if gpa_value is None:
        return "good"
    if gpa_value >= HONORS_GPA:
        return "honors"
    if gpa_value < PROBATION_GPA:
        return "probation"
    return "good"


def update_streak(
    current: int, longest: int, last_completed: str | None, today: str, all_done: bool
) -> tuple[int, int, str | None]:
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
