# Agent instructions

- What to build: `docs/IMPLEMENTATION_PLAN.md`; project hard rules: `CLAUDE.md`.
- Rules for all code in this repo: [CODING_STANDARDS.md](CODING_STANDARDS.md). Cite rule IDs in reviews.
- A change is done when `./scripts/check.sh` passes. Run it before you finish; fix failures, never silence them. When the Makefile lands (M0), `make test` runs `./scripts/check.sh`.
- How to run the app: see the Commands table in CODING_STANDARDS.md.
- Never read or print `.env` files or API keys.
