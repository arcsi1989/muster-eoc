# 03: Hazard exposure on the map

**What to build:** When an advisory is advanced, every asset and staging area gets wind and flood exposure from that advisory's forecast, with uncertainty. The operator sees the forecast track and cone on the map and each asset's P50/P90 wind and flood depth. Spec: `.scratch/storm-prep-prototype/spec.md`; formulas in the implementation plan section 3 with the readings in the decision log.

**Blocked by:** 02 (Synthetic territory, data contracts and data quality)

**Status:** resolved

- [x] Wind: modified Rankine vortex over the hourly-interpolated track, α from config; Vmax × 0.85 while the storm centre is more than 10 km inland; asset wind = maximum over the track
- [x] Surge and flood depth per the plan; null elevation imputed from the median of the 5 nearest assets, flagged for confidence
- [x] Ensemble: 50 members (config), track shifted perpendicular to its heading by a normal draw with standard deviation equal to the cone radius (config), seeded per advisory; P50 and P90 per hazard reported
- [x] Tropical-storm-force arrival time: median hours from advisory issue until wind ≥ 39 mph, null if never
- [x] Exposure is computed on advance and stored per asset × advisory (and per staging area)
- [x] Map shows the current advisory's forecast track and cone; exposure values appear per asset in the UI
- [x] Unit tests: wind equals Vmax at Rmax and decays monotonically beyond; flood depth zero above surge height; P90 ≥ P50; same seed gives the same numbers
- [x] All tunable numbers live in config, none in code
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-29: Resolved with ht-resolve: built in the step 1-10 commits (8a14132 to ac188e6, 102309d); user confirmed 2026-10-29.
