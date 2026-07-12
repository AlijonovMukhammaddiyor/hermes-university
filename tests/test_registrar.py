from datetime import UTC

from engine import registrar as R
from engine.state import Course, State, fresh_state
from tests.conftest import rec


def _state():
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    s.courses["CS250"] = Course(title="DSA", credits=4, runs_in=[1, 2], active=True)
    s.courses["PD101"] = Course(
        title="Behavioral", credits=2, runs_in=[1, 2], active=False, activates_week=9
    )
    return s


def _fixtures():
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def test_register_courses_from_modules():
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    added = R.register_courses(s, _fixtures())
    assert set(added) == {"GEN101", "GEN102"}
    assert s.courses["GEN101"].active is True and s.courses["GEN101"].credits == 3
    assert s.courses["GEN101"].unit == "basics"  # first unit id


def test_catalog_lists_available_courses():
    cat = {c["code"] for c in R.catalog(_fixtures())}
    assert cat == {"GEN101", "GEN102"}


def test_enroll_and_drop():
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    assert s.courses == {}  # un-enrolled by default
    assert R.enroll(s, _fixtures(), "GEN101") == "enrolled"
    assert s.courses["GEN101"].active is True and s.courses["GEN101"].unit == "basics"
    assert R.enroll(s, _fixtures(), "GEN101") == "already"  # idempotent
    R.enroll(s, _fixtures(), "GEN102")
    assert s.courses["GEN101"].active and s.courses["GEN102"].active
    # drop = soft archive (RFC-009): the record is kept, hidden from active views, reversible
    assert R.drop(s, "GEN101") is True
    assert s.courses["GEN101"].status == "archived" and s.courses["GEN101"].active is False
    assert R.drop(s, "GEN101") is False  # already archived
    # restore re-derives status from the filesystem; GEN101 is authored -> placement
    assert R.restore(s, _fixtures(), _fixtures() / "no-uploads", "GEN101") is True
    assert s.courses["GEN101"].status == "placement"


def test_enroll_unknown_course_raises():
    import pytest

    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    with pytest.raises(KeyError):
        R.enroll(s, _fixtures(), "NOPE")


def test_enroll_blocked_by_hold():
    import pytest

    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    s.hold = "probation"
    with pytest.raises(R.EnrollError):
        R.enroll(s, _fixtures(), "GEN101")


def test_enroll_blocked_by_credit_cap():
    import pytest

    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    s.enrollment.credit_cap = 3  # GEN101 is 3, GEN102 is 2 -> 5 > 3
    R.enroll(s, _fixtures(), "GEN101")
    with pytest.raises(R.EnrollError):
        R.enroll(s, _fixtures(), "GEN102")


def test_enroll_copies_grade_weights_and_records():
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    R.enroll(s, _fixtures(), "GEN101", today="2026-07-06")
    assert s.courses["GEN101"].grade_weights  # policy copied from the module
    assert s.enrollment.records[0].code == "GEN101"


def test_refresh_computes_gpa_and_standing():
    s = _state()
    records = [rec("a.apply", 0.95, semester=1), rec("b.apply", 0.72, semester=1)]
    R.refresh(s, records)
    assert s.gpa.semester == 3.0 and s.gpa.cumulative == 3.0
    assert s.standing == "good"


def test_probation_sets_hold_and_recovery_clears_it():
    s = _state()
    R.refresh(s, [rec("a.apply", 0.50, course="CS250")])  # F -> GPA 0 -> probation
    assert s.standing == "probation" and s.hold == "probation"
    R.refresh(s, [rec("a.apply", 0.95, course="CS250"), rec("b.apply", 0.95, course="CS250")])
    assert s.standing in ("good", "honors") and s.hold is None


def test_persist_learner_model_writes_file(tmp_path):
    from datetime import datetime

    (tmp_path / "records").mkdir(parents=True)
    R.persist_learner_model(
        tmp_path,
        [rec("two-pointers.apply", 0.9, tier="med")],
        "UTC",
        datetime(2026, 7, 10, tzinfo=UTC),
    )
    assert (tmp_path / "records" / "learner_model.json").exists()


def test_activate_due_courses_by_week():
    s = _state()
    s.position.week_in_semester = 3
    assert "PD101" not in R.activate_due_courses(s)  # activates at 9
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


def test_promote_activation_agrees_with_weekly_cron():
    # a course that activates in week 1 must be active right after promotion — the same result
    # activate_due_courses gives at that position (regression: promote required activates_week is None)
    s = _state()
    s.courses["WK1"] = Course(title="Wk1", credits=2, runs_in=[2], active=False, activates_week=1)
    s2, status = R.promote_or_graduate(
        _clone(s), "B", "2026-10-01", [rec("x.apply", 0.9, semester=1)]
    )
    assert status == "promoted" and s2.position.week_in_semester == 1
    assert s2.courses["WK1"].active is True  # promote activated it (week 1 already reached)
    # …and it matches what the weekly cron would compute at the same position
    s3 = _clone(s2)
    for c in s3.courses.values():
        c.active = False
    R.activate_due_courses(s3)
    promote_active = {k for k, c in s2.courses.items() if c.active}
    cron_active = {k for k, c in s3.courses.items() if c.active}
    assert promote_active == cron_active


def test_graduation_on_semester_2_finals_awards_the_degree():
    s = _state()
    s.position.semester = 2
    s2, status = R.promote_or_graduate(s, "A", "2027-01-01", [rec("x.apply", 0.95, semester=2)])
    assert status == "graduated"
    assert s2.degree.awarded_on == "2027-01-01"  # the whole point of graduating — must be set


def test_final_finals_failure_does_not_award_the_degree():
    # failing the final semester's finals → remediation, and NO degree is awarded (guards the
    # `sem >= total_semesters and passed` half of the award condition)
    s = _state()
    s.position.semester = 2
    s2, status = R.promote_or_graduate(s, "F", "2027-01-01", [rec("x.apply", 0.5, semester=2)])
    assert status == "remediation"
    assert s2.degree.awarded_on is None


def test_activate_due_courses_deactivates_stale_semester_course():
    # a semester-1-only course must be deactivated once the learner is in semester 2 (the branch the
    # weekly `advance` cron relies on to retire courses that no longer run)
    s = _state()
    s.courses["S1ONLY"] = Course(title="S1", credits=2, runs_in=[1], active=True)
    s.position.semester = 2
    R.activate_due_courses(s)
    assert s.courses["S1ONLY"].active is False


def test_archived_course_is_never_reactivated():
    # regression: a soft-dropped course must stay dropped through both the weekly `advance` cron and
    # promotion — otherwise its credits silently re-enter the cap and block a replacement enrollment.
    s = fresh_state(name="M", timezone="UTC", started_on="2026-07-06")
    R.enroll(s, _fixtures(), "GEN101")  # 3cr, active
    assert R.archive(s, "GEN101") is True
    R.activate_due_courses(s)  # weekly cron
    assert s.courses["GEN101"].active is False and s.courses["GEN101"].status == "archived"
    s2, status = R.promote_or_graduate(s, "B", "2026-10-01", [rec("x.apply", 0.9, semester=1)])
    assert status == "promoted"
    assert s2.courses["GEN101"].active is False  # promotion must not resurrect it
    # …so its credits don't count against the cap and a replacement still enrolls
    s2.enrollment.credit_cap = 3
    assert R.enroll(s2, _fixtures(), "GEN102") == "enrolled"


def test_advance_cli_records_streak_and_advances_week(tmp_path):
    # end-to-end coverage of the record_day tuple-unpacking + advance_week + activate_due_courses
    # wiring the `day close` / `advance` CLIs drive (previously untested).
    from engine.cli import main

    out = tmp_path / "Registrar" / "state.json"
    out.parent.mkdir(parents=True)
    main(
        [
            "state",
            "init",
            "--name",
            "M",
            "--tz",
            "UTC",
            "--started",
            "2026-07-06",
            "--out",
            str(out),
        ]
    )
    assert (
        main(["day", "close", "--vault", str(tmp_path), "--today", "2026-07-06", "--all-done"]) == 0
    )
    s = R.load_state(tmp_path)
    assert s.streak.current == 1 and s.streak.last_completed_date == "2026-07-06"
    assert main(["advance", "--vault", str(tmp_path), "--weeks", "1"]) == 0
    s = R.load_state(tmp_path)
    assert s.position.week_in_semester == 2 and s.position.absolute_week == 2


def test_write_dashboard_emits_frontmatter(tmp_path):
    s = _state()
    R.refresh(s, [rec("a.apply", 0.9, semester=1)])
    R.write_dashboard(tmp_path, s, "2026-07-06")
    status = (tmp_path / "Registrar" / "status.md").read_text()
    assert "type: status" in status and "gpa_cumulative: 4.0" in status
    assert (tmp_path / "Registrar" / "gpa-2026-07-06.md").exists()


def _clone(s: State) -> State:
    return State.model_validate(s.model_dump())
