# Redeploy runbook — bring Hermes University up on a new droplet

Everything you need is in two private GitHub repos + your backup passphrase. This is the exact path
back (RFC-011).

## You need
- **The code repo:** `git@github.com:AlijonovMukhammaddiyor/hermes-university.git` (or HTTPS).
- **The vault repo:** `git@github.com:AlijonovMukhammaddiyor/hermes-vault.git` (or HTTPS).
- **Your backup passphrase** (the contents of the old box's `~/.hermes/backup.key`, which you saved to a
  password manager). Without it you can still restore courses + progress, but you'll re-enter API
  keys/crons/config by hand.
- **Git access on the new box** to clone the two private repos — a GitHub token (HTTPS) or an SSH key
  added to GitHub. (Chicken-and-egg: the token lives *inside* the encrypted bundle, so you supply it
  once for the clone.)

## Steps (new droplet)
1. **Provision** a droplet with the **Hermes Agent** installed (DigitalOcean 1-click), and log in as the
   agent user (the one that owns `~/.hermes`).
2. **Clone the code repo** (HTTPS with a token is simplest):
   ```bash
   git clone https://<GITHUB_TOKEN>@github.com/AlijonovMukhammaddiyor/hermes-university.git ~/hermes-university
   ```
3. **Run bootstrap** with both repo URLs (embed the token in the vault URL too):
   ```bash
   cd ~/hermes-university
   ./bootstrap.sh \
     https://<GITHUB_TOKEN>@github.com/AlijonovMukhammaddiyor/hermes-university.git \
     https://<GITHUB_TOKEN>@github.com/AlijonovMukhammaddiyor/hermes-vault.git
   ```
   It clones the vault, prompts for your **passphrase**, restores `profile.yaml` + `config.env` +
   `~/.hermes/{.env,config.yaml,cron/jobs.json,auth.json}` + the Google-Calendar token + your course
   sources, then runs `install.sh` (engine venv, skills, systemd gateway, vault-sync hook+timer, backup
   timer, and — if Anki is installed — the Anki sync timer).
4. **Install Anki desktop** (only if you want SRS push/pull) so `/usr/local/share/anki` exists, then
   re-run `scripts/install_anki_sync.sh ~/hermes-university ~/vault`.
5. **Re-auth what expired:** Google Calendar (if the token lapsed) and confirm AnkiWeb login in
   `~/.hermes/.env` (the collection re-syncs from AnkiWeb).
6. **Start the gateway:**
   ```bash
   systemctl --user restart hermes-gateway && systemctl --user is-active hermes-gateway
   ```
7. **Verify:**
   ```bash
   ~/hermes-university/.venv/bin/hu-engine status --vault ~/vault --courses ~/hermes-university/courses
   ```
   You should see your courses (e.g. AG201), semester/week, and standing exactly as before. Message the
   bot `status` to confirm Telegram is live.

## Cutover note
If the **old** droplet is still running, **stop its gateway first** (`systemctl --user stop
hermes-gateway`) — two gateways on one Telegram bot token conflict (409). If you deleted the old box,
this is moot.

## What survives without the passphrase
Even if you lose the passphrase: your **vault** (state, grades, progress) and **`_source/courses/`**
(authored course sources, plaintext) restore fine. You'd only re-provide the secrets manually
(`config.env` + `~/.hermes/.env` from your own records) and recreate the crons.
