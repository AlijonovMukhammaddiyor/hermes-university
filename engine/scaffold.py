"""Scaffold a stub course module (RFC-009 `course new`).

`create course` needs a real folder to exist before research begins — the professor overwrites this
stub with the researched, authored course.yaml. The stub is a VALID but deliberately UNAUTHORED
course (no description/resources/dossier), so the authored gate keeps it in `researching` until the
research report lands.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .course import Course


def scaffold_course(
    courses_dir: str | Path,
    code: str,
    title: str,
    goal: str = "",
    domain: str = "general",
    credits: int = 3,
) -> Path:
    """Write `<courses_dir>/<code>/course.yaml` (a valid, empty-of-units stub). Refuses to clobber an
    existing module. Returns the file path."""
    cdir = Path(courses_dir) / code
    path = cdir / "course.yaml"
    if path.exists():
        raise FileExistsError(f"course {code!r} already exists at {path}")
    north = goal.strip() or f"Master {title}."
    stub = Course(
        id=code, title=title, subject_domain=domain, credits=credits, north_star=north
    )  # empty units -> validates, not authored
    cdir.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            stub.model_dump(exclude_none=True, mode="json"), sort_keys=False, allow_unicode=True
        )
    )
    (cdir / "research").mkdir(exist_ok=True)  # where the dossier will be written
    return path
