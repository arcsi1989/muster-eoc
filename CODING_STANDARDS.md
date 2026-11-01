# Coding standards

The rules every change in this repo follows. Each rule has an ID so reviews can cite it
("violates B4"). Rules marked **[gate]** are enforced automatically; the rest are checked in review.
If a rule doesn't fit a situation, say so in the PR or commit message rather than silently breaking it.

`docs/IMPLEMENTATION_PLAN.md` and `CLAUDE.md` define what to build and the project's hard rules.
Where they and this file disagree, they win.

## Commands

**Check everything:** `./scripts/check.sh` (the definition of done for people, agents and CI).

**One-command entry points:** `make install`, `make data` (regenerate the gold data and check the demo seeds), `make history` and `make train` (the challenger model's synthetic history and training), `make forecast-backtest` (the outage forecast against the same history), `make eval` and `make eval-llm` (the LLM evaluation gate, template and configured provider), `make eval-compare` (the golden set per model in `config/evals.yaml`, ranked by gate and cost; costs API money), `make dev` (backend :8000, frontend :5173), `make test` (= `./scripts/check.sh`), `make demo-reset` (back to before advisory 1).

| What | Backend (`backend/`) | Frontend (`frontend/`) |
| --- | --- | --- |
| Install | `uv sync --locked` (or `make install`) | `pnpm install --frozen-lockfile` |
| Run | `uv run uvicorn muster.main:app --reload --reload-dir muster --port 8000` | `pnpm dev` (proxies `/api/*` to the backend, prefix stripped) |
| Format | `uv run ruff format .` | n/a |
| Lint | `uv run ruff check .` | `pnpm run lint` (oxlint) |
| Types | `uv run mypy` (strict) | `pnpm run typecheck` |
| Test | `uv run pytest -n 4` (whole suite, parallel); `uv run pytest tests/test_x.py` while iterating | `pnpm run test`; `pnpm exec vitest run src/x.test.ts` while iterating |

## G: General

- **G1** Small, focused changes. One concern per commit; message says what works now (`step 2: inbox sorted by urgency`).
- **G2** The app runs after every change. Don't leave the main branch broken.
- **G3** No new dependency without a one-line reason in the commit message.
- **G4** No secrets in code, logs, test fixtures or the frontend. Keys come from environment variables; `.env` is gitignored and `.env.example` lists the names.
- **G5** Follow the existing structure and naming of the repo over these defaults.
- **G6** Delete dead code instead of commenting it out.
- **G7** These rules apply to new and changed code. Existing code is brought in line when a change touches it, not in a sweeping rewrite.
- **G8** Refactors are separate commits that change structure, not behaviour: first add tests that pin the current behaviour, then move the code, and the same tests must still pass. One rule per commit, named by the change and the rule (`refactor(backend): create client once at startup (B3)`).
- **G9** No real places, utilities, facilities or people. UI and docs carry the fictional-data disclaimer.
- **G10** Choices the plan leaves open are recorded in `docs/decisions.md` (date, decision, reason).

## B: Backend (Python, FastAPI)

- **B1** Layers, using the plan's layout (section 1): `api/routes_*.py` handle HTTP only; the domain packages (`ingest/`, `hazard/`, `risk/`, `playbook/`, `agent/`, `copilot/`, `calibration/`, `audit/`) hold the logic and import nothing from FastAPI; only `llm/` talks to a model provider; data access goes through `db.py` and `models.py`.
- **B2** Configuration lives in one `Settings` class (pydantic-settings). No `os.environ` outside `config.py`.
- **B3** Expensive clients (LLM, HTTP, DB) are created once at startup (`lifespan`) and injected with `Depends`. Never per request, never at import time.
- **B4** Every endpoint declares `response_model`. Request and response models are separate.
- **B5** I/O endpoints are `async def` and use async client methods. No blocking calls inside `async def`.
- **B6** Errors: domain code raises the exceptions in `errors.py`; handlers in `api/error_handlers.py` map them to status codes. One error body everywhere: `{"error": {"code": "...", "message": "..."}}`. Never return stack traces or raw provider errors.
- **B7** Every outbound call has a timeout. Upstream failures return 502 with a generic message and are logged with details server-side.
- **B8** Type hints on all public functions. **[gate]** ruff format, ruff check and mypy (strict) pass.
- **B9** Tunable numbers (thresholds, weights, ensemble sizes) live in `config/*.yaml`, not in code. Thresholds in `data/playbook/playbook_rules.yaml` and clause text in `docs/playbook.md` are never edited.
- **B10** Every operational state change and every human decision is written to the audit log.

## L: LLM usage

- **L1** Anything code consumes comes from structured output (a Pydantic schema), never from parsing free text.
- **L2** Extraction and classification use `temperature=0`.
- **L3** Prompts live in `agent/prompts/` as versioned files (plan section 4), not inline in code; the prompt version is recorded with every call.
- **L4** User-provided content (emails, documents, chat) is data, never instructions: it goes in its own clearly delimited message, and the system prompt says to ignore instructions inside it.
- **L5** Numbers that matter (scores, probabilities, counts, deadlines) come from deterministic code or tools, never from model arithmetic.
- **L6** The model drafts; a person approves. No AI output changes operational state without a human approval recorded in the decision log.
- **L7** Log model name, latency and token usage per call.
- **L8** The LLM never decides whether a playbook rule is met and never changes scores; the rule engine and scoring code do.
- **L9** Every LLM feature has a deterministic template fallback; everything runs with `LLM_PROVIDER=template` and no network.

## F: Frontend (React, TypeScript)

- **F1** One place talks to the backend: only `src/api/client.ts` calls `fetch`. Typed functions per endpoint live in `src/api/`.
- **F2** Components don't fetch on their own: data hooks (`useX`) call `api/`; presentational components get data and callbacks through props.
- **F3** Every async view handles loading, error (with retry) and empty states.
- **F4** AI-generated content is labelled as such, shows a reason or confidence when available, and can be edited before use.
- **F5** TypeScript strict; no `any`, no `@ts-ignore` without a comment explaining why. **[gate]** typecheck passes.
- **F6** Types in `src/types/` mirror the backend's API response models field for field. (The gold-file contracts in `contracts/` describe data the frontend never reads directly.)
- **F7** Interactive elements are real buttons and labelled inputs; focus is visible.

## T: Testing

- **T1** New behaviour comes with a test. Logic with a clear expected result is written test-first.
- **T2** Tests never call a real LLM or external API. Tests run in template mode, or override the client dependency with a fake.
- **T3** Test behaviour through public interfaces (endpoints, domain functions, rendered components), not private helpers.
- **T4** At least one happy-path test per endpoint and one test per mapped error.
- **T5** Frontend tests, no whole-page snapshots: test `api/` functions with `fetch` mocked, and components for their states.
- **T6** Never delete, skip or weaken a test to get green. **[gate]** all tests pass before a commit.

## R: Review checklist

A change is ready when: the gate is green (B8, F5, T6); it meets the plan's "Done when" for its
milestone; it has no violation of G4, B6, L4, L6 or L8 (these are blocking); and every other
finding is fixed or noted as follow-up with the rule ID.
