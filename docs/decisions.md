# Decisions

Choices the implementation plan leaves open (date, decision, reason).

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-10-28 | Backend tests live in `backend/tests/`, not a root `tests/`. | Keeps pytest, ruff and mypy in the backend's own uv project; `scripts/check.sh` runs them there. |
| 2026-10-28 | Backend routes have no `/api` prefix (plan section 6); the Vite dev server proxies `/api/*` to the backend and strips the prefix. | The frontend calls same-origin `/api/...`, so no CORS setup is needed. |
| 2026-10-28 | `make test` will call `./scripts/check.sh` (ruff, mypy, pytest, oxlint, tsc, vitest). | One definition of done for people, agents and CI. |
