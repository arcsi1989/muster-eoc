# 02: Advisory context module

**What to build:** One module answers the questions every part of the app asks about the advisory: which advisory is current (or none before advisory 1), its scenario time, its activation level, whether the EOC is at Full activation, who commands (Incident Commander or Director), and "require current" with the one existing "no longer current" error. All callers use it; replay stops resetting state it does not own. The EOC sees no change. This is the prefactor for CR-01 (playbook v3.3): it lands on v3.2 and keeps computing the level from hours to landfall, so that CR-01's C3 (activation is declared, not computed) becomes a change inside this one module. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 01 (Seeded session test fixture)

**Status:** resolved

- [x] Every activation-level lookup, Full-activation test and current-advisory check outside the module goes through it; no `"full"` string literal left in callers
- [x] Resetting per-advisory flags lives with the advisory context, not in replay
- [x] Scenario reset asks each owning module to reset its own tables; replay no longer deletes advisory cycle tables
- [x] The top-10 rank cut is read from one place (config, per the hard rule on tunable numbers)
- [x] Frontend reads the current advisory from the scenario state the backend returns, not the last issued advisory
- [x] Seeded-session tests: current advisory before/after advance, level at each boundary hour (boundary belongs to the later level), commander per level, "require current" refusal, flag reset
- [x] "Advisory context" added to `GLOSSARY.md` if the module takes that name, without restating the computed-level definition CR-01 replaces
- [x] For ticket 06 (CR-01 C3): the one place the declared level must replace the computed one is named in this ticket's Comments
- [x] End-to-end demo test green and not edited by this ticket; `./scripts/check.sh` passes

## Comments

- 2026-10-29: Reviewed; auto-merge held back for an owner decision (see .ht/reply.md in the worktree).
- 2026-10-29: **For ticket 06 (CR-01 C3, declared activation):** the one place to change is `advisory_context.at(session, levels, advisory)` in `backend/app/advisory_context.py`. Today it calls `playbook.activation.activation_level(hours_to_landfall, levels)`. Make it read the last declared level from operational state through `session`, which is already passed in for this. Compute `hours_since_full_activation` from the declaration time there too. Add the proposed level (from `propose_at_hours`) and the declaration time to `AdvisoryContext`. No caller computes a level or tests for Full itself, so `full_activation`, `commander` and every caller follow automatically. `playbook.activation.activation_level` then has no caller left except the proposed-level calculation.

- 2026-10-29: Merged into `main` as bd7fe78 after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 9/9 ticked.
