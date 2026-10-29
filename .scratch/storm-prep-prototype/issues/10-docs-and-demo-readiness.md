# 10: Documentation and demo readiness

**What to build:** A reviewer clones the repo, follows the README, and runs the full demo in template mode and with Claude; the docs explain the architecture, the assumptions and limitations, and an 8-minute demo script. Spec: `.scratch/storm-prep-prototype/spec.md`; implementation plan M9 with Docker replaced by `make` per the decision log.

**Blocked by:** 07 (Situation report with Claude and checked citations), 08 (Audit list), 09 (Copilot chat)

**Status:** resolved

- [x] README: what it is, disclaimer, run steps (`make data`, `make dev`, `make demo-reset`, template and Claude modes, env names), screenshots
- [x] Architecture document mapping the prototype's components (to the PRD's layers if `docs/PRD.md` exists; otherwise to the plan's sections)
- [x] Assumptions and limitations, including "approval counts as done", the fictional km grid, the storm modelled on a 2022 landfall, and what was cut (calibration, Docker, Azure)
- [x] Demo script for the section 8 scenario with timings for an 8-minute video
- [x] A fresh clone runs end to end in template mode following only the README
- [x] Disclaimer present in the UI footer and every doc
- [x] `./scripts/check.sh` passes

## Verification

A fresh clone (`git clone` into a scratch folder) followed only the README: `make install`, `make data` (git stayed clean: byte-identical data; all demo seed facts hold), the backend served advisory 1 with a decision package and a template draft, and `./scripts/check.sh` passed 7/7 inside the clone. Screenshots show the stacked small-screen layout (the agent's browser window could not be widened).

## Comments

- 2026-10-29: Resolved with ht-resolve: built in the step 1-10 commits (8a14132 to ac188e6, 102309d); user confirmed 2026-10-29.
