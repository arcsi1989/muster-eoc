# 24: CR-02 C2: field supervisor view

**What to build:** A `/field` page, built for the demo on a laptop screen (no mobile-specific layout): a district selector and the selected district's field tasks, each showing what, where (asset name and ID), why (one line), the playbook clause, and who approved it and when, with "Done" and "Blocked" (optional note) buttons. A task under P-4.7 shows "Stop work: P-4.7" and its "Done" is disabled. Read-only apart from task status. Change request: `docs/change_requests/CR-02_map_field_ics.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 23 (CR-02 C2: field tasks (data and backend))

**Status:** resolved

- [x] `/field` route in the navigation with a district selector
- [x] Field task cards with what, where, why, clause, approved by and when
- [x] Done and Blocked (with optional note) call the backend; the list refreshes
- [x] "Stop work: P-4.7" shown and Done disabled under stop-work
- [x] Loading, error (with retry) and empty states (F3); `fetch` only through the API client (F1)
- [x] Frontend tests for the card states and both calls
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-30: Reviewed; auto-merge held back for an owner decision (see .ht/reply.md in the worktree).

- 2026-10-30: Merged into `main` as 1018cfd after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 7/7 ticked.
