# 18: Typed package payloads

**What to build:** "What changed" and the situation report draft (with its metadata: provider, prompt version, fallback flag) are each one typed model, used for storage and as the API response model. The mirror API classes are deleted and the package routes no longer need `type: ignore`. "Decides as commander" is derived from the commander role definition. On the frontend, a test checks a fixture taken from a real backend response against the TypeScript types. No type generation unless the ticket states why the new dev dependency is worth it. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 12 (The draft request carries its own grounding), 15 (Graph nodes delegate to the lifecycle)

**Status:** ready-for-agent

- [ ] Changes and draft stored and read through typed models; no raw dict walking
- [ ] Mirror API classes for changes and the draft removed; no `type: ignore` in the package routes
- [ ] "Decides as commander" derived from the commander roles
- [ ] Tests: stored draft and changes read back equal to what was written; package response validates
- [ ] Frontend test checks a real response fixture against the types; any codegen dependency justified in `docs/decisions.md`
- [ ] UI unchanged; `./scripts/check.sh` passes
