from engine.learner_model import (
    LearnerModel,
    difficulty_for,
    next_topic,
    recompute,
    weak_areas,
)
from tests.conftest import dt, rec


def build(records, tz="Asia/Tashkent", now="2026-07-10T00:00:00+00:00"):
    return recompute(LearnerModel(), records, tz=tz, now=dt(now))


def test_topic_proficiency_and_ceiling():
    recs = [
        rec("two-pointers.apply", 0.9, tier="med"),
        rec("two-pointers.apply", 0.8, tier="hard"),
        rec("graphs.apply", 0.5, tier="easy", weak=["wrong-invariant"]),
    ]
    m = build(recs)
    assert m.topics["two-pointers"].proficiency == 0.85
    assert m.topics["two-pointers"].difficulty_ceiling == "hard"  # hardest passed tier
    assert m.topics["graphs"].proficiency == 0.5
    assert "wrong-invariant" in m.topics["graphs"].error_tags


def test_weak_areas_sorted_weakest_first():
    recs = [rec("a.apply", 0.6), rec("b.apply", 0.72), rec("c.apply", 0.95)]
    m = build(recs)
    assert weak_areas(m) == ["a", "b"]  # c (0.95) is above threshold
    assert "c" not in weak_areas(m)


def test_difficulty_for_ramps_with_proficiency():
    m = build([rec("dp.apply", 0.95, tier="med")])
    assert difficulty_for(m, "dp") == "med"  # proficient -> at ceiling
    m2 = build([rec("dp.apply", 0.72, tier="hard")])
    assert difficulty_for(m2, "dp") == "med"  # weak -> one below ceiling(hard)
    assert difficulty_for(m2, "unknown-topic") == "easy"


def test_difficulty_baseline_floors_a_strong_learner():
    m = build([])  # no history
    assert difficulty_for(m, "graphs", baseline="med") == "med"  # new topic starts at baseline
    m2 = build([rec("dp.apply", 0.72, tier="hard")])  # weak -> would be "med"
    assert difficulty_for(m2, "dp", baseline="med") == "med"  # not below baseline
    m3 = build([rec("dp.apply", 0.5, tier="easy")])  # weak, ceiling easy -> below is easy
    assert difficulty_for(m3, "dp", baseline="med") == "med"  # floored up to baseline


def test_best_hours_from_completion_hours():
    # 22:00 Tashkent == 17:00 UTC ; put 3 records there, 1 elsewhere
    recs = [rec("x.apply", 0.9, ts="2026-07-06T17:00:00+00:00") for _ in range(3)]
    recs.append(rec("y.apply", 0.9, ts="2026-07-06T05:00:00+00:00"))
    m = build(recs)
    assert m.routine.best_hours[0] == "22:00-00:00"  # the slot skills/docs read for scheduling


def test_proficiency_falls_back_to_all_time_when_window_empty():
    # every record predates the 14-day trend window → the windowed list is empty and recompute must
    # fall back to all-time (`or recs`), not crash on len([])/0 for an inactive learner.
    recs = [rec("dp.apply", 0.9, ts="2026-06-01T20:00:00+00:00")]
    m = build(recs, now="2026-07-10T00:00:00+00:00")
    assert m.topics["dp"].proficiency == 0.9


def test_pace_task_cap_and_rest_day():
    recs = [
        rec("a.apply", 0.9, ts="2026-07-06T10:00:00+00:00"),
        rec("b.apply", 0.9, ts="2026-07-06T11:00:00+00:00"),
        rec("c.apply", 0.9, ts="2026-07-07T10:00:00+00:00"),
    ]
    m = build(recs)
    assert m.pace.task_cap_observed == 2  # two on 07-06 (local)
    assert m.pace.rest_day is not None


def test_next_topic_respects_dag():
    units = [
        {"outcome": "arrays.apply", "depends_on": []},
        {"outcome": "two-pointers.apply", "depends_on": ["arrays.apply"]},
        {"outcome": "sliding-window.apply", "depends_on": ["two-pointers.apply"]},
    ]
    assert next_topic(units, mastered=set()) == "arrays.apply"
    assert next_topic(units, {"arrays.apply"}) == "two-pointers.apply"
    assert next_topic(units, {"arrays.apply", "two-pointers.apply"}) == "sliding-window.apply"
    assert next_topic(units, {"arrays.apply", "two-pointers.apply", "sliding-window.apply"}) is None
