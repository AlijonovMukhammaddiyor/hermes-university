import pytest

from engine import render


def test_render_replaces_vars():
    out = render.render("Hi {{LEARNER_NAME}} in {{TIMEZONE}}",
                        {"LEARNER_NAME": "M", "TIMEZONE": "Asia/Tashkent"})
    assert out == "Hi M in Asia/Tashkent"


def test_render_raises_on_missing_var():
    with pytest.raises(KeyError):
        render.render("Hello {{MISSING}}", {"LEARNER_NAME": "M"})


def test_render_file(tmp_path):
    src = tmp_path / "t.md"; src.write_text("name: {{LEARNER_NAME}}")
    dst = tmp_path / "out" / "t.md"
    render.render_file(src, dst, {"LEARNER_NAME": "M"})
    assert dst.read_text() == "name: M"


def test_load_config_env(tmp_path):
    f = tmp_path / "config.env"
    f.write_text('# comment\nLEARNER_NAME="Ada Lovelace"\nTIMEZONE=UTC\n\nEMPTY=""\n')
    cfg = render.load_config_env(f)
    assert cfg["LEARNER_NAME"] == "Ada Lovelace"
    assert cfg["TIMEZONE"] == "UTC"
    assert cfg["EMPTY"] == ""
