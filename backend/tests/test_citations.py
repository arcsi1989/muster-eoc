"""Situation report citations: a draft may cite exactly what its draft request shows, matched
by the shared ID patterns (app/ids.py). Requests are built by hand: no database, no replay."""

from app.agent.citations import citation_problems
from app.ids import CLAUSE_ID, ENTITY_ID, SITE_ID
from app.llm.schemas import (
    DraftItem,
    DraftRequest,
    Paragraph,
    Prompt,
    RetrievedClause,
    Section,
    SitrepDraft,
    TopAsset,
)
from app.llm.template import TemplateProvider
from app.replay.diff import AdvisoryChanges, RankMove


def draft(text: str, clause_ids: list[str], asset_ids: list[str]) -> SitrepDraft:
    paragraph = Paragraph(text=text, clause_ids=clause_ids, asset_ids=asset_ids)
    return SitrepDraft(sections=[Section(heading="Status", paragraphs=[paragraph])])


def item(rule_id: str, entity_id: str, cites: list[str], action: str = "act") -> DraftItem:
    return DraftItem(
        rule_id=rule_id,
        entity_id=entity_id,
        entity_is_citable=entity_id != "event",
        kind="gap",
        action=action,
        cites=cites,
        overdue=False,
    )


def request(
    items: list[DraftItem] | None = None,
    top: list[str] | None = None,
    changes: AdvisoryChanges | None = None,
    clauses: list[str] | None = None,
    feedback: list[str] | None = None,
) -> DraftRequest:
    return DraftRequest(
        advisory_no=3,
        hours_to_landfall=48,
        activation_level="prepare",
        changes=changes or AdvisoryChanges(advisory_no=3),
        items=items or [],
        top_assets=[TopAsset(a, a, n, 0.5) for n, a in enumerate(top or [], start=1)],
        clauses=[RetrievedClause(c, "title", "text") for c in clauses or []],
        feedback=feedback or [],
    )


def cites(clauses: list[str], sites: list[str]) -> SitrepDraft:
    return draft(" ".join(clauses + sites), clauses, sites)


def test_everything_the_request_shows_is_citable() -> None:
    shown = request(
        items=[item("P-4.5", "PS-09", ["P-4.5", "P-8.2"], action="Stage a generator per P-3.1")],
        top=["SUB-07"],
        changes=AdvisoryChanges(
            advisory_no=3,
            previous_advisory_no=2,
            top10_entered=["SUB-12"],
            top10_left=["WTP-01"],
            rank_moves=[RankMove(asset_id="PS-14", from_rank=30, to_rank=12)],
        ),
        clauses=["P-6.2"],
    )

    found = cites(
        ["P-4.5", "P-8.2", "P-3.1", "P-6.2"], ["PS-09", "SUB-07", "SUB-12", "WTP-01", "PS-14"]
    )
    assert citation_problems(found, shown) == []


def test_a_rank_move_alone_makes_its_asset_citable() -> None:
    moved = request(
        changes=AdvisoryChanges(
            advisory_no=3, rank_moves=[RankMove(asset_id="PS-14", from_rank=30, to_rank=12)]
        )
    )

    assert citation_problems(cites([], ["PS-14"]), moved) == []
    assert citation_problems(cites([], ["PS-14"]), request()) == [
        "asset PS-14 is not in the findings, changes or top assets"
    ]


def test_something_not_shown_is_rejected() -> None:
    shown = request(items=[item("P-4.5", "PS-09", ["P-4.5"])], top=["SUB-07"])

    assert citation_problems(cites(["P-9.9"], ["SUB-99"]), shown) == [
        "asset SUB-99 is not in the findings, changes or top assets",
        "clause P-9.9 is not in the findings or retrieved clauses",
    ]


def test_the_eoc_wide_event_is_not_an_asset() -> None:
    event = request(items=[item("P-2.1", "event", ["P-2.1"])])

    assert event.citable_sites == frozenset()
    assert event.citable_clauses == frozenset({"P-2.1"})


def test_feedback_from_a_rejected_try_does_not_ground_a_retry() -> None:
    retry = request(feedback=["clause P-9.9 is not in the findings or retrieved clauses"])

    assert "P-9.9" not in retry.citable_clauses
    assert "feedback" not in retry.shown()


def test_the_template_draft_is_grounded_in_its_request() -> None:
    conflict = DraftItem(
        "P-8.2", "SUB-07", True, "conflict", "Hold crews", ["P-8.2", "P-4.7"], False
    )
    feeds = item("P-4.5", "PS-09", ["P-4.5"], action="Assign a generator to PS-09 (feeds WTP-01)")
    shown = request(
        items=[feeds, item("P-2.1", "event", ["P-2.1"], action="Notify per P-7.2"), conflict],
        top=["SUB-07", "STG-02", "PS-14"],
    )

    assert (
        citation_problems(
            TemplateProvider(top_risks=5, top_assets=5)
            .draft_sitrep(shown, Prompt("unused", "", max_tokens=1))
            .draft,
            shown,
        )
        == []
    )


def test_a_grounded_paragraph_has_no_problems() -> None:
    found = draft("SUB-07 and STG-02 need action (P-4.5).", ["P-4.5"], ["SUB-07", "STG-02"])

    assert citation_problems(found, request(top=["SUB-07", "STG-02"], clauses=["P-4.5"])) == []


def test_a_lowercase_id_in_the_text_must_still_be_listed() -> None:
    found = draft("sub-07 is at risk under p-4.5.", [], [])

    assert citation_problems(found, request(top=["SUB-07"], clauses=["P-4.5"])) == [
        "asset SUB-07 is mentioned in the text but not listed",
        "clause P-4.5 is mentioned in the text but not listed",
    ]


def test_a_facility_is_named_in_the_text_only() -> None:
    named = draft("SUB-07 feeds HOSP-01 and SHEL-02.", [], ["SUB-07"])
    listed = draft("HOSP-01 is at risk.", [], ["HOSP-01"])
    shown = request(items=[item("P-4.2", "SUB-07", [], action="SUB-07 feeds HOSP-01")])

    assert citation_problems(named, shown) == []
    assert citation_problems(listed, shown) == [
        "asset HOSP-01 is not in the findings, changes or top assets"
    ]


def test_sites_are_the_entities_that_are_not_facilities() -> None:
    for site in ("SUB-07", "PS-14", "WTP-01", "STG-02"):
        assert SITE_ID.fullmatch(site) and ENTITY_ID.fullmatch(site)
    for facility in ("HOSP-01", "SHEL-02"):
        assert not SITE_ID.fullmatch(facility) and ENTITY_ID.fullmatch(facility)
    assert CLAUSE_ID.fullmatch("P-4.5")
