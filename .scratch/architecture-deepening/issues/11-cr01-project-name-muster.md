# 11: CR-01 C7: the product is called Muster

**What to build:** The product is called Muster; "SGW, Bayport County" is the bundled demo scenario. The UI title and header read "Muster" with the subtitle "Storm preparation decision support · Demo scenario: SGW, Bayport County (fictional)", and the disclaimer footer stays. The README title is "Muster: storm preparation decision support", followed by two sentences on what it does and the take-home disclaimer. The Python package and the frontend app are named `muster`. This is a wide mechanical rename: one commit, nothing else in it, and no other ticket in flight. It runs last, after every refactor and CR-02 ticket, so no branch is open while it lands. Change request: `docs/change_requests/CR-01_operational_realism.md`; target files: `docs/change_requests/CR-01_delivered/`. Record anything ambiguous in `docs/decisions.md`.

**Blocked by:** 07 (CR-01 C3: activation proposal card in the decision package), 10 (CR-01 C6: calibration view), 17 (Copilot through grounded generation), 18 (Typed package payloads), 19 (The playbook answers "what satisfies this finding"), 20 (Direct tests for rule inputs, and one owner for re-evaluation), 22 (CR-02 C1: storm map hero screen), 24 (CR-02 C2: field supervisor view), 26 (CR-02 C3: ICS-215 and IAP draft view)

**Status:** ready-for-agent

- [ ] UI title, header and subtitle as above; disclaimer footer unchanged
- [ ] README title and first paragraph as above
- [ ] Python package `muster` (imports, Makefile, scripts, mypy and pytest config) and frontend app name `muster`
- [ ] Scenario data moved to `data/scenarios/sgw_bayport/` if cheap; otherwise paths kept and the choice recorded in `docs/decisions.md`
- [ ] Playbook and SGW names inside the scenario not renamed
- [ ] `docs/change_requests/CR-01_delivered/` deleted (the live files now equal it)
- [ ] Screenshot of the storm map at advisory 3 saved to `docs/img/storm_map_adv3.png` (CR-02 C1), taken after the rename so it shows the final name
- [ ] `make dev` starts both apps; `./scripts/check.sh` passes
