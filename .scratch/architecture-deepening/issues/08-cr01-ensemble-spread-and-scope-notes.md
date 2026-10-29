# 08: CR-01 C4 + C5: ensemble spread and scope notes

**What to build:** The hazard ensemble spreads the track as wide as the cone implies: cross-track σ is `ensemble.sigma_cone_factor` × `cone_radius_km`, with the factor 1.0 in `config/scoring.yaml` (was 0.5, hard-wired). The demo seeds are re-checked after the wider spread moves P90 depths; if a seed breaks, the generator inputs are fixed, never the rules. The assumptions doc and README state the limits the panel will ask about. Change request: `docs/change_requests/CR-01_operational_realism.md`; target files: `docs/change_requests/CR-01_delivered/`. Record anything ambiguous in `docs/decisions.md`.

**Blocked by:** 06 (CR-01 C3: activation is declared, not computed (backend))

**Status:** ready-for-agent

- [ ] `ensemble.sigma_cone_factor: 1.0` in `config/scoring.yaml`, read by the ensemble; no factor left in code
- [ ] Test: the cross-track spread scales with the factor
- [ ] Every demo seed still holds (seed check and demo test green); any generator change recorded in `docs/decisions.md`
- [ ] `docs/assumptions_limitations.md`: production would use NHC probabilistic products (wind-speed probabilities, P-Surge); surge and elevation share one vertical datum; wind is 1-minute sustained; distribution assets are out of scope (PRD A10)
- [ ] README: one line on the distribution scope
- [ ] `./scripts/check.sh` passes
