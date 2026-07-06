# Hermes University

A general, **course-agnostic** autonomous learning engine on the [Hermes Agent](https://github.com/NousResearch/hermes-agent).
Scheduled professors teach concept-first, assign **proof-gated** work, and grade to rubrics; a
**deterministic Registrar** tracks a durable GPA/transcript across two rigorous 3-month semesters,
and spaced-repetition cards flow to your phone via Anki (FSRS).

Designed to be **installed at once** on your own always-on box — bring your own API keys.

- **Design:** see [`docs/RFC-001-architecture.md`](docs/RFC-001-architecture.md) (the canonical spec).
- **Prerequisites (API keys/accounts):** see [`PREREQUISITES.md`](PREREQUISITES.md).
- **Install:** `cp config.env.example config.env`, fill it in, then `./install.sh`.

## Principles
1. **Numbers are computed by code, not the model.** The engine owns GPA/streak/mastery/FSRS; the LLM
   only teaches, grades to a rubric, and nudges.
2. **No outcome without a proof.** Every learning outcome is measurable, Bloom-tagged, and gated by a
   concrete proof — above "apply," passing needs performance *and* a self-explanation.
3. **A course is data, not code.** Register any subject by authoring its module (curriculum +
   rubrics + professor skill + proof mapping); the engine is unchanged.

Status: **v2 in design** (see RFC). v1 runs on the droplet during the rebuild.
