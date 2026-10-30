// A real GET /packages/3 response (template provider, lists cut to three). The backend test
// test_package_payloads.py checks its shape against a fresh response; regenerate it with
// uv run pytest tests/test_package_payloads.py --update-fixtures
import type { DecisionPackage } from '../types/scenario'

export const packageResponse = {
  "advisory_no": 3,
  "status": "open",
  "activation_level": "monitor",
  "proposed_activation_level": "full",
  "decides_as_commander": "director",
  "changes": {
    "advisory_no": 3,
    "previous_advisory_no": 2,
    "landfall_shift": {
      "distance_km": 41.3,
      "direction": "east"
    },
    "max_wind_change_mph": 5.0,
    "peak_surge_change_m": 0.5,
    "activation_level_from": "monitor",
    "activation_level_to": "monitor",
    "top10_entered": [
      "SUB-07",
      "SUB-106",
      "SUB-11"
    ],
    "top10_left": [
      "PS-19",
      "SUB-102",
      "SUB-117"
    ],
    "rank_moves": [
      {
        "asset_id": "SUB-46",
        "from_rank": 18,
        "to_rank": 72
      },
      {
        "asset_id": "SUB-90",
        "from_rank": 53,
        "to_rank": 104
      },
      {
        "asset_id": "SUB-14",
        "from_rank": 76,
        "to_rank": 125
      }
    ]
  },
  "items": [
    {
      "id": 24,
      "rule_id": "P-2.5",
      "title": "Propose activation change at threshold",
      "entity_id": "event",
      "entity_name": null,
      "kind": "proposal",
      "proposed_action": "Declare activation Level 1 (full), now monitor; the incident commander declares it",
      "owner_role": "incident_commander",
      "severity": "high",
      "cites": [
        "P-2.5"
      ],
      "overdue": false,
      "status": "pending",
      "decided_by": null,
      "reason": null,
      "decided_at": null,
      "blocked_note": null
    },
    {
      "id": 25,
      "rule_id": "P-4.1",
      "title": "Risk list reviewed for this advisory",
      "entity_id": "event",
      "entity_name": null,
      "kind": "gap",
      "proposed_action": "Review the ranked risk list for this advisory and record the review",
      "owner_role": "planning",
      "severity": "medium",
      "cites": [
        "P-4.1"
      ],
      "overdue": false,
      "status": "approved",
      "decided_by": "planning",
      "reason": null,
      "decided_at": "2026-10-30T00:13:55.172985Z",
      "blocked_note": null
    },
    {
      "id": 26,
      "rule_id": "P-4.2",
      "title": "Pre-inspect coastal pumping stations at flood risk",
      "entity_id": "PS-14",
      "entity_name": "Seawall Pumping Station",
      "kind": "gap",
      "proposed_action": "Pre-inspect PS-14 Seawall Pumping Station: pumps, controls and the flood door, before crews withdraw",
      "owner_role": "operations",
      "severity": "high",
      "cites": [
        "P-4.2"
      ],
      "overdue": false,
      "status": "pending",
      "decided_by": null,
      "reason": null,
      "decided_at": null,
      "blocked_note": null
    }
  ],
  "draft": {
    "sections": [
      {
        "heading": "Situation",
        "paragraphs": [
          {
            "text": "Advisory 3, 48 h to landfall; activation level monitor. The forecast landfall moved 41 km east.",
            "clause_ids": [],
            "asset_ids": []
          },
          {
            "text": "Highest risk assets: SUB-97, SUB-112, SUB-11, SUB-119, SUB-103.",
            "clause_ids": [],
            "asset_ids": [
              "SUB-97",
              "SUB-112",
              "SUB-11"
            ]
          }
        ]
      },
      {
        "heading": "Playbook actions",
        "paragraphs": [
          {
            "text": "P-4.1: Review the ranked risk list for this advisory and record the review.",
            "clause_ids": [
              "P-4.1"
            ],
            "asset_ids": []
          },
          {
            "text": "P-4.2: Pre-inspect PS-14 Seawall Pumping Station: pumps, controls and the flood door, before crews withdraw.",
            "clause_ids": [
              "P-4.2"
            ],
            "asset_ids": [
              "PS-14"
            ]
          },
          {
            "text": "P-4.2: Pre-inspect PS-27 Eastgate West Pumping Station: pumps, controls and the flood door, before crews withdraw.",
            "clause_ids": [
              "P-4.2"
            ],
            "asset_ids": [
              "PS-27"
            ]
          }
        ]
      }
    ],
    "status": "DRAFT",
    "provider": "template",
    "fallback": false,
    "model": null,
    "prompt_version": null,
    "fallback_reason": null
  },
  "draft_text": "Situation\n\nAdvisory 3, 48 h to landfall; activation level monitor. The forecast landfall moved 41 km east.\n\nHighest risk assets: SUB-97, SUB-112, SUB-11, SUB-119, SUB-103.\n\nPlaybook actions\n\nP-4.1: Review the ranked risk list for this advisory and record the review.\n\nP-4.2: Pre-inspect PS-14 Seawall Pumping Station: pumps, controls and the flood door, before crews withdraw.\n\nP-4.2: Pre-inspect PS-27 Eastgate West Pumping Station: pumps, controls and the flood door, before crews withdraw.\n\nP-4.2: Pre-inspect PS-74 Juniper North Pumping Station: pumps, controls and the flood door, before crews withdraw.\n\nP-4.3: Fuel 4 more portable generators (10 needed, 6 fuelled).\n\nP-4.4: Inspect SUB-07 Medical District Substation.\n\nP-4.4: Inspect SUB-32 Pinewold Ridge East Substation.\n\nP-4.4: Inspect SUB-33 Elm Park Substation.\n\nP-4.4: Inspect SUB-97 Seabreeze Substation.\n\nP-4.4: Inspect SUB-103 Highfield Substation.\n\nP-4.4: Inspect SUB-112 Harbor East Substation.\n\nP-4.5: Assign a portable generator to PS-09 Saltmeadow East Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-19 Mangrove South Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-21 Driftwood East Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-34 Eastgate Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-40 Dune Crest Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-42 Westmoor West Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-48 Coral Lane South Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-53 Brinemoor Run West Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-54 Sandy Flats North Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-60 Bluewater South Pumping Station (feeds WTP-01).\n\nP-5.2: Confirm backup power and remote monitoring at PS-14 Seawall Pumping Station.\n\nP-5.2: Confirm backup power and remote monitoring at PS-27 Eastgate West Pumping Station.\n\nP-5.2: Confirm backup power and remote monitoring at PS-74 Juniper North Pumping Station.\n\nP-6.2: Contact the hospitals fed by SUB-07 Medical District Substation (HOSP-01); confirm on-site backup power is tested with 96 hours of fuel, and record who, when and what was confirmed.\n\nP-6.2: Contact the hospitals fed by SUB-33 Elm Park Substation (HOSP-03); confirm on-site backup power is tested with 96 hours of fuel, and record who, when and what was confirmed.\n\nP-6.2: Contact the hospitals fed by SUB-91 Orchard North Substation (HOSP-02); confirm on-site backup power is tested with 96 hours of fuel, and record who, when and what was confirmed.\n\nP-6.2: Contact the hospitals fed by SUB-103 Highfield Substation (HOSP-04, HOSP-07); confirm on-site backup power is tested with 96 hours of fuel, and record who, when and what was confirmed.\n\nP-6.2: Contact the hospitals fed by SUB-106 Bluewater South Substation (HOSP-06, SHEL-16); confirm on-site backup power is tested with 96 hours of fuel, and record who, when and what was confirmed.",
  "sitrep": {
    "advisory_no": 3,
    "approved_text": "Situation\n\nAdvisory 3, 48 h to landfall; activation level monitor. The forecast landfall moved 41 km east.\n\nHighest risk assets: SUB-97, SUB-112, SUB-11, SUB-119, SUB-103.\n\nPlaybook actions\n\nP-4.1: Review the ranked risk list for this advisory and record the review.\n\nP-4.2: Pre-inspect PS-14 Seawall Pumping Station: pumps, controls and the flood door, before crews withdraw.\n\nP-4.2: Pre-inspect PS-27 Eastgate West Pumping Station: pumps, controls and the flood door, before crews withdraw.\n\nP-4.2: Pre-inspect PS-74 Juniper North Pumping Station: pumps, controls and the flood door, before crews withdraw.\n\nP-4.3: Fuel 4 more portable generators (10 needed, 6 fuelled).\n\nP-4.4: Inspect SUB-07 Medical District Substation.\n\nP-4.4: Inspect SUB-32 Pinewold Ridge East Substation.\n\nP-4.4: Inspect SUB-33 Elm Park Substation.\n\nP-4.4: Inspect SUB-97 Seabreeze Substation.\n\nP-4.4: Inspect SUB-103 Highfield Substation.\n\nP-4.4: Inspect SUB-112 Harbor East Substation.\n\nP-4.5: Assign a portable generator to PS-09 Saltmeadow East Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-19 Mangrove South Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-21 Driftwood East Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-34 Eastgate Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-40 Dune Crest Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-42 Westmoor West Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-48 Coral Lane South Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-53 Brinemoor Run West Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-54 Sandy Flats North Pumping Station (feeds WTP-01).\n\nP-4.5: Assign a portable generator to PS-60 Bluewater South Pumping Station (feeds WTP-01).\n\nP-5.2: Confirm backup power and remote monitoring at PS-14 Seawall Pumping Station.\n\nP-5.2: Confirm backup power and remote monitoring at PS-27 Eastgate West Pumping Station.\n\nP-5.2: Confirm backup power and remote monitoring at PS-74 Juniper North Pumping Station.\n\nP-6.2: Contact the hospitals fed by SUB-07 Medical District Substation (HOSP-01); confirm on-site backup power is tested with 96 hours of fuel, and record who, when and what was confirmed.\n\nP-6.2: Contact the hospitals fed by SUB-33 Elm Park Substation (HOSP-03); confirm on-site backup power is tested with 96 hours of fuel, and record who, when and what was confirmed.\n\nP-6.2: Contact the hospitals fed by SUB-91 Orchard North Substation (HOSP-02); confirm on-site backup power is tested with 96 hours of fuel, and record who, when and what was confirmed.\n\nP-6.2: Contact the hospitals fed by SUB-103 Highfield Substation (HOSP-04, HOSP-07); confirm on-site backup power is tested with 96 hours of fuel, and record who, when and what was confirmed.\n\nP-6.2: Contact the hospitals fed by SUB-106 Bluewater South Substation (HOSP-06, SHEL-16); confirm on-site backup power is tested with 96 hours of fuel, and record who, when and what was confirmed.",
    "approved_by": "director",
    "approved_at": "2026-10-30T00:13:55.204076Z",
    "edited": false
  }
} satisfies DecisionPackage
