# 🎓 Hermes University

### Become genuinely great at one thing — a private tutor that turns your goal into a daily plan, fits it around your real life, and coaches you every day over text.

You don't lack ambition or resources. You lack a **system** — something that turns *"I want to master X"*
into what to actually do *tonight*, fit around your real days, with honest proof you're improving. Without
one, ambition quietly rots into a graveyard of half-finished courses. Hermes University is that system:
name one goal, and it researches the field, builds you a real *cited* course, books each day's study on
your calendar around your actual life, and checks your work — with a deterministic engine tracking real
mastery, never guesswork. No cohort, no fixed schedule to fall behind, no subscription. It runs on your
own machine, with your own keys.

<p align="left">
  <img alt="license: MIT" src="https://img.shields.io/badge/license-MIT-green.svg">
  <img alt="python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-blue.svg">
  <img alt="runs on the Hermes Agent" src="https://img.shields.io/badge/runtime-Hermes%20Agent-8A2BE2.svg">
  <img alt="status: pre-1.0" src="https://img.shields.io/badge/status-pre--1.0-orange.svg">
</p>

> **This page is all you need** — what it does, what you'll need, how to set it up, and how to use it
> every day. The deeper docs at the bottom are optional; you won't touch them to get running.

**Jump to:** [What it's like](#what-its-like) · [Why it's different](#why-its-different) ·
[How it works](#how-it-works) · [What you'll need](#what-youll-need) · [Set it up](#set-it-up) ·
[Using it every day](#using-it-every-day) · [Never lose progress](#never-lose-progress)

## What it's like
You talk to a Telegram bot. Everything else happens around you.

```text
You  ▸  create course  become a great AI engineer

Bot  ▸  Love it — a few quick questions so I build this around *you*:
        where are you with ML now, how many hours a week, and by when?
        …
Bot  ▸  📎 Here's a deep-research prompt. Run it in Claude and drop the report
        back — I design the course from real sources, never from memory.

You  ▸  «uploads the research report»

Bot  ▸  Built  AI Engineering  — 2 semesters · 8 units · cited materials and a
        week-by-week plan. Want a short placement exam to skip what you know?

───────────────  next morning, 8:00  ───────────────

Bot  ▸  ☀️ Today — booked 20:00–21:30 on your calendar (your best hours):
        1.  Read  — "Attention Is All You Need", §3
        2.  Build — a toy self-attention head, ≤ 40 lines
        Reply `done` with a link when the proof is in.

You  ▸  done  github.com/…/attention.py

Bot  ▸  ✓ Verified against the rubric. 🔥 6-day streak · Anki card queued.
        Tomorrow: multi-head attention.
```

<!-- SCREENSHOTS: drop GIFs/PNGs here — (1) the exchange above in Telegram · (2) the Obsidian Kanban
     board · (3) a rendered Syllabus.md. Real visuals sell it. -->

## Why it's different
- **One objective, not a course catalog.** You don't browse subjects — you name the single thing you
  want to become, and everything (the curriculum, the schedule, the daily tasks, the whole transcript)
  exists only to get you there.
- **Built around your life, not a fixed schedule.** It reads your real calendar, finds your free time,
  and books each day's study at your best hours — then re-paces the plan month over month from how you're
  actually doing. No cohort, no course calendar to fall behind.
- **It researches, it doesn't hallucinate.** Course design is grounded in a real, cited research report
  (you run a deep-research prompt in Claude; it authors from that) plus web search — a machine-checked
  gate rejects any course built from the model's memory.
- **It starts from fundamentals, then tests you out.** Every course is built complete from the ground up;
  a rigorous **placement exam** decides what to skip — never an assumption about your level.
- **The numbers are real.** A deterministic engine owns mastery, GPA, streak, standing, and promotion —
  the AI only teaches and grades to a rubric. **No outcome without a proof.**
- **You own it end-to-end.** Self-hosted, your keys, model-agnostic (DeepSeek by default). Your progress
  is backed up to your own private git and moves to a new machine in one command.

## How it works
One brain — a deterministic engine on your server — and a few ways to reach it. Most of the time you
only touch the first.

```mermaid
flowchart LR
  You([you]) <==>|"chat — do everything"| TG["📱 Telegram<br/>coach + control"]
  subgraph brain["your always-on server — your keys"]
    ENG["⚙️ Deterministic engine<br/>research · GPA · mastery · proofs · schedule"]
    VAULT[("📓 Vault<br/>git-synced")]
    ENG <--> VAULT
  end
  TG <--> ENG
  ENG ==>|"builds your routine"| CAL["📅 Google Calendar<br/>study blocks at your best hours"]
  ENG -.->|"see + track"| OB["🗂️ Obsidian<br/>board · syllabus · home"]
  ENG -.->|"optional"| AK["🔁 Anki<br/>spaced repetition"]
```

- **Telegram — where you live.** Your coach *and* control panel: daily nudges, every command, voice
  answers, files. Routine work never needs anything else.
- **Google Calendar — where your routine lives.** It reads your real schedule, finds your free hours,
  and books each day's study on a dedicated calendar you can toggle or wipe.
- **Obsidian — where you look.** A **Kanban board** you track work on, a live **Home** dashboard, and
  every syllabus / transcript. Two-way — drag a card to *Done* and the night audit verifies it.
- **Anki — optional retention.** Turn it on and proven concepts become spaced-repetition cards on your
  phone. Leave it off and everything else still works. *(Plus an optional daily tech/AI briefing.)*

## What you'll need
An *API key* here is just a secret password a service gives you so your bot can use it — the setup
wizard asks for each one, so grab them first.

| What | Why | Need it? | Where to get it |
|---|---|---|---|
| An **always-on computer** | so your coach keeps running when your laptop is closed | ✅ | any cheap Linux/macOS cloud server (a "VPS", ~1–2 GB RAM) |
| The **Hermes Agent** | the free runtime everything sits on | ✅ | one install command (below) |
| An **AI model key** (DeepSeek) | the brain that teaches + grades your work | ✅ | [platform.deepseek.com](https://platform.deepseek.com) |
| A **Telegram bot** | the coach you chat with | ✅ | a token from [@BotFather](https://t.me/BotFather) + your id from [@userinfobot](https://t.me/userinfobot) |
| A **web-search key** (Serper) | grounds course research in real sources | ✅ | [serper.dev](https://serper.dev) (free tier) |
| An **AnkiWeb** account | spaced-repetition review on your phone | optional | [ankiweb.net](https://ankiweb.net) |
| A **Google** account | to book study on your calendar | optional | Google Cloud console (a one-time sign-in) |

## Set it up
Three commands, then you just chat.

**1. Install the Hermes Agent** on your always-on computer (it bundles everything it needs):
```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

**2. Run the setup wizard** — it asks for the keys above and wires everything together:
```bash
git clone https://github.com/AlijonovMukhammaddiyor/hermes-university.git
cd hermes-university
./setup.sh
```
It writes your keys into the agent, installs the web-search plugin, and sets up the engine, your notes
vault, the coaching skills, and the daily automations.

**3. Start the coach and say hello:**
```bash
hermes gateway install && hermes gateway start
```
Then message your bot: **`create course <what you want to become>`** — it takes it from there.

**See your progress in Obsidian (recommended).** Point [Obsidian](https://obsidian.md) at the vault
folder (`~/vault`) and install three free community plugins — **Kanban** (your task board), **Dataview**
(the dashboard), and **Obsidian Git** (keeps it in sync). Now you can watch the board and read every
syllabus and transcript.

**Put study on your calendar (optional).** In the [Google Cloud console](https://console.cloud.google.com):
enable the *Google Calendar API*, create an *OAuth client → Desktop app*, download the JSON to
`~/.hermes/gcp-oauth.keys.json`, then run `hermes mcp login google-calendar` and approve it in the browser
once. (The one-time browser sign-in can't be scripted — the rest is automatic afterward.)

> **The one manual step, by design:** when you create a course, the bot hands you a research prompt to
> run in [Claude](https://claude.ai) (Deep Research). You drop the report back into your vault and it
> authors the course *from those real sources* — this is why courses are cited, never hallucinated.

## Using it every day
**Talk to the bot to *do* things · open Obsidian to *see* things · open Anki to *review*.** You never
touch a terminal for routine work, and every destructive action asks first.

The daily loop — you mostly just do the work and mark it done; the engine drives the rest:
- **Morning** — the bot assigns your day's tasks (a lesson + a sized task), adds them to your **Today**
  board, and books study blocks on your calendar.
- **During the day** — do a task, then reply **`done`** with a link (or drag its card to **Done** in
  Obsidian). Answer quizzes by text or voice memo.
- **Night** — the audit verifies each task's **proof**. Verified counts; not verified moves to *Proof
  Pending* (never a fake pass). Proven concepts become **Anki cards** automatically.

Everything is a chat command, by course **name**:

| Say this | It does |
|---|---|
| `status` | where you are: courses, what's due, what's blocked on you, your streak |
| `create course <goal>` | research → build a new course |
| `courses` | list available + your enrolled courses and their status |
| `enroll <name>` | start a course (it authors first if needed, then a placement exam) |
| `done <link>` | mark today's task done |
| `archive <name>` | **soft-drop** — hides it, keeps everything, reversible (`restore` to undo) |
| `delete <name>` | **hard delete** — removes it for good (you re-type the command to confirm) |
| `tailor <name>` | re-run placement / adjust the pace + depth |
| `pause` · `resume <name>` | stop / restart its daily assignments |
| `profile` · `set goal <…>` · `set daily cap <n>` | see + steer what it builds toward |

## Never lose progress
Your goal, grades, courses, and an encrypted copy of your keys are backed up to your own private git
daily. Moving to a new computer is one command — `./bootstrap.sh <code-url> <vault-url>` — and everything
restores exactly as it was.

## Principles
1. Numbers are computed by code, not the model. 2. No outcome without a proof. 3. A course is data, not
code. 4. Personalize to your **goals**, never your work. 5. No hardcoded personal data — your identity
lives in one private `profile.yaml`.

## Go deeper (optional — not needed to run it)
- **[GUIDE.md](GUIDE.md)** — the full command manual, the daily loop in depth, and troubleshooting.
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — how it works inside (engine · skills · courses · lifecycle).
- **[PREREQUISITES.md](PREREQUISITES.md)** — the accounts/keys checklist on its own.
- **[CONTRIBUTING.md](CONTRIBUTING.md)** · **`docs/RFC-00*.md`** — how to help + the full design record.

## Built on
The [Hermes Agent](https://github.com/NousResearch/hermes-agent) (skills, cron, Telegram gateway) + a
deterministic Python engine. Model-agnostic via the provider seam (DeepSeek by default).

## License
[MIT](LICENSE).
