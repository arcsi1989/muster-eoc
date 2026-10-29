# 03: One set of citation ID patterns

**What to build:** The situation report and the copilot recognise clause IDs and entity IDs with patterns defined once, in the shared ID module. The situation report's citation check keeps its rule that critical facilities (HOSP-, SHEL-) are named in the text only and never listed (prompt sitrep-v2), but takes that "site" pattern (assets and staging areas) from the shared module instead of its own copy, and applies the same case rule as the copilot: a lowercase ID in the text is still a citation. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] One module defines the clause ID pattern, the site pattern (assets and staging areas) and the entity pattern (sites plus hospitals and shelters), with one case rule
- [x] Situation report citation checking and the copilot both use it; no second copy remains
- [x] Tests: a facility named in the text is not a problem, a facility listed in asset_ids is; a lowercase ID in the text must be listed; sites and facilities are told apart by the patterns
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-29: The original premise ("a draft that cites a hospital or shelter ID is wrongly rejected") was wrong: the situation report leaves HOSP-/SHEL- out of its text check on purpose, because prompt sitrep-v2 tells the model to name facilities in the text only. The real defects were the duplicated pattern and its case sensitivity (a lowercase `sub-07` in the text went unchecked). The check is now slightly stricter: a lowercase ID in the text must be listed.
