# CR-02: Storm map hero screen, field task view, ICS-215 draft

> Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM document. SGW, Bayport County and all data are fictional.

**For the coding agent.** Apply after CR-01. Read this file fully first, implement C1 to C3 in order, run `make test` after each, and record open choices in `docs/decisions.md`. C1 is a Must. C2 and C3 are Should: if time is short, finish C1 and C2 and stop.

## Why
The live demo needs one screen an EOC lead recognises instantly: the hurricane forecast track and uncertainty cone, with SGW's assets and their risk on top, changing with each advisory. The PRD also now gives field supervisors a task view (L1-9) and drafts ICS planning products (L1-10); one screen each makes the human-in-the-loop story visible beyond the commander.

## C1. Storm map hero screen (Must)

Make this the default screen of the app.

**Forecast track**
- Dashed line through the advisory's forecast points (`track` in `adv_NN.json`), plus a solid line through past positions from earlier advisories.
- Each forecast point is a dot coloured by intensity category, with a time label in local time ("07:00 Thu") for every 12-hour point. Label collisions: show every other label.
- Category from 1-minute sustained wind (mph), Saffir-Simpson: tropical storm 39 to 73; Cat 1 74 to 95; Cat 2 96 to 110; Cat 3 111 to 129; Cat 4 130 to 156; Cat 5 157 and above. Put the thresholds in `config/scoring.yaml`, not in code.
- Legend: "Hurricane: Cat 1 to Cat 5, tropical storm", like a standard NHC graphic.

**Uncertainty cone**
- Built the way NHC draws it: a circle around each forecast point with radius `cone_radius_km` at that lead time, joined into one shape (the convex hull of consecutive circle pairs, unioned). Use a geometry helper (shapely or turf.js), not a hand-drawn polygon.
- **Use exactly the same cone radius per lead time that drives the 50-member ensemble.** Add a unit test that reads both from the same source.
- Fixed note under the map: "Cone shows forecast track uncertainty, not the area that will be impacted."

**Assets and context**
- Assets on top of the cone: colour by risk band, size by consequence, ring for low data confidence. Facilities (hospitals, shelters, the treatment plant) and staging areas use distinct icons.
- Hover: name, type, rank, p_fail, top factor. Click: the existing explain panel.
- Synthetic coastline only, no tile layer, no real places. A small inset locator is optional and must show the fictional territory, not a real map.

**Advisory stepper**
- Header: advisory number, issue time, hours to landfall, declared activation level.
- Stepping redraws the track, cone and asset colours with a short transition (300 ms), and the ranked list reorders in place. The eastward track shift between advisories 2 and 4 must be visible on the map.
- Everything is computed live on each step (exposure, scores, playbook check). Only the advisory files are pre-authored. No precomputed results.

**Acceptance**
- Stepping 1 to 5 runs without a reload; each step completes in under 2 seconds on a laptop.
- The cone at each advisory widens with lead time and matches the ensemble's spread (test above).
- A screenshot of advisory 3 is saved to `docs/img/storm_map_adv3.png` for the README and the deck.

## C2. Field supervisor task view (Should, PRD L1-9)

- Route `/field` with an area selector (districts from the asset data). Mobile-first layout, read-only except task status.
- Lists only **approved** package items that need field work (inspection, barrier, generator staging, relocation): what, where (asset name and ID), why (one-line reason), playbook clause, approved by and when.
- Each task: buttons "Done" and "Blocked" with an optional note. "Done" sets the matching op_state key (`inspection_completed`, `barrier_installed`, `generator_assigned`, `relocated`) and writes an audit event with actor `field_supervisor`. "Blocked" writes the note and shows it in the next decision package as a gap.
- Supervisors cannot change priorities, approve items or see other areas' restricted detail.
- Show the P-4.7 stop-work state on any task whose site has tropical-storm wind arriving within 12 hours ("Stop work: P-4.7"), and disable "Done" there.

**Acceptance:** marking the PS-14 inspection done at advisory 3 removes the P-4.2 finding and prevents the advisory-5 conflict (this is the alternative demo path from plan section 8); a "Blocked" note appears in the next package.

## C3. ICS-215 and IAP draft (Should, PRD L1-10)

- After each package is decided, generate a draft **operational planning worksheet (ICS-215)** for the next operational period, from approved items only. Columns: location (asset or area), work assignment, resource kind, required, have, need, reporting location, requested arrival time. "Have" comes from op_state and staging data; "need" = required minus have.
- Also draft the **IAP objectives and assignments** section: three to six incident objectives derived from the open findings (for example "Protect water supply to WTP-01: generators at at-risk pumping stations by T-36"), each citing its clause IDs.
- Generation is deterministic from the approved items (template mode). The LLM may only rephrase objective wording, with citations validated as in the agent.
- Both are marked DRAFT. Release needs two approvals: Planning Section Chief, then Incident Commander; both logged. Export as printable HTML.

**Acceptance:** after advisory 3 decisions, the ICS-215 lists the PS-09 generator and the flood barrier tasks with correct have and need counts; nothing unapproved appears; release without both approvals is refused.

## Demo path additions
- Open on the storm map at advisory 1; step to advisory 3 and point at the cone narrowing over Bayport.
- At advisory 3, switch to `/field` for the Bayport East district and show the approved tasks with their clauses (C2).
- At advisory 4, show the ICS-215 draft and release it with the two approvals (C3).
