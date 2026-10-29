"""The seeded scenario (tests/conftest.py) runs the app's own replay and advisory cycle without
HTTP, so it must agree with what the API serves."""

from typing import Any

from fastapi.testclient import TestClient

from app import advisory_context
from app.api.schemas import FindingOut
from app.playbook.service import finding_views
from tests.conftest import SeededScenario


def test_issue_until_makes_the_advisory_current(seeded: SeededScenario) -> None:
    assert advisory_context.current_advisory_no(seeded.session) == 0

    seeded.issue_until(2)

    assert advisory_context.current_advisory_no(seeded.session) == 2


def test_findings_match_what_the_api_serves(seeded: SeededScenario, client: TestClient) -> None:
    seeded.issue_until(2)
    for _ in range(2):
        client.post("/advisories/next").raise_for_status()
    response = client.get("/findings", params={"advisory": 2})
    response.raise_for_status()

    def key(f: dict[str, Any]) -> tuple[str, str]:
        return f["rule_id"], f["entity_id"]

    fields = set(FindingOut.model_fields)
    in_process = [
        {**v.finding.model_dump(include=fields), "title": v.title, "entity_name": v.entity_name}
        for v in finding_views(seeded.session, seeded.playbook, 2)
    ]

    assert in_process
    assert sorted(in_process, key=key) == sorted(response.json(), key=key)
