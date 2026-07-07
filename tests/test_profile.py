from pathlib import Path

from engine.profile import Profile, load_profile

ROOT = Path(__file__).resolve().parents[1]


def test_profile_example_loads_generic_defaults():
    # the shipped example must be generic — no personal/org data
    p = load_profile(ROOT)
    assert isinstance(p, Profile)
    assert p.name and p.goal and p.target_level and p.credential_name
    blob = (p.name + p.goal + p.target_level + p.credential_name).lower()
    for banned in ("employer", "top-tier-company", "maintainer", "university"):
        assert banned not in blob


def test_profile_defaults_when_absent(tmp_path):
    p = load_profile(tmp_path)          # no profile.yaml / profile.example.yaml -> defaults
    assert p.name == "Learner" and p.daily_task_cap == 4


def test_profile_yaml_overrides_example(tmp_path):
    (tmp_path / "profile.yaml").write_text(
        "name: Ada\ngoal: master systems\ntarget_level: staff\ndaily_task_cap: 2\n")
    p = load_profile(tmp_path)
    assert p.name == "Ada" and p.target_level == "staff" and p.daily_task_cap == 2
