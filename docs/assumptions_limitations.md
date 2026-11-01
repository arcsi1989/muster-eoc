# Assumptions and limitations

> **Fictional prototype.** Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM document. SGW, Bayport County and all data are invented. Nothing here is fit for real operations.

The reasoning behind each item is in `docs/decisions.md`, by date and topic.

## The world

- **Fictional territory on a planar km grid.** No real geography: a synthetic Gulf-style coastline, assets placed by a seeded generator, distances in straight kilometres.
- **One storm, modelled on a 2022 Gulf landfall** (values in `docs/research/florida-hurricanes.md`): Cat 4, radius of maximum wind 37 km, forecast landfall shifting about 80 km east between advisories 2 and 4. The storm is unnamed.
- **Demo seeds are placed by construction** (SUB-07 feeding the hospital, the coastal PS-14, the flooding STG-02, …) and `make data` fails if any stops holding.
- **Distribution is out of scope (PRD A10).** The prototype covers substations, pumping stations and the treatment plant, the single points of failure for critical customers. The outage forecast counts the customers those assets serve; feeders, transformers and service drops below them are not modelled.

## Hazard and risk

- **Hazard is a screening model**, not a surge or wind model: Rankine vortex (decay exponent 0.7 instead of the plan's 0.5, so tropical-storm-force wind reaches ~240 km), 15% inland decay, Gaussian alongshore surge with 3 km inland decay, no waves, rainfall or river flooding.
- **The ensemble** shifts whole tracks sideways by the cone radius at landfall; it does not vary intensity, speed or timing.
- **Ensemble, not NHC products.** Cross-track σ is `ensemble.sigma_cone_factor` (`config/scoring.yaml`) × the cone radius at landfall, an approximation of the forecast spread. Production would consume the NHC probabilistic products instead: wind-speed probabilities and P-Surge.
- **One vertical datum.** Surge height and ground elevation are assumed to share it, so flood depth is their plain difference.
- **Wind is 1-minute sustained** throughout (advisory Vmax, wind field and playbook thresholds); there are no gusts.
- **Fragility curves are illustrative.** The published curves overstate capacity by about 20 % against the hidden truth that Storm Delta's synthetic failures were drawn from; calibration fits them to that one storm (196 assets, in-sample: there is no hold-out storm, so the improvement is not an out-of-sample test). The condition score lowers capacity by up to 30%.
- **The challenger can only find what the synthetic world contains.** It trains on 20 fictional past storms (`make history`) whose failures were drawn from the hidden true curves plus one planted effect: assets older than 40 years in condition 4 or 5 fail more often under strong wind, more still with flood. Finding that effect shows the engineering discipline (leave-storms-out validation, in-fold calibration, a held-out storm, the same metrics for champion and challenger), not that the model would find anything in SGW's assets: its accuracy says nothing about SGW. Each storm is replayed over today's asset base (today's ages and condition scores), and Storm Delta, the held-out storm, predates the planted effect (`docs/decisions.md`).
- **The outage forecast is a screening estimate, and on the synthetic history it forecasts too few.** Per district it draws failures from the rule-based curves' per-member probabilities and follows the dependency graph; crews and generators per failed asset are illustrative numbers in `config/scoring.yaml`, and there is no restoration time, crew travel or mutual aid. Back-tested on the 20 synthetic storms (`make forecast-backtest`, `docs/eval/forecast_results.json`), the P90 covers the simulated outcome in only about half the storm-district cases for customers (power 50 %, water 57 %, crews 46 %, generators 79 %), and the summed medians are about a sixth of what the storms did (power 0.65 M against 3.7 M customers). On the held-out Storm Delta the P90 covers 2 of 4 districts; its medians are about a third of the outcome (power 69 k against 203 k). The cause is the champion, not the drawing: the published curves expect two to five times fewer failures than the synthetic truth produces (the same under-prediction the challenger's reliability table shows), and the forecast inherits it. A forecast from the calibrated curves or the challenger's probabilities is the next step. As for the challenger, accuracy on synthetic data shows the discipline (seeded, held-out storm, the same metrics every run), not skill on SGW.
- **Consequence is one hop**, with a dependent's customers and a facility's policy weight shared among its feeders; there is no network flow or restoration model.
- **Confidence is a data-quality flag** (imputed elevation, stale inspection); it never changes the score.

## Playbook and decisions

- **Rules are evaluated exactly as written** in `playbook_rules.yaml`; nothing is edited. This produces many items (about 10 generator gaps from advisory 3, about 20 conflicts at advisory 5): realistic, and the reason the package is grouped.
- **Approval counts the action as done** from that moment. There is no field confirmation, no crew or generator capacity, and generators are not a pool.
- **No authentication**: a role selector stands in for identity; the backend enforces what each role may decide. Below full activation the Director holds the Incident Commander's decisions.
- **Activation level is derived** from hours to landfall, not declared by a person; deadlines run on scenario time.
- **Advancing never waits**: undecided items close as *not decided*. Advisory 5's package stays open because nothing comes after it.

## The LLM

- **The model narrates; code decides.** The draft and the copilot see plain data and read-only tools only.
- **Citations are checked by membership**: a clause and an entity that are each allowed but unrelated would pass. Numbers in copilot answers are not checked against tool output.
- **No temperature** (the API rejects it for Sonnet 5.5): structured output and the validator keep the draft grounded.
- **Live mode is not exercised by the automated tests** (fakes stand in); one manual check with a real key remains (ticket 09).
- **Azure OpenAI** is a stub behind the provider interface.

## What was cut or left out

- Calibration against a past storm (plan M8), Docker, a working Azure provider, the historical-tracks panel.
- Optimisation and crew routing (lighthouse 2), data pipelines, multi-user, cloud deployment, streaming.
- UI polish is a known follow-up (ticket 11): only the stacked small-screen layout was checked in a browser by the agent.
