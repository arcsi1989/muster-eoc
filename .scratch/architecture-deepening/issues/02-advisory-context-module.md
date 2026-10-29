# 02: Advisory context module

**What to build:** One module answers the questions every part of the app asks about the advisory: which advisory is current (or none before advisory 1), its scenario time, its activation level, whether the EOC is at Full activation, who commands (Incident Commander or Director), and "require current" with the one existing "no longer current" error. All callers use it; replay stops resetting state it does not own. The EOC sees no change. This is the prefactor for CR-01 (playbook v3.3): it lands on v3.2 and keeps computing the level from hours to landfall, so that CR-01's C3 (activation is declared, not computed) becomes a change inside this one module. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 01 (Seeded session test fixture)

**Status:** ready-for-agent

- [ ] Every activation-level lookup, Full-activation test and current-advisory check outside the module goes through it; no `"full"` string literal left in callers
- [ ] Resetting per-advisory flags lives with the advisory context, not in replay
- [ ] Scenario reset asks each owning module to reset its own tables; replay no longer deletes advisory cycle tables
- [ ] The top-10 rank cut is read from one place (config, per the hard rule on tunable numbers)
- [ ] Frontend reads the current advisory from the scenario state the backend returns, not the last issued advisory
- [ ] Seeded-session tests: current advisory before/after advance, level at each boundary hour (boundary belongs to the later level), commander per level, "require current" refusal, flag reset
- [ ] "Advisory context" added to `GLOSSARY.md` if the module takes that name, without restating the computed-level definition CR-01 replaces
- [ ] Comment for CR-01: the one place C3 must change is named in this ticket's Comments
- [ ] End-to-end demo test green and not edited by this ticket; `./scripts/check.sh` passes
