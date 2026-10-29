# 03: One set of citation ID patterns

**What to build:** The situation report and the copilot recognise clause IDs and entity IDs with the same patterns, defined once. A draft that cites a hospital or shelter ID is no longer wrongly rejected, and both features apply the same case rule. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] One module defines the clause ID pattern and the entity ID pattern, covering every entity prefix the gold data uses (including hospitals and shelters), with one case rule
- [ ] Situation report citation checking and the copilot both use it; no second copy remains
- [ ] Tests: a hospital ID and a shelter ID are recognised by both; an unknown prefix is not
- [ ] `./scripts/check.sh` passes
