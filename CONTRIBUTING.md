# Contributing

Thanks for helping build Hermes University. The bar is a **solid, coherent base** — read
[ARCHITECTURE.md](ARCHITECTURE.md) first.

## Dev setup
```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/pytest -q          # must be green
```
Python: ruff-formatted, type-friendly, 4-space indent, ~100-char lines.

## Principles to preserve (don't regress these)
1. **The engine owns all numbers.** Skills/prompts never compute GPA/mastery/standing — they call
   `hu-engine`. If you need a number, add it to the engine with a test.
2. **No outcome without a proof.** Keep the `course.yaml` validator strict.
3. **A course is data.** Add subjects by authoring a `course.yaml`, never by adding per-course code or
   per-course skills. The single Faculty professor + Examiner teach any course from its module.
4. **No hardcoded personal/organizational data** in code, skills, or shipped content. Identity/goals
   live in `profile.yaml`; personalize to goals, not work. CI-style check:
   `grep -riE "employer|top-tier-company|<yourname>" engine/ skills/ courses/_TEMPLATE/` must be empty.
5. **Telegram messages are plain text** — no tables/markdown pipe-rows (Telegram can't render them).

## Adding a course
You don't commit courses. Run the system and let the Faculty professor **author** it (deep research →
validated `course.yaml`). Authored courses are private instance data (git-ignored). To share an
example, add a generic, de-personalized module under `tests/fixtures/`.

## Tests
Every change ships with tests. Course/rendering tests use `tests/fixtures/` (generic), never the
private catalog — so `git clone && pytest` passes on a fresh checkout.

## Commits & PRs
Conventional commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`). Keep diffs minimal and
localized; explain the why. Run the suite before opening a PR.
