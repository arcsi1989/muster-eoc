# 02: Synthetic territory, data contracts and data quality

**What to build:** The toy data is replaced by the full seeded synthetic territory. A data steward can open a Data quality page and see each loaded file with its hash and rows accepted and rejected, with rejection reasons. Regenerating the data gives identical files. Spec: `.scratch/storm-prep-prototype/spec.md`; data model in the implementation plan section 2, with planar km coordinates and the storm values from the decision log and the research note.

**Blocked by:** 01 (Walking skeleton)

**Status:** ready-for-agent

- [ ] `make data` (seed 42) writes every gold file the plan lists except the calibration history: about 200 assets (about 120 substations, 75 pumping stations, 1 treatment plant), dependencies, about 30 critical facilities, 5 staging areas, initial state, coastline, and 5 advisories with tracks to 24 h after landfall
- [ ] Advisories follow the decision log: max wind 130, 130, 135, 140, 145 mph; peak surge 2.5, 2.5, 3.0, 3.5, 4.0 m; radius of maximum wind 37 km; forecast landfall about 40 km further east at advisories 3 and 4; cone radii per lead time from the 2022 NHC table
- [ ] Demo seed assets are placed by construction: SUB-07 feeds HOSP-01 with no generator; PS-14 coastal; STG-02 the only coastal staging area; 6 fuelled generators; 3 null elevations; 5 inspections over 3 years old; 2 contract-breaking rows in a separate example file
- [ ] Two runs of `make data` give byte-identical files (test compares hashes)
- [ ] Pydantic contracts per gold file, exported as JSON Schemas; frontend types mirror them
- [ ] The loader validates every file, rejects bad rows into a quality report with reasons, and records lineage (file, hash, loaded at, rows accepted, rows rejected); the loader test rejects exactly the 2 bad example rows
- [ ] `GET /facilities`, `/staging-areas`, `/lineage`; facilities and staging areas shown on the map; a Data quality route
- [ ] No real place, utility or person names anywhere in the data
- [ ] `./scripts/check.sh` passes
