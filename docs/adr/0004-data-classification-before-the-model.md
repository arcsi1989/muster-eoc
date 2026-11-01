# Data classification: restricted fields never reach a model

Status: accepted, 2026-10-30 (CR-03 C1, ticket 27; option A chosen by the owner on 2026-10-29).

## Context

A utility's asset coordinates, elevations and its dependency graph (which substation feeds which
hospital or pumping station) are what an attacker would want. A hosted model is a third party, and
copilot answers end up pasted into chats and reports. At the same time a person must see why an
action is proposed ("SUB-07 feeds HOSP-01"), and the maps must draw everything.

## Decision

- Every field of the gold-data contracts (`backend/muster/ingest/contracts.py`, written to
  `contracts/*.schema.json`) carries a **data class**: `public`, `internal` or `restricted`.
  Restricted: coordinates (`x_km`, `y_km`, coastline and storm coordinates), `elevation_m` and the
  dependency graph (`from_id`, `to_id`, `to_kind`, `feeds`, `fed_by`, `downstream_assets`,
  `feeders`). The one dependency that is the reason for a finding is internal.
- One filter, `muster.classification.for_model`, drops restricted fields by name at any depth. It
  runs at the two places a model is shown data: a generation request's `shown()` (situation report,
  IAP rewording, in `llm/schemas.py`) and every copilot tool result (`copilot/chat.py`). The
  template copilot reads the filtered data too.
- The copilot's dependency tools show only the critical facilities an asset feeds directly, never
  asset-to-asset edges.
- A field name has one class in every contract (checked at import), so the filter can go by name.

## Consequences

- Every LLM feature, present and future, inherits the filter if it goes through grounded generation
  or the copilot tools.
- The UI still draws coordinates and the network; only the model never sees them.
- The evaluation has a zero-tolerance classification gate: any restricted value of a case's
  entities in an answer fails it ([ADR 0005](0005-rule-based-evaluation-with-a-gate.md)).
- Limits: the filter goes by key name. A restricted value under another name or in free text (a
  field supervisor's note) would pass, and a new graph view must be added to the list in
  `classification.py`.

## Alternatives rejected

- **Redacting values in the prompt text after it is built.** Fragile string matching on prose;
  filtering structured data before serialisation is simpler and testable.
- **A self-hosted model so nothing needs filtering.** Moves the risk, does not remove it, and the
  prototype must run on the template or a hosted API.
- **Classifying per tool by hand.** Each tool would need its own rules and could drift; one class per
  contract field is one source of truth.

## Links

- `docs/decisions.md`: 2026-10-30 CR-03 C1 data classification (ticket 27).
- Code: `classification.py`, `ingest/contracts.py`, `contracts/`, `llm/schemas.py`,
  `copilot/tools.py`; tests in `backend/tests/test_classification.py`.
