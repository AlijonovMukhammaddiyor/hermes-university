"""Learner Model — the personalization asset (RFC §4.4 / §15).

Engine-owned. Aggregate stats (proficiency, difficulty ceiling, misconceptions, routine, pace) are
RECOMPUTED from the grade log; per-outcome FSRS card states are PERSISTED (updated per review).
Adaptation reads a trailing window so it tracks trends, not a single day. Exposes the query API the
skills call to personalize topics / difficulty / reviews / routine.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from .gradebook import GradeRecord

TIER_ORDER = ["easy", "med", "hard"]
WEAK_THRESHOLD = 0.75


class TopicStat(BaseModel):
    proficiency: float = 0.0            # 0..1 (windowed mean score)
    difficulty_ceiling: str = "easy"    # hardest passed tier
    error_tags: list[str] = []          # recent misconceptions
    attempts: int = 0


class Routine(BaseModel):
    best_hours: list[str] = []          # e.g. ["20:00-22:00"]
    adherence_by_slot: dict[str, int] = {}


class Pace(BaseModel):
    task_cap_observed: int = 0
    rest_day: str | None = None         # weekday name with fewest completions


class OutcomeState(BaseModel):
    mastery_band: str | None = None
    fsrs: dict | None = None            # engine.fsrs card dict (persisted)
    attempts: int = 0
    last_seen: str | None = None
    misconceptions: list[str] = []


class LearnerModel(BaseModel):
    outcomes: dict[str, OutcomeState] = Field(default_factory=dict)
    topics: dict[str, TopicStat] = Field(default_factory=dict)
    routine: Routine = Field(default_factory=Routine)
    pace: Pace = Field(default_factory=Pace)
    prefs: dict = Field(default_factory=dict)
    goals: dict = Field(default_factory=dict)
    trend_window_days: int = 14


def _hour_slot(h: int) -> str:
    return f"{h:02d}:00-{(h + 2) % 24:02d}:00"


def recompute(model: LearnerModel, records: list[GradeRecord], *, tz: str,
              now: datetime, window_days: int | None = None) -> LearnerModel:
    """Recompute aggregate stats + per-outcome mastery from the grade log, in place.
    FSRS card states already on the model are preserved (reviews update them separately)."""
    window = window_days if window_days is not None else model.trend_window_days
    cutoff = now - timedelta(days=window)
    zone = ZoneInfo(tz)

    def in_window(r: GradeRecord) -> bool:
        return _parse(r.ts) >= cutoff

    # --- per-topic proficiency / ceiling / misconceptions (windowed, fallback all-time) ---
    by_topic: dict[str, list[GradeRecord]] = defaultdict(list)
    for r in records:
        by_topic[r.topic_of()].append(r)
    topics: dict[str, TopicStat] = {}
    for topic, recs in by_topic.items():
        win = [r for r in recs if in_window(r)] or recs
        prof = round(sum(r.score for r in win) / len(win), 3)
        passed_tiers = [r.tier for r in recs if r.band != "F" and r.tier]
        ceiling = max(passed_tiers, key=TIER_ORDER.index) if passed_tiers else _infer_tier(prof)
        errs = [t for r in win for t in r.weak_areas]
        top_errs = [t for t, _ in Counter(errs).most_common(5)]
        topics[topic] = TopicStat(proficiency=prof, difficulty_ceiling=ceiling,
                                   error_tags=top_errs, attempts=len(recs))
    model.topics = topics

    # --- per-outcome mastery (latest band) + misconceptions ---
    for r in sorted(records, key=lambda x: x.ts):
        st = model.outcomes.setdefault(r.outcome, OutcomeState())
        st.mastery_band = r.band
        st.attempts += 0  # attempts tracked below to avoid double count on recompute
        st.last_seen = r.ts
        if r.weak_areas:
            st.misconceptions = r.weak_areas
    for oid, recs in _group(records, key=lambda r: r.outcome).items():
        model.outcomes[oid].attempts = len(recs)

    # --- routine: completion-hour histogram (in learner tz) ---
    slots: Counter = Counter()
    for r in records:
        local = _parse(r.ts).astimezone(zone)
        slots[_hour_slot(local.hour)] += 1
    model.routine.adherence_by_slot = dict(slots)
    model.routine.best_hours = [s for s, _ in slots.most_common(2)]

    # --- pace: max tasks/day + quietest weekday ---
    by_day: Counter = Counter()
    by_weekday: Counter = Counter()
    for r in records:
        local = _parse(r.ts).astimezone(zone)
        by_day[local.date().isoformat()] += 1
        by_weekday[local.strftime("%A")] += 1
    model.pace.task_cap_observed = max(by_day.values(), default=0)
    if by_weekday:
        all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        model.pace.rest_day = min(all_days, key=lambda d: by_weekday.get(d, 0))
    return model


# --------------------------- query API (skills call these) ---------------------------

def weak_areas(model: LearnerModel, threshold: float = WEAK_THRESHOLD) -> list[str]:
    """Topics below the proficiency threshold, weakest first."""
    weak = [(t, s.proficiency) for t, s in model.topics.items() if s.proficiency < threshold]
    return [t for t, _ in sorted(weak, key=lambda x: x[1])]


def difficulty_for(model: LearnerModel, topic: str) -> str:
    """Next problem tier: at the ceiling once proficient, one below while weak."""
    st = model.topics.get(topic)
    if st is None:
        return "easy"
    if st.proficiency >= 0.85:
        return st.difficulty_ceiling
    return _tier_below(st.difficulty_ceiling)


def best_slot(model: LearnerModel) -> str | None:
    return model.routine.best_hours[0] if model.routine.best_hours else None


def next_topic(units: list[dict], mastered: set[str]) -> str | None:
    """First outcome whose prereqs are all mastered and itself is not, respecting the DAG.
    `units`: ordered [{"outcome": id, "depends_on": [ids]}]. Returns an outcome id or None."""
    for u in units:
        oid = u["outcome"]
        if oid in mastered:
            continue
        if all(dep in mastered for dep in u.get("depends_on", [])):
            return oid
    return None


# --------------------------- helpers ---------------------------

def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _infer_tier(prof: float) -> str:
    return "easy" if prof < 0.7 else "med" if prof < 0.85 else "hard"


def _tier_below(tier: str) -> str:
    i = TIER_ORDER.index(tier)
    return TIER_ORDER[max(0, i - 1)]


def _group(items, key):
    out: dict = defaultdict(list)
    for it in items:
        out[key(it)].append(it)
    return out
