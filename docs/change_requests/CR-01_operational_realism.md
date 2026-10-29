# CR-01: Operational realism fixes (playbook v3.3)

> Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM document.

**For the coding agent.** The prototype is already built from `docs/IMPLEMENTATION_PLAN.md` (playbook v3.2). This change request updates it to playbook v3.3 after an independent review. First replace `docs/playbook.md`, `data/playbook/playbook_rules.yaml` and `docs/IMPLEMENTATION_PLAN.md` with the versions delivered alongside this file. Then apply the changes below, run `make test`, and record anything ambiguous in `docs/decisions.md`. Do not change any other behaviour.

## Why
A review by utility-operations eyes found three things that would look naive to the panel:
1. Utilities do not put portable generators on substations to protect hospitals. Hospitals have their own on-site emergency power; portable generators go to water pumping stations.
2. The activation level was computed from hours to landfall. In ICS practice the EOC Director or Incident Commander declares it. A computed level contradicts "AI recommends, people decide".
3. The ensemble track spread was too narrow by about 2x (σ was half the cone radius; it should be about the cone radius).

## Changes

### C1. Generators move to pumping stations (P-4.3, P-4.5)
- P-4.5 now matches pumping stations that serve the treatment plant (`asset.type == pump_station`, `feeds_facility_types` contains `treatment_plant`, `p_fail >= 0.20`).
- P-4.3 compares `event.generators_fuelled` with the new `event.wtp_pump_stations_top25` (pumping stations in the top 25 that serve WTP-01). Remove `critical_feeding_assets_top25`.
- Generator: seed `PS-09` (serves WTP-01, no generator, `p_fail >= 0.20` at advisory 3). Make sure at least 8 pumping stations serving WTP-01 sit in the top 25 at advisory 1, so P-4.3 is a gap with 6 fuelled generators.
- UI: the generator approval action appears on pumping stations only.

### C2. Hospital readiness check (P-6.2)
- P-6.2 is now satisfied only when both `state.critical_customer_contacted` and the new `state.hospital_backup_confirmed` are true.
- Keep the `SUB-07` → `HOSP-01` (Bayport General) seed, but its finding is P-6.2 ("confirm on-site backup power has been tested and has 96 hours of fuel"), not P-4.5.
- Add `hospital_backup_confirmed` to `initial_state.json` (false) and to the op_state keys an approval can set.

### C3. Activation is declared, not computed (P-2.5)
- `event.activation_level` is the last **declared** level, stored in op_state. Start the scenario at `monitor`.
- New `event.proposed_activation_level`, derived from the `propose_at_hours` thresholds in `playbook_rules.yaml`.
- New rule P-2.5 (kind `proposal`): when the proposed level differs from the declared one, the decision package shows an activation proposal at the top. No data can satisfy it; only a declaration closes it.
- New endpoint `POST /activation/declare {level, declared_by, reason?}`. It writes op_state, an audit event and a decision row, and sets the declaration time.
- `hours_since_full_activation` counts from the Level 1 declaration time. P-7.2 is inactive until `full` is declared.
- Rules gated by `active_from_hours` keep using hours to landfall, but rules that depend on a level (P-7.2) use the declared level.
- UI: a prominent "Declare Level N" button on the proposal card, which shows who declared and when afterwards. The engine never changes the level itself.

### C4. Ensemble spread
- `config/scoring.yaml`: ensemble cross-track σ = 1.0 × `cone_radius_km` (was 0.5). Make the factor a named config value (`ensemble.sigma_cone_factor: 1.0`).
- Re-check the demo seeds after the change (wider spread moves P90 depths); fix the generator inputs, not the rules, if a seed breaks.
- `docs/assumptions_limitations.md`: add that production would consume NHC probabilistic products (wind-speed probabilities, P-Surge); that surge and elevation are assumed to share one vertical datum; that wind is treated as 1-minute sustained.

### C5. Distribution out of scope (PRD A10)
- No code change. Add one line to `assumptions_limitations.md` and the README: the prototype covers substations, pumping stations and the treatment plant, the single points of failure for critical customers; distribution follows as an outage-forecast module.

### C6. Calibration is now a Must
- If M8 calibration is not built yet, build it now, as specified in plan section 7, M8: a prior about 20% off the hidden truth, a back-test on Storm Delta, a 10-bin reliability chart, Brier score and top-decile capture before and after, a MAP fit, and a `proposed` model version that a human approves.
- Add a "Calibration" view reachable from the main navigation. Show the two reliability curves on one chart, and the Brier score and top-decile capture as before-and-after numbers.
- After approval, the next advisory replay uses the new model version, and the audit timeline shows who approved it.
- Test: the Brier score after calibration is lower than before; scores differ between model versions; an unapproved version is never used for scoring.

### C7. Project name: Muster
- The product is called **Muster**; "SGW, Bayport County" is the bundled demo scenario (data pack), so the project can later be shown with other scenarios.
- UI title and header: "Muster", with the subtitle "Storm preparation decision support · Demo scenario: SGW, Bayport County (fictional)". Keep the disclaimer footer.
- README title: "Muster: storm preparation decision support". First paragraph: what it does in two sentences, then the take-home disclaimer.
- Python package and frontend app name: `muster`. Keep scenario data under `data/scenarios/sgw_bayport/` if a move is cheap; otherwise leave the paths and record that choice in `docs/decisions.md`.
- Do not rename the playbook or SGW names inside the scenario.

## Updated demo path (replaces the one in plan section 8)
1. Advisory 1 (T-72): the package proposes Level 2; the commander declares it. P-4.3 gap: 6 generators fuelled, fewer than the at-risk pumping stations serving the plant.
2. Advisory 2 (T-60): the track shifts east; the diff explains the top-10 moves.
3. Advisory 3 (T-48): the package proposes Level 1; the IC declares it, which starts the regulator clock. P-4.5 for PS-09 (generator, approve). P-6.2 for Bayport General (confirm on-site backup, record it). P-4.2 for PS-14 (inspection, **override**: "crew shortage, re-plan at next advisory"). Regulator notified (P-7.2).
4. Advisory 4 (T-36): P-4.6 for STG-02, P-5.1 flood barriers.
5. Advisory 5 (T-24): conflict on PS-14 between P-4.2 and P-4.7, citing P-8.2; the IC decides.

## Acceptance
- `tests/test_demo_scenario.py` updated to the table in plan section 8 (v3.3) and green on both paths (PS-14 inspected at advisory 3 or deferred).
- New tests: P-2.5 is never closed without a declaration; P-7.2 is inactive before `full` is declared and becomes overdue 12 hours after the declaration; no code path sets `activation_level` except `/activation/declare`; P-4.5 never matches a substation.
- A grep finds no remaining `critical_feeding_assets_top25`.
