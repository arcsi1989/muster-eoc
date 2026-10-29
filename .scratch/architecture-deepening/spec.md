# Spec: deepen the decision package, grounding and advisory context modules

Status: ready-for-agent

Source: the architecture review of 2026-10-29 (six candidates, found by walking the commit hot spots and the uncommitted grounding fix), the glossary, ADR 0001, the decision log, and change request CR-01 (playbook v3.3, `docs/change_requests/CR-01_operational_realism.md`). This is a refactor: the EOC-facing behaviour of the prototype stays the same except where a story below says otherwise.

**Relation to CR-01.** CR-01 is a behaviour change implemented on its own, not by these tickets. Tickets 01–03 land first, on playbook v3.2, with no behaviour change; ticket 02 is the prefactor that turns CR-01's C3 (activation is declared, not computed) into a one-module change. CR-01 then lands. Tickets 04–12 are built against playbook v3.3, where the activation level is the last level a person declared, P-2.5 proposes a change of level, declaring a level is a human decision, and P-6.2 is satisfied by two state keys.

## Problem Statement

The prototype works and the demo runs, but the code that guards its most important promise ("the prototype prepares; it never acts; humans approve") is spread thin over many small modules that each work out part of the answer.

- **Whether a decision package is open is recorded twice.** The package row has a status, and the advisory cycle's checkpoint says whether it is waiting. Item decisions check the checkpoint and ignore the status. Situation report approval checks neither: it checks only that the advisory is current. It also writes operational state and re-evaluates a finding outside the one step that is documented as the only writer of operational state.
- **Each item decision runs the same work twice.** The activation level is resolved twice and the decision rule checked twice per decision: once before the cycle resumes, and again inside it.
- **The situation report's grounding drifts from what the model is shown.** What the model may cite is assembled separately from what it is shown. The uncommitted fix (asset IDs from rank moves) patches one instance of that drift. The ID patterns used to check citations also disagree between the situation report and the copilot: the situation report's pattern misses hospital and shelter IDs and is case-sensitive.
- **The deterministic fallback policy is written twice.** The draft and the copilot each implement try, validate, fall back to the template. Each detects the template provider by type and defines its own fallback label. Test fakes have to pretend to be the Anthropic provider to get around this.
- **Advisory questions are re-derived at about fifteen call sites.** The current advisory, the activation level (with its boundary-hour rule), whether the EOC is at Full activation (a string literal in four places) and who commands are all worked out by each caller. Replay resets tables that belong to the advisory cycle.
- **Changes and the draft are copied by hand into four shapes:** domain model, untyped JSON column, API schema and TypeScript type. A mismatch shows up only when a response is validated.
- **Playbook semantics leak out of the playbook module.** The code that turns a finding into a proposed action and its approval state reads the rule engine's internal predicate and detail-key formats. The code that builds rule inputs is tested only through multi-advisory replays.

For the developer, every change in these areas means reading five to nine files, and every test means replaying the storm over HTTP. For the EOC, the risk is a situation report approved against a closed package, or a citation accepted or rejected by the wrong pattern.

## Solution

Six refactors, each one a deep module behind a small interface, delivered one ticket at a time with the app runnable and `./scripts/check.sh` green after each:

1. **Seeded session test fixture**: one new test seam, used by every later ticket.
2. **Advisory context module**: one place that answers "which advisory is current, what is the scenario time, what is the activation level, who commands, is this advisory still current", and owns resetting per-advisory state. Before CR-01 it computes the level as today; after CR-01 it reads the declared level and also gives the proposed level and the declaration time.
3. **Decision package lifecycle module**: one place that opens a package, takes decisions on its items, approves its situation report, records an activation declaration, expires the package and closes it, and the only place that answers "is it open". The LangGraph advisory cycle stays (ADR 0001) as the module's internal adapter for step order and the approval pause.
4. **Draft request with built-in grounding**: whatever the model is shown is exactly what it may cite, checked by one validator that owns the clause and entity ID patterns shared with the copilot.
5. **Grounded generation module**: one place that owns attempt → validate → retry → template fallback and the attempt log for both the situation report and the copilot. Providers become transport only.
6. **Typed package payloads**: changes and the draft are stored and served as one typed model each, and the mirror API schemas are removed.
7. **Playbook module answers "what satisfies this finding"**: rule semantics stop leaking into the action and package code. Building rule inputs gets direct tests.

## User Stories

### EOC behaviour that must not change

1. As an EOC operator, I want advancing to the next advisory to produce the same scores, findings, package items and draft as before each refactor ticket (at the playbook version in force), so that the rehearsed demo is unchanged.
2. As an EOC operator, I want resetting the scenario to return to before advisory 1 exactly as before, so that the demo can be run again.
3. As an Owner role, I want to approve or override the items assigned to my role exactly as before, so that the refactor costs me nothing.
4. As the Director, I want to hold the Incident Commander's decisions while the EOC is below Full activation, as before, so that authority follows the activation level.
5. As the Incident Commander, I want to be the only one who decides conflicts at Full activation, as before, so that personnel safety prevails (P-8.2).
6. As an EOC operator, I want the decision log to keep recording every approval, override and situation report approval with the same event types and summaries, so that the audit trail reads the same.
7. As an EOC operator, I want the demo to keep running with `LLM_PROVIDER=template` and no network, so that the offline fallback still holds.
8. As an EOC operator, I want the copilot to answer with the same cited tool results as before, so that follow-up questions still work.

### EOC behaviour that becomes stricter

9. As the Incident Commander, I want approving the situation report to be refused once the decision package for that advisory is closed, so that a report is never approved against a package nobody can act on any more.
10. As the Incident Commander, I want approving the situation report to be refused with the same "package closed" error as an item decision, so that the two kinds of approval behave alike.
11. As an EOC operator, I want a situation report citation of a hospital or shelter ID to be checked against the same patterns the copilot uses, so that a valid citation is not rejected and an invalid one is not accepted.
12. As an EOC operator, I want every asset or clause shown to the model in the draft request to be citable, so that a correct draft is never thrown away for citing something it was shown.
13. As an EOC operator, I want a citation of something the model was not shown to still be rejected, so that the draft stays grounded.

### Developer: decision package lifecycle

14. As a developer, I want one interface that answers "is the decision package for advisory N open", so that the frontend, routes and decisions agree.
15. As a developer, I want the package status the API returns to come from that same answer, so that the frontend never has to recompute whether the situation report is open.
16. As a developer, I want an item decision to resolve the activation level and run the decision rule check exactly once, so that a refusal and an acceptance are decided in one place.
17. As a developer, I want situation report approval to go through the same lifecycle path as item decisions, so that operational state changes only through one recorded path.
18. As a developer, I want the claim that only the decision step changes operational state to be true, so that the module's documentation can be trusted.
19. As a developer, I want the LangGraph nodes to hold only orchestration (order of steps, the pause for decisions) and call the lifecycle module for the work, so that the domain logic can be tested without running the graph.
20. As a developer, I want to test opening, deciding, approving and closing a package against a seeded session without HTTP, so that a lifecycle test does not pay for a full replay.
21. As a developer, I want the P-7.1 situation report rule ID, the per-advisory situation report flag and the item status values defined once each, so that a rename cannot leave one copy behind.
22. As a developer, I want a test that proves the package status and the cycle's waiting state cannot disagree, so that the two sources never drift again.
22a. As the EOC Director or Incident Commander, I want declaring an activation level (playbook v3.3, P-2.5) to go through the same lifecycle path as other decisions, with the same "who may decide" answer and one audit record, so that a declaration is recorded like every other human decision.
22b. As a developer, I want a test proving that no code path sets the activation level except a declaration, so that the engine never changes the level itself (CR-01 acceptance).

### Developer: advisory context

23. As a developer, I want one interface that gives the current advisory, its scenario time and its activation level, so that no caller recomputes or re-reads them.
24. As a developer, I want one interface that says whether the EOC is at Full activation and who commands (Incident Commander or Director), so that the string literal "full" disappears from callers.
25. As a developer, I want one check that an advisory is still current, with one error, so that the six copies of that check collapse.
26. As a developer, I want the activation level rule tested once, directly, so that every caller inherits it: before CR-01 the boundary-hour rule ("a boundary hour belongs to the later, higher level"); after CR-01 the declared level, the proposed level from the `propose_at_hours` thresholds, and the hours since Full was declared.
26a. As a developer implementing CR-01, I want switching from a computed to a declared activation level to be a change inside the advisory context module only, so that C3 does not touch ten call sites.
27. As a developer, I want resetting per-advisory flags to live with the advisory context, not inside replay, so that replay knows nothing about playbook flags.
28. As a developer, I want scenario reset to ask each module to reset its own tables, so that replay stops deleting advisory cycle tables it does not own.
29. As a developer, I want the top-10 rank cut defined once, so that "what changed" and the cycle's top-risk list cannot disagree.
30. As a frontend developer, I want the current advisory to come from the scenario state the backend returns, so that the frontend stops inferring it from the last issued advisory.

### Developer: draft request and grounding

31. As a developer, I want the draft request to expose which clause and entity IDs it makes citable, derived from its own contents, so that grounding cannot be assembled separately.
32. As a developer, I want one validator that checks a draft against a draft request, so that the citation check has one input instead of three.
33. As a developer, I want the clause and entity ID patterns defined once and shared by the situation report and the copilot, so that they cannot disagree.
34. As a developer, I want "what changed" to arrive in the draft request as a typed model, not an untyped dict, so that a renamed field fails the type check.
35. As a developer, I want to test grounding with a hand-built draft request, so that checking one grounding rule does not need two replays to advisory 3.
36. As a developer, I want the uncommitted rank-move grounding fix to become a consequence of the design rather than a special case, so that the next field added to the request is citable automatically.

### Developer: grounded generation and fallback

37. As a developer, I want one module that runs attempt → validate → retry → template fallback for both the situation report and the copilot, so that the fallback policy (a hard rule) is implemented once.
38. As a developer, I want the fallback label ("template (fallback)") defined once, so that the audit log and the UI show the same text.
39. As a developer, I want the module to decide whether a result came from the template without checking the provider's type, so that adding a provider does not mean editing two `isinstance` checks.
40. As a developer, I want the fallback template to use the configured settings (for example the number of top risks), so that a fallback draft matches a configured template draft.
41. As a developer, I want providers to only send a prompt and return a result, with prompt version and settings passed the same way for the situation report and the copilot, so that both tasks look alike to a provider.
42. As a developer, I want test fakes to be honest fakes that do not pretend to be the Anthropic provider, so that tests describe what they actually exercise.
43. As a developer, I want every attempt (provider, prompt version, validation problems, fallback used) recorded in one format, so that the audit log reads the same for both tasks.
44. As a developer, I want the template to be the fallback and the `LLM_PROVIDER=template` choice through the same seam, so that it is not both an adapter and a special case.

### Developer: typed package payloads

45. As a developer, I want "what changed" stored and served as one typed model, so that the domain shape and the API shape cannot drift.
46. As a developer, I want the situation report draft stored as a typed model (draft plus its metadata), so that reading it back does not walk a raw dict.
47. As a developer, I want the mirror API classes for changes and the draft removed, so that one model change shows up everywhere.
48. As a developer, I want the `type: ignore` lines in the package routes gone, so that the type checker sees the real shapes.
49. As a developer, I want "decides as commander" to come from the same definition as the commander roles, so that a role change cannot leave the API out of date.
50. As a frontend developer, I want the TypeScript package types to match the backend models, kept honest by a test or by generation, so that a renamed field breaks the build rather than the UI.

### Developer: playbook module

51. As a developer, I want the playbook module to answer "which state would satisfy this finding", including findings satisfied only by several state keys together (P-6.2 in v3.3) and proposal findings that no state satisfies (P-2.5), so that the action code stops inverting rule predicates itself.
52. As a developer, I want the proposed action and its approval state to come from the playbook module, so that the engine's detail-key format stays internal.
53. As a developer, I want the playbook module to decide which findings become package items and how (leaving out the P-7.1 situation report rule; presenting a P-2.5 proposal as an activation proposal, not an ordinary item), so that the cycle stops filtering findings itself.
54. As a developer, I want entity names resolved in one place, so that the three copies collapse.
55. As a developer, I want the rule inputs (for example the facilities an asset feeds, the pumping stations in the top 25 that serve the treatment plant, the proposed activation level) tested directly against a seeded session, so that a field-name bug is caught without a replay.
56. As a developer, I want re-evaluating one finding after a state change to be part of the playbook interface, not a patch the situation report code calls, so that partial re-evaluation has one owner.

### Developer: tests and runnability

57. As a developer, I want a seeded session fixture that gives a database with the gold data loaded and a chosen advisory issued, so that every deepened module can be tested in process.
58. As a developer, I want the HTTP end-to-end demo test to stay green throughout and never be edited by a refactor ticket (CR-01 alone updates it to v3.3), so that it remains the regression net for the whole refactor.
59. As a developer, I want each ticket to leave `./scripts/check.sh` green and the app runnable, so that the refactor can stop after any ticket.
60. As a developer, I want tests that only reached past an interface to be replaced by tests at the new interface, not kept alongside them, so that the test suite does not double in size.

## Implementation Decisions

### Order and slicing

- Tickets are delivered one at a time, in this order: seeded session fixture → advisory context → shared citation ID patterns → **CR-01 (outside this spec)** → draft request grounding → decision package lifecycle → grounded generation → typed package payloads → playbook module. Advisory context comes before the lifecycle because the lifecycle uses "who commands" and "is current". Grounding comes before grounded generation because the generation module validates through the draft request.
- Advisory context lands before CR-01 as a prefactor ("make the change easy, then make the easy change"): it moves every activation-level lookup behind one interface without changing behaviour, so CR-01's C3 changes that one module.
- CR-01's project rename (C7, Python package and frontend app named `muster`) is a wide mechanical change. It lands as its own commit and never at the same time as a refactor ticket. The tickets name no file paths, so they survive it.
- Start ticket 01 from a clean tree. The CR-01 playbook, rules and plan files currently sit uncommitted and make `./scripts/check.sh` fail (the rule loader does not know `kind: proposal` yet); hold them back until CR-01 starts.
- Each ticket is a vertical slice that keeps the app runnable. No ticket leaves a half-moved concept with both an old and a new path in use.

### Seeded session fixture (the one new test seam)

- A test fixture yields a database session on a fresh engine with the gold data loaded, plus the playbook and scoring config. A helper issues advisories up to a given number using the same replay code the app uses.
- The deepened modules are tested through this fixture with a fake provider, without the FastAPI app or `TestClient`.
- The existing HTTP fixtures (`create_app(settings, llm)` plus `TestClient`) stay the regression seam. No refactor ticket edits the end-to-end demo test; CR-01 updates it to v3.3.

### Advisory context module

- Interface: from a session and the playbook, give the current advisory (or none before advisory 1), its scenario time, its activation level, whether it is at Full activation, the commander role for that level, and a "require current" check that raises the one existing "no longer current" conflict error.
- Before CR-01 (ticket 02): the activation level boundary rule stays where it is computed today; the module becomes its only caller outside tests. No behaviour change.
- After CR-01: the module reads the activation level as the last declared level from operational state, gives the proposed level from the `propose_at_hours` thresholds, the declaration time, and the hours since Full was declared. It never sets the level; only a declaration through the lifecycle does. Rules gated by `active_from_hours` keep using hours to landfall.
- Full activation is named by the existing constant, never by a string literal in callers.
- Resetting per-advisory flags moves here from replay. Scenario reset calls each owning module's reset, so replay no longer deletes advisory cycle tables.
- The top-10 rank cut moves to scoring config if it is not already there, per the hard rule "all tunable numbers live in config", and is read from one place.
- The frontend reads the current advisory from the scenario state the backend returns.

### Decision package lifecycle module

- Interface (operations, not signatures): open the package for an advisory; read the package view (including whether it is open, who commands, and any activation proposal); decide an item; approve the situation report; declare an activation level (v3.3, P-2.5); expire the package when the next advisory is issued; close it.
- Declaring an activation level (CR-01 adds the endpoint) becomes a lifecycle operation: it checks who may declare (the EOC Director for Level 3 and 2, the Incident Commander for Level 1), writes the declared level and its time through the single state-writing path, records the decision and the audit event, and closes the P-2.5 proposal. It is the only code that sets the activation level. "Is it open" has exactly one source, which the API's package status reports.
- The DB package status is the record (ADR 0001 says the DB stays the record the API and audit log read). The LangGraph checkpoint is the lifecycle's internal adapter for the approval pause. The lifecycle keeps the two consistent and is the only code that reads the checkpoint's waiting state.
- An item decision resolves the activation level once and runs the decision rule check once, before anything changes, so a refusal changes nothing (current guarantee kept). Then it resumes the cycle.
- Situation report approval goes through the same open/closed gate and the same "who commands" answer as item decisions. Its operational state write (the per-advisory situation report flag) and the re-evaluation of the P-7.1 finding go through the same single state-writing path as item decisions. The rule "only the decision step changes operational state" becomes true and stays documented.
- The LangGraph graph keeps its nodes and the interrupt (ADR 0001 is not reopened). The node bodies (creating items, saving the draft, expiring, closing, writing audit records) move into the lifecycle module; the nodes call it.
- The P-7.1 rule ID, the situation report flag and the item status values are each defined once. The API schema's item status reuses the backend definition.
- Behaviour change: approving the situation report for a closed package is refused with the existing "package closed" conflict error. If the current graph closes the package before the situation report can be approved in the demo flow, the ticket must find this and keep the demo flow working (for example, by closing only after the situation report is decided) rather than break it.

### Draft request with built-in grounding

- The draft request exposes the clause IDs and entity IDs it makes citable, derived from its own contents: findings, retrieved clauses, top risks and what changed (including rank moves). Separate grounding assembly is removed.
- One validator takes a draft and the draft request it answered, and returns the list of problems (empty when grounded). This replaces the three-argument citation check.
- One module defines the clause ID and entity ID patterns (all entity prefixes the gold data uses, including hospitals and shelters, with one case rule). The situation report and the copilot both use it.
- "What changed" enters the draft request as the typed changes model, not as an untyped dict.

### Grounded generation module

- One module runs a generation task: call the configured provider, validate the result with the task's validator, retry up to the configured number of attempts, and fall back to the template if every attempt fails or the provider raises. It returns the result, the attempts and a "came from fallback" flag.
- The situation report and the copilot are two tasks through this module. Each supplies its own validator: the draft request validator for the situation report, and tool-returned IDs for the copilot.
- The template is the fallback the module owns and a selectable provider (`LLM_PROVIDER=template`). The module tells a fallback result from a configured template result by how it was produced, not by checking the provider's type.
- The fallback label is defined once. The fallback template is built from the same configuration as a configured template.
- Providers expose transport only. The prompt version and prompt settings reach the provider in the same shape for both tasks. The provider factory stops reaching into the agent's prompt folder; prompts are loaded by the tasks that own them.
- The Azure OpenAI stub stays behind the same interface (decision log, 2026-10-28).
- The hard rule holds: the LLM still never decides whether a rule is met, changes scores or writes operational state. Validation and fallback are deterministic.

### Typed package payloads

- "What changed" and the situation report draft (with its metadata: provider, prompt version, fallback flag) are each one typed model, used for storage and as the API response model. The JSON columns are written and read through these models.
- The mirror API classes for changes and the draft are deleted. The package routes stop needing `type: ignore`.
- "Decides as commander" is derived from the commander role definition.
- The TypeScript types stay hand-written unless the ticket adds generation. Generating from OpenAPI would add a dev dependency, which the ticket must state and justify (global rule: no new dependencies without saying why). Either way, a frontend test checks a fixture taken from a real backend response against the types.

### Playbook module

- Interface: evaluate an advisory and get its findings; get the package items an advisory's findings produce (the playbook decides which rules are left out, such as P-7.1, and that a P-2.5 proposal is presented as an activation proposal); for a finding, get the proposed action and the state that would satisfy it, which may be several state keys together (P-6.2 in v3.3) or none for a proposal; re-evaluate one finding after a state change.
- The rule engine stays as it is (deep, pure, already well tested). The context builder (the namespace the YAML rules read) stays internal to the playbook module, but gets direct tests through the seeded session fixture.
- Entity name lookup is defined once and used by the package view, the playbook read views and the cycle.
- Clause text and thresholds in the playbook files are not edited (project hard rule).

## Testing Decisions

- A good test exercises a module through its interface and checks external behaviour: what a caller sees (the package view, a refusal, the problems list, the audit records, the HTTP response). It does not assert on private helpers, call counts or the shape of graph state.
- Two seams only:
  - **HTTP** through `create_app(settings, llm)` and `TestClient`: the regression net. The end-to-end demo test and the existing HTTP tests stay green. An HTTP test that existed only to reach one internal rule (for example, the rank-move grounding test that replays to advisory 3 twice) is replaced by a test at the new interface, not kept alongside it.
  - **Seeded session**: the new in-process seam for the advisory context, decision package lifecycle, grounded generation and playbook modules, with a fake provider where an LLM is involved.
- The draft request validator is also tested with hand-built draft requests and drafts, since its interface needs no database.
- Modules tested and what each test proves:
  - Advisory context: current advisory before and after advance, commander per level, "require current" refusal, per-advisory flag reset; before CR-01, activation level at each boundary hour; after CR-01, declared level, proposed level at each threshold, hours since Full was declared.
  - Decision package lifecycle: open → decide → approve situation report → close; a refusal changes nothing; a decision on a closed or expired package is refused; situation report approval on a closed package is refused; the package status and the cycle's waiting state never disagree; one audit record per decision; after CR-01, a declaration by the wrong role is refused, a declaration closes the P-2.5 proposal, and no other code path sets the activation level.
  - Draft request: everything shown is citable; something not shown is rejected; hospital and shelter IDs are recognised; the copilot and the situation report share the patterns.
  - Grounded generation: a valid first attempt is used; an invalid attempt is retried; exhausting attempts falls back with the fallback label; a raising provider falls back; a configured template is not labelled a fallback; the attempt log has the same format for both tasks.
  - Typed payloads: a stored draft and stored changes read back equal to what was written; the package response validates with no ignores; the frontend fixture check.
  - Playbook module: rule inputs for a seeded advisory (fed facilities, pumping stations in the top 25 serving the treatment plant, proposed activation level); the satisfying state for a finding, including P-6.2's two keys and a proposal's none; package items leave out P-7.1 and present P-2.5 as a proposal; re-evaluating one finding after a state write.
- Prior art: the rule engine tests that build entities by hand (the playbook test module) for the style of direct interface tests; the HTTP fixtures in the test configuration and the end-to-end demo test for the regression seam; the situation report tests' fake provider passed through `create_app` for injecting a provider (to be replaced by an honest fake); the Anthropic provider unit tests for testing a provider as transport only.
- Frontend: Vitest tests for the package panel keep passing. The "situation report open" logic moves to reading the backend's package status, and its test is updated to match.

## Out of Scope

- Everything CR-01 delivers (playbook v3.3 rules and seeds, the declaration endpoint and UI, ensemble spread, calibration, the Muster rename, the updated demo test). These tickets only reshape the code CR-01 touches, before or after it.
- Replacing LangGraph or changing the advisory cycle's step order or interrupt (ADR 0001).
- Removing the Azure OpenAI stub (decision log, 2026-10-28).
- Any change to playbook clause text, rule thresholds or scoring numbers.
- New EOC features, new UI pages or new LLM features.
- Optimisation or routing code (project hard rule).
- Changing the audit log's event types or the decision log's wording.
- Docker packaging (cut in the decision log).
- Performance work beyond what the seeded session seam gives the test suite for free.

## Further Notes

- Each ticket records any choice this spec leaves open in `docs/decisions.md`, per the project rules.
- If a ticket finds that the deletion test fails for a planned module (it would only move code, not concentrate it), the ticket stops, says so in its Comments and proposes a smaller change, rather than building a shallow module to match this spec.
- The glossary's "Activation level" entry says the level is derived from hours to landfall. CR-01 makes that wrong; updating the entry (declared level, proposed level, declaration) is CR-01 work, and ticket 02 must not add glossary text that repeats the old definition.
- The glossary already names the domain concepts these modules use (advisory, scenario time, activation level, decision package, situation report, approval, override, finding, Incident Commander, Director). If a ticket names a module after a concept not in the glossary (for example "advisory context"), it adds the term to `GLOSSARY.md`.
- The architecture review that produced this spec was a throwaway HTML report in the OS temp directory, not kept in the repo.
