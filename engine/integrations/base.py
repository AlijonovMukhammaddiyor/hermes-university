"""Integration contract + registry (RFC-012). Same shape as the proof-gate registry.

`doctor` enumerates it to preflight setup; skills read it to degrade when an optional connector is
absent. Adding a connector = one `Integration(...)` entry.
"""

from __future__ import annotations

import os
import shlex
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

# ok = ready · missing_config = required env not set · unavailable = configured but not reachable
Status = str


class IntegrationStatus(BaseModel):
    name: str
    required: bool
    status: Status
    detail: str = ""
    missing: list[str] = []

    @property
    def ok(self) -> bool:
        return self.status == "ok"


@dataclass
class Integration:
    """One external connector. `env_all` all required; `env_any` needs at least one; optional
    `probe` runs once config is present to confirm real usability (`None` = config is enough)."""

    name: str
    summary: str
    required: bool = False
    env_all: list[str] = field(default_factory=list)
    env_any: list[str] = field(default_factory=list)
    probe: Callable[[dict[str, str]], IntegrationStatus | None] | None = None

    def check(self, env: dict[str, str]) -> IntegrationStatus:
        missing = [k for k in self.env_all if not env.get(k)]
        if self.env_any and not any(env.get(k) for k in self.env_any):
            missing.append(" | ".join(self.env_any))
        if missing:
            return IntegrationStatus(
                name=self.name,
                required=self.required,
                status="missing_config",
                detail="set " + ", ".join(missing),
                missing=missing,
            )
        if self.probe and (result := self.probe(env)) is not None:
            return result
        return IntegrationStatus(name=self.name, required=self.required, status="ok")


_REGISTRY: dict[str, Integration] = {}


def register(integration: Integration) -> None:
    _REGISTRY[integration.name] = integration


def get(name: str) -> Integration:
    if name not in _REGISTRY:
        raise KeyError(f"no integration named {name!r}; have {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def all_integrations() -> list[Integration]:
    return list(_REGISTRY.values())


def check_all(env: dict[str, str] | None = None) -> list[IntegrationStatus]:
    env = dict(os.environ) if env is None else env
    return [i.check(env) for i in _REGISTRY.values()]


def load_env_file(path: str | Path) -> dict[str, str]:
    """Parse a `KEY=value` file (config.env) over the process env, so `doctor` can preflight before
    install.sh sources it. Quoted values ok; missing file returns just the process env."""
    env = dict(os.environ)
    p = Path(path)
    if p.exists():
        for raw in p.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            # setup.sh writes values with shlex.quote, so read them back the same way: this drops a
            # trailing comment without eating a '#' that is inside quotes (passwords have them).
            try:
                env[key] = " ".join(shlex.split(val, comments=True))
            except ValueError as e:
                raise ValueError(f"{p}: cannot parse {key} — {e}") from e
    return env
