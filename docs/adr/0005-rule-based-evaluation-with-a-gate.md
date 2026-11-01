# Rule-based evaluation with a gate, no LLM judge

> Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM document. SGW, Bayport County and all data are fictional.

Status: accepted, 2026-10-30 (CR-03 C1, ticket 28; live runs ticket 29, model comparison ticket 40).

## Context

The runtime validators ([ADR 0003](0003-grounded-generation.md)) stop a bad answer from being shown,
but they do not say how often a model or prompt gets it right, or whether a prompt change broke
something. CR-03 asks for an evaluation of grounding, refusal, data classification, prompt
injection and drafting, with a gate. A common approach is a second model that grades answers; its
grades vary between runs and cannot be audited.

## Decision

- A **golden set** of 30 cases (`backend/tests/evals/golden.yaml`): an advisory state, a question or
  drafting task, and machine-checkable expectations.
- Cases run the way the app runs them (`muster/evals/scenario.py`): a fresh database, advisories
  issued through the advisory cycle, setup steps through the decision package lifecycle, then the
  copilot or the draft through grounded generation. What is checked is what the user is served.
- **Checks are rules only** (`muster/evals/checks.py`): substrings, regexes, ID sets, the tool-call
  log (only read-only tools), a state snapshot before and after, no restricted field or value, and
  every number in the answer present in the turn's tool results (the same
  `numbers.ungrounded_numbers` the runtime copilot uses).
- **Gates** in `config/evals.yaml`: a minimum pass rate for grounding, refusal and drafting, and
  zero failures for classification and injection in any case of any category.
- `./scripts/check.sh` (and CI) runs the gate with the template provider on every change;
  `make eval-llm` runs it against the configured model, each case 3 times; `make eval-compare` runs
  it per model with latency, tokens and cost and reports without gating.
- A gate is fixed by fixing the checker where it misread a correct answer, or the prompt where the
  model fell short, never by lowering a threshold.

## Consequences

- The template run is deterministic and stamped with the git commit, so the committed
  `docs/eval/report.md` is reproducible; the latest result is recorded in the audit log at startup.
- The live runs found real faults (a refusal without "nobody can say", a derived number) and checker
  bugs (percentile names read as numbers), each fixed in the open (decisions of 2026-11-01).
- Rule checks cannot judge tone, completeness or usefulness; no readability score is reported.
  The golden set is small and the prompts were tuned on Sonnet, so the comparison favours it.

## Alternatives rejected

- **LLM-as-judge.** Non-deterministic, costs a call per check, and puts a model in the judging seat
  the hard rules keep for code and people.
- **Human-rated samples only.** Valuable but slow; it cannot gate every commit.
- **No gate, report only.** A report nobody reads does not stop a regression; CI runs the template
  gate on every push.

## Links

- `docs/decisions.md`: 2026-10-30 golden set and evaluation gate (ticket 28); 2026-11-01 live
  evaluation (ticket 29), runtime number check (ticket 39), model comparison and its live run
  (ticket 40).
- Code: `muster/evals/`, `numbers.py`, `config/evals.yaml`; reports `docs/eval/report.md`,
  `docs/eval/comparison.md`.
