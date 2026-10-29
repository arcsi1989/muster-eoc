# 14: Situation report approval and activation declaration through the lifecycle

**What to build:** Approving the situation report goes through the same open/closed gate and the same "who commands" answer as item decisions. Approving it for a closed package is refused with the existing "package closed" error. Its operational state write (the per-advisory situation report flag) and the re-evaluation of the P-7.1 finding go through the single state-writing path, so "only the decision step changes operational state" becomes true. Declaring an activation level (playbook v3.3, P-2.5, added by CR-01) becomes a lifecycle operation too: the same role check (EOC Director for Level 3 and 2, Incident Commander for Level 1), the declared level and its time written through the same path, one decision and one audit record, and the P-2.5 proposal closed. It is the only code that sets the activation level. The demo flow keeps working: if the cycle currently closes the package before the report can be approved, change when it closes rather than break the demo. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 13 (Decision package lifecycle: one answer to "is it open")

**Status:** resolved

- [x] Situation report approval is a lifecycle operation behind the same gate as item decisions
- [x] Approval on a closed package refused with the "package closed" error
- [x] Flag write and P-7.1 re-evaluation go through the single state-writing path; the module docs state this and are true
- [x] Activation declaration is a lifecycle operation through the same path; it closes the P-2.5 proposal
- [x] Test: no code path sets the activation level except a declaration
- [x] Audit event types and summaries for situation report approval and declaration unchanged
- [x] Seeded-session tests: approve on open package; refuse on closed package; wrong role refused; finding P-7.1 satisfied after approval; declaration by the wrong role refused; declaring Full starts the P-7.2 clock
- [x] Choice of when the package closes recorded in `docs/decisions.md` if it changes
- [x] End-to-end demo test green and not edited by this ticket; `./scripts/check.sh` passes

## Comments

- 2026-10-29: Merged into `main` as 07884ac after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 9/9 ticked.
