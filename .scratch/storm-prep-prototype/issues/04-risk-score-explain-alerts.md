# 04: Risk score, explanation and alerts

**What to build:** The placeholder score is replaced by the real risk score. A Planning Section member sees the ranked risk list with rank-change arrows, opens an asset's explanation drawer to see exactly why it ranks where it does, and gets alerts for sudden changes. `make data` now proves every demo seed fact. Spec: `.scratch/storm-prep-prototype/spec.md`; formulas in the implementation plan section 3 with the readings in the decision log.

**Blocked by:** 03 (Hazard exposure on the map)

**Status:** resolved

- [x] Fragility per asset type and hazard with the condition adjustment; p_fail combines wind and flood; failure probability is the mean over ensemble members
- [x] Consequence is one hop: own customers + customers of directly dependent assets + policy weight of each directly fed facility (config), each downstream entity counted once
- [x] Risk = p_fail × consequence; rank descending; factor breakdown stored per asset × advisory
- [x] Confidence high / medium (inspection over 3 years) / low (imputed elevation), with reason; never changes the score
- [x] Alerts: risk crosses the threshold (config), entry into the top 10, or a rise of 10+ places; at advisory 1 the top 10 is "initial", with no rank moves
- [x] `GET /assets/{id}/explain?advisory=` and `GET /alerts?advisory=`; explain drawer with factor bar chart, confidence badge and dependencies; rank-change arrows in the list; alert panel; clicking an asset on the map opens its explanation
- [x] `make data` runs hazard and scoring and fails loudly if any seed fact from the plan's section 2.2 does not hold (SUB-07 p_fail ≥ 0.20 at advisory 3; PS-14 flood P90 > 0.5 m from advisory 3 and wind arrival within 12 h at advisory 5; STG-02 floods from advisory 4; 6 fuelled generators fewer than critical-feeding top-25 assets)
- [x] Unit tests: p_fail in [0, 1] and monotonic in exposure; poor condition never lowers p_fail; top 10 changes between advisories 2 and 4; explanation factors reproduce the stored risk
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-29: Resolved with ht-resolve: built in the step 1-10 commits (8a14132 to ac188e6, 102309d); user confirmed 2026-10-29.
