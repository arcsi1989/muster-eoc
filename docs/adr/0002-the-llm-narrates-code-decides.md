# The LLM narrates; code decides

Status: accepted, 2026-10-28 (the brief's hard rule; held through CR-01 to CR-03).

## Context

An EOC acts on what the tool shows: which assets are at risk, which playbook clauses are not met,
which actions are proposed. A language model is good at writing the situation report and at
answering questions about the state, and bad at being reproducible, explainable or accountable. If a
model decided whether a rule is met, changed a score or wrote operational state, nobody could say
why the package looks the way it does, the same advisory could produce a different package, and
the demo could not run offline.

## Decision

Every judgement is deterministic code; the model only writes prose about results code already
produced.

- **Rules**: the rule engine (`backend/muster/playbook/engine.py`) evaluates
  `data/playbook/playbook_rules.yaml` as written and produces the findings (gap, conflict,
  satisfied). The draft gets the findings as plain data in a `DraftRequest`
  (`backend/muster/llm/schemas.py`); it never sees the rules to evaluate.
- **Scores**: hazard (`hazard/`), risk (`risk/`) and the outage forecast (`forecast/`) are
  numerical code with every tunable in `config/*.yaml`. The champion that ranks is a model version a
  person approved ([ADR 0006](0006-champion-and-challenger.md)).
- **Planning products**: ICS-215 rows come from approved field work (`planning/ics215.py`); the IAP
  objectives and their clause citations come from a template over the open findings
  (`planning/objectives.py`). A model may only reword an objective.
- **State**: providers receive no database session. Only the advisory cycle's decision step writes
  decided operational state ([ADR 0007](0007-human-approval-is-the-only-path-to-state.md)).
- **Offline**: every LLM task has a deterministic template (`llm/template.py`,
  `llm/template_chat.py`); `LLM_PROVIDER=template` is the default and the demo runs with no network.

## Consequences

- The same advisory always gives the same findings, scores, ranking and package items; only the
  wording of the draft, the copilot answers and the IAP objectives varies with the provider.
- Each LLM feature is small: it narrates, so its output can be checked against the data it was
  given ([ADR 0003](0003-grounded-generation.md)).
- What looks naive in the output (many generator gaps, about 20 conflicts at advisory 5) is the
  playbook as written, and is fixed in the playbook, not by a model smoothing it over.
- Nothing the model writes is trusted as a fact; numbers and IDs are validated before an answer is
  shown.

## Alternatives rejected

- **An agent that calls tools to evaluate the playbook and propose actions.** Flexible, but its
  findings would be neither reproducible nor auditable, and it fails the offline rule.
- **A model that adjusts risk scores ("this asset looks worse than the curves say").** Unexplainable
  and untestable; the challenger ([ADR 0006](0006-champion-and-challenger.md)) is the governed way
  to change how risk is scored.
- **LLM-generated IAP objectives with model-chosen citations.** Rejected for the template plus
  rewording: the citations must always come from the findings.

## Links

- `CLAUDE.md` hard rules; `docs/decisions.md`: 2026-10-28 (LLM providers, structured draft),
  2026-10-30 CR-02 C3 (ICS-215 and IAP, ticket 25).
- Code: `playbook/engine.py`, `playbook/service.py`, `risk/score.py`, `agent/draft_request.py`,
  `planning/objectives.py`, `llm/provider.py`.
