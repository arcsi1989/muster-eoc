# 27: CR-03 C1: data classification before anything reaches a model

**What to build:** Every field in the data contracts carries a data class: `public`, `internal` or `restricted`. Only `public` and `internal` values ever reach an LLM. The filter sits at the two places a model is shown data: the grounded generation module's task input (situation report, IAP rephrasing) and the copilot tool layer, so every LLM feature inherits it. Maps and coordinates stay UI-only. Classification follows the owner's reading of CR-03 (option A, 2026-10-29), recorded in `docs/decisions.md`:
- **restricted:** `x_km`, `y_km` (the prototype's coordinates; CR-03 says lat/lon), `elevation_m`, and the dependency graph itself: the edge list, and "everything an asset feeds and is fed by";
- **internal:** the one dependency that is the reason for a finding or action (for example "SUB-07 feeds HOSP-01" on P-6.2, "PS-09 serves WTP-01" on P-4.5), because a person must understand why an action is proposed; it reveals one edge, not the network.
`get_asset` stops returning coordinates and elevation. `get_dependencies` narrows to the critical facilities an asset supports and whether it serves the treatment plant: no upstream feeders, no asset-to-asset edges. Change request: `docs/change_requests/CR-03_eval_ml_tracing.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 17 (Copilot through grounded generation)

**Status:** resolved

- [x] Every contract field has a data class; classes defined once
- [x] One filter applied to every LLM input: grounded generation task input and every copilot tool result
- [x] `get_asset` without coordinates and elevation; `get_dependencies` narrowed as above; the template provider's dependency question still answers, from the narrowed result
- [x] Situation report P-4.5 and P-6.2 narration unchanged (the finding's own dependency is internal)
- [x] Unit test: no tool result and no generation input can contain a restricted field, for every tool and every task
- [x] Decision (option A) recorded in `docs/decisions.md`
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-30: Merged into `main` as 91aed4f after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 7/7 ticked.
