# 22: CR-02 C1: storm map hero screen

**What to build:** The storm map is the default screen. An EOC lead sees the hurricane as on an NHC graphic: a dashed forecast track with dots coloured by intensity category and a local-time label ("07:00 Thu") on every 12-hour point (every other label when they collide), a solid line through past positions, the cone, and a legend ("Hurricane: Cat 1 to Cat 5, tropical storm"). The fixed note under the map reads "Cone shows forecast track uncertainty, not the area that will be impacted." SGW's assets sit on top: colour by risk band, size by consequence, a ring for low data confidence; facilities (hospitals, shelters, the treatment plant) and staging areas have distinct icons. Hover shows name, type, rank, p_fail and top factor; click opens the existing explain panel. The header shows the advisory number, issue time, hours to landfall and declared activation level. Stepping redraws track, cone and asset colours with a 300 ms transition and reorders the ranked list in place; the eastward shift between advisories 2 and 4 is visible. Synthetic coastline only, no tile layer, no real places. Change request: `docs/change_requests/CR-02_map_field_ics.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 21 (CR-02 C1: storm map data)

**Status:** resolved

- [x] Storm map is the default route; existing routes still reachable
- [x] Track, intensity dots, 12-hour local-time labels with collision thinning, past positions, cone, legend and the fixed cone note
- [x] Assets by risk band, consequence and confidence; distinct facility and staging icons; hover details; click opens the explain panel
- [x] Header with advisory number, issue time, hours to landfall, declared activation level
- [x] Stepping 1 to 5 without a reload, 300 ms transition, ranked list reorders in place
- [x] Loading, error (with retry) and empty states (F3); `fetch` only through the API client (F1)
- [x] Frontend tests: legend and labels render, category colours, stepping updates the header and the list
- [x] `./scripts/check.sh` passes

## Comments

- 2026-10-30: Merged into `main` as 5613c39 after `./scripts/check.sh` passed on the combined code. Acceptance criteria: 8/8 ticked.
