# 37: The copilot shows its work: a dock on every page, live progress, "how I got this"

**What to build:** The copilot is the main AI feature, but it hides behind the third tab of the operations side panel and shows only a final answer. Make it visible and auditable. (1) **Dock**: a header button on every page opens the copilot in a side drawer that stays open across page changes and always asks about the current advisory; the operations side panel loses its copilot tab. (2) **Live progress**: while a turn runs, the UI shows each step as it happens (tool called, with its arguments; validating; retrying; falling back to the template), streamed from the backend (server-sent events or a streamed response; record the choice). The answer text appears only once it has passed validation, so nothing unvalidated is ever shown as an answer. (3) **"How I got this"**: under each answer, a collapsible panel with the tools called, their arguments and results as the model saw them (restricted fields already filtered, CR-03 C1), the validator's result, retries, provider, model, prompt version, tokens and estimated cost, and whether the template answered. The audit event and the run trace keep recording the same turn. Update `docs/demo_script.md` (where the copilot is, and showing the panel in the copilot scene) and retake `docs/screenshots/operations.jpg`. Laptop layout only. Record open choices in `docs/decisions.md`.

**Blocked by:** 39 (the copilot validates numbers at runtime)

**Status:** ready-for-agent

- [ ] The copilot opens from a header button on every page, stays open across page changes, and asks about the current advisory; no copilot tab remains in the operations panel (tests)
- [ ] Progress events (tool call, validation, retry, fallback) reach the UI while the turn runs; the answer text is shown only after validation (backend and frontend tests)
- [ ] Each answer has a "How I got this" panel with tools, arguments, results as shown to the model, validation result, retries, provider, model, prompt version, tokens and cost; no restricted field appears in it (tests)
- [ ] Template mode works the same offline; the audit event and run trace are unchanged in content
- [ ] Demo script and screenshot updated
- [ ] `./scripts/check.sh` passes
