# 16: Grounded generation for the situation report

**What to build:** One grounded generation module runs a task: call the configured provider, validate with the task's validator, retry up to the configured attempts, and fall back to the template when every attempt fails or the provider raises. It returns the result, the attempts and whether the fallback was used. The situation report runs through it with the draft request validator. The fallback label is defined once, the fallback template uses the configured settings, and the module tells a fallback from a configured template by how the result was produced, not by checking the provider's type. The demo still runs with `LLM_PROVIDER=template` and no network. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 12 (The draft request carries its own grounding)

**Status:** resolved

- [x] Grounded generation module owns attempt → validate → retry → fallback and the attempt log
- [x] Situation report drafting uses it; no provider type check remains in the draft code
- [x] Fallback label defined once; fallback template built from configuration (for example the number of top risks)
- [x] Test fakes are honest fakes (no pretending to be the Anthropic provider)
- [x] Tests: valid first attempt used; invalid attempt retried; exhausted attempts fall back with the label; raising provider falls back; configured template not labelled a fallback
- [x] Audit records for drafting unchanged in meaning; `./scripts/check.sh` passes

## Comments

- 2026-10-29: Merged into `main` as d3d73d6 after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 6/6 ticked.
