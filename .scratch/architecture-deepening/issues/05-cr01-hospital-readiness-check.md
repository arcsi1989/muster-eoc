# 05: CR-01 C2: hospital readiness check (P-6.2)

**What to build:** The Regulatory Liaison closes the Bayport General finding only by confirming two things: the hospital was contacted, and its on-site backup power has been tested and has 96 hours of fuel. P-6.2 is satisfied only when both `state.critical_customer_contacted` and the new `state.hospital_backup_confirmed` are true. The SUB-07 → HOSP-01 seed stays, but its finding at advisory 3 is P-6.2, not P-4.5. Change request: `docs/change_requests/CR-01_operational_realism.md`; target files: `docs/change_requests/CR-01_delivered/`. Record anything ambiguous in `docs/decisions.md`.

**Blocked by:** 04 (CR-01 C1: portable generators go to pumping stations)

**Status:** ready-for-agent

- [ ] `playbook_rules.yaml` P-6.2 hunk and `docs/playbook.md` P-6.2 text match the delivered copies
- [ ] `hospital_backup_confirmed` in `initial_state.json` (false) and among the operational state keys an approval can set
- [ ] Approving the P-6.2 action records both confirmations, and the finding is satisfied after approval
- [ ] Generator: SUB-07 rank ≤ 25 at advisory 3 and Bayport General not yet contacted; seed check covers it
- [ ] Tests: P-6.2 stays open with only one of the two keys true; P-6.2 open for SUB-07 at advisory 3 (cites HOSP-01); demo test row updated to plan section 8 (v3.3)
- [ ] `./scripts/check.sh` passes
