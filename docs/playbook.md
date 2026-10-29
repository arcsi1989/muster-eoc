# SGW Hurricane Response Playbook

> **FICTIONAL DOCUMENT.** Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM document. Southeastern Grid & Water (SGW), the Bayport service territory, every facility name and every threshold below are invented for a prototype. They are plausible, not authoritative, and must not be used for real operations.

| Field | Value |
|---|---|
| Document | EOP-HUR-01, Hurricane Response Playbook |
| Version | 3.2 |
| Owner | Director, Emergency Operations Center (EOC) |
| Approved by | Chief Operating Officer |
| Approved on | 15 May 2026 |
| Review cycle | Annually before 1 June, and after every activation |
| Machine-readable triggers | `data/playbook/playbook_rules.yaml` (same clause IDs) |

---

## 1. Purpose and scope

**P-1.1 Purpose.** This playbook sets out what SGW does, and who decides, from the moment a hurricane threatens the Bayport service territory until normal operations resume. It covers electric substations, water pumping stations and the water treatment plant.

**P-1.2 Thresholds.** Distances, wind speeds, water depths and times in this playbook are planning thresholds. Wind is sustained wind in mph. Flood depth is water above the asset's ground elevation in metres. Hours count down to forecast landfall (T-minus).

**P-1.3 Forecast source.** The official source is the latest public hurricane advisory. Where SGW's risk platform shows a range, plan against the 90th percentile (P90) for flood depth and the median (P50) for wind, unless a clause says otherwise.

## 2. Activation levels

**P-2.1 Level 3, Monitor (T-120 to T-72).** The EOC duty officer monitors each advisory and briefs the Director daily. No field changes.

**P-2.2 Level 2, Prepare (T-72 to T-48).** The EOC is partly staffed. Operational periods are 12 hours. Planning produces a ranked asset risk list for every advisory.

**P-2.3 Level 1, Full activation (T-48 to landfall).** The EOC is fully staffed under the Incident Command System. An Incident Commander (IC) is appointed and holds authority for all decisions in this playbook until stand-down.

**P-2.4 Stand-down.** The IC declares stand-down when restoration of critical customers is complete and no further hazard is forecast.

## 3. Roles and decision rights

**P-3.1 Incident Commander.** Approves the priority list, every staging plan, every situation report and every deviation from this playbook.

**P-3.2 Operations Section.** Directs field crews: inspections, protective measures, and later restoration.

**P-3.3 Planning Section.** Maintains the ranked risk list, tracks open actions against this playbook, and drafts the situation report.

**P-3.4 Logistics Section.** Owns generators, fuel, flood barriers, staging areas and mutual assistance requests.

**P-3.5 Public Information and Regulatory Liaison.** Releases all external messages and regulator notifications. No other role communicates externally.

## 4. Actions by phase

**P-4.1 Risk list review (from T-72).** For every advisory, Planning reviews the ranked risk list with the IC (or the Director at Level 2) and records that it was reviewed. Changes to the top 10 are explained in the briefing.

**P-4.2 Coastal pumping stations (from T-48).** Pre-inspect every pumping station within 5 km of the coast whose forecast P90 flood depth exceeds 0.5 m. Confirm pumps, controls and the station's flood door before crews withdraw.

**P-4.3 Generator readiness (from T-72).** Logistics fuels all portable generators and confirms that the number fuelled and available is at least the number of pumping stations in the top 25 of the risk list that serve the water treatment plant.

**P-4.4 Poor-condition substations (from T-72).** Inspect every substation in the top 10 of the risk list whose condition score is 4 or 5 (poor or very poor).

**P-4.5 Backup power for water supply (from T-48).** Every pumping station that serves the water treatment plant, and whose failure probability is 20% or more, has a portable generator assigned to it and staged within reach. Portable generators are not used to back up substations; hospitals and shelters rely on their own on-site emergency power (see P-6.2).

**P-4.6 Staging areas (from T-36).** Crews and equipment are moved out of any staging area with a forecast P90 flood depth above zero, to an inland staging area.

**P-4.7 Stop-work on wind (always in force).** No field work at a site where tropical-storm-force wind (39 mph or more) is forecast to arrive within 12 hours. Crews withdraw to staging areas. This clause protects personnel and is not waived.

## 5. Asset-specific protections

**P-5.1 Substation flood barriers (from T-36).** Install temporary flood barriers at every substation with a forecast P90 flood depth above 0.3 m.

**P-5.2 Pumping station backup power (from T-48).** At every pumping station with a forecast P90 flood depth above 0.5 m, confirm that backup power is available and that the station can be monitored remotely.

**P-5.3 Water treatment plant (from T-48).** When the treatment plant's failure probability is 10% or more, confirm at least 7 days of treatment chemicals on site and have a boil-water notice ready for release by the Public Information Officer.

## 6. Critical customers

**P-6.1 Restoration priority.** After landfall, restore in this order: hospitals; the water treatment plant and the pumping stations that serve it; emergency shelters; registered life-support customers; then by number of customers affected.

**P-6.2 Critical customer readiness (from T-48).** Contact every hospital whose supply depends on an asset in the top 25 of the risk list. Confirm that its on-site emergency power has been tested and has at least 96 hours of fuel, and share the asset's risk and the restoration priority under P-6.1. Record who was contacted, when, and what was confirmed.

## 7. Communications and notifications

**P-7.1 Situation report.** Planning issues a situation report every operational period. The IC approves it before release. Drafts, including AI-generated drafts, are marked DRAFT until approved.

**P-7.2 Regulator notification.** The Regulatory Liaison notifies the state utility commission within 12 hours of Level 1 activation, and records the time of notification.

**P-7.3 Public messages.** External messages are released only by the Public Information Officer, from approved text.

## 8. Deviations and conflicts

**P-8.1 Deviations.** Any departure from this playbook needs the IC's approval and a recorded reason.

**P-8.2 Conflicting clauses.** Where two clauses cannot both be met, the safety of personnel prevails. The IC decides how to proceed and the decision and reason are recorded. Tools may point out the conflict but do not resolve it.

---

*End of playbook. 29 clauses. Clauses with machine-checkable triggers are listed in `playbook_rules.yaml`; the others (for example P-6.1) guide narrative and judgement and are retrieved for context only.*
