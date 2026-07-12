#!/usr/bin/env python3
"""Render skill templates against the instance profile → an output dir.

Renders registrar + examiner + professor (one each — the single Faculty Handbook professor teaches
every course by reading its module, RFC-004). Identity/goals come from profile.yaml (RFC-005); the
5th arg is kept for backward compatibility and ignored. Fails loudly on any unresolved placeholder.

Usage: render_skills.py <repo_root> <ignored> <out_dir> <vault> <engine_path>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.profile import load_profile  # noqa: E402
from engine.render import render_file  # noqa: E402


def main(argv: list[str]) -> int:
    root, _cfg_ignored, out_dir, vault, engine = argv[1:6]
    root, out = Path(root), Path(out_dir)
    prof = load_profile(root)
    base = {
        "LEARNER_NAME": prof.name,
        "TIMEZONE": prof.timezone,
        "DAILY_TASK_CAP": str(prof.daily_task_cap),
        "GOAL": prof.goal,
        "TARGET_LEVEL": prof.target_level,
        "VAULT": vault,
        "ENGINE": engine,
        "COURSES_DIR": str(root / "courses"),
        # source list lives in the VAULT (Obsidian-editable, auto-synced) — seeded from vault-template
        "BRIEFING_SOURCES": str(Path(vault) / "Briefing" / "sources.yaml"),
    }
    # registrar + examiner + professor (Faculty Handbook: the single professor teaches every course by
    # reading its module — RFC-004) + briefer (the daily digest — RFC-010).
    for name in ("registrar", "examiner", "professor", "briefer"):
        render_file(root / "skills" / f"{name}.template.md", out / name / "SKILL.md", base)
        print(f"rendered {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
