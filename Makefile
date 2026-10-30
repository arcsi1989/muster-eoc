# One-command entry points (docs/decisions.md: make replaces docker compose).
FRONTEND_PORT ?= 5173
BACKEND_PORT ?= 8000

.PHONY: install data history train dev test demo-reset

install: ## Install backend and frontend dependencies from the lockfiles
	cd backend && uv sync --locked
	cd frontend && pnpm install --frozen-lockfile

data: ## Regenerate the gold data and the synthetic storm history (deterministic)
	cd backend && uv run python -m app.datagen.generate
	$(MAKE) history

history: ## Regenerate the synthetic storm history the challenger trains on (seed 42)
	cd backend && uv run python -m app.datagen.history

train: ## Train the challenger, compare it with the rule-based champion on Storm Delta, save it for shadow scoring
	cd backend && uv run python -m app.challenger.train

dev: ## Backend and frontend together; Ctrl-C stops both
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --reload-dir app --port $(BACKEND_PORT)) & \
	(cd frontend && pnpm dev --port $(FRONTEND_PORT) --strictPort) & \
	wait

test: ## Every check: ruff, mypy, pytest, oxlint, tsc, vitest
	./scripts/check.sh

demo-reset: ## Back to before advisory 1 (backend must be running)
	@curl -fsS -X POST localhost:$(BACKEND_PORT)/advisories/reset > /dev/null && echo "Reset to before advisory 1."
