# CLAUDE.md

@AGENTS.md

- Coding rules: `CODING_STANDARDS.md`. Definition of done: `./scripts/check.sh` passes.

Prototype for a take-home case: an EOC storm-preparation tool for a fictional utility (SGW).
Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM document.

## Start here
1. Read `docs/IMPLEMENTATION_PLAN.md` fully. Build milestones M0 to M9 in order; do not start a milestone before the previous one's "Done when" passes.
2. `docs/playbook.md` and `data/playbook/playbook_rules.yaml` are inputs. Do not edit clause text or thresholds.
3. Record any choice the plan leaves open in `docs/decisions.md`.

## Commands
- `make data`: regenerate `data/gold/` (seed 42, reproducible)
- `make dev`: backend on :8000, frontend on :5173
- `make test`: ruff, mypy, pytest, vitest
- `make demo-reset`: reset to before advisory 1
- `docker compose up`: cut for the time box (see `docs/decisions.md`); `make dev` is the one-command run

## Hard rules
- The LLM never decides whether a playbook rule is met, never changes scores, never writes operational state. Humans approve; the decision log records it.
- Every LLM feature has a deterministic template fallback; the demo must run with `LLM_PROVIDER=template` and no network.
- No optimisation or routing code (out of scope, lighthouse 2).
- No real places, utilities, facilities or people. Keep the disclaimer in the UI footer and in docs.
- All tunable numbers live in `config/*.yaml`, not in code.
- Small commits; `make test` green before each one.

## Agent skills

### Issue tracker

Local markdown: issues and specs live as files under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
