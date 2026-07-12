"""Template renderer — makes 'everything in sync' mechanical (RFC §10).

Renders `{{VAR}}` placeholders in skill/cron templates against config.env values (+ per-course
values). One value, one place. Used by install.sh phase 2. Fails loudly on an unresolved
placeholder so a missing config key can never ship a half-rendered skill.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_PLACEHOLDER = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")

# Hermes' SKILL.md limits (see docs/hermes-agent-reference.md). We render straight to disk, bypassing
# Hermes' own skill_manage validation, so the renderer must enforce them itself.
MAX_SKILL_CHARS = 100_000  # hard reject above this
MAX_DESC_CHARS = 1024  # hard reject on a longer frontmatter description
DESC_DISPLAY_CHARS = 60  # …and only this much is shown in the skills index


def render(text: str, values: dict[str, str]) -> str:
    missing: set[str] = set()

    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key not in values:
            missing.add(key)
            return m.group(0)
        return str(values[key])

    out = _PLACEHOLDER.sub(sub, text)
    if missing:
        raise KeyError(f"unresolved template vars: {sorted(missing)}")
    return out


def render_file(src: str | Path, dst: str | Path, values: dict[str, str]) -> None:
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(render(Path(src).read_text(), values))


def check_skill_caps(path: str | Path) -> list[str]:
    """Guard a rendered SKILL.md against Hermes' caps. Raises ValueError on a hard-reject violation
    (body/description too long); returns soft warnings (description longer than the shown limit)."""
    p = Path(path)
    content = p.read_text()
    if len(content) > MAX_SKILL_CHARS:
        raise ValueError(
            f"{p}: {len(content)} chars exceeds Hermes' {MAX_SKILL_CHARS}-char skill cap"
        )
    desc = str(_frontmatter(content).get("description", "") or "")
    if len(desc) > MAX_DESC_CHARS:
        raise ValueError(f"{p}: description {len(desc)} chars exceeds Hermes' {MAX_DESC_CHARS} cap")
    if len(desc) > DESC_DISPLAY_CHARS:
        return [
            f"{p.parent.name}: description {len(desc)} chars — Hermes shows only {DESC_DISPLAY_CHARS}"
        ]
    return []


def _frontmatter(content: str) -> dict:
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end < 0:
        return {}
    try:
        fm = yaml.safe_load(content[3:end])
    except (
        yaml.YAMLError
    ) as e:  # e.g. an unquoted colon in a description — fail loud, not a raw traceback
        raise ValueError(f"invalid SKILL.md frontmatter YAML: {e}") from e
    return fm if isinstance(fm, dict) else {}


def load_config_env(path: str | Path) -> dict[str, str]:
    """Parse a dotenv-style config.env into a flat dict (KEY=VALUE, quotes stripped)."""
    out: dict[str, str] = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out
