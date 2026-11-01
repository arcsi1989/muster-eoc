# 43: Whole-repo review against the coding standards, and fixes

**What to build:** Forty tickets by different agents were reviewed one at a time; inconsistencies across them only show in a whole-repo pass. Review the entire codebase (backend, frontend, scripts, config), not a diff, against `CODING_STANDARDS.md` (cite rule IDs) and the deep-module vocabulary (`docs/agents/`, `GLOSSARY.md`, the ADRs): duplicated logic across modules, shallow pass-through modules, naming drift from the glossary, tunable numbers in code instead of `config/`, dead code (for example prompt files or helpers no longer loaded), inconsistent error handling or API shapes, missing tests on public behaviour. Write the findings, ranked, to `docs/review/whole-repo-review.md`, then fix every finding that is mechanical and safe in small commits, each with `./scripts/check.sh` green; list what was left and why. Do not change behaviour, playbook text or thresholds.

**Blocked by:** 37, 38, 39, 40, 41, 42

**Status:** resolved

- [x] `docs/review/whole-repo-review.md`: ranked findings with file references and rule IDs, each marked fixed or left with a reason
- [x] Fixes in small commits; no behaviour change (the demo scenario tests and the eval gate unchanged)
- [x] `./scripts/check.sh` passes

## Comments

- 2026-11-01: Reviewed; auto-merge held back for an owner decision (see .ht/reply.md in the worktree).

- 2026-11-01: Merged into `main` as 35920e9 after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 3/3 ticked.
- 2026-11-01: Owner accepted both disclosed visible changes (JSON body on unexpected 500s; glossary wording in UI and README); merged as 35920e9.
