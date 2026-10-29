# 01: Seeded session test fixture

**What to build:** A developer can test any backend module in process against a real database without the FastAPI app: a fixture gives a session on a fresh engine with the gold data loaded, the playbook and the scoring config, and a helper issues advisories up to a given number using the same replay code the app uses. This is the one new test seam the refactor uses. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** None (can start immediately). Start from a clean tree: hold back the uncommitted CR-01 playbook, rules and plan files, which make `./scripts/check.sh` fail until CR-01 is implemented.

**Status:** done

- [x] Fixture yields a seeded session, the playbook and the scoring config; no `TestClient`, no `.env` read (CODING_STANDARDS T2)
- [x] Helper issues advisories 1..N through the app's own replay code
- [x] One test proves parity: the findings at advisory 2 from the fixture match what the HTTP route returns for advisory 2
- [x] Existing HTTP fixtures and the end-to-end demo test unchanged
- [x] `./scripts/check.sh` passes
