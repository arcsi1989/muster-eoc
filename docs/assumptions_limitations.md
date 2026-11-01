# Assumptions and limitations

> **Fictional prototype.** Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM document. SGW, Bayport County and all data are invented. Nothing here is fit for real operations.

The reasoning behind each item is in `docs/decisions.md`, by date and topic; the larger choices are ADRs in `docs/adr/`.

## The world

- **Fictional territory on a planar km grid.** No real geography: a synthetic Gulf-style coastline, assets placed by a seeded generator, distances in straight kilometres, four districts cut by position west to east.
- **One storm, modelled on a 2022 Gulf landfall** (values in `docs/research/florida-hurricanes.md`): Cat 4, radius of maximum wind 37 km, forecast landfall shifting about 80 km east between advisories 2 and 4. The storm is unnamed.
- **Demo seeds are placed by construction** (SUB-07 feeding the hospital, the coastal PS-14, the flooding STG-02, …) and `make data` fails if any stops holding, with the published curves and again with the curves calibrated on Storm Delta.
- **All data is synthetic**, including the past storms: Storm Delta and the 20-storm history are drawn from hidden "true" fragility curves that only the generator knows (`muster/datagen/truth.py`). Every model result below is measured against that invented truth.
- **Distribution is out of scope (PRD A10).** The prototype covers substations, pumping stations and the treatment plant, the single points of failure for critical customers. The outage forecast counts the customers those assets serve; feeders, transformers and service drops below them are not modelled.

## Hazard and risk

- **Hazard is a screening model**, not a surge or wind model: Rankine vortex (decay exponent 0.7 instead of the plan's 0.5, so tropical-storm-force wind reaches ~240 km), 15% inland decay, Gaussian alongshore surge with 3 km inland decay, no waves, rainfall or river flooding.
- **The ensemble** shifts whole tracks sideways by the cone radius at landfall; it does not vary intensity, speed or timing.
- **Ensemble, not NHC products.** Cross-track σ is `ensemble.sigma_cone_factor` (`config/scoring.yaml`) × the cone radius at landfall, an approximation of the forecast spread. Production would consume the NHC probabilistic products instead: wind-speed probabilities and P-Surge.
- **One vertical datum.** Surge height and ground elevation are assumed to share it, so flood depth is their plain difference.
- **Wind is 1-minute sustained** throughout (advisory Vmax, wind field and playbook thresholds); there are no gusts.
- **Fragility curves are illustrative.** The published curves overstate capacity by about 20 % against the hidden truth that Storm Delta's synthetic failures were drawn from; calibration fits them to that one storm (196 assets, in-sample: there is no hold-out storm for the calibration, so the improvement is not an out-of-sample test). The condition score lowers capacity by up to 30%. A calibrated version is used only once a person approves it.
- **The challenger can only find what the synthetic world contains.** It trains on 20 fictional past storms (`make history`) whose failures were drawn from the hidden true curves plus one planted effect: assets older than 40 years in condition 4 or 5 fail more often under strong wind, more still with flood. Finding that effect shows the engineering discipline (leave-storms-out validation, in-fold calibration, a held-out storm, the same metrics for champion and challenger), not that the model would find anything in SGW's assets: its accuracy says nothing about SGW. Each storm is replayed over today's asset base (today's ages and condition scores), and Storm Delta, the held-out storm, predates the planted effect (`docs/decisions.md`), so the promotion rule is checked on a storm without it.
- **The challenger stays in shadow in the demo.** It passes the promotion rule and can be proposed, but nobody approves it; a promoted challenger would change p_fail, risk and rank only, while the explain panel keeps the rule-based wind and flood breakdown. The saved model is a pickle tied to the locked scikit-learn version.
- **The outage forecast is a screening estimate, and on the synthetic history it forecasts too few.** Per district it draws failures from the rule-based curves' per-member probabilities and follows the dependency graph; crews and generators per failed asset are illustrative numbers in `config/scoring.yaml`, and there is no restoration time, crew travel or mutual aid. Generators available are the fuelled fleet for the whole territory, so no per-district generator shortfall is shown. Back-tested on the 20 synthetic storms (`make forecast-backtest`, `docs/eval/forecast_results.json`), the P90 covers the simulated outcome in only about half the storm-district cases for customers (power 50 %, water 57 %, crews 46 %, generators 79 %), and the summed medians are about a sixth of what the storms did (power 0.65 M against 3.7 M customers). On the held-out Storm Delta the P90 covers 2 of 4 districts; its medians are about a third of the outcome (power 69 k against 203 k). The cause is the champion, not the drawing: the published curves expect two to five times fewer failures than the synthetic truth produces (the same under-prediction the challenger's reliability table shows), and the forecast inherits it. A forecast from the calibrated curves or the challenger's probabilities is the next step. As for the challenger, accuracy on synthetic data shows the discipline (seeded, held-out storm, the same metrics every run), not skill on SGW.
- **Consequence is one hop**, with a dependent's customers and a facility's policy weight shared among its feeders; there is no network flow or restoration model.
- **Confidence is a data-quality flag** (imputed elevation, stale inspection); it never changes the score.

## Playbook and decisions

- **Rules are evaluated exactly as written** in `playbook_rules.yaml`; nothing is edited. This produces many items (about 10 generator gaps from advisory 3, about 20 conflicts at advisory 5): realistic, and the reason the package is grouped.
- **Approval counts the action as done** from that moment. A field supervisor can confirm an approved field task (Done) or retract it (Blocked, with a note), and a blocked task's gap returns in the next package; but nothing waits for the field, and approvals with no field work have no confirmation at all. Generators are not a pool: approving one generator action does not consume another's.
- **Resources are counted, not scheduled.** The ICS-215 shows required, available and the shortfall per work assignment from staging data; the outage forecast shows crews needed against those staged. Nothing assigns, routes or optimises crews (lighthouse 2).
- **No authentication**: a role selector stands in for identity, and a field supervisor's district is the caller's word. The backend enforces what each role may decide and which district's tasks a report may touch, not who the person is. Below Full activation the Director holds the Incident Commander's decisions.
- **The activation level is declared by a person**, on the P-2.5 activation proposal; the proposal comes from hours to landfall (Prepare from T-72, Full from T-48). The Director declaring Level 1 "until an IC is appointed" is not modelled. Deadlines run on scenario time.
- **Advancing never waits**: undecided items close as *not decided*. Advisory 5's package stays open because nothing comes after it.

## The LLM

- **The model narrates; code decides** ([ADR 0002](adr/0002-the-llm-narrates-code-decides.md)). The draft, the copilot and the IAP rewording see plain, filtered data and read-only tools only.
- **Copilot answers are checked at runtime** for IDs and numbers: every ID and every number must be in that turn's tool results (`muster/numbers.py`, the same rule the evaluation uses), else the template answers. A number from the question or an earlier turn does not count, so a correct answer quoting it is replaced by the template.
- **Citations are checked by membership**: a clause and an entity that are each allowed but unrelated would pass. The situation report's numbers are not checked, only its citations.
- **Data classification goes by field name** ([ADR 0004](adr/0004-data-classification-before-the-model.md)): a restricted value under another name or in free text (a field supervisor's note) would reach the model; notes are quoted and never citable.
- **The evaluation is rule-based and small** ([ADR 0005](adr/0005-rule-based-evaluation-with-a-gate.md)): 30 golden cases, no LLM judge, so it cannot judge tone or completeness. The live evaluation and the model comparison were run by hand on 2026-11-01 (Sonnet 5.5 passes every gate; Haiku 5.5 and Opus 5.5 fail grounding on answer format, listing more assets than asked or paraphrasing a clause). **The prompts were tuned on Sonnet**, so the comparison favours it; a per-model prompt would be the next step if cost mattered.
- **Costs are estimates** from list prices in `config/llm.yaml`; a model without a price shows its tokens with no cost.
- **No temperature** (the API rejects it for Sonnet 5.5): structured output and the validator keep the draft grounded.
- **Automated tests never call a real model** (fakes stand in); live mode is exercised only by `make eval-llm` and `make eval-compare`, by hand, with a key.
- **Azure OpenAI** is a stub behind the provider interface.

## Operations and delivery

- **One process, one SQLite file, one EOC session.** Every backend start rebuilds the database from the gold files, so a restart is a fresh scenario and loses approved model versions too; a scenario reset (`make demo-reset`) keeps the model versions and the recorded evaluation. There is no multi-user state.
- **Tracing is local by default**: spans go to a table and the run trace page; an OTLP endpoint (Langfuse, Jaeger) is optional and needs the `otlp` extra.
- **CI exists but has not run**: `.github/workflows/check.yml` is ready, and the repo has no remote yet.

## What was cut or left out

- Docker (`make dev` is the one-command run), a working Azure provider, the historical-tracks panel.
- Optimisation and crew routing (lighthouse 2), data pipelines, authentication, multi-user, cloud deployment.
- Small screens: the layout targets a laptop screen (the copilot dock is laptop layout only, ticket 37).
