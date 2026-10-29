"""The ID patterns of the fictional territory and the playbook, in one place."""

import re

ASSET_ID = re.compile(r"\b(?:SUB|PS|WTP)-\d{2,3}\b", re.IGNORECASE)
CLAUSE_ID = re.compile(r"\bP-\d+\.\d+\b", re.IGNORECASE)
# Sites: assets and staging areas, the entities a situation report lists in asset_ids.
# Critical facilities (HOSP-, SHEL-) are named in the text only (prompt sitrep-v2).
SITE_ID = re.compile(r"\b(?:SUB|PS|WTP|STG)-\d{2,3}\b", re.IGNORECASE)
# Anything that names an entity: assets, staging areas, critical facilities.
ENTITY_ID = re.compile(r"\b(?:SUB|PS|WTP|STG|HOSP|SHEL)-\d{2,3}\b", re.IGNORECASE)
