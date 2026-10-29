"""Every clause and asset ID in a draft must be shown in the draft request it answered (plan
section 4, validate_citations)."""

import re

from app.ids import CLAUSE_ID, SITE_ID
from app.llm.schemas import DraftRequest, SitrepDraft


def _mentioned(pattern: re.Pattern[str], text: str) -> set[str]:
    return {m.upper() for m in pattern.findall(text)}


def citation_problems(draft: SitrepDraft, request: DraftRequest) -> list[str]:
    """Problems found; empty when every citation is grounded in the request."""
    allowed_clauses, allowed_assets = request.citable_clauses, request.citable_sites
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
