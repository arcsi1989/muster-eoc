# 25: CR-02 C3: ICS-215 and IAP draft (backend)

**What to build:** After a package is decided, the app drafts the operational planning worksheet (ICS-215) for the next operational period from approved items only: location, work assignment, resource kind, required, have, need, reporting location, requested arrival time; "have" from operational state and staging data, "need" = required minus have. It also drafts the IAP objectives and assignments: three to six incident objectives derived from the open findings, each citing its clause IDs. Generation is deterministic (template); the LLM may only rephrase objective wording, through the grounded generation module (ticket 16) with citations validated like the situation report. Both are marked DRAFT and stored as typed models (ticket 18). Release needs two approvals, Planning Section Chief then Incident Commander, as decision package lifecycle operations, both logged. Add **ICS-215**, **IAP** and **Release** to `GLOSSARY.md`. Change request: `docs/change_requests/CR-02_map_field_ics.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 17 (Copilot through grounded generation), 18 (Typed package payloads)

**Status:** ready-for-agent

- [ ] ICS-215 rows from approved items only, with have and need computed from operational state and staging data
- [ ] Three to six IAP objectives from open findings, each with clause IDs; rephrasing runs through the grounded generation module with template fallback
- [ ] Release: Planning Section Chief then Incident Commander, through the lifecycle, both audited; any other order or a single approval refused
- [ ] Endpoint for the draft (DRAFT until released) and for each approval
- [ ] Tests: after advisory 3 decisions, the ICS-215 lists the PS-09 generator and the flood barrier tasks with correct have and need; nothing unapproved appears; release without both approvals refused
- [ ] `GLOSSARY.md`: ICS-215, IAP, Release
- [ ] `./scripts/check.sh` passes
