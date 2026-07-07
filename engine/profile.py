"""Instance identity + goals (RFC-005) — the ONLY place personal data lives.

Loads a git-ignored `profile.yaml`, falling back to the shipped generic `profile.example.yaml`.
No person- or org-specific data is ever hardcoded in code, skills, or courses; everything reads here.
Personalization is to the learner's GOALS, never their work/employer.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class Profile(BaseModel):
    name: str = "Learner"
    timezone: str = "UTC"
    goal: str = "Become one of the best in the fields you study, able to work with the best people."
    target_level: str = "top of the field"        # the bar to design courses backward from
    current_level: str = "capable beginner"        # calibrates placement
    interests: list[str] = Field(default_factory=list)
    daily_task_cap: int = 4
    credential_name: str = "Hermes University Certificate of Mastery"


def load_profile(root: str | Path) -> Profile:
    """profile.yaml (private) if present, else profile.example.yaml (generic), else defaults."""
    root = Path(root)
    for name in ("profile.yaml", "profile.example.yaml"):
        p = root / name
        if p.exists():
            return Profile.model_validate(yaml.safe_load(p.read_text()) or {})
    return Profile()
