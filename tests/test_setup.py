"""Setup scripts — install_crons renders crons.yaml into the verified `hermes cron create` CLI."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_install_crons_dry_run_renders_valid_commands(capsys):
    ic = _load("install_crons")
    assert ic.main(["install_crons.py", "--vault", "/v", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "hermes cron create" in out
    assert "--name uni-assign" in out and "--skill registrar" in out
    assert "--name uni-briefing" in out and "--skill briefer" in out
    assert "/v" in out and "{{" not in out  # {{VAULT}} etc. resolved
