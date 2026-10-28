# Spec: SGW storm preparation prototype

Status: ready-for-agent

Source: the implementation plan (M0–M7 plus the parts of M8 and M9 kept in scope), the hurricane playbook and its machine-readable rules, the glossary, ADR 0001, and the decision log. Where this spec and the decision log disagree, the decision log wins; where both are silent, the implementation plan wins.

## Problem Statement

In the 72 hours before a hurricane lands, the Emergency Operations Center (EOC) of a utility receives a new advisory every 12 hours. With each one, staff must work out by hand which of about 200 substations, pumping stations and the treatment plant are most at risk, what the hurricane playbook now requires, which of those requirements are not yet met, and where two clauses contradict each other. They then write a situation report and get the Incident Commander's approval. This is slow, error-prone and hard to audit afterwards, and the one moment that matters most (a gap or a conflict noticed too late) is exactly what tired people miss.

## Solution

A local web app that replays five synthetic advisories for the fictional "Bayport County". On each advisory it computes hazard exposure and a transparent risk score per asset, evaluates the playbook rules deterministically, and assembles a decision package: what changed, the gaps with their proposed actions, the conflicts the Incident Commander must decide, and a draft situation report written by an LLM (or a deterministic template) with checked citations. People approve or override each item, by role; every step is written to an audit log. A chat copilot answers follow-up questions with cited tool results. The prototype prepares; it never acts: no AI output changes operational state without a recorded human approval.

## User Stories

### Replay and situational awareness

1. As an EOC operator, I want to advance to the next advisory with one action, so that I can rehearse the storm cycle at my own pace.
2. As an EOC operator, I want to reset the scenario to before advisory 1, so that I can run the demo again from a clean state.
3. As an EOC operator, I want to see the current advisory number, hours to landfall and activation level in the header at all times, so that I always know where we are in the storm.
4. As an EOC operator, I want the activation level to follow hours to landfall (Prepare at T-72, Full at T-48), so that the playbook's phases apply without anyone forgetting to declare them.
5. As an EOC operator, I want to advance even when some items are still undecided, so that the tool never holds me up while the storm keeps coming.
6. As an EOC operator, I want items left undecided at an advance to be closed as "not decided" in the audit log, so that it is clear later what was never acted on.
7. As an EOC operator, I want the map, the risk list and the decision package to update together when I advance, so that I don't have to reload or hunt for what changed.

### Map

8. As an EOC operator, I want a map of the fictional territory with its coastline, so that I can orient myself without real map tiles or a network connection.
9. As an EOC operator, I want assets coloured by risk on the map, so that I can see where the danger concentrates.
10. As an EOC operator, I want critical facilities (hospitals, shelters) and staging areas shown on the map, so that I can see what the assets protect and where crews are based.
11. As an EOC operator, I want the forecast track and the cone for the current advisory on the map, so that I understand why exposure changed.
12. As an EOC operator, I want to click an asset on the map to open its explanation, so that I can move from "where" to "why" in one step.

### Risk list and explanations

13. As a Planning Section member, I want a ranked risk list for every advisory, so that I can produce the list the playbook requires (P-2.2).
14. As a Planning Section member, I want rank-change arrows since the previous advisory, so that I can explain top-10 changes in the briefing (P-4.1).
15. As a Planning Section member, I want the top 10 at advisory 1 marked as "initial" rather than as ten new entries, so that the first briefing isn't cluttered with false moves.
16. As a Planning Section member, I want an asset's explanation to show wind exposure, flood exposure, fragility, the condition adjustment and the consequence components, so that I can justify its rank.
17. As a Planning Section member, I want the explanation's factors to reproduce the stored risk exactly, so that I can trust the number on screen.
18. As a Planning Section member, I want each asset to show a confidence badge (high, medium, low) with the reason, so that I know when data quality limits the score.
19. As a Planning Section member, I want confidence never to change the score itself, so that the ranking stays transparent.
20. As a Planning Section member, I want to see an asset's dependencies (what feeds it and what it feeds), so that I can see knock-on effects on hospitals and the treatment plant.
21. As a Planning Section member, I want P50 and P90 exposure shown, so that I can plan against P90 flood depth and P50 wind as the playbook says (P-1.3).
22. As an EOC operator, I want alerts when an asset crosses the risk threshold, enters the top 10, or rises 10 or more places, so that sudden changes aren't missed.

### Playbook findings

23. As a Planning Section member, I want every machine-checkable playbook rule evaluated for every relevant entity on each advisory, so that open actions are tracked against the playbook (P-3.3).
24. As a Planning Section member, I want each gap to cite its clause ID and the entity it concerns, so that anyone can check it against the playbook.
25. As a Planning Section member, I want each gap to come with a proposed action, so that the decision in front of people is concrete.
26. As a Logistics Section member, I want the generator gap (P-4.3) to show how many fuelled generators are needed against how many we have, so that I know the shortfall.
27. As a Logistics Section member, I want staging areas forecast to flood flagged from T-36 (P-4.6), so that crews move inland in time.
28. As a Regulatory Liaison, I want the regulator notification (P-7.2) shown with its 12-hour deadline after Full activation, and marked overdue when the deadline passes, so that we don't miss a legal obligation.
29. As an Operations Section member, I want stop-work (P-4.7) to block any field work at an entity where tropical-storm-force wind arrives within 12 hours, so that crews are never sent into danger.
30. As an Incident Commander, I want a blocked action shown as a conflict citing both clauses and P-8.2, so that I see exactly which rules collide.
31. As an EOC operator, I want satisfied findings visible but out of the way, so that the package focuses on what still needs a decision.

### Decision package and decisions

32. As an EOC operator, I want a decision package per advisory with "What changed", the gaps with proposed actions, "Conflicts (Incident Commander decides)" and the draft situation report, so that one screen holds everything to decide.
33. As an EOC operator, I want to choose my role (Incident Commander or Director, Planning, Operations, Logistics, Regulatory Liaison) in the header, so that my decisions are recorded under the right role without a login.
34. As a section member, I want to approve the actions my section owns, so that the right people decide the right things (P-3.x).
35. As an Incident Commander (or Director below Full activation), I want to approve any action, so that I can clear items when a section is unavailable.
36. As an Incident Commander (or Director below Full activation), I want to be the only one who can override an action, with a required reason, so that every deviation from the playbook has my approval (P-8.1).
37. As an Incident Commander, I want to be the only one who can decide a conflict, so that personnel safety decisions sit with the person accountable for them (P-8.2).
38. As an Incident Commander, I want a conflict's choices to be "Defer" or "Alternative measure" with a reason, and never "proceed", so that the tool can't be used to waive stop-work.
39. As an EOC operator, I want a clear refusal when my role may not take a decision, so that I know to hand it to the right person.
40. As an EOC operator, I want an approval to count the action as done from that moment, and the UI to say so, so that the next advisory reflects it and nobody mistakes the prototype's simplification for field confirmation.
41. As an EOC operator, I want an overridden gap to reappear at the next advisory if it is still unmet, so that a deferred action isn't forgotten.
42. As an EOC operator, I want state set by approvals (generator assigned, inspected, barriers installed) to carry over between advisories, while the per-advisory flags (risk list reviewed, situation report approved) reset, so that the package matches each operational period.
43. As a Planning Section member, I want to record that the risk list was reviewed for this advisory (P-4.1), so that the process requirement is met and logged.

### Situation report

44. As a Planning Section member, I want a draft situation report generated for every advisory, marked DRAFT, so that I start from a draft rather than a blank page (P-7.1).
45. As an Incident Commander, I want every clause ID and asset ID in the draft to be real and to match a finding or a retrieved clause, so that I never approve an invented citation.
46. As an Incident Commander, I want citations shown as chips I can click to open the clause or asset, so that I can check them in seconds.
47. As an Incident Commander, I want to edit the draft before approving it, so that the final text is mine.
48. As an Incident Commander, I want both the draft and the approved text kept, with the edit marked in the audit log, so that it's clear what the AI wrote and what a person changed.
49. As an Incident Commander, I want approving the situation report to satisfy P-7.1 for this advisory, so that the playbook's reporting requirement is tracked.
50. As an EOC operator, I want the draft clearly labelled as AI-generated (or template-generated), so that nobody mistakes it for approved text.

### Copilot

51. As an EOC operator, I want to ask "Why is PS-14 ranked where it is?" and get the factors with IDs, so that I can answer questions in the briefing.
52. As an EOC operator, I want to ask for the top risks, what depends on an asset, and what a clause says, so that I can explore without clicking through screens.
53. As an EOC operator, I want every copilot answer to cite the asset and clause IDs its tools returned, as clickable chips, so that I can verify it.
54. As an EOC operator, I want the copilot to work offline for its fixed set of questions, so that the demo never depends on the network.

### Audit and data quality

55. As an Incident Commander, I want an audit list of every step (system, agent and human), filterable by actor, so that I can reconstruct what happened and who decided.
56. As an auditor, I want each audit event to record scenario time and wall-clock time, so that deadlines and real timing can both be checked.
57. As an auditor, I want each agent step to record an input hash and the model, rules and prompt versions, so that any output can be traced back.
58. As an auditor, I want each LLM call to record the provider (including "template (fallback)"), model, latency and token usage, so that AI use is transparent.
59. As a data steward, I want a data quality page showing each loaded file, its hash, and rows accepted and rejected, so that I can trust the inputs.
60. As a data steward, I want rows that break the data contract rejected with a reason, so that bad data never reaches the scores.

### Running the prototype

61. As a reviewer, I want one command to start backend and frontend, so that I can run the prototype without setup knowledge.
62. As a reviewer, I want the demo to run with the Anthropic model from a local key file, so that I see the real LLM feature.
63. As a reviewer, I want the demo to run fully offline with the template provider, so that it works anywhere.
64. As a reviewer, I want a clear error at startup when the Anthropic provider is chosen but the key is missing, naming the variable and the template option, so that I am never shown a silent fallback.
65. As a reviewer, I want a failed LLM call during the run to fall back to the template draft for that advisory, so that one network error doesn't stop the demo.
66. As a reviewer, I want regenerating the synthetic data to give byte-identical files, so that results are reproducible.
67. As a reviewer, I want a disclaimer in the UI footer and the docs that everything is fictional, so that nothing is mistaken for a real utility or place.

## Implementation Decisions

### Shape and modules

- Backend: one FastAPI app with HTTP-only routers and domain modules that import nothing from FastAPI: ingest (contracts, loader, quality report, lineage), hazard (wind, surge, ensemble, arrival time), risk (fragility, consequence, score, confidence, alerts), playbook (clause parsing, retrieval, rule engine), agent (the advisory cycle graph, decision package, citation validation, versioned prompts), copilot (tools, chat), llm (provider interface with Anthropic, template, and an Azure OpenAI stub), audit (event log). SQLite via SQLModel for all state; tunable numbers in YAML config files, never in code.
- Frontend: one operations screen. Header: advisory stepper, hours to landfall, activation level, role selector. Left: map. Right: tabs for Risk list, Decision package, Copilot. The asset explanation opens as a side drawer. Audit and Data quality are separate routes. Disclaimer footer. All backend calls go through one API client module with typed functions per endpoint; data hooks feed presentational components.
- Stack additions (each justified in its commit): numpy and scipy (lognormal CDF), SQLModel, LangGraph and its SQLite checkpointer, rank-bm25, PyYAML, the Anthropic SDK (already present); react-leaflet and Recharts in the frontend.

### Geography and data

- The territory is fictional and on a planar km grid (`x_km`, `y_km` instead of the plan's lat/lon), rendered with Leaflet's simple CRS and no tiles. A synthetic Gulf-style peninsula coastline. All distances are Euclidean.
- The seeded generator (seed 42) writes the gold JSON files from the plan's data model and is committed. Demo seed assets (SUB-07 feeding HOSP-01, PS-14 on the coast, STG-02 flooding from advisory 4, 6 fuelled generators, 3 null elevations, 5 stale inspections, 2 contract-breaking rows in a separate example file) are placed by construction relative to the scripted track. Data generation then runs the hazard and scoring code and fails loudly if any seed fact does not hold.
- The scenario storm is unnamed and modelled on a 2022 Gulf landfall (values in the research note): max wind 130, 130, 135, 140, 145 mph and peak surge 2.5, 2.5, 3.0, 3.5, 4.0 m for advisories 1–5; radius of maximum wind 37 km; forecast landfall shifts about 40 km east at advisories 3 and 4; cone radii by lead time 48/72/96/124/156/185/263 km at 12–96 h.

### Scoring

- Per the plan's scoring section, with these readings: inland decay (Vmax × 0.85) applies while the storm centre is more than 10 km inland; the ensemble has 50 members, seeded per advisory, spreading the track perpendicular to its heading by a normal distribution with standard deviation equal to the cone radius (configurable); consequence is one hop: own customers, plus customers of directly dependent assets, plus the policy weight of each directly fed facility, each downstream entity counted once.
- Scoring runs when an advisory is advanced, before the advisory cycle starts. Approvals never change scores.
- Activation level is derived: Monitor for hours in (72, 120], Prepare for (48, 72], Full for [0, 48]. Hours since Full activation = 48 − hours to landfall. P-7.2 is overdue when that exceeds 12. All deadlines run on scenario time.

### Rule engine

- Implements the semantics at the top of the playbook rules file: active-from hours, `when` and `satisfied_if` predicates with all listed operators (including `value_field` and `contains_any`), deadlines with escalation to critical when overdue, and prohibition blocking: a prohibition never becomes a finding on its own; it turns any open rule with field work on the same entity into a conflict citing both clauses and P-8.2. The rules and clause text are never edited.
- Findings: one per rule × entity × advisory, with status satisfied, open (a gap) or conflict, severity, owner role and details.

### Advisory cycle (LangGraph, per ADR 0001)

- Nodes: load context → diff → retrieve → evaluate rules → draft (the only LLM node) → validate citations → await approval (interrupt) ⇄ apply decision → finalise. Every node writes an audit event with input hash and versions.
- One graph thread per advisory, with its checkpointer in its own SQLite file that reset deletes.
- Each decision resumes the paused thread; the deterministic apply-decision node validates the role, writes the state change and the audit event, then loops back to await approval until no items remain. Advancing to the next advisory resumes the previous thread once with "expire", which closes undecided items as "not decided" and runs finalise.
- Retrieval: BM25 over the playbook's clauses, one query per gap (rule title plus asset type), filtered by activation level; returns clause IDs and text as context for the draft.

### Decisions and state

- Approval sets every `satisfied_if` key of the rule to true for that entity. Exceptions: P-4.3 sets the fuelled generator count to the required number; P-7.1 is not an item and is satisfied only by approving the situation report. Generators are not a pool. Per-advisory flags (risk list reviewed, situation report approved) reset on each advisory; all other state carries over.
- Permissions: approve by the item's owner role or the Incident Commander/Director; override (reason required) only by the Incident Commander/Director; conflicts only by the Incident Commander, with outcomes "Defer" or "Alternative measure" plus a reason; neither outcome sets the blocked action's state. Below Full activation the Director holds the Incident Commander's decisions. A refused decision returns the standard error body and changes nothing.

### LLM

- The provider is chosen by `LLM_PROVIDER` (`anthropic` or `template`) and `LLM_MODEL` (default `claude-sonnet-5-5`), read through the settings class from the environment and a local, gitignored backend env file; an example env file lists the names. Anthropic without a usable key fails at startup with a message naming `ANTHROPIC_API_KEY` and the template option.
- The draft is structured output: sections, each with paragraphs carrying `text`, `clause_ids` and `asset_ids`. The template provider returns the same shape. The validator rejects any ID that isn't real or doesn't match a finding or retrieved clause, and any ID in the text that isn't in the lists; on failure it retries once, then uses the template draft. A failed call also falls back to the template draft for that advisory, recorded as `template (fallback)`. Draft temperature is 0.
- Prompts are versioned files in the agent module; the version is recorded with every call. Findings and data go in their own delimited message; the LLM narrates and cites, never decides rules, scores or state.
- Copilot: tool calling over the same domain functions (top risks, asset, explain score, dependencies, search playbook, decision package, findings by status). Template mode supports a fixed set of intents: why ranked, top risks, what depends on X, what does clause Y say. Answers carry the IDs their tools returned.

### API contract

- `GET /health`, `/assets`, `/facilities`, `/staging-areas`, `/coastline`, `/advisories`; `POST /advisories/next`, `/advisories/reset`; `GET /risk?advisory=`, `/assets/{id}/explain?advisory=`, `/alerts?advisory=`, `/packages/{advisory}`; `POST /packages/{advisory}/items/{item_id}/decision` (role, action, reason, conflict outcome); `POST /sitrep/{advisory}/approve` (role, final text); `POST /copilot/chat`; `GET /audit` (filter by actor), `/lineage`. Routes have no `/api` prefix; the frontend dev server proxies `/api/*` to them.
- Every endpoint declares a response model; one error body everywhere: `{"error": {"code", "message"}}`. JSON Schemas for the gold files are exported from the Pydantic models; frontend types mirror them.

### Running

- `make dev` (backend :8000, frontend :5173), `make data`, `make test` (calls the repo's check script), `make demo-reset`. No Docker.

## Testing Decisions

- A good test drives external behaviour through the highest seam available and asserts what a user or caller would see: HTTP responses and persisted outcomes, not internal function calls or graph internals. Tests never call a real LLM or the network; they always force the template provider, whatever a local env file says.
- Seam 1, the HTTP API in template mode (main seam): FastAPI's test client drives the whole flow. It covers the plan's demo scenario contract on both paths (PS-14 overridden at advisory 3, giving a conflict citing P-4.2, P-4.7 and P-8.2 at advisory 5; and PS-14 inspected at advisory 3, giving no conflict), every row of that contract's table, role refusals (a non-owner approving, a non-Incident Commander overriding or deciding a conflict), "not decided" closure on advance, situation report edit and approval satisfying P-7.1, reset, and one happy-path test per endpoint plus one per mapped error. A fake LLM provider, substituted behind the provider interface, returns a draft with an invented clause ID: the test asserts it was rejected and the template draft served, and that no code path lets the provider write state.
- Seam 2, domain functions, only where the plan's done-when demands unit properties: hazard (wind equals Vmax at Rmax and decays monotonically beyond; flood depth zero above surge; P90 ≥ P50; same seed gives same numbers), scoring (p_fail in [0, 1] and monotonic in exposure; poor condition never lowers p_fail; top 10 changes between advisories 2 and 4; explanation factors reproduce stored risk), and the rule engine (at least one test per rule in the rules file, plus prohibition blocking and deadline escalation).
- Seam 3, the data generator: two runs give identical hashes; every demo seed fact holds; the loader rejects exactly the 2 bad example rows with reasons and records lineage.
- Seam 4, the frontend: API client functions with `fetch` mocked (URL, method, typed error on non-2xx), and components for their loading, error, empty and data states. No whole-page snapshots, no styling tests.
- Prior art: the backend health test using a TestClient fixture, and the frontend App test using Testing Library and user events. The check script runs ruff, mypy (strict), pytest, oxlint, tsc and vitest; it must pass before every commit.

## Out of Scope

- Calibration (fragility fitting, back-test, reliability chart, model version approval), moved out of M8 for the time box.
- Docker and docker compose.
- A working Azure OpenAI provider (a stub behind the interface only).
- Real geography, real place, utility or storm names, real customer data; map tiles.
- The optional "Historical context" panel with real past storm tracks (a stretch goal after M6, specified separately if pursued).
- Optimisation or crew routing (lighthouse 2), data pipelines, authentication, multi-user, cloud deployment, streaming.
- Field confirmation of actions: approval stands in for completion.
- A generator pool linking P-4.3 and P-4.5.

## Further Notes

- Build order follows the plan's milestones M0 → M7, each passing its done-when before the next; situation report approval and the audit list land with M6/M7; M9 documentation (README, architecture, assumptions and limitations, demo script for an 8-minute video) closes the work.
- The full seed check in data generation depends on hazard and scoring (M2–M3); until then, data-only seed tests run alone.
- Every choice the plan left open is in the decision log; new open choices go there too. Domain terms follow the glossary (gap, action, conflict, approval, override, decision package, scenario time, activation level).
