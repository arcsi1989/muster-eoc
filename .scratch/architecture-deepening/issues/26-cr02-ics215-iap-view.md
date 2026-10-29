# 26: CR-02 C3: ICS-215 and IAP draft view

**What to build:** A page for the planning products of the current operational period: the ICS-215 worksheet as a table and the IAP objectives with their clause IDs, marked DRAFT until released, with the two release approvals (Planning Section Chief, then Incident Commander) and who approved when. It prints cleanly as HTML (print stylesheet). Change request: `docs/change_requests/CR-02_map_field_ics.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 25 (CR-02 C3: ICS-215 and IAP draft (backend))

**Status:** ready-for-agent

- [ ] Route in the navigation; ICS-215 table and IAP objectives with clause IDs; DRAFT marking
- [ ] Release approvals in order, by role, with who and when shown afterwards
- [ ] Printable: a print stylesheet hides navigation and controls
- [ ] Loading, error (with retry) and empty states (F3); `fetch` only through the API client (F1)
- [ ] Frontend tests for the draft, the approval order and the released state
- [ ] `./scripts/check.sh` passes
