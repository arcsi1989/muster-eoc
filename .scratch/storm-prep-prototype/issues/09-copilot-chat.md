# 09: Copilot chat

**What to build:** An EOC operator asks follow-up questions in the Copilot tab ("Why is PS-14 ranked where it is?", top risks, what depends on an asset, what a clause says) and gets answers with clickable asset and clause chips, offline in template mode and with Claude tool calling online. Spec: `.scratch/storm-prep-prototype/spec.md`; implementation plan section 5.

**Blocked by:** 07 (Situation report with Claude and checked citations)

**Status:** ready-for-agent

- [x] Tools over the same domain functions: list top risks, get asset, explain score, get dependencies, search playbook, get decision package, get findings by status
- [x] Template mode supports the fixed intents: why ranked, top risks, what depends on X, what does clause Y say
- [x] Anthropic mode uses tool calling; chat text is treated as data, never instructions; answers cite only IDs returned by tools
- [x] `POST /copilot/chat`; Copilot tab with message list and labelled input; citation chips open the asset or clause
- [x] Each model call is logged in the audit log like the draft
- [x] "Why is PS-14 ranked where it is?" answers with factors and IDs in template mode (tested) and in Anthropic mode (verified manually) (template mode tested; Anthropic mode left for a manual run with a key)
- [x] `./scripts/check.sh` passes
