# 11: CR-01 C7: the product is called Muster

**What to build:** The product is called Muster; "SGW, Bayport County" is the bundled demo scenario. The UI title and header read "Muster" with the subtitle "Storm preparation decision support · Demo scenario: SGW, Bayport County (fictional)", and the disclaimer footer stays. The README title is "Muster: storm preparation decision support", followed by two sentences on what it does and the take-home disclaimer. The Python package and the frontend app are named `muster`. This is a wide mechanical rename: one commit, nothing else in it, and no other ticket in flight. It runs last, after every refactor, CR-02 and CR-03 ticket, so no branch is open while it lands. Change request: `docs/change_requests/CR-01_operational_realism.md`; target files: `docs/change_requests/CR-01_delivered/`. Record anything ambiguous in `docs/decisions.md`.

**Blocked by:** 07 (CR-01 C3: activation proposal card in the decision package), 10 (CR-01 C6: calibration view), 17 (Copilot through grounded generation), 18 (Typed package payloads), 19 (The playbook answers "what satisfies this finding"), 20 (Direct tests for rule inputs, and one owner for re-evaluation), 22 (CR-02 C1: storm map hero screen), 24 (CR-02 C2: field supervisor view), 26 (CR-02 C3: ICS-215 and IAP draft view), 28 (CR-03 C1: golden set and evaluation gate), 31 (CR-03 C3: run trace panel), 34 (CR-03 C2: champion and challenger view)

**Status:** resolved

- [x] UI title, header and subtitle as above; disclaimer footer unchanged
- [x] README title and first paragraph as above
- [x] Python package `muster` (imports, Makefile, scripts, mypy and pytest config) and frontend app name `muster`
- [x] Scenario data moved to `data/scenarios/sgw_bayport/` if cheap; otherwise paths kept and the choice recorded in `docs/decisions.md`
- [x] Playbook and SGW names inside the scenario not renamed
- [x] `docs/change_requests/CR-01_delivered/` deleted (the live files now equal it)
- [x] Screenshot of the storm map at advisory 3 saved to `docs/img/storm_map_adv3.png` (CR-02 C1), taken after the rename so it shows the final name
- [x] `make dev` starts both apps; `./scripts/check.sh` passes

## Comments

- 2026-10-30: Merged into `main` as b957c91 after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 8/8 ticked.
