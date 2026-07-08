# Prerequisites

Hermes University installs against services you own. Obtain these **before** running `install.sh`,
then put them in `config.env` (or supply interactively where noted).

| # | What | Where to get it | Goes in |
|---|---|---|---|
| 1 | **Always-on Linux box** (2GB+ RAM; +2GB swap recommended) with the **Hermes Agent** installed | https://github.com/NousResearch/hermes-agent (DO 1-click droplet) | the host |
| 2 | **LLM API key** (default DeepSeek) | https://platform.deepseek.com | `DEEPSEEK_API_KEY` |
| 3 | **Telegram bot** token + your chat/user id | @BotFather | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS`, `TELEGRAM_HOME_CHANNEL` |
| 4 | **AnkiWeb account** (same one your phone Anki uses) | https://ankiweb.net | `ANKIWEB_EMAIL` (+ password entered interactively) |
| 5 | **Google Cloud OAuth** (Desktop client) `credentials.json` — Calendar API enabled, consent published | https://console.cloud.google.com/auth (see ARCHITECTURE.md) | `GOOGLE_OAUTH_CREDENTIALS` (path) |
| 6 | **Web search** for research — Serper (default) | https://serper.dev | `SERPER_API_KEY` (+ optional `BRAVE_API_KEY`) |
| 7 | **LeetCode session cookie** (`LEETCODE_SESSION`) — coding proof-gate (best-effort) | browser devtools → cookies → leetcode.com | `LEETCODE_SESSION` |
| 8 | *(later)* **Judge0** instance/API — real coding sandbox proof-gate | https://github.com/judge0/judge0 | `JUDGE0_URL` (optional) |

## Obsidian (your workspace)
Point Obsidian at the vault folder and install three community plugins:
- **Kanban** — renders `Board.md` as your task board.
- **Dataview** — powers `Dashboard.md`.
- **Obsidian Git** — two-way sync with the agent (auto-commit/pull).

Deep research is **human-in-the-loop**: when you create a course, the bot hands you a research prompt to
run in **[Claude](https://claude.ai)** (Deep Research); you upload the report into `Uploads/<CODE>/`.

`install.sh` handles the interactive one-time flows (Google OAuth via SSH-tunneled loopback,
AnkiWeb login) and derives the Mentor calendar id automatically. It is idempotent — re-run to
upgrade.
