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
2. **OAuth consent screen** → *External* → **Publish app**. Leave it in *Testing* and Google expires the
   refresh token after **7 days**, so booking dies every week. It's your own unverified app, so the
   browser warns once — *Advanced → Go to … (unsafe)*.
3. **Credentials → Create OAuth client ID → Desktop app** → download the JSON. It must be *Desktop app*;
   a *Web application* client can't do the loopback redirect this uses.
4. Save it to `~/.hermes/gcp-oauth.keys.json` and give the wizard that path (`GOOGLE_OAUTH_CREDENTIALS`).
   `setup.sh` registers the MCP for you.
5. Authorize once — opens a browser, so it can't be scripted:
   ```bash
   GOOGLE_OAUTH_CREDENTIALS=~/.hermes/gcp-oauth.keys.json npx -y @cocal/google-calendar-mcp auth
   ```
   **Headless server?** Tokens aren't machine-bound: run that on your laptop, then copy them over.
   ```bash
   ssh you@server mkdir -p .config/google-calendar-mcp
   scp ~/.config/google-calendar-mcp/tokens.json you@server:~/.config/google-calendar-mcp/
   ```

## How course research works
Deep research is **human-in-the-loop**: when you create a course, the bot hands you a research prompt to
run in **[Claude](https://claude.ai)** (Deep Research); you drop the report into `Uploads/<CODE>/`, and it
authors the course from that. `install.sh`/`setup.sh` are **idempotent** — re-run to upgrade.
