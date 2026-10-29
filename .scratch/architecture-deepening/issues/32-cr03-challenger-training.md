# 32: CR-03 C2: synthetic history and challenger training

**What to build:** `scripts/generate_history.py` (seed 42) creates 20 past fictional storms over the same asset base, with varied tracks and intensities, and simulates outcomes from the hidden true fragility parameters plus one effect the rule-based score does not model: assets older than 40 years with condition score 4 or 5 fail more often under combined wind and flood. `docs/assumptions_limitations.md` says the challenger can only find what the synthetic world contains, so its accuracy says nothing about SGW. `make train` trains a gradient-boosted challenger (scikit-learn `HistGradientBoostingClassifier`, new dependency justified in `docs/decisions.md`; no LightGBM, no SHAP) on wind and flood P50/P90, condition score, age, type, elevation-imputed flag, distance to coast and the critical-dependency flag, with isotonic calibration fitted inside the training folds. Validation is by storm: leave-storms-out cross-validation, with Storm Delta held out and never used in training or tuning. It reports Brier score, ROC AUC, top-decile capture and a 10-bin reliability table for the challenger and the rule-based champion on the same storms, and permutation importance per feature. Tunable numbers in `config/models.yaml`. Change request: `docs/change_requests/CR-03_eval_ml_tracing.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `scripts/generate_history.py` reproducible (seed 42); the age × condition effect is in the simulated outcomes only
- [ ] `make train` trains with in-fold isotonic calibration and leave-storms-out validation; Storm Delta held out
- [ ] Storm Delta metrics for both models: Brier, ROC AUC, top-decile capture, reliability bins; written to a results file
- [ ] Test: the age × condition interaction appears among the challenger's top features (permutation importance)
- [ ] `docs/assumptions_limitations.md` note on what the challenger can and cannot show
- [ ] `./scripts/check.sh` passes (training in tests uses a small fixed slice so the suite stays fast)
