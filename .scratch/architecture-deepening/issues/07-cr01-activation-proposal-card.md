# 07: CR-01 C3: activation proposal card in the decision package

**What to build:** When the package carries a P-2.5 proposal, it shows at the top as an activation proposal with a prominent "Declare Level N" button for the role allowed to declare it. After the declaration the card shows who declared, when, and the reason. The engine never changes the level itself; the button calls `POST /activation/declare`. The scenario header shows the declared level. Change request: `docs/change_requests/CR-01_operational_realism.md`; target files: `docs/change_requests/CR-01_delivered/`. Record anything ambiguous in `docs/decisions.md`.

**Blocked by:** 06 (CR-01 C3: activation is declared, not computed (backend))

**Status:** ready-for-agent

- [ ] Proposal card at the top of the decision package with the proposed level, the reason it is proposed (hours to landfall), and "Declare Level N"
- [ ] Only the role allowed to declare sees the button enabled; the others see who must declare
- [ ] After declaring: who, when and reason shown; the card no longer offers the button; the header shows the declared level
- [ ] Loading, error (with retry) and empty states (CODING_STANDARDS F3); `fetch` only through the API client (F1)
- [ ] Frontend tests for the card states and the declare call
- [ ] `./scripts/check.sh` passes
