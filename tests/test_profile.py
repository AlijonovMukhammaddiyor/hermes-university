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


def test_no_personal_identifiers_leak_into_the_tree():
    """Systematic guard (RFC-005): the real name/school must not appear in any shippable file — the
    profile-blob check above only covers profile.example.yaml, which let the name slip into docs/ and
    tests/. This scans the source tree so it can't regress. (employer/top-tier-company stay allowed as documented
    ban-examples in CONTRIBUTING/RFC-005.)"""
    import re
    banned = re.compile(r"maintainer|university", re.I)
    dirs = [ROOT / d for d in ("engine", "skills", "docs", "tests", "courses/_TEMPLATE")]
    exts = {".py", ".md", ".yaml", ".yml", ".txt", ".env", ".example"}
    self_path = Path(__file__).resolve()            # this file names them on purpose (the ban list)
    hits = []
    for base in dirs:
        for f in base.rglob("*"):
            if (f.is_file() and f.suffix in exts and f.resolve() != self_path
                    and banned.search(f.read_text(errors="ignore"))):
                hits.append(str(f.relative_to(ROOT)))
    for f in ROOT.glob("*.md"):                      # root-level README/ARCHITECTURE/etc.
        if banned.search(f.read_text(errors="ignore")):
            hits.append(f.name)
    assert not hits, f"personal identifiers leaked into: {sorted(hits)}"


def test_profile_defaults_when_absent(tmp_path):
    p = load_profile(tmp_path)          # no profile.yaml / profile.example.yaml -> defaults
    assert p.name == "Learner" and p.daily_task_cap == 4


def test_profile_yaml_overrides_example(tmp_path):
    (tmp_path / "profile.yaml").write_text(
        "name: Ada\ngoal: master systems\ntarget_level: staff\ndaily_task_cap: 2\n")
    p = load_profile(tmp_path)
    assert p.name == "Ada" and p.target_level == "staff" and p.daily_task_cap == 2
