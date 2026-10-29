# 22: CR-02 C1: storm map hero screen

**What to build:** The storm map is the default screen. An EOC lead sees the hurricane as on an NHC graphic: a dashed forecast track with dots coloured by intensity category and a local-time label ("07:00 Thu") on every 12-hour point (every other label when they collide), a solid line through past positions, the cone, and a legend ("Hurricane: Cat 1 to Cat 5, tropical storm"). The fixed note under the map reads "Cone shows forecast track uncertainty, not the area that will be impacted." SGW's assets sit on top: colour by risk band, size by consequence, a ring for low data confidence; facilities (hospitals, shelters, the treatment plant) and staging areas have distinct icons. Hover shows name, type, rank, p_fail and top factor; click opens the existing explain panel. The header shows the advisory number, issue time, hours to landfall and declared activation level. Stepping redraws track, cone and asset colours with a 300 ms transition and reorders the ranked list in place; the eastward shift between advisories 2 and 4 is visible. Synthetic coastline only, no tile layer, no real places. Change request: `docs/change_requests/CR-02_map_field_ics.md`. Record open choices in `docs/decisions.md`. Spec: `.scratch/architecture-deepening/spec.md`.

**Blocked by:** 21 (CR-02 C1: storm map data)

**Status:** ready-for-agent

- [ ] Storm map is the default route; existing routes still reachable
- [ ] Track, intensity dots, 12-hour local-time labels with collision thinning, past positions, cone, legend and the fixed cone note
- [ ] Assets by risk band, consequence and confidence; distinct facility and staging icons; hover details; click opens the explain panel
- [ ] Header with advisory number, issue time, hours to landfall, declared activation level
- [ ] Stepping 1 to 5 without a reload, 300 ms transition, ranked list reorders in place
- [ ] Loading, error (with retry) and empty states (F3); `fetch` only through the API client (F1)
- [ ] Frontend tests: legend and labels render, category colours, stepping updates the header and the list
- [ ] `./scripts/check.sh` passes
