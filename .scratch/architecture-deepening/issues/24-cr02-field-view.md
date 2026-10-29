# 24: CR-02 C2: field supervisor view

**What to build:** A `/field` page, built for the demo on a laptop screen (no mobile-specific layout): a district selector and the selected district's field tasks, each showing what, where (asset name and ID), why (one line), the playbook clause, and who approved it and when, with "Done" and "Blocked" (optional note) buttons. A task under P-4.7 shows "Stop work: P-4.7" and its "Done" is disabled. Read-only apart from task status. Change request: `docs/change_requests/CR-02_map_field_ics.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 23 (CR-02 C2: field tasks (data and backend))

**Status:** ready-for-agent

- [ ] `/field` route in the navigation with a district selector
- [ ] Field task cards with what, where, why, clause, approved by and when
- [ ] Done and Blocked (with optional note) call the backend; the list refreshes
- [ ] "Stop work: P-4.7" shown and Done disabled under stop-work
- [ ] Loading, error (with retry) and empty states (F3); `fetch` only through the API client (F1)
- [ ] Frontend tests for the card states and both calls
- [ ] `./scripts/check.sh` passes
