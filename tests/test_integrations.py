"""Integrations registry + doctor (RFC-012): the uniform contract for external connectors."""

import json

from engine import cli
from engine.integrations import base

_REQUIRED_KEYS = (
    "DEEPSEEK_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_ALLOWED_USERS",
    "SERPER_API_KEY",
    "BRAVE_API_KEY",
)


def test_missing_required_config_is_reported_with_keys():
    i = base.Integration(name="x", summary="s", required=True, env_all=["A_KEY", "B_KEY"])
    st = i.check({"A_KEY": "set"})
    assert st.status == "missing_config" and "B_KEY" in st.missing and not st.ok


def test_all_keys_present_is_ok():
    i = base.Integration(name="x", summary="s", env_all=["A_KEY"])
    assert i.check({"A_KEY": "v"}).ok


def test_env_any_needs_at_least_one():
    i = base.Integration(
        name="search", summary="s", required=True, env_any=["SERPER_API_KEY", "BRAVE_API_KEY"]
    )
    assert not i.check({}).ok
    assert i.check({"BRAVE_API_KEY": "v"}).ok


def test_probe_can_downgrade_to_unavailable():
    def probe(env):
        return base.IntegrationStatus(
            name="anki", required=False, status="unavailable", detail="desktop not installed"
        )

    i = base.Integration(name="anki", summary="s", probe=probe)
    assert i.check({}).status == "unavailable"  # keys ok, but the probe says no


def test_registry_holds_the_real_integrations():
    names = {i.name for i in base.all_integrations()}
    assert {"llm", "telegram", "web-search", "google-calendar", "anki"} <= names


def test_load_env_file_overlays_and_parses(tmp_path):
    f = tmp_path / "config.env"
    f.write_text('# comment\nSERPER_API_KEY="abc"\nLLM_MODEL=deepseek-chat\n\n')
    env = base.load_env_file(f)
    assert env["SERPER_API_KEY"] == "abc" and env["LLM_MODEL"] == "deepseek-chat"


def test_doctor_cli_flags_missing_required_and_exits_nonzero(tmp_path, capsys, monkeypatch):
    for k in _REQUIRED_KEYS:
        monkeypatch.delenv(k, raising=False)
    f = tmp_path / "config.env"
    f.write_text('DEEPSEEK_API_KEY="k"\n')  # telegram + web-search still missing
    code = cli.main(["doctor", "--env", str(f), "--json"])
    out = json.loads(capsys.readouterr().out)
    by = {r["name"]: r for r in out["integrations"]}
    assert by["llm"]["status"] == "ok"
    assert by["telegram"]["status"] == "missing_config"
    assert out["ok"] is False and code == 1


def test_doctor_cli_all_required_present_exits_zero(tmp_path, capsys, monkeypatch):
    for k in _REQUIRED_KEYS:
        monkeypatch.delenv(k, raising=False)
    f = tmp_path / "config.env"
    f.write_text(
        'DEEPSEEK_API_KEY="k"\nTELEGRAM_BOT_TOKEN="t"\nTELEGRAM_ALLOWED_USERS="1"\nSERPER_API_KEY="s"\n'
    )
    code = cli.main(["doctor", "--env", str(f), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True and code == 0  # optional integrations missing doesn't fail preflight
