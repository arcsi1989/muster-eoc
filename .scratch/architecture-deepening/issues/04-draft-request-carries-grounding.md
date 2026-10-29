# 04: The draft request carries its own grounding

**What to build:** Whatever the model is shown in the draft request is exactly what it may cite. The draft request exposes its citable clause and entity IDs derived from its own contents (findings, retrieved clauses, top risks, what changed including rank moves), and one validator checks a draft against the request it answered. The rank-move fix becomes a consequence of the design, not a special case. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 03 (One set of citation ID patterns), CR-01 implemented (playbook v3.3)

**Status:** ready-for-agent

- [ ] Separate grounding assembly removed; citable IDs come from the request itself
- [ ] One validator: (draft, draft request) → problems, empty when grounded
- [ ] "What changed" enters the request as the typed changes model, not an untyped dict
- [ ] Tests with hand-built requests: everything shown is citable; something not shown is rejected
- [ ] The HTTP test that replays to advisory 3 twice for one grounding rule is replaced by the hand-built test, not kept alongside
- [ ] `./scripts/check.sh` passes
