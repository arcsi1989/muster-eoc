# 26: CR-02 C3: ICS-215 and IAP draft view

**What to build:** A page for the planning products of the current operational period: the ICS-215 worksheet as a table and the IAP objectives with their clause IDs, marked DRAFT until released, with the two release approvals (Planning Section Chief, then Incident Commander) and who approved when. It prints cleanly as HTML (print stylesheet). Change request: `docs/change_requests/CR-02_map_field_ics.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 25 (CR-02 C3: ICS-215 and IAP draft (backend))

**Status:** resolved

- [x] Route in the navigation; ICS-215 table and IAP objectives with clause IDs; DRAFT marking
- [x] Release approvals in order, by role, with who and when shown afterwards
- [x] Printable: a print stylesheet hides navigation and controls
- [x] Loading, error (with retry) and empty states (F3); `fetch` only through the API client (F1)
- [x] Frontend tests for the draft, the approval order and the released state
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-30: Merged into `main` as 0bcd571 after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 6/6 ticked.
