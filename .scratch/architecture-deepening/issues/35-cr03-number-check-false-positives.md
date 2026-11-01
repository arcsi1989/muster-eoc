# 35: CR-03 C1: number check accepts percentile names and half-up rounding

**What to build:** The first live `make eval-llm` run (ticket 29) failed grounding, refusal and injection on correct answers, because the grounding rule "no number that is absent from the tool results" has two false positives. Fix the checker so a correct answer passes and an invented number still fails. Change request: `docs/change_requests/CR-03_eval_ml_tracing.md`. Record the choice in `docs/decisions.md`.

1. **Percentile names.** The model writes "the 90th-percentile wind is 129.1 mph" (and "50th percentile") for the tool fields `wind_p90_mph`, `flood_depth_p90_m` and the like. The checker reads "90" as a number no tool returned. An ordinal that names a percentile ("90th percentile", "90th-percentile", "50th percentile") is a name, like P90, not a value.
2. **Half-up rounding.** The tool returns `p_fail: 0.565`; the model writes "0.57" or "57%". Python's `round(0.565, 2)` gives 0.56 (binary float), so the checker rejects a correct half-up rounding. A written number matches a tool value when it is within half a unit of its last written decimal (with a small float tolerance), for the value and for a probability written as a percentage.

**Blocked by:** 28 (CR-03 C1: golden set and evaluation gate)

**Status:** resolved

- [x] Test: "the 90th-percentile wind is 129.1 mph" with a tool result holding `wind_p90_mph: 129.1` has no ungrounded number
- [x] Test: "about 57%" and "0.57" with a tool result holding `p_fail: 0.565` have no ungrounded number
- [x] Test: an invented number (e.g. "140 mph" with no 140 in the tool results) is still reported, and "0.58" from 0.565 is still reported
- [x] Classification check still catches a restricted coordinate in an answer (existing tests stay green)
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-30: Merged into `main` as 77e13ad after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 5/5 ticked.
