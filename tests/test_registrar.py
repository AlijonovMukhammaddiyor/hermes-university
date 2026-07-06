from engine import registrar as R
from engine.state import Course, State, fresh_state
from tests.conftest import rec


def _state():
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    s.courses["CS250"] = Course(title="DSA", credits=4, runs_in=[1, 2], active=True)
    s.courses["PD101"] = Course(title="Behavioral", credits=2, runs_in=[1, 2],
                                active=False, activates_week=9)
    return s


def test_refresh_computes_gpa_and_standing():
    s = _state()
    records = [rec("a.apply", 0.95, semester=1), rec("b.apply", 0.72, semester=1)]
    R.refresh(s, records)
    assert s.gpa.semester == 3.0 and s.gpa.cumulative == 3.0
    assert s.standing == "good"


def test_activate_due_courses_by_week():
    s = _state()
    s.position.week_in_semester = 3
    assert "PD101" not in R.activate_due_courses(s)   # activates at 9
    assert s.courses["PD101"].active is False
    s.position.week_in_semester = 9
    assert "PD101" in R.activate_due_courses(s)
    assert s.courses["PD101"].active is True


def test_promote_on_pass_and_remediation_on_fail():
    s = _state()
    records = [rec("x.apply", 0.9, semester=1)]
    s2, status = R.promote_or_graduate(_clone(s), "B", "2026-10-01", records)
    assert status == "promoted"
    assert s2.position.semester == 2 and s2.position.week_in_semester == 1
    assert s2.position.phase == "depth" and len(s2.history) == 1

    s3, status3 = R.promote_or_graduate(_clone(s), "F", "2026-10-01", records)
    assert status3 == "remediation" and s3.position.semester == 1


def test_graduation_on_semester_2_finals():
    s = _state(); s.position.semester = 2
    _, status = R.promote_or_graduate(s, "A", "2027-01-01", [rec("x.apply", 0.95, semester=2)])
    assert status == "graduated"


def test_write_dashboard_emits_frontmatter(tmp_path):
    s = _state(); R.refresh(s, [rec("a.apply", 0.9, semester=1)])
    R.write_dashboard(tmp_path, s, "2026-07-06")
    status = (tmp_path / "Registrar" / "status.md").read_text()
    assert "type: status" in status and "gpa_cumulative: 4.0" in status
    assert (tmp_path / "Registrar" / "gpa-2026-07-06.md").exists()


def _clone(s: State) -> State:
    return State.model_validate(s.model_dump())
