# Hermes University

> Give it a goal. It researches and builds you a real university course — syllabus, best-in-class
> materials, and a path to mastery — then teaches it every day, grades proof-gated work, and tracks a
> durable GPA across two rigorous semesters.

A **course-agnostic autonomous learning engine** on the [Hermes Agent](https://github.com/NousResearch/hermes-agent).
A single **Faculty** professor authors any course by deep, cited research (never the model's memory)
and teaches it; a **deterministic Registrar** owns every number (GPA, mastery, FSRS, promotion);
spaced-repetition cards flow to your phone via Anki. Install it on your own always-on box, bring your
own API keys, and manage it all from Telegram.

## Principles
1. **Numbers are computed by code, not the model** — the engine owns GPA/streak/mastery/FSRS/standing.
2. **No outcome without a proof** — every outcome is measurable, Bloom-tagged, and proof-gated.
3. **A course is data, not code** — the whole curriculum + teaching profile + mastery model is one
   `course.yaml`; the engine and professor never change per course.
4. **Personalize to your goals, not your work.**
5. **No hardcoded personal/organizational data** — identity lives in one git-ignored `profile.yaml`.

## Quickstart
```bash
git clone <repo> hermes-university && cd hermes-university
cp profile.example.yaml profile.yaml     # your name + goals (git-ignored)
cp config.env.example config.env         # your API keys / infra (git-ignored)
# fill both in — see PREREQUISITES.md for the keys/accounts you need
./install.sh                             # idempotent; re-run to upgrade
```
The catalog starts **empty**. Message the bot **`create course <your goal>`** (or `enroll <CODE>`) and
the Faculty professor interviews you, researches the field, and authors the course.

## How it works
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — the canonical design (engine · skills · courses · lifecycle).
- **[PREREQUISITES.md](PREREQUISITES.md)** — the third-party keys/accounts (LLM, Telegram, Anki, Calendar).
- **`docs/RFC-00*.md`** — the historical design record.

## Layout
```
engine/     deterministic authority (state, gradebook, FSRS, proof-gates, course schema, docs, CLI)
skills/     registrar · professor (Faculty Handbook) · examiner   (rendered per instance)
courses/    course modules — ships with only _TEMPLATE/ (author on demand; authored courses are private)
profile.yaml   your identity + goals (git-ignored; ships as profile.example.yaml)
tests/      pytest suite (fixtures under tests/fixtures — no personal data)
```

## Develop
```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/pytest -q
```
See [CONTRIBUTING.md](CONTRIBUTING.md).

## License
[MIT](LICENSE).
