"""Every clause and asset ID in a draft must be real and match a finding or retrieved clause
(plan section 4, validate_citations)."""

import re

from app.ids import CLAUSE_ID, SITE_ID
from app.llm.schemas import SitrepDraft


def _mentioned(pattern: re.Pattern[str], text: str) -> set[str]:
    return {m.upper() for m in pattern.findall(text)}


def citation_problems(
    draft: SitrepDraft, allowed_clauses: set[str], allowed_assets: set[str]
) -> list[str]:
    """Problems found; empty when every citation is grounded."""
    problems = []
    for section in draft.sections:
        for paragraph in section.paragraphs:
            for clause in paragraph.clause_ids:
                if clause not in allowed_clauses:
                    problems.append(f"clause {clause} is not in the findings or retrieved clauses")
            for asset in paragraph.asset_ids:
                if asset not in allowed_assets:
                    problems.append(f"asset {asset} is not in the findings, changes or top assets")
            for clause in _mentioned(CLAUSE_ID, paragraph.text) - set(paragraph.clause_ids):
                problems.append(f"clause {clause} is mentioned in the text but not listed")
            for asset in _mentioned(SITE_ID, paragraph.text) - set(paragraph.asset_ids):
                problems.append(f"asset {asset} is mentioned in the text but not listed")
    return sorted(set(problems))
