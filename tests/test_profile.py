from pathlib import Path

import yaml

from engine.profile import Profile, load_profile

ROOT = Path(__file__).resolve().parents[1]


def test_profile_example_loads_generic_defaults():
    # validate the SHIPPED example explicitly — not load_profile(ROOT), which prefers a private
    # profile.yaml (so on a live host it would check the real profile, not the example).
    p = Profile.model_validate(yaml.safe_load((ROOT / "profile.example.yaml").read_text()) or {})
    assert isinstance(p, Profile)
    assert p.name and p.goal and p.target_level and p.credential_name
    blob = (p.name + p.goal + p.target_level + p.credential_name).lower()
    for banned in ("employer", "top-tier-company", "maintainer", "university"):
        assert banned not in blob


def test_no_personal_identifiers_leak_into_the_tree():
    """Guard (RFC-005): the real name/school must not appear in any shippable file; this scans
    the whole tree, not just profile.example.yaml. GitHub handle `AlijonovMukhammaddiyor` is
    allow-listed (clone URLs) and stripped before the scan, so a bare `the maintainer` trips."""
    import re

    allowed_handle = re.compile(re.escape("AlijonovMukhammaddiyor"), re.I)
    banned = re.compile(r"maintainer|university", re.I)

    def leaks(text: str) -> bool:
        return bool(banned.search(allowed_handle.sub("", text)))

    dirs = [ROOT / d for d in ("engine", "skills", "docs", "tests", "courses/_TEMPLATE")]
    exts = {".py", ".md", ".yaml", ".yml", ".txt", ".env", ".example"}
    self_path = Path(__file__).resolve()  # this file names them on purpose (the ban list)
    hits = []
    for base in dirs:
        for f in base.rglob("*"):
            if (
                f.is_file()
                and f.suffix in exts
                and f.resolve() != self_path
                and leaks(f.read_text(errors="ignore"))
            ):
                hits.append(str(f.relative_to(ROOT)))
    for f in ROOT.glob("*.md"):  # root-level README/ARCHITECTURE/etc.
        if leaks(f.read_text(errors="ignore")):
            hits.append(f.name)
    assert not hits, f"personal identifiers leaked into: {sorted(hits)}"


def test_profile_defaults_when_absent(tmp_path):
    p = load_profile(tmp_path)  # no profile.yaml / profile.example.yaml -> defaults
    assert p.name == "Learner" and p.daily_task_cap == 4


def test_profile_yaml_overrides_example(tmp_path):
    (tmp_path / "profile.yaml").write_text(
        "name: Ada\ngoal: master systems\ntarget_level: staff\ndaily_task_cap: 2\n"
    )
    p = load_profile(tmp_path)
    assert p.name == "Ada" and p.target_level == "staff" and p.daily_task_cap == 2


def test_set_field_persists_and_coerces(tmp_path):
    from engine.profile import set_field

    p = set_field(tmp_path, "goal", "become a great researcher")
    assert p.goal == "become a great researcher"
    assert (tmp_path / "profile.yaml").exists()  # written to the private file
    assert load_profile(tmp_path).goal == "become a great researcher"
    p2 = set_field(tmp_path, "daily_task_cap", "3")  # coerced to int
    assert p2.daily_task_cap == 3 and load_profile(tmp_path).goal == "become a great researcher"


def test_set_field_rejects_unknown_field(tmp_path):
    import pytest

    from engine.profile import set_field

    with pytest.raises(KeyError):
        set_field(tmp_path, "employer", "anything")
