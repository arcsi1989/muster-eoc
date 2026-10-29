# 09: CR-01 C6: calibration back-test and approved model versions (backend)

**What to build:** Calibration is built as specified in plan section 7, M8 (v3.3). A prior about 20% off the hidden truth is back-tested on Storm Delta: a 10-bin reliability table, the Brier score and the top-decile capture, before and after a MAP fit. The fit produces a `proposed` model version that a human approves. After approval, the next advisory replay scores with the new version, and the audit log shows who approved it. An unapproved version is never used for scoring. All tunable numbers live in `config/*.yaml`. Change request: `docs/change_requests/CR-01_operational_realism.md`; target files: `docs/change_requests/CR-01_delivered/`. Record anything ambiguous in `docs/decisions.md`.

**Blocked by:** 08 (CR-01 C4 + C5: ensemble spread and scope notes)

**Status:** ready-for-agent

- [ ] `POST /calibration/run` returns the reliability bins, Brier score and top-decile capture before and after, and creates a `proposed` model version
- [ ] `POST /model-versions/{id}/approve` approves it, by role, with an audit event
- [ ] Replay scores with the latest approved model version; scores record their model version
- [ ] Storm Delta back-test data generated reproducibly (seed 42) and checked by the seed check
- [ ] Tests: Brier score after calibration is lower than before; scores differ between model versions; an unapproved version is never used for scoring
- [ ] `./scripts/check.sh` passes
