"""Template renderer — makes 'everything in sync' mechanical (RFC §10).

Renders `{{VAR}}` placeholders in skill/cron templates against config.env values (+ per-course
values). One value, one place. Used by install.sh phase 2. Fails loudly on an unresolved
placeholder so a missing config key can never ship a half-rendered skill.
"""

from __future__ import annotations

import re
from pathlib import Path

_PLACEHOLDER = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")


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
