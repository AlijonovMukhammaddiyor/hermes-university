import pytest

from engine import gradebook as gb
from tests.conftest import rec


def test_score_to_band_boundaries():
    assert gb.score_to_band(0.90) == "A"
    assert gb.score_to_band(0.899) == "B"
    assert gb.score_to_band(0.80) == "B"
    assert gb.score_to_band(0.70) == "C"
    assert gb.score_to_band(0.699) == "F"


from engine.state import Course as SC

COURSES = {"CS250": SC(title="DSA", credits=4), "CS270": SC(title="AI", credits=2)}


def test_course_gpa_kind_weighted():
    # two hw records A(4) + C(2) -> equal-weight mean 3.0 with no policy
    assert gb.course_gpa([rec("a", 0.95), rec("b", 0.72)], {}) == 3.0
    # policy weights renormalize over present kinds: hw=A(4), finals=C(2), weights hw.2/finals.8
    recs = [rec("a", 0.95, kind="hw"), rec("b", 0.72, kind="finals")]
    assert gb.course_gpa(recs, {"hw": 0.2, "finals": 0.8}) == pytest.approx(4 * 0.2 + 2 * 0.8, abs=0.01)
    assert gb.course_gpa([], {}) is None


def test_gpa_credit_weighted_over_courses():
    # CS250 (4cr) all A=4.0, CS270 (2cr) all C=2.0 -> (4*4 + 2*2)/6
    recs = [rec("a", 0.95, course="CS250"), rec("b", 0.72, course="CS270")]
    assert gb.gpa(recs, COURSES) == pytest.approx((4 * 4 + 2 * 2) / 6, abs=0.01)
    assert gb.gpa([], COURSES) is None


def test_semester_and_cumulative():
    recs = [rec("a", 0.95, course="CS250", semester=1), rec("b", 0.72, course="CS250", semester=2)]
    assert gb.semester_gpa(recs, COURSES, 1) == 4.0
    assert gb.semester_gpa(recs, COURSES, 2) == 2.0
    assert gb.cumulative_gpa(recs, COURSES) == 3.0


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
