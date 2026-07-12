# Prerequisites

Two steps get you running: install the **Hermes Agent** (the runtime), then run our **wizard**.

## 1. Install the Hermes Agent
On an always-on Linux/macOS host (a small VPS is plenty — ~1–2 GB RAM; the only hard prereq is `git`):

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

It bundles Python 3.11, Node, ripgrep and ffmpeg. You'll need a model provider with **≥64k context**
(DeepSeek by default). Config lives in `~/.hermes/` (`config.yaml` + `.env`).

## 2. Get these accounts / keys
The wizard asks for them; grab them first.

| What | Where | Key(s) | Required |
|---|---|---|---|
| **LLM key** (DeepSeek) | https://platform.deepseek.com | `DEEPSEEK_API_KEY` | ✅ |
| **Telegram bot** token + your numeric user id | @BotFather · @userinfobot | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS` | ✅ |
| **Web search** | https://serper.dev (free tier) | `SERPER_API_KEY` | ✅ |
| **AnkiWeb** account (same one your phone uses) | https://ankiweb.net | `ANKIWEB_USERNAME`, `ANKIWEB_PASSWORD` | optional |
| **Google OAuth** (Desktop client json) | https://console.cloud.google.com | `GOOGLE_OAUTH_CREDENTIALS` (path) | optional |
| **LeetCode session cookie** | browser devtools → cookies → leetcode.com | `LEETCODE_SESSION` | optional |
| **Judge0** endpoint | https://github.com/judge0/judge0 | `JUDGE0_URL` | optional |

## 3. Run the wizard
```bash
git clone https://github.com/AlijonovMukhammaddiyor/hermes-university.git
cd hermes-university
./setup.sh
```
It prompts for the keys above, writes them to `config.env` **and** into the agent (`hermes config set`),
installs the web-search plugin (`robbyczgw-cla/hermes-web-search-plus`), then runs `install.sh` (engine ·
vault · skills · crons · timers · a `doctor` preflight). Finally:

```bash
hermes gateway install && hermes gateway start     # the always-on Telegram gateway
```

Then message your bot: **`create course <what you want to become>`**.

## Obsidian (your workspace)
Point Obsidian at the vault folder (`~/vault`) and install three community plugins:
- **Kanban** — renders `Board.md` as your task board.
- **Dataview** — powers the dashboard views.
- **Obsidian Git** — two-way sync with the agent (auto-commit/pull).

## Google Calendar (optional) — one-time OAuth
1. In the [Google Cloud console](https://console.cloud.google.com): create/select a project and
   **enable the Google Calendar API**.
2. **OAuth consent screen** → *External* → add your own account as a test user.
3. **Credentials → Create OAuth client ID → Desktop app** → download the JSON.
4. Save it to `~/.hermes/gcp-oauth.keys.json` (or point `GOOGLE_OAUTH_CREDENTIALS` at its path).
5. Register + authorize the calendar MCP: `hermes mcp catalog` to find it, then
   `hermes mcp login google-calendar`. *(This step is guided, not scripted — the OAuth browser consent
   can't be automated.)*

## How course research works
Deep research is **human-in-the-loop**: when you create a course, the bot hands you a research prompt to
run in **[Claude](https://claude.ai)** (Deep Research); you drop the report into `Uploads/<CODE>/`, and it
authors the course from that. `install.sh`/`setup.sh` are **idempotent** — re-run to upgrade.
