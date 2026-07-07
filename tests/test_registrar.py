from engine import registrar as R
from engine.state import Course, State, fresh_state
from tests.conftest import rec


def _state():
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    s.courses["CS250"] = Course(title="DSA", credits=4, runs_in=[1, 2], active=True)
    s.courses["PD101"] = Course(title="Behavioral", credits=2, runs_in=[1, 2],
                                active=False, activates_week=9)
    return s


def test_register_courses_from_modules():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    added = R.register_courses(s, root / "courses")
    assert set(added) == {"CS250", "CS301", "CS270", "PD101"}
    assert s.courses["CS250"].active is True and s.courses["CS250"].credits == 4
    assert s.courses["CS250"].unit == "arrays-hashing"      # first unit id
    # PD101 dormant until week 9
    assert s.courses["PD101"].active is False and s.courses["PD101"].activates_week == 9


def test_catalog_lists_available_courses():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    cat = {c["code"] for c in R.catalog(root / "courses")}
    assert cat == {"CS250", "CS301", "CS270", "PD101"}   # _TEMPLATE excluded


def test_enroll_and_drop():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    assert s.courses == {}                                 # un-enrolled by default
    assert R.enroll(s, root / "courses", "CS250") == "enrolled"
    assert s.courses["CS250"].active is True and s.courses["CS250"].unit == "arrays-hashing"
    assert R.enroll(s, root / "courses", "CS250") == "already"   # idempotent
    # PD101 enrolls but stays dormant until week 9
    R.enroll(s, root / "courses", "PD101")
    assert s.courses["PD101"].active is False
    assert R.active_courses(s) == ["CS250"]
    assert R.drop(s, "CS250") is True and "CS250" not in s.courses
    assert R.drop(s, "CS250") is False


def test_enroll_unknown_course_raises():
    import pytest
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    with pytest.raises(KeyError):
        R.enroll(s, root / "courses", "NOPE")


def test_enroll_blocked_by_hold():
    import pytest
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    s.hold = "probation"
    with pytest.raises(R.EnrollError):
        R.enroll(s, root / "courses", "CS250")


def test_enroll_blocked_by_credit_cap():
    import pytest
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    s.enrollment.credit_cap = 5                    # CS250 is 4, CS301 is 4 -> 8 > 5
    R.enroll(s, root / "courses", "CS250")
    with pytest.raises(R.EnrollError):
        R.enroll(s, root / "courses", "CS301")


def test_enroll_copies_grade_weights_and_records():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    R.enroll(s, root / "courses", "CS250", today="2026-07-06")
    assert s.courses["CS250"].grade_weights                      # policy copied from the module
    assert s.enrollment.records[0].code == "CS250"


def test_refresh_computes_gpa_and_standing():
    s = _state()
    records = [rec("a.apply", 0.95, semester=1), rec("b.apply", 0.72, semester=1)]
    R.refresh(s, records)
    assert s.gpa.semester == 3.0 and s.gpa.cumulative == 3.0
    assert s.standing == "good"


def test_probation_sets_hold_and_recovery_clears_it():
    s = _state()
    R.refresh(s, [rec("a.apply", 0.50, course="CS250")])          # F -> GPA 0 -> probation
    assert s.standing == "probation" and s.hold == "probation"
    R.refresh(s, [rec("a.apply", 0.95, course="CS250"), rec("b.apply", 0.95, course="CS250")])
    assert s.standing in ("good", "honors") and s.hold is None


def test_persist_learner_model_writes_file(tmp_path):
    from datetime import datetime, timezone
    (tmp_path / "records").mkdir(parents=True)
    R.persist_learner_model(tmp_path, [rec("two-pointers.apply", 0.9, tier="med")],
                            "UTC", datetime(2026, 7, 10, tzinfo=timezone.utc))
    assert (tmp_path / "records" / "learner_model.json").exists()


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
