# 09: Copilot through grounded generation

**What to build:** The copilot runs through the same grounded generation module as the situation report, with its own validator (tool-returned IDs). Both tasks record attempts in one format. Providers become transport only: the prompt version and prompt settings reach them in the same shape for both tasks, and the provider factory stops loading the agent's prompts (the tasks that own the prompts load them). The Azure OpenAI stub stays behind the same interface. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 08 (Grounded generation for the situation report)

**Status:** ready-for-agent

- [ ] Copilot chat uses the grounded generation module; its own fallback loop and provider type check removed
- [ ] Attempt log has one format for both tasks
- [ ] Providers take prompt version and settings the same way for both tasks; factory no longer reaches into agent prompts
- [ ] Anthropic provider unit tests still test it as transport only
- [ ] Copilot answers with the same cited tool results; template mode works offline
- [ ] `./scripts/check.sh` passes
