"""Registered integrations (RFC-012). Add a connector = one `register(Integration(...))`.

`doctor` and skills read this list; required connectors gate setup, optional ones degrade.
"""

from __future__ import annotations

from pathlib import Path

from .base import (
    Integration,
    IntegrationStatus,
    all_integrations,
    check_all,
    get,
    load_env_file,
    register,
)


def _anki_probe(env: dict[str, str]) -> IntegrationStatus | None:
    """Creds already checked; confirm the Anki desktop is actually installed."""
    found = any(
        p.exists()
        for p in (
            Path("/usr/local/share/anki"),
            Path.home() / ".local/share/Anki2",
            Path("/Applications/Anki.app"),
        )
    )
    if found:
        return None
    return IntegrationStatus(
        name="anki",
        required=False,
        status="unavailable",
        detail="Anki desktop not found — install it to enable spaced-repetition sync",
    )


def _calendar_probe(env: dict[str, str]) -> IntegrationStatus | None:
    creds = env.get("GOOGLE_OAUTH_CREDENTIALS", "")
    if creds and not Path(creds).expanduser().exists():
        return IntegrationStatus(
            name="google-calendar",
            required=False,
            status="unavailable",
            detail=f"credentials file not found: {creds}",
        )
    if not (Path.home() / ".config/google-calendar-mcp/tokens.json").exists():
        return IntegrationStatus(
            name="google-calendar",
            required=False,
            status="ok",
            detail="authorize once — no OAuth token yet",
        )
    return None


register(
    Integration(
        name="llm",
        summary="the model that teaches + grades to a rubric (DeepSeek by default)",
        required=True,
        env_all=["DEEPSEEK_API_KEY"],
    )
)
register(
    Integration(
        name="telegram",
        summary="your coach + control surface",
        required=True,
        env_all=["TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USERS"],
    )
)
register(
    Integration(
        name="web-search",
        summary="grounds course research in real sources (mandatory)",
        required=True,
        env_any=["SERPER_API_KEY", "BRAVE_API_KEY"],
    )
)
register(
    Integration(
        name="google-calendar",
        summary="books your study routine onto your calendar",
        env_all=["GOOGLE_OAUTH_CREDENTIALS"],
        probe=_calendar_probe,
    )
)
register(
    Integration(
        name="anki",
        summary="spaced-repetition review (FSRS) pushed to your phone",
        env_all=["ANKIWEB_USERNAME", "ANKIWEB_PASSWORD"],
        probe=_anki_probe,
    )
)
register(
    Integration(
        name="briefing",
        summary="daily curated tech/engineering reading (uses web search)",
        env_any=["SERPER_API_KEY", "BRAVE_API_KEY"],
    )
)
register(
    Integration(
        name="judge0",
        summary="sandboxed code execution for auto-graded proofs",
        env_all=["JUDGE0_URL"],
    )
)

__all__ = [
    "Integration",
    "IntegrationStatus",
    "all_integrations",
    "check_all",
    "get",
    "load_env_file",
    "register",
]
