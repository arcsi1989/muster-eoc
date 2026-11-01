# 23: CR-02 C2: field tasks (data and backend)

**What to build:** A field supervisor works the **field tasks** of one district: the approved package items that need field work (inspection, barrier, generator staging, relocation), as the playbook module reports them (ticket 19). Marking a field task "Done" sets the state key the playbook names and writes an audit event with actor `field_supervisor`; "Blocked" records a note that shows as a gap in the next decision package. Both go through the decision package lifecycle's single state-writing path. A task whose site is under P-4.7 stop-work (tropical-storm wind within 12 hours) cannot be marked done. Supervisors cannot change priorities, approve items or see other districts' detail. Assets gain a fictional district, generated reproducibly (seed 42); "Bayport East" exists and holds PS-14. Add **Field task** and **Field supervisor** to `GLOSSARY.md` (a field task is an approved action that needs field work; "action" stays the term everywhere else). Change request: `docs/change_requests/CR-02_map_field_ics.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 15 (Graph nodes delegate to the lifecycle), 19 (The playbook answers "what satisfies this finding")

**Status:** resolved

- [x] District on every asset (generator, contract, loader); seed check covers "Bayport East" holding PS-14
- [x] Endpoints: list a district's field tasks (what, where, why, clause, approved by and when, stop-work flag); mark done; mark blocked with a note
- [x] Done and Blocked are lifecycle operations through the single state-writing path, with audit events by `field_supervisor`; the field-work mapping and stop-work come from the playbook module, not re-derived
- [x] Done refused under P-4.7 stop-work; a Blocked note appears as a gap in the next package
- [x] Tests: marking the PS-14 inspection done at advisory 3 removes the P-4.2 finding and prevents the advisory-5 conflict; Blocked shows in the next package; Done refused under stop-work; unapproved items never listed
- [x] A Blocked note is human free text: it reaches any LLM input only as delimited, quoted data, never as instructions (CR-03 tests it as a prompt-injection case)
- [x] `GLOSSARY.md`: Field task, Field supervisor
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-30: Merged into `main` as d07f8b4 after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 8/8 ticked.
