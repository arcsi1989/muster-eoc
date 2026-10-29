# 04: CR-01 C1: portable generators go to pumping stations

**What to build:** Logistics sees generator gaps where a utility would actually put portable generators: on pumping stations that serve the treatment plant, never on substations. P-4.5 matches only pumping stations that serve WTP-01 with a failure probability of 20% or more, and P-4.3 compares the generators fuelled with the pumping stations in the top 25 that serve WTP-01. The demo seeds change so the story still plays: PS-09 is the P-4.5 gap at advisory 3, and P-4.3 is a gap at advisory 1 with 6 generators fuelled. The generator approval action appears on pumping stations only. Change request: `docs/change_requests/CR-01_operational_realism.md`; target files: `docs/change_requests/CR-01_delivered/`. Record anything ambiguous in `docs/decisions.md`.

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] `playbook_rules.yaml` P-4.3 and P-4.5 hunks and `docs/playbook.md` P-4.3 and P-4.5 text match the delivered copies (only these clauses; the rest of v3.3 lands in tickets 05 and 06)
- [x] New rule input `event.wtp_pump_stations_top25` (pumping stations in the top 25 that serve the treatment plant); `critical_feeding_assets_top25` removed, and a grep of `backend/`, `frontend/`, `data/` and `config/` finds no copy left
- [x] Generator (seed 42): PS-09 serves WTP-01, no generator, p_fail ≥ 0.20 at advisory 3; at least 8 pumping stations serving WTP-01 in the top 25 at advisory 1; `make data` regenerates `data/gold/` reproducibly; the generator's seed check covers both
- [x] UI: the generator approval action shows on pumping stations only
- [x] Tests: P-4.5 never matches a substation; P-4.5 open for PS-09 at advisory 3 (cites WTP-01); P-4.3 is a gap at advisory 1
- [x] Demo test rows for P-4.3 and P-4.5 updated to plan section 8 (v3.3); the SUB-07 → HOSP-01 row moves to P-6.2 in ticket 05, so this ticket drops the SUB-07 P-4.5 assertion and says so in its Comments
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-29: Merged into `main` as 1742391 after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 7/7 ticked.
