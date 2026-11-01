# 40: Model comparison in the evaluation report

**What to build:** An AI engineer has to answer "which model is good enough, at what cost?". Extend the evaluation so one command runs the golden set against several models of the configured provider and writes a comparison: per model, pass rate per category and the gate result, median and P90 latency per answer, input and output tokens, and estimated cost per answer and per run (prices from `config/llm.yaml`). The models to compare live in `config/evals.yaml` (default: the Claude Haiku, Sonnet and Opus entries `config/llm.yaml` already prices). A run records tokens and latency per answer in `results.json` (they are not recorded today). Add `make eval-compare` and a "Model comparison" section in `docs/eval/report.md` (or a sibling `docs/eval/comparison.md`, linked from the report and the README). **Do not call a live provider in this ticket**: build and test it with fake providers that report tokens and latency; a person runs the live comparison afterwards (it costs API money). Record open choices in `docs/decisions.md`.

**Blocked by:** 39 (the copilot validates numbers at runtime)

**Status:** resolved

- [x] `results.json` records tokens in and out, latency and estimated cost per answer and per run
- [x] `make eval-compare` runs the golden set per configured model and writes the comparison table (category pass rates, gate, latency P50/P90, tokens, cost); models listed in `config/evals.yaml`
- [x] Tests with fake providers of different quality, speed and token use show the table ranks and sums them correctly; no network in tests
- [x] README documents `make eval-compare` and its cost
- [x] `./scripts/check.sh` passes

## Comments

- 2026-11-01: Merged into `main` as 13d8d95 after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 5/5 ticked.
