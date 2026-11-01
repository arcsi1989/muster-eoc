# Grounded generation: one module runs every LLM task

Status: accepted, 2026-10-29 (ticket 16; the copilot moved onto it in ticket 17, numbers checked
at runtime since ticket 39).

## Context

Three features call a model: the situation report draft, the copilot and the rewording of the IAP
objectives. Each can fail in the same ways: the call errors or times out, the model cites a clause
or asset it was not shown, or states a number nothing supports. Before ticket 16 the draft and the
copilot each had their own retry and fallback loop, a type check for "is this the template", and a
different attempt log, so the audit trail and the eval read them differently.

## Decision

`backend/muster/llm/grounded.py` is the one place that runs an LLM task:
**attempt → validate → retry → template fallback**.

- The task owns its prompt (versioned files in `agent/prompts/`) and its **validator**; the
  provider is transport only (`llm/provider.py`).
- The validator is deterministic code and decides whether a result is grounded, never the model:
  - situation report: every clause and site ID cited must be one the draft request shows
    (`agent/citations.py`);
  - copilot: every ID must come from a tool result of that turn, and every number must be in one
    (`numbers.ungrounded_numbers`, the same function the evaluation uses);
  - IAP objectives: a rewording may not mention a clause or site its objective does not cite
    (`planning/objectives.py`).
- A rejected attempt is retried with the validator's problems (`retries` per task in
  `config/scoring.yaml`), then the task's template answers. A failing or ungrounded model answer is
  never shown.
- Every attempt (provider, model, prompt version, latency, tokens, problems or error) goes into one
  attempt log, the same format in the audit event, the trace span, the copilot's "How I got this"
  and the evaluation's cost figures.

## Consequences

- One fallback policy (L9) and one attempt-log format; the run trace, the eval and the model
  comparison all read cost and retries from it.
- The configured template goes through the same loop and passes its own validator, so "fallback"
  means only "the module served the template after a failure", never "the provider was the
  template".
- The copilot's streamed steps (`POST /copilot/chat/stream`) come from an observer on this module:
  a step never carries answer text, so a rejected answer is never shown.
- Limits: citations are checked by membership (an allowed clause next to an unrelated allowed asset
  passes); the situation report's numbers are not checked, only its citations.

## Alternatives rejected

- **A loop per feature.** That was the state before ticket 16; it drifted (different logs,
  different fallback rules).
- **A model as the validator ("is this answer grounded?").** Not deterministic, costs a second call,
  and puts a model in the judging seat ([ADR 0005](0005-rule-based-evaluation-with-a-gate.md)).
- **Showing an ungrounded answer with a warning.** An EOC reader skims; a flagged wrong number is
  still a wrong number on screen.

## Links

- `docs/decisions.md`: 2026-10-29 grounded generation for the situation report (ticket 16), copilot
  through grounded generation (ticket 17); 2026-11-01 runtime number check (ticket 39), the copilot
  shows its work (ticket 37).
- Code: `llm/grounded.py`, `agent/draft.py`, `agent/citations.py`, `copilot/chat.py`, `numbers.py`,
  `planning/objectives.py`.
