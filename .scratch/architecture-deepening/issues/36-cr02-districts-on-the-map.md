# 36: CR-02: districts on the storm map and the operations map

**What to build:** The Field tasks page offers four districts (Westshore, Bayport West, Bayport East, Eastern Plains), but no map shows them, so a viewer cannot see where a district is or that the forecast landfall walks from Bayport West (advisories 1 to 3) into Bayport East (advisories 4 and 5), where PS-14 and STG-02 sit. Draw the districts on both maps: a faint dashed boundary between neighbouring districts and each district's name, unobtrusive under the cone, track and assets, readable in the advisory-3 screenshot. Today the districts exist only as west edges in the data generator (`DISTRICTS`) and as a field on each asset; the boundaries must come from the data, not be repeated in the frontend: the generator writes them into the gold data pack (seed 42, the other gold files unchanged), the loader validates them, and the API serves them (with the storm map's static layers or with the field districts, whichever fits the existing contracts). The field view's district list comes from the same source. Synthetic territory only, no real places. Change request: `docs/change_requests/CR-02_map_field_ics.md` (C1 assets and context, C2 area selector). Record open choices in `docs/decisions.md`.

**Blocked by:** 22 (CR-02 C1: storm map screen), 24 (CR-02 C2: field view)

**Status:** ready-for-agent

- [ ] The gold data pack holds the district boundaries, written by the generator from one definition; `make data` reproduces it and every other gold file is unchanged
- [ ] The API serves the boundaries, and every asset's district matches the boundary its x lies in (test)
- [ ] The storm map and the operations map draw the boundaries (dashed) and labels beneath the cone, track and assets; test that four labels render from the served data
- [ ] The field view's districts come from the same source
- [ ] `docs/img/storm_map_adv3.png` retaken with the districts visible
- [ ] `./scripts/check.sh` passes
