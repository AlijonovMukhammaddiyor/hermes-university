#!/usr/bin/env python3
"""Render skill templates against config.env + course modules → an output dir.

Called by install.sh (phase 2). Renders registrar + examiner once, and the professor template
once per course found under courses/. Fails loudly on any unresolved placeholder.

Usage: render_skills.py <repo_root> <config.env> <out_dir> <vault> <engine_path>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.render import load_config_env, render_file  # noqa: E402


def main(argv: list[str]) -> int:
    root, cfg_path, out_dir, vault, engine = argv[1:6]
    root, out = Path(root), Path(out_dir)
    cfg = load_config_env(cfg_path)
    base = {
        "LEARNER_NAME": cfg.get("LEARNER_NAME", ""),
        "TIMEZONE": cfg.get("TIMEZONE", "Asia/Tashkent"),
        "DAILY_TASK_CAP": cfg.get("DAILY_TASK_CAP", "4"),
        "VAULT": vault,
        "ENGINE": engine,
        "COURSES_DIR": str(root / "courses"),
    }
    # registrar + examiner + professor — ONE each (Faculty Handbook: the single professor teaches
    # every course by reading its module; no per-course professor artifacts — RFC-004).
    for name in ("registrar", "examiner", "professor"):
        render_file(root / "skills" / f"{name}.template.md",
                    out / name / "SKILL.md", base)
        print(f"rendered {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
