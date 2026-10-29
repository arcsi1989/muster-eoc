"""The ID patterns of the fictional territory and the playbook, in one place."""

import re

ASSET_ID = re.compile(r"\b(?:SUB|PS|WTP)-\d{2,3}\b", re.IGNORECASE)
CLAUSE_ID = re.compile(r"\bP-\d+\.\d+\b", re.IGNORECASE)
# Anything that names an entity: assets, staging areas, critical facilities.
ENTITY_ID = re.compile(r"\b(?:SUB|PS|WTP|STG|HOSP|SHEL)-\d{2,3}\b", re.IGNORECASE)
