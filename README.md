# 🎓 Hermes University

**A self-driving personal university.** Tell it a goal; it **researches the field**, **builds you a
real course** (full A–Z syllabus, best-in-class materials, week-by-week plan), then **teaches you every
day** — tracking your progress on a Kanban board, coaching you over Telegram, and drilling you with
spaced repetition. All on your own always-on box, with your own API keys.

> *"I want to be one of the best AI engineers."* → a researched 10-week course, a placement exam so it
> skips what you already know, daily proof-gated tasks, and a transcript that means something.

<!-- SCREENSHOTS: (1) the Telegram create-course + research handoff, (2) the Obsidian Kanban board,
     (3) a rendered Syllabus.md with the week-by-week plan. Drop GIFs/PNGs here — visuals sell it. -->

---

## Why it's different
- **It researches, it doesn't hallucinate.** Course design is grounded in a real, cited research
  report (you run a deep-research prompt in Claude; it authors from that) plus mandatory web search — a
  machine-checked gate rejects any course built from the model's memory.
- **It starts from fundamentals, then tests you out.** Every course is built complete from the
  foundations up; a rigorous **placement exam** decides what to skip — never an assumption about your
  level.
- **The numbers are real.** A deterministic engine owns GPA, mastery, streak, standing, and promotion —
  the LLM only teaches and grades to a rubric. No outcome without a proof.
- **A course is data, not code.** One `course.yaml` holds the whole curriculum + teaching profile +
  mastery model. One professor skill teaches *any* course. Add a subject, not a subsystem.

## Three surfaces, one brain
- **Telegram** — your coach: daily nudges, quick-actions, voice answers, file handoffs.
- **Obsidian** — your workspace: a **Kanban board** you track work on, a live dashboard, and every
  syllabus / resource / transcript. Two-way — drag a card to *Done* and the night audit verifies it.
- **Anki** — retention: spaced-repetition cards to your phone (FSRS).

## Quickstart
```bash
git clone <repo> hermes-university && cd hermes-university
cp profile.example.yaml profile.yaml     # your name + goals (git-ignored)
cp config.env.example config.env         # your API keys / infra (git-ignored)
# fill both in — see PREREQUISITES.md
./install.sh                             # idempotent; re-run to upgrade
```
In Obsidian, install the **Kanban**, **Dataview**, and **Obsidian Git** plugins (see the vault README).
Then message the bot **`create course <your goal>`** and it takes it from there.

## How a course gets built
```
create course <goal>
   → short intake interview
   → 📎 it hands you a deep-research prompt → you run it in Claude, upload the report
   → it builds the FULL A–Z syllabus (fundamentals → advanced) with cited materials + a week-by-week plan
   → placement exam (skip only what you prove at ≥B)
   → your personalized MyPlan.md — and the daily loop begins
```

## Using it every day
**One rule: talk to the bot to *do* things · open Obsidian to *see* things · open Anki to *review*.**
You never need a terminal for anything routine.

**The daily loop** — morning it assigns your tasks onto the Board's **Today**; you do them and drag a
card to **Done** (or reply `done`, or answer by voice); night it verifies each **proof** — unverified
work bounces to *Proof Pending*, never a fake pass — and proven concepts become Anki cards. Ask
`status` (or open `Home.md`) anytime for where you are and what's blocked on you.

**Manage everything from Telegram, by course name:**

| Say | It does |
|---|---|
| `courses` · `status` · `profile` | list courses · where you are · view/edit your goals |
| `create course <goal>` · `enroll <name>` | research + build · enroll (authors, then placement) |
| `archive <name>` / `restore <name>` | soft-drop (reversible) / bring it back |
| `delete <name>` | permanent — asks you to echo `delete <name>` to confirm |
| `tailor <name>` · `pause` / `resume <name>` | re-run placement, adjust pace · stop/restart assignments |

Every destructive action **confirms first** (`yes` / `cancel`; a hard delete needs the name echo).
Courses move through a visible lifecycle: `🔬 researching → ✍️ authoring → 🎯 placement → 🟢 active →
🗄️ archived` (🔬 = waiting on your research upload). **Full manual: [GUIDE.md](GUIDE.md).**

## Principles
1. Numbers are computed by code, not the model. 2. No outcome without a proof. 3. A course is data,
not code. 4. Personalize to your **goals**, never your work. 5. No hardcoded personal/organizational
data — identity lives in one git-ignored `profile.yaml`.

## Learn more
- **[GUIDE.md](GUIDE.md)** — how to use & manage it day-to-day (commands, the daily loop, surfaces).
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — how it works (engine · skills · courses · lifecycle).
- **[PREREQUISITES.md](PREREQUISITES.md)** — the API keys/accounts + Obsidian plugins.
- **`docs/RFC-00*.md`** — the design record. **[CONTRIBUTING.md](CONTRIBUTING.md)** to help.

## Built on
The [Hermes Agent](https://github.com/NousResearch/hermes-agent) (skills, cron, Telegram gateway) +
a deterministic Python engine. Model-agnostic via the provider seam (DeepSeek by default).

## License
[MIT](LICENSE).
