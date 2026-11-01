# 33: CR-03 C2: challenger in shadow, promotion by approval

**What to build:** A `RiskModel` protocol (`predict(asset_features) -> p_fail, factors, version`) that the rule-based score and the challenger both implement. The challenger runs in **shadow**: it scores every advisory and its scores are stored with its model version, but it never drives the ranking, the playbook check or the package. A promotion rule in `config/models.yaml` lets the challenger be proposed only if it beats the champion on held-out storms by a set margin on Brier score and top-decile capture and passes the calibration check; promotion then needs human approval through the existing model-version approval path (ticket 09), logged. Never auto-promote. Issuing an advisory stays under 2 seconds (CR-02 C1). Change request: `docs/change_requests/CR-03_eval_ml_tracing.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 32 (CR-03 C2: synthetic history and challenger training)

**Status:** resolved

- [x] `RiskModel` protocol; rule-based score and challenger both implement it
- [x] Shadow scores stored per advisory with the challenger's model version; ranking, playbook check and package use only the approved champion
- [x] Promotion rule in `config/models.yaml`; a challenger is proposed only when it passes; approval through the existing model-version path, audited
- [x] Tests: unapproved model scores never reach the package; the rules stay champion until a person approves; a challenger failing the margin is never proposed
- [x] Advance stays under 2 seconds with shadow scoring
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-30: Merged into `main` as d250850 after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 6/6 ticked.
