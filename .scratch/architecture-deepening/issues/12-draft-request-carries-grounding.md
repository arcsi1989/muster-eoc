# 12: The draft request carries its own grounding

**What to build:** Whatever the model is shown in the draft request is exactly what it may cite. The draft request exposes its citable clause and entity IDs derived from its own contents (findings, retrieved clauses, top risks, what changed including rank moves), and one validator checks a draft against the request it answered. The rank-move fix becomes a consequence of the design, not a special case. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 03 (One set of citation ID patterns), 09 (CR-01 C6: calibration back-test and approved model versions (backend))

**Status:** resolved

- [x] Separate grounding assembly removed; citable IDs come from the request itself
- [x] One validator: (draft, draft request) → problems, empty when grounded
- [x] "What changed" enters the request as the typed changes model, not an untyped dict
- [x] Tests with hand-built requests: everything shown is citable; something not shown is rejected
- [x] The HTTP test that replays to advisory 3 twice for one grounding rule is replaced by the hand-built test, not kept alongside
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-29: Merged into `main` as a8ec291 after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 6/6 ticked.
