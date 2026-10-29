"""Situation report citations use the shared ID patterns (app/ids.py)."""

from app.agent.citations import citation_problems
from app.ids import CLAUSE_ID, ENTITY_ID, SITE_ID
from app.llm.schemas import Paragraph, Section, SitrepDraft


def draft(text: str, clause_ids: list[str], asset_ids: list[str]) -> SitrepDraft:
    paragraph = Paragraph(text=text, clause_ids=clause_ids, asset_ids=asset_ids)
    return SitrepDraft(sections=[Section(heading="Status", paragraphs=[paragraph])])


def test_a_grounded_paragraph_has_no_problems() -> None:
    found = draft("SUB-07 and STG-02 need action (P-4.5).", ["P-4.5"], ["SUB-07", "STG-02"])

    assert citation_problems(found, {"P-4.5"}, {"SUB-07", "STG-02"}) == []


def test_a_lowercase_id_in_the_text_must_still_be_listed() -> None:
    found = draft("sub-07 is at risk under p-4.5.", [], [])

    assert citation_problems(found, {"P-4.5"}, {"SUB-07"}) == [
        "asset SUB-07 is mentioned in the text but not listed",
        "clause P-4.5 is mentioned in the text but not listed",
    ]


def test_a_facility_is_named_in_the_text_only() -> None:
    named = draft("SUB-07 feeds HOSP-01 and SHEL-02.", [], ["SUB-07"])
    listed = draft("HOSP-01 is at risk.", [], ["HOSP-01"])

    assert citation_problems(named, set(), {"SUB-07"}) == []
    assert citation_problems(listed, set(), {"SUB-07"}) == [
        "asset HOSP-01 is not in the findings, changes or top assets"
    ]


def test_sites_are_the_entities_that_are_not_facilities() -> None:
    for site in ("SUB-07", "PS-14", "WTP-01", "STG-02"):
        assert SITE_ID.fullmatch(site) and ENTITY_ID.fullmatch(site)
    for facility in ("HOSP-01", "SHEL-02"):
        assert not SITE_ID.fullmatch(facility) and ENTITY_ID.fullmatch(facility)
    assert CLAUSE_ID.fullmatch("P-4.5")
