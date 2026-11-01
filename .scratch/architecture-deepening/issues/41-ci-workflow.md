# 41: Continuous integration: the quality gate and the eval gate on every push

**What to build:** The definition of done (`./scripts/check.sh`: ruff, mypy strict, pytest, the template eval gate, oxlint, tsc, vitest) runs only on a developer's machine. Add a GitHub Actions workflow that runs it on every push and pull request with the locked toolchain (uv and pnpm from the lockfiles, the Python and Node versions the repo pins), caches dependencies, needs no secrets and no network beyond installing (template mode), and uploads `docs/eval/report.md` from the template run plus a test coverage report as artifacts. Add the workflow badge to the README. The repo has no remote yet: validate the workflow locally (for example with `actionlint`, installed for the check only, not as a project dependency) and say in the README that it runs once the repo is pushed. Record open choices in `docs/decisions.md`.

**Blocked by:** None (can start immediately)

**Status:** claimed

- [ ] `.github/workflows/` runs `./scripts/check.sh` on push and pull request with locked dependencies and caching; no secrets
- [ ] The template eval report and a coverage report are uploaded as artifacts
- [ ] The workflow passes a linter (for example `actionlint`); how it was validated is recorded
- [ ] README badge and a note on when it runs
- [ ] `./scripts/check.sh` passes
