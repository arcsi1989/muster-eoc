# 21: CR-02 C1: storm map data (track, NHC cone, intensity)

**What to build:** The backend gives the storm map everything it draws for an advisory, computed live: the forecast track points with time and intensity category, the past positions from earlier advisories, and the uncertainty cone built the way NHC draws it (a circle of radius `cone_radius_km` at each forecast point's lead time, consecutive circle pairs joined by their convex hull, all unioned). The cone uses exactly the same radius per lead time as the 50-member ensemble. Intensity categories come from 1-minute sustained wind with Saffir-Simpson thresholds in `config/scoring.yaml` (tropical storm 39–73 mph, Cat 1 74–95, Cat 2 96–110, Cat 3 111–129, Cat 4 130–156, Cat 5 157+). The cone geometry uses `shapely` (new dependency, asked for by CR-02; recorded in `docs/decisions.md`), replacing the hand-built cone outline. Change request: `docs/change_requests/CR-02_map_field_ics.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Advisory response (or a new endpoint) carries forecast points with time, wind and category, past positions from earlier advisories, and the NHC-style cone polygon
- [ ] Saffir-Simpson thresholds in `config/scoring.yaml`, none in code; tests at each boundary
- [ ] Cone built with `shapely` from circles per forecast point, hulls of consecutive pairs, unioned; the old hand-built outline removed
- [ ] Unit test: the cone and the ensemble read the cone radius per lead time from the same source, and the cone widens with lead time at every advisory
- [ ] Issuing an advisory (exposure, scores, playbook check) stays under 2 seconds; a test or a recorded measurement says so
- [ ] `./scripts/check.sh` passes
