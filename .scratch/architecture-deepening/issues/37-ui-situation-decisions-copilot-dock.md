# 37: UI: Situation and Decisions pages, and a copilot dock on every page

**What to build:** The Storm map and Operations pages differ only in zoom: both show the ranked risk list, and the copilot hides behind a third side-panel tab. Give each page one job. **Storm map** stays the situation page (storm, cone, assets, risk list, what changed). **Operations** becomes **Decisions**: its side panel opens on the decision package (no risk list tab); selecting a package item highlights its asset on the map, and selecting an asset on the map scrolls to and highlights its items. The **copilot** becomes a dock reachable from every page (a header button opens a side drawer that stays open across page changes), always asking about the current advisory; its answers, chips and citations behave as today. Keep the hash routes stable or redirect the old `#/operations` to the new route. Update `docs/demo_script.md` (page names, where the copilot is) and the README's screen list, and retake `docs/screenshots/operations.jpg` and `docs/screenshots/decision-package.jpg`. Laptop layout only (no mobile work). Record open choices in `docs/decisions.md`.

**Blocked by:** 36 (CR-02: districts on the storm map and the operations map)

**Status:** ready-for-agent

- [ ] The Decisions page (formerly Operations) opens on the decision package; the risk list is no longer duplicated there; `#/operations` still lands on it
- [ ] Selecting a package item highlights its asset on the map, and selecting an asset highlights its package items (tests)
- [ ] The copilot opens from a header button on every page, stays open across page changes, and asks about the current advisory (tests)
- [ ] Every existing behaviour of the package, the copilot and the explanation drawer is kept (existing tests pass, updated only for the new placement)
- [ ] Demo script, README and the two screenshots updated
- [ ] `./scripts/check.sh` passes
