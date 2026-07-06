import pytest

from engine import gradebook as gb
from tests.conftest import rec


def test_score_to_band_boundaries():
    assert gb.score_to_band(0.90) == "A"
    assert gb.score_to_band(0.899) == "B"
    assert gb.score_to_band(0.80) == "B"
    assert gb.score_to_band(0.70) == "C"
    assert gb.score_to_band(0.699) == "F"


def test_gpa_credit_weighted():
    # A(4.0)*1 + C(2.0)*1 => 3.0 ; weighting changes it
    recs = [rec("a.apply", 0.95, credits_weight=1.0), rec("b.apply", 0.72, credits_weight=1.0)]
    assert gb.gpa(recs) == 3.0
    recs2 = [rec("a.apply", 0.95, credits_weight=3.0), rec("b.apply", 0.72, credits_weight=1.0)]
    assert gb.gpa(recs2) == pytest.approx((4.0 * 3 + 2.0) / 4, abs=0.01)


def test_gpa_empty_is_none():
    assert gb.gpa([]) is None


def test_semester_and_cumulative():
    recs = [rec("a.apply", 0.95, semester=1), rec("b.apply", 0.72, semester=2)]
    assert gb.semester_gpa(recs, 1) == 4.0
    assert gb.semester_gpa(recs, 2) == 2.0
    assert gb.cumulative_gpa(recs) == 3.0


def test_standing():
    assert gb.standing_for(3.8) == "honors"
    assert gb.standing_for(3.7) == "honors"
    assert gb.standing_for(3.0) == "good"
    assert gb.standing_for(2.49) == "probation"
    assert gb.standing_for(None) == "good"


def test_streak_consecutive_and_gap():
    c, l, last = gb.update_streak(0, 0, None, "2026-07-06", True)
    assert (c, l, last) == (1, 1, "2026-07-06")
    c, l, last = gb.update_streak(c, l, last, "2026-07-07", True)
    assert (c, l, last) == (2, 2, "2026-07-07")
    # same-day repeat is idempotent
    assert gb.update_streak(c, l, last, "2026-07-07", True) == (2, 2, "2026-07-07")
    # a gap resets to 1 but keeps longest
    c, l, last = gb.update_streak(c, l, last, "2026-07-10", True)
    assert (c, l) == (1, 2)


def test_streak_reset_on_incomplete():
    assert gb.update_streak(5, 9, "2026-07-06", "2026-07-07", False) == (0, 9, "2026-07-06")


def test_records_roundtrip(tmp_path):
    p = tmp_path / "grades.jsonl"
    gb.append_record(p, rec("a.apply", 0.9))
    gb.append_record(p, rec("b.apply", 0.6))
    loaded = gb.load_records(p)
    assert len(loaded) == 2 and loaded[1].band == "F"
    assert gb.load_records(tmp_path / "missing.jsonl") == []
