# 10: CR-01 C6: calibration view

**What to build:** A "Calibration" view, reachable from the main navigation, lets a person run the back-test and see whether the fitted model is better: the two reliability curves (before and after) on one chart, and the Brier score and top-decile capture as before-and-after numbers. The person approves the proposed model version from the view; the audit timeline then shows who approved it, and the next advisory uses it. Change request: `docs/change_requests/CR-01_operational_realism.md`; target files: `docs/change_requests/CR-01_delivered/`. Record anything ambiguous in `docs/decisions.md`.

**Blocked by:** 09 (CR-01 C6: calibration back-test and approved model versions (backend))

**Status:** resolved

- [x] Calibration route in the main navigation
- [x] One chart with both reliability curves and the diagonal; Brier score and top-decile capture before and after
- [x] Approve button for the proposed version; approved state shown afterwards
- [x] Loading, error (with retry) and empty states (F3); `fetch` only through the API client (F1)
- [x] Frontend tests for the view states and the approve call
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-29: Merged into `main` as 00699b9 after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 6/6 ticked.
