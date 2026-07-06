import pytest
from pydantic import ValidationError

from engine.state import Course, State, fresh_state


def test_fresh_state_defaults():
    s = fresh_state(name="the maintainer", timezone="Asia/Tashkent", started_on="2026-07-06")
    assert s.schema_version == 3
    assert s.position.semester == 1 and s.position.week_in_semester == 1
    assert s.standing == "good" and s.gpa.cumulative is None
    assert s.learner.name == "the maintainer" and s.learner.persona_stage == "guide"
    assert s.program.total_semesters == 2


def test_save_load_roundtrip(tmp_path):
    s = fresh_state(name="X", timezone="UTC", started_on="2026-07-06")
    s.courses["CS250"] = Course(title="DSA", credits=4, active=True, unit="arrays-hashing")
    f = tmp_path / "state.json"
    s.save(f)
    back = State.load(f)
    assert back.courses["CS250"].title == "DSA"
    assert back == s


def test_rejects_bad_schema_version(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text('{"schema_version": 2}')
    with pytest.raises(ValidationError):
        State.load(f)


def test_rejects_bad_standing():
    with pytest.raises(ValidationError):
        State(standing="excellent")  # not in Literal
