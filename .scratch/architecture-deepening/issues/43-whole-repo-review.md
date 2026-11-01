# 43: Whole-repo review against the coding standards, and fixes

**What to build:** Forty tickets by different agents were reviewed one at a time; inconsistencies across them only show in a whole-repo pass. Review the entire codebase (backend, frontend, scripts, config), not a diff, against `CODING_STANDARDS.md` (cite rule IDs) and the deep-module vocabulary (`docs/agents/`, `GLOSSARY.md`, the ADRs): duplicated logic across modules, shallow pass-through modules, naming drift from the glossary, tunable numbers in code instead of `config/`, dead code (for example prompt files or helpers no longer loaded), inconsistent error handling or API shapes, missing tests on public behaviour. Write the findings, ranked, to `docs/review/whole-repo-review.md`, then fix every finding that is mechanical and safe in small commits, each with `./scripts/check.sh` green; list what was left and why. Do not change behaviour, playbook text or thresholds.

**Blocked by:** 37, 38, 39, 40, 41, 42

**Status:** ready-for-agent

- [ ] `docs/review/whole-repo-review.md`: ranked findings with file references and rule IDs, each marked fixed or left with a reason
- [ ] Fixes in small commits; no behaviour change (the demo scenario tests and the eval gate unchanged)
- [ ] `./scripts/check.sh` passes
