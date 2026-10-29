# 34: CR-03 C2: champion and challenger view

**What to build:** A "Champion and challenger" view shows both models on the held-out storms: reliability curves on one chart (reusing the calibration view's chart), metric tables (Brier, ROC AUC, top-decile capture), and a list of disagreements: assets the challenger ranks in its top 10 that the champion does not, and why (its top features). The explain panel shows the challenger's top three features beside the rule-based factor breakdown. The proposal and approval of a promotion are shown when the rule allows one. Change request: `docs/change_requests/CR-03_eval_ml_tracing.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 33 (CR-03 C2: challenger in shadow, promotion by approval)

**Status:** ready-for-agent

- [ ] View in the navigation with both reliability curves, metric tables and the disagreements list
- [ ] Explain panel shows the challenger's top three features beside the rule-based breakdown
- [ ] Promotion proposal and approval shown when available; never offered otherwise
- [ ] Loading, error (with retry) and empty states (F3); `fetch` only through the API client (F1)
- [ ] Frontend tests for the view states and the disagreements list
- [ ] `./scripts/check.sh` passes
