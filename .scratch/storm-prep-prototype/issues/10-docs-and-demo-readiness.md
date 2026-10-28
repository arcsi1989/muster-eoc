# 10: Documentation and demo readiness

**What to build:** A reviewer clones the repo, follows the README, and runs the full demo in template mode and with Claude; the docs explain the architecture, the assumptions and limitations, and an 8-minute demo script. Spec: `.scratch/storm-prep-prototype/spec.md`; implementation plan M9 with Docker replaced by `make` per the decision log.

**Blocked by:** 07 (Situation report with Claude and checked citations), 08 (Audit list), 09 (Copilot chat)

**Status:** ready-for-agent

- [ ] README: what it is, disclaimer, run steps (`make data`, `make dev`, `make demo-reset`, template and Claude modes, env names), screenshots
- [ ] Architecture document mapping the prototype's components (to the PRD's layers if `docs/PRD.md` exists; otherwise to the plan's sections)
- [ ] Assumptions and limitations, including "approval counts as done", the fictional km grid, the storm modelled on a 2022 landfall, and what was cut (calibration, Docker, Azure)
- [ ] Demo script for the section 8 scenario with timings for an 8-minute video
- [ ] A fresh clone runs end to end in template mode following only the README
- [ ] Disclaimer present in the UI footer and every doc
- [ ] `./scripts/check.sh` passes
