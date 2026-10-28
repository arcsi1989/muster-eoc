# 01: Walking skeleton: replay a toy storm on screen

**What to build:** An EOC operator opens the operations screen, sees a small fictional territory on a km-grid map, and steps through five advisories: the header shows advisory number, hours to landfall and activation level, assets recolour and the ranked list reorders with each advisory, and reset returns to before advisory 1. The scores are a placeholder; the point is the full path from stored data through the API to the screen. Spec: `.scratch/storm-prep-prototype/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A small hand-made territory (synthetic coastline, about 10 assets, 5 advisories with a simple track, hours to landfall 72, 60, 48, 36, 24) loads into SQLite at startup; coordinates are planar km (`x_km`, `y_km`)
- [ ] One settings class reads configuration from the environment; nothing reads the environment elsewhere
- [ ] `POST /advisories/next` advances 1 → 5 and refuses to go past 5 with the standard error body; `POST /advisories/reset` returns to before advisory 1; `GET /advisories`, `/assets`, `/coastline`, `/risk?advisory=` exist with response models
- [ ] Activation level is derived from hours to landfall with `(to, from]` bounds: advisory 1 → Prepare, advisory 3 → Full
- [ ] The operations screen: header (stepper, hours to landfall, activation level), map on the left (Leaflet simple CRS, no tiles) with assets coloured by score, ranked list on the right, disclaimer footer; stepping 1 → 5 updates map and list without a page reload
- [ ] All frontend backend calls go through one API client module; the list and map get data through a data hook
- [ ] Makefile targets: `make dev` (backend :8000, frontend :5173), `make test` (runs `./scripts/check.sh`), `make data` (writes the toy data), `make demo-reset`
- [ ] API tests for next, reset, past-5 refusal and activation level; frontend tests for the API client and the list's loading, error and empty states
- [ ] `./scripts/check.sh` passes
