# 07: Situation report with Claude and checked citations

**What to build:** Each decision package gets a draft situation report written by Claude (or the template), marked DRAFT, with every clause and asset citation checked and shown as clickable chips. The Incident Commander edits and approves it, which satisfies P-7.1. A bad citation or a failed call never reaches the screen; the template draft does. Spec: `.scratch/storm-prep-prototype/spec.md`; decision log for provider, model, fallback and key handling.

**Blocked by:** 06 (Advisory cycle and decisions by role)

**Status:** ready-for-agent

- [x] LLM provider interface with Anthropic, template and an Azure OpenAI stub; `LLM_PROVIDER` and `LLM_MODEL` (default `claude-sonnet-5-5`) read through settings from the environment and a gitignored backend env file; an example env file lists the names
- [x] Anthropic without a usable key fails at startup naming `ANTHROPIC_API_KEY` and the template option
- [x] Retrieval: BM25 over clauses, one query per gap (rule title + asset type), filtered by activation level; feeds the draft as context
- [x] The draft is structured output (sections → paragraphs with text, clause IDs, asset IDs), temperature 0; findings and data in their own delimited message; prompts are versioned files and the version is recorded
- [x] The citation validator rejects unknown IDs, IDs not matching a finding or retrieved clause, and IDs in text missing from the lists; retry once, then the template draft; a failed call also falls back, recorded as `template (fallback)`
- [x] Each LLM call logs provider, model, latency and token usage in its audit event
- [x] `POST /sitrep/{advisory}/approve`: only the Incident Commander/Director; editable text; draft and approved text both stored; the audit event marks edits; approval satisfies P-7.1 for that advisory
- [x] UI: draft labelled AI- or template-generated and DRAFT; citation chips open the clause or asset; edit-and-approve flow
- [x] Tests (template mode only): a fake provider returning an invented clause ID is rejected and the template draft served; no provider path writes state; situation report approval satisfies P-7.1
- [x] `./scripts/check.sh` passes
