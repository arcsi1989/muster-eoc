"""Typed package payloads: what changed and the draft situation report are each one model,
stored in the decision package and served by the API as they are."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from muster.api.schemas import PackageOut
from muster.llm.schemas import PackageDraft, Paragraph, Section
from muster.models import DecisionPackage
from muster.replay import service
from muster.replay.diff import AdvisoryChanges, LandfallShift, RankMove
from tests.conftest import SeededScenario

# A real package response, checked against the TypeScript types by the frontend's type check.
FIXTURE = Path(__file__).parents[2] / "frontend/src/test/packageResponse.ts"
FIXTURE_HEAD = (
    "// A real GET /packages/3 response (template provider, lists cut to three). The backend test\n"
    "// test_package_payloads.py checks its shape against a fresh response; regenerate it with\n"
    "// uv run pytest tests/test_package_payloads.py --update-fixtures\n"
    "import type { DecisionPackage } from '../types/scenario'\n\n"
    "export const packageResponse = "
)
FIXTURE_TAIL = " satisfies DecisionPackage\n"


def stored(seeded: SeededScenario, advisory_no: int) -> DecisionPackage:
    """The package as a fresh read gives it back."""
    seeded.session.expire_all()
    package = seeded.session.get(DecisionPackage, advisory_no)
    assert package is not None
    return package


def test_stored_changes_read_back_equal_to_what_was_written(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    changes = AdvisoryChanges(
        advisory_no=1,
        previous_advisory_no=None,
        landfall_shift=LandfallShift(distance_km=41.2, direction="east"),
        max_wind_change_mph=5.0,
        peak_surge_change_m=0.3,
        activation_level_from="prepare",
        activation_level_to="prepare",
        top10_entered=["SUB-12"],
        top10_left=["WTP-01"],
        rank_moves=[RankMove(asset_id="PS-14", from_rank=30, to_rank=12)],
    )
    package = stored(seeded, 1)
    package.changes = changes
    seeded.session.add(package)
    seeded.session.commit()

    assert stored(seeded, 1).changes == changes


def test_the_cycle_stores_what_changed_since_the_previous_advisory(
    seeded: SeededScenario,
) -> None:
    seeded.issue_until(2)

    expected = service.changes(seeded.session, 2, seeded.playbook.levels, seeded.scoring.risk.top_n)

    assert stored(seeded, 2).changes == expected
    assert stored(seeded, 1).changes == AdvisoryChanges(
        advisory_no=1, activation_level_to=expected.activation_level_from
    )


def test_stored_draft_read_back_equal_to_what_was_written(seeded: SeededScenario) -> None:
    seeded.issue_until(1)
    draft = PackageDraft(
        provider="template (fallback)",
        fallback=True,
        model=None,
        prompt_version=None,
        fallback_reason="cited P-9.9, which it was not shown",
        sections=[
            Section(
                heading="Situation",
                paragraphs=[
                    Paragraph(text="SUB-07 (P-4.2).", clause_ids=["P-4.2"], asset_ids=["SUB-07"])
                ],
            )
        ],
    )
    package = stored(seeded, 1)
    package.draft = draft
    seeded.session.add(package)
    seeded.session.commit()

    assert stored(seeded, 1).draft == draft


def test_the_cycle_stores_the_draft_with_its_metadata(seeded: SeededScenario) -> None:
    seeded.issue_until(1)

    draft = stored(seeded, 1).draft

    assert draft is not None
    assert (draft.status, draft.provider, draft.fallback) == ("DRAFT", "template", False)
    assert draft.sections and draft.text().startswith(draft.sections[0].heading)


def shape(value: Any) -> Any:
    """The keys and value types of a JSON document; a list by its first element."""
    if isinstance(value, dict):
        return {key: shape(v) for key, v in value.items()}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    return type(value).__name__


def trimmed(value: Any, keep: int = 3) -> Any:
    """The document with each list cut to its first `keep` elements: same shape, smaller file."""
    if isinstance(value, dict):
        return {key: trimmed(v, keep) for key, v in value.items()}
    if isinstance(value, list):
        return [trimmed(v, keep) for v in value[:keep]]
    return value


def test_the_package_response_validates_and_matches_the_frontend_fixture(
    client: TestClient, request: pytest.FixtureRequest
) -> None:
    # Advisory 3 has a landfall shift; one decided item and the approved situation report fill
    # in every field that is null on a fresh package.
    for _ in range(3):
        assert client.post("/advisories/next").status_code == 200
    package = client.get("/packages/3").json()
    gap = next(i for i in package["items"] if i["kind"] == "gap")
    decision = {"role": gap["owner_role"], "action": "approve"}
    assert client.post(f"/packages/3/items/{gap['id']}/decision", json=decision).is_success
    approval = {"role": package["decides_as_commander"], "text": package["draft_text"]}
    assert client.post("/sitrep/3/approve", json=approval).is_success

    response = client.get("/packages/3")

    assert response.status_code == 200
    body = response.json()
    PackageOut.model_validate(body)
    if request.config.getoption("--update-fixtures"):
        FIXTURE.write_text(FIXTURE_HEAD + json.dumps(trimmed(body), indent=2) + FIXTURE_TAIL)
    fixture = FIXTURE.read_text().removeprefix(FIXTURE_HEAD).removesuffix(FIXTURE_TAIL)
    assert shape(json.loads(fixture)) == shape(body)
