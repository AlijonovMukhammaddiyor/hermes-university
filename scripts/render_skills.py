#!/usr/bin/env python3
"""Render skill templates against the instance profile → an output dir.

Identity/goals come from profile.yaml (RFC-005); the `<ignored>` arg is kept for backward compat.
Fails loudly on any unresolved placeholder.

Usage: render_skills.py <repo_root> <ignored> <out_dir> <vault> <engine_path>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.profile import load_profile  # noqa: E402
from engine.render import check_skill_caps, render_file  # noqa: E402


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
    # registrar + examiner + professor (RFC-004: one professor teaches every course) + briefer
    # (daily digest, RFC-010). Shared reference docs pulled on demand via skill_view (RFC-013).
    references = {
        "registrar": ["observe-the-learner.md"],
        "professor": ["observe-the-learner.md"],
    }
    for name in ("registrar", "examiner", "professor", "briefer"):
        dst = out / name / "SKILL.md"
        render_file(root / "skills" / f"{name}.template.md", dst, base)
        for ref in references.get(name, []):
            render_file(root / "skills" / "references" / ref, out / name / "references" / ref, base)
        for warning in check_skill_caps(dst):  # raises on a hard-cap breach; warns on soft ones
            print(f"warning: {warning}")
        print(f"rendered {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
