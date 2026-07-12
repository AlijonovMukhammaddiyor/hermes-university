"""Scaffold a stub course module (RFC-009 `course new`).

The stub is a VALID but deliberately UNAUTHORED course, so the authored gate keeps it in
`researching` until the research report lands and the professor overwrites it.
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
    """Write a valid empty-of-units stub at `<code>/course.yaml`; refuses to clobber. Returns the
    path."""
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
