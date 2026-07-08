"""Course lifecycle state machine + authoring gate + scaffold (RFC-009)."""

from pathlib import Path

from engine import registrar as R
from engine.authoring import authored_report, authoring_status, report_present
from engine.course import load_course
from engine.scaffold import scaffold_course
from engine.state import fresh_state

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _state():
    return fresh_state(name="M", timezone="UTC", started_on="2026-07-06")


# ---- authoring gate + status derivation ----
def test_authored_report_gates_on_full_depth():
    c = load_course(FIXTURES / "GEN101" / "course.yaml")
    assert authored_report(c, FIXTURES / "GEN101")["authored"] is True
    c2 = load_course(FIXTURES / "GEN102" / "course.yaml")
    rep = authored_report(c2, FIXTURES / "GEN102")
    assert rep["authored"] is False and rep["missing_for_authored"]


def test_report_present_ignores_scaffold_markers(tmp_path):
    up = tmp_path / "AG201"
    up.mkdir()
    (up / ".gitkeep").write_text("")
    (up / "RESEARCH-PROMPT.md").write_text("prompt")
    assert report_present(tmp_path, "AG201") is False        # only markers -> no report
    (up / "report.md").write_text("the cited research report")
    assert report_present(tmp_path, "AG201") is True


def test_authoring_status_tracks_the_filesystem(tmp_path):
    scaffold_course(tmp_path, "NEW101", "New Course", "learn things")
    cf = tmp_path / "NEW101" / "course.yaml"
    up = tmp_path / "Uploads"
    assert authoring_status(cf, up, "NEW101") == "researching"       # stub, no report
    (up / "NEW101").mkdir(parents=True)
    (up / "NEW101" / "report.md").write_text("report")
    assert authoring_status(cf, up, "NEW101") == "authoring"         # report in, not built
    assert authoring_status(FIXTURES / "GEN101" / "course.yaml", up, "GEN101") == "placement"


# ---- scaffold ----
def test_scaffold_creates_valid_unauthored_stub(tmp_path):
    path = scaffold_course(tmp_path, "AB101", "Alpha Beta", "become great", credits=4)
    c = load_course(path)                                    # validates
    assert c.id == "AB101" and c.credits == 4 and "great" in c.north_star
    assert authored_report(c, path.parent)["authored"] is False
    assert (tmp_path / "AB101" / "research").is_dir()


def test_scaffold_refuses_to_clobber(tmp_path):
    scaffold_course(tmp_path, "AB101", "Alpha", "x")
    try:
        scaffold_course(tmp_path, "AB101", "Alpha", "x")
        raise AssertionError("expected FileExistsError")
    except FileExistsError:
        pass


# ---- transitions ----
def test_enroll_sets_status_from_authored_gate():
    s = _state()
    R.enroll(s, FIXTURES, "GEN101")          # authored -> placement
    assert s.courses["GEN101"].status == "placement"
    R.enroll(s, FIXTURES, "GEN102")          # not authored -> researching
    assert s.courses["GEN102"].status == "researching"


def test_activate_then_archive_then_restore():
    s = _state()
    R.enroll(s, FIXTURES, "GEN101")
    assert R.activate_course(s, "GEN101") is True and s.courses["GEN101"].status == "active"
    assert R.archive(s, "GEN101", "2026-07-08") is True
    sc = s.courses["GEN101"]
    assert sc.status == "archived" and sc.active is False and sc.archived_on == "2026-07-08"
    assert any(r.code == "GEN101" and r.dropped_on for r in s.enrollment.records)
    assert R.archive(s, "GEN101") is False                 # already archived
    assert R.restore(s, FIXTURES, FIXTURES / "no-up", "GEN101") is True
    assert s.courses["GEN101"].status == "placement" and s.courses["GEN101"].archived_on is None


def test_refresh_course_status_only_moves_pipeline_courses():
    s = _state()
    R.enroll(s, FIXTURES, "GEN101")
    R.activate_course(s, "GEN101")                          # now active (live)
    # refresh must NOT drag a live course back into the authoring pipeline
    assert R.refresh_course_status(s, FIXTURES, FIXTURES / "no-up", "GEN101") is None
    assert s.courses["GEN101"].status == "active"


def test_refresh_reconciles_a_draft_course():
    # a course loaded from an older state.json defaults to 'draft'; sync-status must re-derive it
    s = _state()
    R.enroll(s, FIXTURES, "GEN101")
    s.courses["GEN101"].status = "draft"                    # simulate the pre-RFC-009 default
    assert R.refresh_course_status(s, FIXTURES, FIXTURES / "no-up", "GEN101") == "placement"
    assert s.courses["GEN101"].status == "placement"


def test_delete_removes_state_entry():
    s = _state()
    R.enroll(s, FIXTURES, "GEN101")
    assert R.delete(s, "GEN101") is True and "GEN101" not in s.courses
    assert R.delete(s, "GEN101") is False
