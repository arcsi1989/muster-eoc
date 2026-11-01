# Muster: storm preparation decision support

[![check](https://github.com/OWNER/REPO/actions/workflows/check.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/check.yml)

Muster replays a hurricane's forecast advisories for a utility's Emergency Operations Center (EOC) and, for each one, scores asset risk, checks the hurricane playbook with a deterministic rule engine, and assembles a decision package of gaps, conflicts and a draft situation report. People approve or override every item, and the audit trail records each decision; no AI output changes operational state. Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM document.

> **Fictional prototype.** The bundled demo scenario, SGW (Southeastern Grid & Water) in Bayport County, and every asset, facility and threshold in it are invented, and the storm is unnamed (its parameters are modelled on a real past landfall); all data is synthetic. Not for real operations.

The demo scenario starts 72 hours before a hurricane lands. Five forecast advisories are replayed one at a time. For each one the app:

1. computes hazard exposure (wind, storm surge, flood depth) for about 200 assets from a 50-member forecast ensemble, and a transparent risk score per asset;
2. evaluates the utility's hurricane playbook with a deterministic rule engine: which actions are required, which are not done (gaps), and where stop-work collides with field work (conflicts);
3. assembles a **decision package**: what changed, the gaps with proposed actions, the conflicts for the Incident Commander, and a draft situation report written by Claude (or a template, offline) with checked citations;
4. waits for people: each item is approved or overridden by role, conflicts are decided only by the Incident Commander, and every step lands in an audit trail.

**Scope:** substations, pumping stations and the treatment plant, the single points of failure for critical customers; distribution assets are out of scope (PRD A10) and follow as an outage-forecast module.

**The prototype prepares; it never acts.** No AI output changes operational state: only a person's recorded decision does.

![Operations screen at advisory 3](docs/screenshots/operations.jpg)

## Run it

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 24 (`frontend/.nvmrc`; 22.22+ also works) with [pnpm](https://pnpm.io/).

```bash
make install     # backend and frontend dependencies, from the lockfiles
make dev         # backend on http://localhost:8000, frontend on http://localhost:5173
```

Open http://localhost:5173. `make dev` runs offline with the template provider unless `backend/.env` says otherwise.

**With Claude** (the live draft and copilot): copy `backend/.env.example` to `backend/.env` and fill in the key.

```bash
LLM_PROVIDER=anthropic          # or "template" (offline, the default)
LLM_MODEL=claude-sonnet-5-5
ANTHROPIC_API_KEY=...
```

With `LLM_PROVIDER=anthropic` and no key the backend refuses to start and says which variable to set. A failing or ungrounded model answer is never shown: the template takes over and the audit trail says why.

Other commands:

| Command | What it does |
|---|---|
| `make demo-reset` | Back to before advisory 1 (the backend must be running). Restarting the backend also resets. |
| `make data` | Regenerate the synthetic data (seed 42, byte-identical every run) and replay all five advisories to check every demo fact still holds. |
| `make history` | Regenerate the synthetic storm history the challenger trains on (20 fictional storms, seed 42; `make data` runs it too). |
| `make train` | Train the challenger model and compare it with the rule-based champion, by storm and on held-out Storm Delta; writes `docs/eval/challenger_results.json`. |
| `make eval` | Run the LLM evaluation's golden set (30 cases: grounding, refusal, data classification, prompt injection, drafting) with the template provider and gate it on `config/evals.yaml`; writes `docs/eval/report.md` and `results.json`. `./scripts/check.sh` runs the same gate. |
| `make eval-llm` | The same golden set against the configured provider (`LLM_PROVIDER`, needs its key), each case 3 times, pass rate per category. Exits non-zero below a threshold. |
| `make eval-compare` | Which model is good enough, at what cost: the same golden set (each case 3 times) against every model of the configured provider listed under `compare` in `config/evals.yaml` (default Claude Haiku, Sonnet and Opus 5.5). Writes [docs/eval/comparison.md](docs/eval/comparison.md): per model, pass rate per category, the gate, latency P50/P90 per answer, tokens, and cost per answer and per run at the prices in `config/llm.yaml`, ranked cheapest passing model first. Needs `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`; refuses to run with the template. **It costs API money**: 90 answers per model; the run of 2026-11-01 cost $4.68 for the three defaults ($0.09 Haiku, $1.48 Sonnet, $3.11 Opus, measured, retries included; [docs/eval/comparison.md](docs/eval/comparison.md)). |
| `make test` | Every check: ruff, mypy (strict), pytest, the eval gate, oxlint, tsc, vitest (`./scripts/check.sh`). |

**Continuous integration**: [`.github/workflows/check.yml`](.github/workflows/check.yml) runs `./scripts/check.sh` on every push and pull request, in template mode with no secrets, on the pinned toolchain (Python from `backend/.python-version`, Node from `frontend/.nvmrc`, pnpm from `frontend/package.json`, dependencies from the lockfiles, cached). It uploads the template eval report (`eval-report`) and the backend coverage report (`coverage-backend`) as artifacts. The repo has no remote yet, so the workflow runs once it is pushed to GitHub; then replace `OWNER/REPO` in the badge above.

Latest evaluation report: [docs/eval/report.md](docs/eval/report.md); model comparison: [docs/eval/comparison.md](docs/eval/comparison.md). The backend records it in the audit log at startup.

The 8-minute demo walkthrough is in [docs/demo_script.md](docs/demo_script.md).

## Using it

- **Issue advisory ▶** in the header replays the next forecast. The timeline shows the five advisories and the activation level (Prepare from T-72 h, Full activation from T-48 h).
- **Map**: assets coloured by failure probability, hospitals, shelters, staging areas, the forecast track, the previous track and the cone. Click an asset to see why it ranks where it does.
- **Risk list**: ranked by risk = failure probability × consequence, with rank changes and alerts.
- **Decision package**: pick your role under *Deciding as*, then approve, override (with a reason) or, as Incident Commander, decide conflicts. Edit and approve the situation report.
- **Copilot** (the button at the right of the page bar, on every page): it streams each step while it works and shows an answer only once it has passed validation; **How I got this** under each answer lists the tools, their results, the validation, retries, model, tokens and cost. Ask "Why is PS-14 ranked where it is?", "What are the top risks?", "What depends on SUB-07?", "What does P-4.7 say?".
- **Audit** and **Data quality** pages: every step with its actor and versions; every loaded file with its hash and rejected rows.

![Decision package with a conflict at advisory 5](docs/screenshots/decision-package.jpg)

More screens, in demo order (`docs/demo_script.md`): [field tasks](docs/screenshots/field-tasks.jpg), [run trace](docs/screenshots/run-trace.jpg), [ICS-215 and IAP](docs/screenshots/ics215.jpg), [calibration](docs/screenshots/calibration.jpg), [champion and challenger](docs/screenshots/champion-challenger.jpg).

## Sample data

Every data file is **synthetic**: generated with seed 42 for a fictional utility, territory and storm, and committed so the demo runs without generating anything. `make data` and `make history` are deterministic and regenerate byte-identical files. The backend loads `data/gold/` (each file against its contract in `contracts/`) into a fresh SQLite database at every start.

| File | What it holds | Regenerated by |
|---|---|---|
| `data/gold/advisories/adv_01.json` … `adv_05.json` | The five forecast advisories, T-72 h to T-24 h: track points with max wind, cone radius, forecast landfall, peak surge | `make data` |
| `data/gold/assets.json` | 196 assets (120 substations, 75 pumping stations, 1 treatment plant): name, type, district, condition, install year, last inspection, elevation, distance to coast, customers served, coordinates | `make data` |
| `data/gold/assets_rejected_example.json` | Two malformed asset rows loaded as an incoming batch, so the Data quality page shows rejected rows with their reasons | `make data` |
| `data/gold/critical_facilities.json` | 30 critical facilities: 8 hospitals and 22 shelters | `make data` |
| `data/gold/dependencies.json` | 117 supply edges: which asset feeds which asset or facility | `make data` |
| `data/gold/districts.json` | The four districts, west to east, with their boundaries and map labels | `make data` |
| `data/gold/staging_areas.json` | Five staging areas for crews and equipment | `make data` |
| `data/gold/coastline.geojson` | The synthetic coastline the maps draw and the surge model measures along | `make data` |
| `data/gold/fragility_curves.json` | The six published fragility curves (wind and flood per asset type): model version 1, the rule-based champion | `make data` |
| `data/gold/initial_state.json` | Operational state before advisory 1: activation level Monitor, 6 generators fuelled, per-site state flags (generator assigned, barrier installed, inspection completed, backup power confirmed, …; relocated for staging areas) | `make data` |
| `data/gold/history/storm_delta_track.json` | Storm Delta, the past storm: its best track | `make data` |
| `data/gold/history/storm_delta_outcomes.json` | Which of the 196 assets Storm Delta failed (51), drawn from the hidden true curves; used by calibration and as the challenger's held-out storm | `make data` |
| `data/history/synthetic_storms.json` | 20 fictional past storms (S01–S20) with tracks and per-asset outcomes, including one planted age-and-condition effect; the challenger trains on it (not loaded by the app) | `make history` (also run by `make data`) |
| `data/models/challenger.pkl` | The trained challenger with its baseline and Storm Delta comparison, loaded at startup for shadow scoring | `make train` |
| `data/playbook/playbook_rules.yaml` | The fictional hurricane playbook's machine-checkable rules, an input of the brief beside `docs/playbook.md`; never generated or edited by code | not generated |

`make data` also rewrites the JSON Schemas in `contracts/` and replays all five advisories to check the demo seed facts. `make train` also writes `docs/eval/challenger_results.json`; `make forecast-backtest` writes `docs/eval/forecast_results.json`. Each gold file's hash and its rejected rows are on the Data quality page. What the data assumes is in [docs/assumptions_limitations.md](docs/assumptions_limitations.md).

## Documentation

| Document | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | The system as built: module diagram with its seams, the flow of one advisory, where each hard rule is enforced |
| [docs/assumptions_limitations.md](docs/assumptions_limitations.md) | What is simplified, assumed or left out |
| [docs/demo_script.md](docs/demo_script.md) | The scripted demo, with timings |
| [docs/decisions.md](docs/decisions.md) | Every choice the plan left open, with its reason |
| [docs/adr/](docs/adr/) | Architecture decision records: [0001 LangGraph for the advisory cycle](docs/adr/0001-langgraph-for-the-advisory-cycle.md), [0002 the LLM narrates, code decides](docs/adr/0002-the-llm-narrates-code-decides.md), [0003 grounded generation](docs/adr/0003-grounded-generation.md), [0004 data classification](docs/adr/0004-data-classification-before-the-model.md), [0005 rule-based evaluation with a gate](docs/adr/0005-rule-based-evaluation-with-a-gate.md), [0006 champion and challenger](docs/adr/0006-champion-and-challenger.md), [0007 human approval is the only path to state](docs/adr/0007-human-approval-is-the-only-path-to-state.md) |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md), [docs/playbook.md](docs/playbook.md) | The brief: plan and fictional playbook |
| [GLOSSARY.md](GLOSSARY.md) | Domain terms: gap, action, conflict, approval, override, … |
| [CODING_STANDARDS.md](CODING_STANDARDS.md), [AGENTS.md](AGENTS.md) | Rules for code and agents; the definition of done |
