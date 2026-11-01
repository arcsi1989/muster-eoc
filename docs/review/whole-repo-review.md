# Whole-repo review against the coding standards

> **Fictional prototype.** Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM document. All names and data are synthetic.

Ticket architecture-deepening/43, 2026-11-01. About forty tickets were each reviewed on their own.
This review covers the whole codebase: `backend/`, `frontend/src/`, `scripts/` and `config/`.
It checks them against [CODING_STANDARDS.md](../../CODING_STANDARDS.md) (rule IDs in brackets), the vocabulary in [GLOSSARY.md](../../GLOSSARY.md), and the ADRs.

Findings are ranked most severe first. Each one is marked **fixed** (with its commit) or **left** (with the reason).
The fixes change structure, names and user-visible wording only. They change no playbook text, no threshold and no scenario outcome: the demo scenario tests and the evaluation gate pass unchanged.

## Ranked findings

### 1. Unexpected exceptions broke the error body [B6], and the domain exceptions pulled in FastAPI [B1]: fixed
- **What was wrong:**
  - `backend/muster/errors.py` only had handlers for `AppError`, validation errors and Starlette HTTP errors.
  - Any other exception reaching a route was answered with Starlette's plain-text `Internal Server Error` and was not logged with the request. Examples are a `KeyError` in `playbook/service.py` and an `IndexError` on an empty score list in `routes_risk.py`.
  - The handlers also sat in the same module as the domain exceptions, so the 21 domain modules that raise them imported FastAPI.
- **Fix:**
  - The handlers moved to `api/error_handlers.py`, and `errors.py` now holds only exceptions.
  - A catch-all handler returns `{"error": {"code": "internal", "message": "internal error"}}`. Starlette re-raises after it, so the server logs the traceback, and the handler logs one line naming the request.
  - This is a visible change: such a 500 used to be plain text. `docs/decisions.md` records it, and CODING_STANDARDS B6 now names `api/error_handlers.py`.
  - It is tested in `tests/test_error_handlers.py`, along with the `http_error` mapping, which had no test before [T4].

### 2. Tests took the LLM provider from the shell environment [T2]: fixed
- **What was wrong:** `tests/conftest.py` `test_settings` stopped `.env` from being read, but pydantic-settings still read the process environment. A developer with `LLM_PROVIDER=anthropic` and a key exported in the shell would have made real API calls from every `client` test.
- **Fix:** `test_settings` now passes `llm_provider="template"`.

### 3. Mapped errors were asserted by status only [T4]: fixed
- **What was wrong:** these three errors were checked only by status code:
  - `already_approved` (409, `calibration/versions.py`)
  - `sitrep_already_approved` (409, `agent/sitrep.py`)
  - `note_required` (422, `agent/field.py`)

  A 422 cannot tell `note_required` apart from `validation_error`.
- **Fix:** the tests now assert the error code as well (`test_calibration.py`, `test_sitrep.py`, `test_field_tasks.py`).

### 4. The UI said the EOC "is at full activation" from T-48 [glossary: Activation level, Declaration]: fixed
- **What was wrong:** `features/scenario/IntroPanel.tsx` told the user the level changes by itself. The activation level is only ever declared by a person; at T-48 Full is merely proposed (P-2.5).
- **Fix:** the text now says the playbook proposes Full activation and a person declares it.

### 5. "Audit trail", an avoided term, in the UI and README [glossary: Run trace]: fixed
- **What was wrong:**
  - The Audit page heading, its loading and error text, and the `AuditList` empty state said "audit trail".
  - So did `README.md` (three places).
  - The run trace page said "audit log" for the same thing.
- **Fix:** all of these now say "audit log". `docs/decisions.md` is a dated record and was left as written.

### 6. Planning page said "the commander" [glossary: Incident Commander, Release]: fixed
- **What was wrong:** `features/planning/PlanningPage.tsx` used "the commander" in its hint and in the fallback label.
- **Fix:** the hint now names the Incident Commander (the Director below Full activation), and the fallback reads "role that commands".

### 7. Duplicated issued-advisory guard and scenario-state lookup [G5, deep modules]: fixed
- **What was wrong:**
  - `forecast/service.py` copied `replay/service.require_issued` line for line. It could not import replay without an import cycle.
  - `replay/service._state` copied the `ScenarioState` lookup in `advisory_context.py`.
  - Two routes called `replay.service.require_issued` to reach a question about the advisory context.
- **Fix:** `advisory_context.require_issued` and `advisory_context.scenario_state` are now the one place for these, and every caller uses them.

### 8. Duplicated held-out-storm guard [G5]: fixed
- **What was wrong:** `challenger/train.py` and `forecast/backtest.py` both refused a history containing the held-out storm, with the same three lines.
- **Fix:** the check is now `challenger/dataset.training_storms`, pinned by a new test in `test_challenger.py` [G8, T1].

### 9. Dead code [G6]: fixed
- **Deleted:**
  - `replay/service.issued_advisories`: never called.
  - `agent/prompts/copilot_v1.md`: never loaded. The copilot loads v2, and `docs/decisions.md` keeps its history.
  - The frontend's `getFindings` in `api/scenario.ts`: never imported. The `Finding` type stays because it mirrors `GET /findings` [F6].
  - Five frontend names were exported but used only in their own file: `IDLE_GAP_SHARE`, `BREAK_LABEL_MIN_GAP` (`trace/waterfall.ts`), `LOCAL_TIME_ZONE` (`storm-map/stormTrack.ts`), `ROLE_LABEL` (`lib/roles.ts`) and `DistrictForecastTable`. They are no longer exported.

### 10. Routers redefined shared dependencies and parameters [G5]: fixed
- **What was wrong:**
  - `routes_advisories.py` defined its own `ConfigDep` (the same as `deps.ScoringConfigDep`) and its own `LevelsDep`.
  - Three routes wrote `Annotated[int, Query(ge=1)]` inline instead of using `api/params.AdvisoryQuery`.
- **Fix:** the shared aliases are now used everywhere, and `ActivationLevelsDep` lives in `deps.py`.

### 11. `/health` had no `response_model` [B4]: fixed
- **Fix:** it now returns `HealthOut`. It was the only route without a response model; the SSE chat route sets `response_model=None` on purpose.

### 12. Glossary drift in code and UI text: fixed
- **What was wrong:**
  - `calibration/versions.ActiveModelVersion` was named with an avoided word for Champion, but it means the latest approved curves.
  - Map and risk-list tooltips showed the field name `p_fail`.
  - The API, UI and README use "alert" for risk-list changes, but the glossary listed "Alert" only as an avoided word for Finding.
- **Fix:** `ActiveModelVersion` is renamed `LatestCurves`. The tooltips say "failure probability" (`StormMap.tsx`, `RiskList.tsx`). A **Risk alert** entry has been added to the glossary.

### 13. Duplicated helpers across features [G5]: partly fixed
- **Fixed:**
  - `ChallengerFeatures.formatContribution` and the percentages in `TerritoryMap.tsx` now use `lib/labels.formatDelta` and `lib/format.formatPercent`, which give the same output.
  - The package and copilot panels' identical clause loading and indexing is now one `lib/useClauses.ts`.
- **Left (not mechanical; refactors for their own commits under G8):**
  - About 20 "Could not load X" + Retry blocks could become one `<LoadError>` component.
  - The busy/action-error `try/catch/finally` appears in six hooks, but the stale-reload rules differ per feature.
  - `App`'s operations screen and `StormMapScreen` share the header and territory loading.
  - The token and cost strings in `HowIGotThis.tsx` and `AuditList.tsx` differ from `formatTokens` and `formatCost`, so unifying them changes visible text.

### 14. Copilot input limit: config key that nothing reads [B9, G6]: left
- **What is wrong:** `config/scoring.yaml` `copilot.history_max: 20` is parsed into `CopilotConfig` but never used. The limit that actually applies is `Field(max_length=20)` in `api/schemas.py` `ChatIn`. The 4,000- and 2,000-character limits next to it are also in code; `docs/decisions.md` records the values.
- **Why left:** the owner has to choose:
  - enforce the config value in the copilot route, which changes how the 422 is raised; or
  - delete the key and record the limits as API-schema constants, which moves further from B9.

  Either way is a decision, not a mechanical edit.

### 15. Copilot token usage is lost when a multi-round chat fails [L7]: left
- **What is wrong:** `llm/anthropic_provider.chat` adds up usage across tool rounds but logs it only on success. A refusal, deadline, round-limit or API error after round 1 raises `LLMUnavailable` without the tokens already spent, so `llm/grounded.py`'s attempt log and the run-trace cost understate them.
- **Why left:** the fix carries usage on the exception, or logs per round. That changes the attempt-log contract and the trace cost, so it is a behaviour change with its own tests.

### 16. Some text sent to the model sits in code, outside the versioned prompt files [L3]: left
- **What is wrong:**
  - The retry feedback ("Your previous … was rejected") is in `anthropic_provider._content` and again in `copilot/chat._REJECTED`.
  - The task lines for the situation report and the IAP objective reword are in `anthropic_provider.py`.
  - Changing this text does not change the recorded prompt version.
- **Why left:** moving the text into `agent/prompts/` means bumping `sitrep-v2`, `copilot-v2` and `iap-objectives-v1`, and re-running the evaluation against the provider. That is a prompt change, not a mechanical one.

### 17. Routes doing data access and view shaping [B1]: left
- **What is wrong:**
  - `api/routes_territory.py` queries `Asset`, `Facility` and `StagingArea` directly.
  - `routes_advisories._scenario` builds the storm view in the route: valid-at times, intensity category, past positions and cone.
- **Why left:** moving them into `territory.py` and a replay view function is a refactor that G8 says should be pinned with tests and done in its own commit. No behaviour depends on where the code sits.

### 18. Uneven API shapes: left
- **What is uneven:**
  - Three domain models are the wire format: `replay.diff.AdvisoryChanges` (`/advisories/{n}/changes`, and inside `PackageOut`), `llm.schemas.PackageDraft`, and `planning.products.PlanningProducts` (subclassed by `PlanningOut`). A change to one of them silently changes the API.
  - `/risk` wraps its list (`RiskListOut`), while `/alerts`, `/exposure` and `/findings` return bare lists.
- **Why left:** wrapping the lists changes the frontend contract. Separate `*Out` mirrors are worth a ticket of their own. The frontend types match the current shapes field for field [F6].

### 19. Components that load and mutate without a data hook [F2]: left
- **What is wrong:** `PackagePanel.tsx` (package load, plus decide, declare and approve situation report), `CopilotPanel.tsx` (streaming chat) and `App.tsx` `OperationsScreen` (five loaders) do their work inline. Sibling features use `usePlanning`, `useFieldTasks` and `useChallenger`.
- **Why left:** extracting `usePackage`, `useCopilot` and `useOperationsData` is a medium refactor per G8. `AuditPage`, `DataQualityPage` and `ExplainDrawer` already go through `useLoad`, which is a data hook, so they are not findings.

### 20. Wall-clock times shown in UTC on some pages and local time on others: left
- **What is inconsistent:**
  - `formatIssuedAt` (UTC) formats `drafted_at`, `released_at`, `decided_at` and `loaded_at` (`PlanningPage.tsx`, `ActivationProposalCard.tsx`, `DataQualityTable.tsx`).
  - `formatWallClock` (local time) formats the same kind of timestamp in `FieldTaskCard.tsx` and `AuditList.tsx`.
- **Why left:** unifying them changes visible output and a pinned test (`ActivationProposalCard.test.tsx`), so it needs a choice of time zone first.

### 21. Tunables in code [B9]: left (documented)
- **What is in code:** `llm/factory.py` `max_retries=1`, and `output_config` effort `low` in `anthropic_provider.py`.
- **Why left:**
  - The retry count is recorded in `docs/decisions.md` ("one SDK retry"), and the timeouts already live in `Settings`. Moving it means threading `llm.yaml` into `build_provider` and its callers in the evaluation CLIs.
  - The effort setting was written twice and is now one constant (`OUTPUT_CONFIG`).
- **Also left:**
  - UI text that repeats config values: "50 forecast variants" in `ExplainPanel.tsx`, and "72 hours" and "every 12 hours" in `IntroPanel.tsx`. Deriving them needs the backend to expose the member count.
  - `datagen/seed_check.py` recomputes the top 25 instead of reusing `WTP_PUMP_STATIONS_TOP_N`. That is a plan assertion, not a tunable.

### 22. Error paths without an HTTP test [T4]: left
- **What is untested:**
  - `DataNotLoaded` is asserted only as a copilot SSE error event.
  - `PackageOutOfStep` is tested only at domain level. It is documented as a bug, never a refusal.
- **Why left:** each needs a fixture that breaks the loaded data. That is low value, so it is noted here.

### 23. The audit log's actor badge showed the raw enum: fixed
- **What was wrong:** `AuditList.tsx` printed `field_supervisor`, `human` and so on, while the filter beside it used labels.
- **Fix:** the badge now shows a label ("Field supervisor", "Person"), pinned in `AuditPage.test.tsx`.

### 24. Minor: left
- **`AdvisoryContext.scenario_time`** (`advisory_context.py`) is read only by tests. Deleting it would also delete their assertions [T6], and it names a glossary term the context should answer.
- **`TerritoryMap.tsx` markers** are mouse-only, whereas `StormMap.tsx` markers have keyboard handling [F7]. The risk list's buttons give keyboard access to the same action.
- **`AuditList.tsx` parses LLM attempts with its own local type** and ignores `problems`. `TraceSpanOut.attempts` is `list[dict]`, so a shared attempt type is a backend change first.

## Checked and found clean
- **`scripts/check.sh`:** it runs every gate the standards name:
  - ruff format and ruff check, mypy strict and pytest [B8, T6];
  - prettier, tsc, oxlint and vitest [F5];
  - the evaluation gate in template mode [L9].

  It installs from the lockfiles, fails when nothing was checked, and treats a change under `config/` or `data/` as a reason to check everything.
- **`config/*.yaml`:** every key in `scoring.yaml`, `models.yaml`, `llm.yaml`, `evals.yaml` and `consequence_weights.yaml` was checked for a reader. Only `copilot.history_max` has none (finding 14). The `hgb.*` keys reach the model through `model_dump()` in `challenger/train.py`.
- **Layering and configuration [B1, B2]:**
  - No domain package imports FastAPI (after fix 1).
  - Nothing reads `os.environ` outside `config.py`.
- **Clients [B3]:** the Anthropic client is built once in the lifespan.
- **Async [B5]:** every route is a plain `def`, recorded in `docs/decisions.md` (the LangGraph cycle is synchronous).
- **Timeouts [B7]:** every outbound call has a timeout.
- **Audit [B10]:** every mutating path writes the audit log. Challenger registration is deliberately not audited (`docs/decisions.md`, ticket 33).
- **LLM rules [L1–L9]:** within the deviations `docs/decisions.md` records:
  - copilot citations are parsed from the model's text, but only IDs that tools returned count;
  - situation-report numbers are not number-checked;
  - no temperature is set on a model that takes no sampling parameters.

  The LLM decides no rule and writes no state. Every feature has its template fallback.
- **Frontend [F1, F5, F6]:** only `api/client.ts` calls `fetch`; there is no `any` and no `@ts-ignore`; the types match every response model field for field.
- **Tests [T3, T4, T6]:** every endpoint has a happy-path test; no test calls a private helper; nothing is skipped.
- **Glossary terms:** no "zone" or "region" for District, no "sitrep" in UI text, no "tuning" for Calibration, and none of the other avoided terms appear in user-visible text.
