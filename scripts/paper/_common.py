"""Shared helpers for the Hermes Daily data desks.

A data desk is code, never a model: it reads the learner's own record and
renders an article. If it cannot read its source it raises, and the caller
drops the story rather than printing a guessed number.

Standard library only, on purpose — these run on the agent host with no
virtualenv of their own.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# The paper sets tables in a column about fifty-two characters wide, so the
# longest cell in any column must stay under this (docs/WRITING.md).
CELL_LIMIT = 25


class DeskError(RuntimeError):
    """The desk cannot source its numbers. The story is dropped, not guessed."""


def resolve_vault(explicit: str | None = None) -> Path:
    """The vault root: --vault, else $HERMES_UNIVERSITY_VAULT, else ~/vault."""
    raw = explicit or os.environ.get("HERMES_UNIVERSITY_VAULT") or "~/vault"
    vault = Path(raw).expanduser()
    if not vault.is_dir():
        raise DeskError(f"no vault at {vault}")
    return vault


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise DeskError(f"missing {path}")
    try:
        with path.open() as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise DeskError(f"{path} is not valid JSON: {exc}") from exc


def load_jsonl(path: Path) -> list[dict]:
    """Every well-formed row. A truncated final line is normal for an append log."""
    if not path.is_file():
        raise DeskError(f"missing {path}")
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def clip(text: str, limit: int = CELL_LIMIT) -> str:
    """Shorten in words where we can; the column cuts what still does not fit.

    The paper's rule is never to cut a cell with an ellipsis ourselves, so this
    drops whole words and only falls back to a hard cut for a single long one.
    """
    text = str(text).strip()
    if len(text) <= limit:
        return text
    words = text.split()
    out = ""
    for word in words:
        candidate = (out + " " + word).strip()
        if len(candidate) > limit:
            break
        out = candidate
    return out or text[:limit].rstrip()


def _scalar(value) -> str:
    """One YAML scalar, quoted only when it would otherwise change meaning."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    risky = text.startswith(("#", "-", "[", "{", "*", "&", "!", "%", "@", "`", ">", "|"))
    # Any colon is quoted: YAML 1.1 reads 21:00 as a sexagesimal number, and a
    # time label must survive as the string the desk wrote.
    if not text or risky or ":" in text or "," in text or '"' in text:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def frontmatter(fields: dict) -> str:
    """Emit the article's YAML frontmatter.

    Only the shapes the format uses: scalars, flat lists, and the one nested
    mapping (``chart``). Hand-rolled because the desks stay stdlib-only.
    """
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for sub_key, sub_value in value.items():
                if sub_value is None:
                    continue
                if isinstance(sub_value, list):
                    rendered = ", ".join(_scalar(item) for item in sub_value)
                    lines.append(f"  {sub_key}: [{rendered}]")
                else:
                    lines.append(f"  {sub_key}: {_scalar(sub_value)}")
        elif isinstance(value, list):
            if not value:
                continue
            lines.append(f"{key}: [" + ", ".join(_scalar(item) for item in value) + "]")
        else:
            lines.append(f"{key}: {_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def write_article(edition_dir: Path, filename: str, fields: dict, body: str) -> Path:
    """Write one article into <edition_dir>/articles/ and return its path."""
    articles = Path(edition_dir) / "articles"
    articles.mkdir(parents=True, exist_ok=True)
    target = articles / filename
    text = frontmatter(fields) + "\n\n" + body.strip() + "\n"
    target.write_text(text)
    return target
