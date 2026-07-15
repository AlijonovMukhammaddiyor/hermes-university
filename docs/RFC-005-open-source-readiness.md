# RFC-005 — Open-Source Readiness & Goal-Based Personalization

Status: **ACCEPTED — implementing** · Date: 2026-07-07
Consolidation pass. Makes the base a solid, publishable open-source repo. Supersedes scattered
identity/config across RFC-001..004.

## 0. Why
The system works but has accumulated patchiness and **hardcoded personal/organizational data**, which
blocks open-sourcing. Two owner rules now bind everything:
1. **No hardcoded person- or org-specific data anywhere in the code, skills, or shipped courses.**
   (No learner name, no employer, no school, no target-company framing.)
2. **Personalize to the learner's *goals*, never their *work*.** Applied projects advance the learner
   toward who they want to become (portfolio / signature work), not their day job.

And the base must be **worth starring/forking**: coherent architecture, clean docs, reproducible
install, no drift.

## 1. Identity → one `profile.yaml` (goal-based, git-ignored)
A single instance config holds **all** identity + goals; nothing personal lives in code:
```yaml
# profile.yaml  (git-ignored; ships as profile.example.yaml with generic defaults)
name: "Learner"
timezone: "UTC"
goal: "Become one of the best in the fields you study, able to work with the best people."
target_level: "top of the field"          # the bar to design courses backward from
current_level: "capable beginner"          # calibrates placement
interests: []                              # optional depth branches
daily_task_cap: 4
credential_name: "Hermes University Certificate of Mastery"   # was a hardcoded degree name
```
- New `engine/profile.py` loads `profile.yaml` (falls back to `profile.example.yaml`).
- `render_skills.py` sources template vars from the profile: `{{LEARNER_NAME}}`, `{{GOAL}}`,
  `{{TARGET_LEVEL}}`, `{{TIMEZONE}}`, `{{DAILY_TASK_CAP}}`.
- `engine/state.py` `Degree.name` + `engine/docs.py` degree title come from the profile — **no
  hardcoded credential string**.

## 2. De-personalization (surgical, complete)
- **Engine:** remove `DEGREE_NAME`/`Degree.name` hardcoded strings → profile-driven, generic default.
- **Skills:** professor/registrar reference `{{GOAL}}` / `{{TARGET_LEVEL}}` — never a hardcoded level.
  Applied work is grounded in the learner's **goal**, never an employer/product.
- **Courses:** the shipped repo contains **no personal courses** (see §3). The `_TEMPLATE` and the
  authoring protocol reference goals, not work.
- **Tests:** fixtures use a neutral name.

## 3. Empty catalog (owner's choice)
- The public repo ships **only `courses/_TEMPLATE/`**. The catalog starts empty; the learner authors
  courses on demand via `create course`.
- `.gitignore`: `courses/*` **except** `!courses/_TEMPLATE/`, plus `profile.yaml`, `config.env`,
  `.env`, and the vault. Authored courses are **private instance data** (backed up via the vault's
  rendered docs and/or a private overlay) — never in the public repo.
- Existing personal courses are `git rm --cached`ed (kept on disk as instance data), so history going
  forward is clean. (A pre-publish squash/fresh-init can purge them from history entirely.)

## 4. Modernize the examiner (data-driven, like the professor)
The examiner must not hardcode per-course finals. It reads the course module's **finals unit +
assessments** and grades against them — one examiner, any course. (Same principle that RFC-004 applied
to professors.)

## 5. Consolidate & document (OSS-grade)
- `ARCHITECTURE.md` — one canonical description of the system (engine owns numbers; course = data;
  Faculty Handbook professor; lifecycle; personalization). RFC-001..005 kept as historical `docs/`.
- **Align skill versions** (registrar/examiner/professor) to one coherent version.
- `README.md` (what it is · quickstart · how it works · third-party keys), `CONTRIBUTING.md`, repo
  `LICENSE` (MIT), and a **reproducible install/deploy** script/doc (replaces hand-run SSH).

## 6. Fix the accumulated breakage in a clean redeploy
- Restore `courses/CS270` from git (working-tree deletion) — as **instance data**.
- Repoint stale crons: `uni-week` → `examiner` + `professor`; `uni-monthly` → `registrar` +
  `professor`; **remove** the leftover one-off `deepen-cs270`.
- Deploy via the reproducible script, not manual git surgery (the drift source).

## 7. Acceptance
`pytest tests/test_profile.py` — scans the tree against your private, git-ignored `.pii-banlist`
returns **nothing**. Fresh clone + `profile.example.yaml` + keys → a working, empty-catalog instance
that authors its first course on demand. Tests green. Skill versions aligned. README/ARCHITECTURE
present.

## 8. Risks
- **Breaking the live instance** → migrate the owner's identity into a private `profile.yaml` and keep
  their authored courses as git-ignored instance data before untracking; verify before redeploy.
- **History still contains personal data** → note the pre-publish squash option; not blocking for a
  private repo today.
