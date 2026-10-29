#!/usr/bin/env bash
# The repo's definition of done: every check a change must pass.
# Same command for people, agents and CI:   ./scripts/check.sh
#
# No layout is assumed. The script finds Python projects (pyproject.toml) and JS/TS projects
# (package.json) up to two levels deep and runs only what each one has configured:
#   Python: ruff format + ruff check (if [tool.ruff] or ruff.toml), pytest (if a tests/ dir)
#   JS/TS:  prettier --check (if prettier is installed and configured), and the package.json
#           scripts typecheck, lint, test (whichever exist)
# Tools run through each project's own lockfile (uv run / pnpm run), so versions match everywhere.
# First it installs from the lockfiles (uv sync --locked, pnpm install --frozen-lockfile), so the
# checks always run against the dependencies the lockfiles name, and a run after a merge installs
# what the merge added. A lockfile out of step with pyproject.toml / package.json fails here.
# Skip the installs (offline): CHECK_NO_INSTALL=1 ./scripts/check.sh
#
# To pin the folders instead of discovering them, set them here or in the environment:
#   PY_DIRS="backend" JS_DIRS="frontend" ./scripts/check.sh
# Checks it can't discover (another language, a framework's own checker) go in extra_checks below.
#
# A run where nothing was checked FAILS: a gate that checks nothing must not look green.
set -uo pipefail
cd "$(dirname "$0")/.."

find_projects() {  # find_projects <marker file>
  find . -maxdepth 3 -name "$1" \
    -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/dist/*' -not -path '*/.git/*' \
    -exec dirname {} \; | sed 's|^\./||; s|^\.$|.|' | sort
}

PY_DIRS="${PY_DIRS-$(find_projects pyproject.toml)}"   # set but empty = none
JS_DIRS="${JS_DIRS-$(find_projects package.json)}"
echo "check.sh: python projects: ${PY_DIRS:-none} | js projects: ${JS_DIRS:-none}" | tr '\n' ' '; echo

failed=0
ran=0
step() {  # step <dir> <label> <command...>
  local dir="$1" label="$2"; shift 2
  ran=$((ran + 1))
  echo "==> [$dir] $label"
  if ! (cd "$dir" && "$@"); then
    echo "FAILED: [$dir] $label"
    failed=1
  fi
}

# Installs aren't checks: they don't count towards "something was checked".
install() {  # install <dir> <label> <command...>
  local dir="$1" label="$2"; shift 2
  [ -z "${CHECK_NO_INSTALL:-}" ] || return 0
  echo "==> [$dir] install ($label)"
  if ! (cd "$dir" && "$@" </dev/null); then
    echo "FAILED: [$dir] install ($label)"
    failed=1
  fi
}
for d in $PY_DIRS; do
  [ -f "$d/uv.lock" ] && install "$d" "uv sync" uv sync --locked -q
done
for d in $JS_DIRS; do
  [ -f "$d/pnpm-lock.yaml" ] && install "$d" "pnpm" pnpm install --frozen-lockfile --config.strict-dep-builds=false --reporter=silent
done

for d in $PY_DIRS; do
  if grep -q '^\[tool\.ruff' "$d/pyproject.toml" 2>/dev/null || [ -f "$d/ruff.toml" ] || [ -f "$d/.ruff.toml" ]; then
    step "$d" "format" uv run ruff format --check .
    step "$d" "lint"   uv run ruff check .
  fi
  if [ -d "$d/tests" ]; then
    # pytest-xdist, where the project has it (each test has its own tmp_path). Capped at
    # CHECK_WORKERS (default 4) so parallel agents' runs don't oversubscribe the CPU;
    # CHECK_WORKERS=auto gives one worker per CPU. vite.config.ts caps vitest the same way.
    if grep -q 'pytest-xdist' "$d/pyproject.toml" 2>/dev/null; then
      step "$d" "test" uv run pytest -q -x -n "${CHECK_WORKERS:-4}"
    else
      step "$d" "test" uv run pytest -q -x
    fi
  fi
done

# Prettier: checked only where the project has it installed AND configured, so a repo that doesn't
# use prettier never fails on it. (The personal format-on-edit hook formats files as they're edited;
# this catches files changed any other way.) Prettier skips what .gitignore / .prettierignore list;
# lockfiles are skipped too, since the package manager writes them.
prettier_configured() {  # prettier_configured <dir>
  [ -x "$1/node_modules/.bin/prettier" ] || return 1
  for f in "$1"/.prettierrc* "$1"/prettier.config.*; do [ -e "$f" ] && return 0; done
  (cd "$1" && node -e "process.exit(require('./package.json').prettier ? 0 : 1)") 2>/dev/null
}

for d in $JS_DIRS; do
  before=$ran
  if prettier_configured "$d"; then
    step "$d" "format" pnpm exec prettier --check . '!**/pnpm-lock.yaml' '!**/package-lock.json' --log-level warn
  fi
  for s in typecheck lint test; do
    if (cd "$d" && node -e "process.exit(require('./package.json').scripts?.['$s'] ? 0 : 1)") 2>/dev/null; then
      step "$d" "$s" pnpm run --silent "$s"
    fi
  done
  [ "$ran" -gt "$before" ] || echo "check.sh: WARNING [$d] has no typecheck, lint or test script: not checked"
done

# Checks this script can't discover. One line each:  step <dir> <label> <command...>
# For example:   step frontend "svelte-check" pnpm exec svelte-check
#                step services/api "go test" go test ./...
extra_checks() {
  step backend "types" uv run mypy
}
extra_checks

if [ "$ran" -eq 0 ]; then
  echo "check.sh: FAILED nothing was checked. Add ruff/pytest config, typecheck/lint/test scripts,"
  echo "          or lines in extra_checks (scripts/check.sh). /project-setup sets this up."
  exit 1
fi
if [ "$failed" -ne 0 ]; then
  echo "check.sh: FAILED"
  exit 1
fi
echo "check.sh: all $ran checks passed"
