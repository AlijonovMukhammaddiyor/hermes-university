#!/usr/bin/env python3
"""Create the Hermes University cron jobs from crons/crons.yaml.

Renders {{VAR}} against profile.yaml, then runs `hermes cron create` per job. Idempotent: skips jobs
already in ~/.hermes/cron/jobs.json. `--dry-run` prints the commands instead of running them.

Usage: install_crons.py [--vault PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.profile import load_profile  # noqa: E402
from engine.render import render  # noqa: E402


def _existing_names(hermes_home: Path) -> set[str]:
    jf = hermes_home / "cron" / "jobs.json"
    if not jf.exists():
        return set()
    try:
        return {j.get("name") for j in json.loads(jf.read_text()).get("jobs", [])}
    except (json.JSONDecodeError, AttributeError):
        return set()


def commands(root: Path, vault: str) -> list[tuple[str, list[str]]]:
    """(name, argv) for `hermes cron create` per job — verified CLI: positional schedule + prompt."""
    prof = load_profile(root)
    vals = {"VAULT": vault, "TIMEZONE": prof.timezone, "DAILY_TASK_CAP": str(prof.daily_task_cap)}
    jobs = yaml.safe_load((root / "crons" / "crons.yaml").read_text())["jobs"]
    out = []
    for job in jobs:
        cmd = [
            "hermes",
            "cron",
            "create",
            job["schedule"],
            render(job["intent"], vals).strip(),
            "--name",
            job["name"],
            "--deliver",
            job.get("deliver", "telegram"),
        ]
        if job.get("workdir"):
            cmd += ["--workdir", render(job["workdir"], vals)]
        for skill in job.get("skills", []):
            cmd += ["--skill", skill]
        out.append((job["name"], cmd))
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="install_crons.py")
    ap.add_argument("--vault", default=str(Path.home() / "vault"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv[1:])
    root = Path(__file__).resolve().parents[1]
    cmds = commands(root, args.vault)
    if args.dry_run:
        for _name, cmd in cmds:
            print(" ".join(shlex.quote(c) for c in cmd))
        return 0
    existing = _existing_names(Path.home() / ".hermes")
    for name, cmd in cmds:
        if name in existing:
            print(f"skip {name} (already exists)")
            continue
        subprocess.run(cmd, check=True)
        print(f"created {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
