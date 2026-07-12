"""Authored-gate + lifecycle derivation (RFC-007/009).

One home for the gate, reused by CLI `course validate` and the registrar so no surface
re-implements it.
"""

from __future__ import annotations

import re
from pathlib import Path

from .course import Course, load_course
from .state import CourseStatus

_URL = re.compile(r"https?://[^\s)\]>]+")
_UPLOAD_MARKERS = {".gitkeep", "README.md", "RESEARCH-PROMPT.md", "PROMPT.md"}


def authored_report(course: Course, course_dir: Path) -> dict:
    """The authored gate (RFC-004/007). `course_dir` is the course's own folder (holds
    `research/dossier.md`); returns the JSON the CLI emits."""
    teaching = [u for u in course.units if not u.id.endswith("finals")]
    dossier = course_dir / "research" / "dossier.md"
    dtext = dossier.read_text() if dossier.exists() else ""
    n_urls = len(set(_URL.findall(dtext)))
    has_dossier = (
        n_urls >= 5
        and "confidence" in dtext.lower()
        and any(
            s in dtext.lower()
            for s in ("open question", "couldn't verify", "could not verify", "cannot verify")
        )
    )
    mm = course.mastery_model
    has_mastery = bool(mm and mm.excellence_bar and mm.staying_current)
    aud = course.audience
    has_audience = bool(aud and aud.good_fit and aud.not_a_fit)
    missing: list[str] = []
    if not course.description:
        missing.append("description")
    if not has_audience:
        missing.append("audience(who-it's-for + not-for)")
    if not all(u.resources for u in teaching):
        missing.append("unit-resources")
    if not all(u.sessions for u in teaching):
        missing.append("weekly-plan")
    if not course.professor_profile:
        missing.append("professor_profile")
    if not has_mastery:
        missing.append("mastery_model")
    if not has_dossier:
        missing.append("research-dossier(needs ≥5 cited URLs + confidence + open-questions)")
    return {
        "authored": not missing,
        "missing_for_authored": missing,
        "no_resource_units": [u.id for u in course.units if not u.resources],
        "n_dossier_urls": n_urls,
    }


def report_present(uploads_dir: str | Path, code: str) -> bool:
    """Has the learner dropped a research report for <code>? True if Uploads/<code>/ holds any
    real file (ignoring scaffold markers)."""
    up = Path(uploads_dir) / code
    if up.is_dir():
        for f in up.iterdir():
            if f.is_file() and f.name not in _UPLOAD_MARKERS:
                return True
    return False


def authoring_status(course_file: str | Path, uploads_dir: str | Path, code: str) -> CourseStatus:
    """Deterministic authoring-phase lifecycle status (RFC-009), from the filesystem alone:
    authored → 'placement'; report uploaded but not yet authored → 'authoring';
    else blocked on the learner → 'researching'."""
    try:
        c = load_course(course_file)
    except FileNotFoundError:
        return "researching"  # no course.yaml yet → still awaiting the research report
    # a course.yaml that exists but won't parse/validate is a real fault — fail loud, don't mask it
    if authored_report(c, Path(course_file).parent)["authored"]:
        return "placement"
    if report_present(uploads_dir, code):
        return "authoring"
    return "researching"
