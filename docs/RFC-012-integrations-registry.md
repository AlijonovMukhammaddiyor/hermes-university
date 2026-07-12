# RFC-012 — Integrations registry (add a connector like a lego brick)

**Status:** Implemented · **Supersedes:** the ad-hoc integration wiring scattered across scripts/skills

## Problem
External connectors (LLM, Telegram, web search, Google Calendar, Anki, briefing, Judge0) were each
wired differently — some in `engine/`, some in `scripts/`, some only in a skill prompt or a cron —
with no common shape and no single answer to *"is this integration available?"*. That made two things
hard: **adding** a connector (no template to follow) and **degrading gracefully** when an optional one
is absent (every surface guessed). It also left setup with no preflight.

## Design
One registry, the same shape as the proof-gate registry (`engine/proofgate/`). A connector is declared
once; nothing else in the engine changes.

```python
# engine/integrations/__init__.py
register(Integration(
    name="google-calendar",
    summary="books your study routine onto your calendar",
    env_all=["GOOGLE_OAUTH_CREDENTIALS"],   # every key must be set
    # env_any=[...]                          # at least one must be set (e.g. SERPER|BRAVE)
    probe=_calendar_probe,                    # optional deeper check once config is present
))
```

- `required=True` connectors gate setup; the rest are optional and degrade gracefully.
- `Integration.check(env)` returns an `IntegrationStatus`: `ok` · `missing_config` (+ which keys) ·
  `unavailable` (configured but not reachable — e.g. Anki desktop not installed).
- `probe(env)` runs only after the declared env is present and may return `None` to mean
  "config is enough".

## Surfaces
- **`hu-engine doctor`** enumerates the registry and prints REQUIRED/OPTIONAL with each connector's
  status. Exit `1` if any *required* connector isn't ready, so setup can gate on it.
- **`hu-engine doctor --json`** → `{ok, integrations:[{name,status,detail,missing,...}]}` — skills read
  this to skip an unavailable optional step (no Anki → skip cards; no calendar → skip blocks).
- **`doctor --env config.env`** overlays a `config.env` before install.sh sources it, so preflight
  works pre-install.

## Adding a connector
1. Add one `register(Integration(...))` in `engine/integrations/__init__.py` (a `probe` only if
   "keys present" isn't a strong enough availability check).
2. Add its keys to `config.env.example`.
3. If it needs a skill step or cron, wire those — but the *availability* check is already uniform.

That's the whole contract. No caller, no `doctor`, and no setup code changes when a connector is added.

## Not in scope (deliberately)
A heavy plugin system (dynamic discovery, per-connector manifests that also own crons/skills) — there
are ~7 real connectors, so a lightweight registry is the right size. Revisit only if the count grows.
