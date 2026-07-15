from pathlib import Path

import pytest
import yaml

from engine.profile import Profile, load_profile

ROOT = Path(__file__).resolve().parents[1]
# Your private identifiers live in a git-ignored file, so this public repo never ships them.
# Copy .pii-banlist.example -> .pii-banlist and add yours. Absent = nothing private to guard.
BANLIST = ROOT / ".pii-banlist"
# The GitHub handle is public (it's in the clone URL), so it's allow-listed and stripped before
# scanning — a bare identifier still trips the guard.
ALLOWED_HANDLE = "AlijonovMukhammaddiyor"


def _banned() -> list[str]:
    if not BANLIST.exists():
        return []
    return [
        ln.strip()
        for ln in BANLIST.read_text().splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


def test_profile_example_loads_generic_defaults():
    # validate the SHIPPED example explicitly — not load_profile(ROOT), which prefers a private
    # profile.yaml (so on a live host it would check the real profile, not the example).
    p = Profile.model_validate(yaml.safe_load((ROOT / "profile.example.yaml").read_text()) or {})
    assert isinstance(p, Profile)
    assert p.name and p.goal and p.target_level and p.credential_name
    blob = (p.name + p.goal + p.target_level + p.credential_name).lower()
    for banned in _banned():
        assert banned.lower() not in blob


def test_no_personal_identifiers_leak_into_the_tree():
    """Guard (RFC-005): your private identifiers must never reach a shippable file. Patterns come
    from the git-ignored `.pii-banlist`; a clean clone has nothing to guard, so this skips."""
    import re

    patterns = _banned()
    if not patterns:
        pytest.skip("no .pii-banlist — nothing private to guard in a clean clone")

    allowed = re.compile(re.escape(ALLOWED_HANDLE), re.I)
    # word-bounded: a bare identifier trips, but the same letters buried inside a longer,
    # unrelated word must not (that would make the guard cry wolf on ordinary prose).
    banned = re.compile("|".join(rf"\b{re.escape(p)}\b" for p in patterns), re.I)

    def leaks(text: str) -> bool:
        return bool(banned.search(allowed.sub("", text)))

    dirs = [ROOT / d for d in ("engine", "skills", "docs", "tests", "courses/_TEMPLATE")]
    exts = {".py", ".md", ".yaml", ".yml", ".txt", ".env", ".example"}
    hits = []
    for base in dirs:
        for f in base.rglob("*"):
            if f.is_file() and f.suffix in exts and leaks(f.read_text(errors="ignore")):
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
