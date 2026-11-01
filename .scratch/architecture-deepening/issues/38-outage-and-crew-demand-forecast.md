# 38: Customers-out and crew-demand forecast by district

**What to build:** After "which assets are at risk", an EOC lead asks "how bad, where, and do we have enough?". For each advisory and district, forecast the **customers affected** (power customers of failed substations, water customers of failed pumping stations and the treatment plant, kept separate) and the **field demand** (crews and portable generators the expected failures and open playbook actions would need) against what is available (`generators_fuelled`, staging-area crews as the ICS-215 counts them). Compute it per ensemble member, so each figure has a median and a P90, not just an expected value: a member's failures come from the asset failure probabilities under that member's hazard. Every tunable number (crews per failed asset type, generator needs, the number of draws) lives in `config/*.yaml`; the forecast is deterministic for a seed. **Back-test** it on the synthetic history (`data/history/`): forecast vs simulated outcomes per storm, with Storm Delta held out, reported like the challenger's results, with the same caveat in `docs/assumptions_limitations.md` (accuracy on synthetic data shows the discipline, not skill on SGW). **UI**: on the Storm map, a per-district summary (customers out P50–P90, crews and generators needed vs available) that changes with each advisory and uses the district overlay from ticket 36; on the ICS-215 page, the forecast demand shown beside the worksheet as context, never as worksheet rows (the ICS-215 stays built from approved items only, CR-02 C3). The copilot gets a read-only tool for it, with public or internal fields only (CR-03 C1 classification). The LLM never computes the forecast. Record open choices in `docs/decisions.md` and add one scene line to `docs/demo_script.md` (advisory 3 or 4: "how bad, where").

**Blocked by:** 36 (CR-02: districts on the storm map and the operations map), 37 (UI: Situation and Decisions pages, and a copilot dock on every page)

**Status:** wontfix

- [ ] Forecast per advisory and district: customers affected (power and water separately) and crews and generators needed vs available, each as median and P90 from the ensemble members; deterministic for a seed; tunables in `config/`
- [ ] Tests with known expected results (a district with no at-risk assets forecasts zero; doubling customers served doubles customers affected; P90 ≥ median)
- [ ] Back-test on the synthetic history with Storm Delta held out, written to `docs/eval/` and documented with its caveat in `docs/assumptions_limitations.md`
- [ ] Storm map per-district summary and ICS-215 context panel, changing with each advisory (tests); the ICS-215 rows unchanged
- [ ] Copilot read-only tool for the forecast; no restricted field in its result (test)
- [ ] `./scripts/check.sh` passes

## Comments

- 2026-11-01: Parked by the owner's priorities: the reviewers care about code quality and AI capabilities, not new operational functionality. The ML discipline this would show is already shown by the champion and challenger (tickets 32 to 34). Kept as the documented next module (`docs/assumptions_limitations.md`, distribution and outage forecast).
