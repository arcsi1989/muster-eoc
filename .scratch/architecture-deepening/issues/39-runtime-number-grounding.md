# 39: The copilot validates numbers at runtime, not only in the eval

**What to build:** The copilot's runtime validator rejects an answer that names an asset or clause ID no tool returned, but not one that states a number no tool returned; only the evaluation checks numbers (`docs/decisions.md`, ticket 28: "the runtime copilot still does not check numbers"). Move the number rule into one place used by both: an answer that states a number absent from that turn's tool results (as written, half-up rounded, or a probability written as a percentage; percentile names such as "90th percentile" are names, ticket 35) fails validation, so grounded generation retries with the problem and then falls back to the template, exactly as for an invented ID. The evaluation's grounding check calls the same function, so the eval and production cannot drift. Record the attempt's problems in the audit event as today. Record open choices in `docs/decisions.md`.

**Blocked by:** 35 (number check accepts percentile names and half-up rounding)

**Status:** ready-for-agent

- [ ] One number-grounding function, used by the copilot's runtime validator and by the evaluation's grounding check (no second copy)
- [ ] Test: an answer with an invented number is rejected at runtime, retried with the problem, and falls back to the template when the retry also invents one; the audit event lists both attempts' problems
- [ ] Test: correct answers (percentile names, half-up rounding, percentages of probabilities, numbers glued to units) pass at runtime
- [ ] The template provider's answers pass the new validation for every golden-set question (`make eval` stays green)
- [ ] `./scripts/check.sh` passes
