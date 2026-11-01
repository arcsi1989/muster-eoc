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
| `make eval-compare` | Which model is good enough, at what cost: the same golden set (each case 3 times) against every model of the configured provider listed under `compare` in `config/evals.yaml` (default Claude Haiku, Sonnet and Opus 5.5). Writes [docs/eval/comparison.md](docs/eval/comparison.md): per model, pass rate per category, the gate, latency P50/P90 per answer, tokens, and cost per answer and per run at the prices in `config/llm.yaml`, ranked cheapest passing model first. Needs `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`; refuses to run with the template. **It costs API money**: 90 answers per model, about $8 for the three defaults (roughly $0.13 Haiku, $2.60 Sonnet, $5.20 Opus), estimated at about 12k input and 500 output tokens per answer; retries add to it, and the comparison reports the measured cost. |
| `make test` | Every check: ruff, mypy (strict), pytest, the eval gate, oxlint, tsc, vitest (`./scripts/check.sh`). |

**Continuous integration**: [`.github/workflows/check.yml`](.github/workflows/check.yml) runs `./scripts/check.sh` on every push and pull request, in template mode with no secrets, on the pinned toolchain (Python from `backend/.python-version`, Node from `frontend/.nvmrc`, pnpm from `frontend/package.json`, dependencies from the lockfiles, cached). It uploads the template eval report (`eval-report`) and the backend coverage report (`coverage-backend`) as artifacts. The repo has no remote yet, so the workflow runs once it is pushed to GitHub; then replace `OWNER/REPO` in the badge above.

Latest evaluation report: [docs/eval/report.md](docs/eval/report.md); model comparison: [docs/eval/comparison.md](docs/eval/comparison.md). The backend records it in the audit log at startup.

The 8-minute demo walkthrough is in [docs/demo_script.md](docs/demo_script.md).

## Using it

- **Issue advisory ▶** in the header replays the next forecast. The timeline shows the five advisories and the activation level (Prepare from T-72 h, Full activation from T-48 h).
- **Map**: assets coloured by failure probability, hospitals, shelters, staging areas, the forecast track, the previous track and the cone. Click an asset to see why it ranks where it does.
- **Risk list**: ranked by risk = failure probability × consequence, with rank changes and alerts.
- **Decision package**: pick your role under *Deciding as*, then approve, override (with a reason) or, as Incident Commander, decide conflicts. Edit and approve the situation report.
- **Copilot**: ask "Why is PS-14 ranked where it is?", "What are the top risks?", "What depends on SUB-07?", "What does P-4.7 say?".
- **Audit** and **Data quality** pages: every step with its actor and versions; every loaded file with its hash and rejected rows.

![Decision package with a conflict at advisory 5](docs/screenshots/decision-package.jpg)

More screens, in demo order (`docs/demo_script.md`): [field tasks](docs/screenshots/field-tasks.jpg), [run trace](docs/screenshots/run-trace.jpg), [ICS-215 and IAP](docs/screenshots/ics215.jpg), [calibration](docs/screenshots/calibration.jpg), [champion and challenger](docs/screenshots/champion-challenger.jpg).

## Documentation

| Document | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Components, data flow, and where each part of the plan lives |
| [docs/assumptions_limitations.md](docs/assumptions_limitations.md) | What is simplified, assumed or left out |
| [docs/demo_script.md](docs/demo_script.md) | The scripted demo, with timings |
| [docs/decisions.md](docs/decisions.md) | Every choice the plan left open, with its reason |
| [docs/adr/](docs/adr/) | Architecture decision records |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md), [docs/playbook.md](docs/playbook.md) | The brief: plan and fictional playbook |
| [GLOSSARY.md](GLOSSARY.md) | Domain terms: gap, action, conflict, approval, override, … |
| [CODING_STANDARDS.md](CODING_STANDARDS.md), [AGENTS.md](AGENTS.md) | Rules for code and agents; the definition of done |
