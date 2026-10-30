"""What the champion and challenger view reads (CR-03 C2, ticket 34): the disagreements at an
advisory, from the stored shadow scores, and the challenger's top features in the explain panel."""

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import REPO_ROOT
from app.main import create_app
from app.models import Score, ShadowScore
from app.models_config import load_models_config
from app.scoring_config import load_scoring_config
from tests.conftest import test_settings as settings_in

TOP_N = load_scoring_config(REPO_ROOT / "config" / "scoring.yaml").risk.top_n
SHOWN = load_models_config(REPO_ROOT / "config" / "models.yaml").challenger.explain_features


def ranks(client: TestClient, advisory_no: int) -> tuple[dict[str, int], dict[str, ShadowScore]]:
    engine: Any = client.app.state.engine  # type: ignore[attr-defined]
    with Session(engine) as session:
        champion = {
            s.asset_id: s.rank
            for s in session.exec(select(Score).where(Score.advisory_no == advisory_no))
        }
        shadow = {
            s.asset_id: s
            for s in session.exec(select(ShadowScore).where(ShadowScore.advisory_no == advisory_no))
        }
    return champion, shadow


def test_disagreements_are_the_challengers_top_ranks_the_champion_leaves_out(
    client: TestClient,
) -> None:
    client.post("/advisories/next")
    champion, shadow = ranks(client, 1)
    expected = {a for a, s in shadow.items() if s.rank <= TOP_N and champion[a] > TOP_N}

    body = client.get("/challenger/disagreements", params={"advisory": 1}).json()

    assert body["advisory_no"] == 1
    assert body["top_n"] == TOP_N
    assert body["model_version"] == client.get("/challenger").json()["model_version"]["id"]
    items = body["items"]
    assert {i["asset_id"] for i in items} == expected
    assert [i["challenger_rank"] for i in items] == sorted(i["challenger_rank"] for i in items)
    for item in items:
        stored = shadow[item["asset_id"]]
        assert item["challenger_rank"] == stored.rank
        assert item["asset_name"]
        assert item["champion_rank"] == champion[item["asset_id"]]
        assert item["challenger_p_fail"] == stored.p_fail
        assert item["top_features"] == stored.factors["features"][:SHOWN]


def test_disagreements_before_the_advisory_is_issued_answer_404(client: TestClient) -> None:
    response = client.get("/challenger/disagreements", params={"advisory": 1})
    assert response.status_code == 404


def test_the_explanation_shows_the_challengers_rank_and_top_features(client: TestClient) -> None:
    client.post("/advisories/next")
    _, shadow = ranks(client, 1)
    stored = shadow["PS-14"]

    body = client.get("/assets/PS-14/explain", params={"advisory": 1}).json()

    challenger = body["challenger"]
    assert challenger["model_version"] == stored.model_version
    assert challenger["rank"] == stored.rank
    assert challenger["p_fail"] == stored.p_fail
    assert challenger["top_features"] == stored.factors["features"][:SHOWN]
    assert len(challenger["top_features"]) == SHOWN
    assert body["wind"] and body["flood"]  # the rule-based breakdown stays beside it


def test_without_a_challenger_the_explanation_has_none_and_disagreements_404(
    tmp_path: Path,
) -> None:
    settings = settings_in(tmp_path).model_copy(
        update={"challenger_model_path": tmp_path / "missing.pkl"}
    )
    with TestClient(create_app(settings)) as client:
        client.post("/advisories/next")
        body = client.get("/assets/PS-14/explain", params={"advisory": 1}).json()
        assert body["challenger"] is None
        response = client.get("/challenger/disagreements", params={"advisory": 1})
        assert response.status_code == 404


def test_once_the_challenger_is_champion_nothing_disagrees_and_it_explains_nothing_in_shadow(
    client: TestClient,
) -> None:
    version_id = client.get("/challenger").json()["model_version"]["id"]
    client.post("/challenger/propose")
    client.post(f"/model-versions/{version_id}/approve", json={"role": "planning"})
    client.post("/advisories/next")

    body = client.get("/challenger/disagreements", params={"advisory": 1}).json()
    assert body["items"] == []
    explained = client.get("/assets/PS-14/explain", params={"advisory": 1}).json()
    assert explained["challenger"] is None
