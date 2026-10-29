# Assumptions and limitations

> **Fictional prototype.** Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM document. SGW, Bayport County and all data are invented. Nothing here is fit for real operations.

The reasoning behind each item is in `docs/decisions.md`, by date and topic.

## The world

- **Fictional territory on a planar km grid.** No real geography: a synthetic Gulf-style coastline, assets placed by a seeded generator, distances in straight kilometres.
- **One storm, modelled on a 2022 Gulf landfall** (values in `docs/research/florida-hurricanes.md`): Cat 4, radius of maximum wind 37 km, forecast landfall shifting about 80 km east between advisories 2 and 4. The storm is unnamed.
- **Demo seeds are placed by construction** (SUB-07 feeding the hospital, the coastal PS-14, the flooding STG-02, …) and `make data` fails if any stops holding.

## Hazard and risk

- **Hazard is a screening model**, not a surge or wind model: Rankine vortex (decay exponent 0.7 instead of the plan's 0.5, so tropical-storm-force wind reaches ~240 km), 15% inland decay, Gaussian alongshore surge with 3 km inland decay, no waves, rainfall or river flooding.
- **The ensemble** shifts whole tracks sideways by the cone radius; it does not vary intensity, speed or timing.
- **Fragility curves are illustrative** and uncalibrated (calibration was cut). The condition score lowers capacity by up to 30%.
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
