# 06: CR-01 C3: activation is declared, not computed (backend)

**What to build:** The activation level is the last level a person declared, never computed. The scenario starts at `monitor`. A new P-2.5 rule (kind `proposal`) raises an activation proposal when the level proposed from the `propose_at_hours` thresholds differs from the declared one; no data satisfies it, only a declaration. `POST /activation/declare {level, declared_by, reason?}` checks who may declare (EOC Director for Level 3 and 2, Incident Commander for Level 1), writes the declared level and its time to operational state, and records a decision row and an audit event. `hours_since_full_activation` counts from the Level 1 declaration, so P-7.2 is inactive until Full is declared. Rules gated by `active_from_hours` keep using hours to landfall. Who commands follows the declared level. After ticket 02 this is a change inside the advisory context module plus the new rule kind and endpoint. Change request: `docs/change_requests/CR-01_operational_realism.md`; target files: `docs/change_requests/CR-01_delivered/`. Record anything ambiguous in `docs/decisions.md`.

**Blocked by:** 02 (Advisory context module), 05 (CR-01 C2: hospital readiness check)

**Status:** ready-for-agent

- [ ] `playbook_rules.yaml`, `docs/playbook.md` and `docs/IMPLEMENTATION_PLAN.md` now equal the delivered copies
- [ ] Rule loader and engine accept `kind: proposal` and the `propose_at_hours` level shape; a proposal finding is never satisfied by data
- [ ] `event.activation_level` (declared), `event.proposed_activation_level` and `event.hours_since_full_activation` (from the declaration time) in the rule inputs; `activation_level: monitor` in `initial_state.json`
- [ ] `POST /activation/declare` with role check, operational state write, decision row and audit event; declaring closes the P-2.5 proposal
- [ ] The advisory context module reads the declared level; who commands follows it
- [ ] `GLOSSARY.md` "Activation level" entry updated (declared, proposed, declaration); "Declaration" added if used as a term
- [ ] Tests: P-2.5 is never closed without a declaration; P-7.2 inactive before Full is declared and overdue 12 hours after the declaration; no code path sets the activation level except the declare endpoint; wrong role refused
- [ ] Demo test updated to the plan section 8 (v3.3) path: declare `prepare` at advisory 1 and `full` at advisory 3, green on both PS-14 paths
- [ ] `./scripts/check.sh` passes
