"""The challenger in shadow and its promotion by approval (CR-03 C2): both models behind the
risk model interface, shadow scores stored and never ranking, a challenger proposed only when it
passes the promotion rule, and the rules champion until a person approves it."""

from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from muster.calibration import service as calibration
from muster.calibration import versions
from muster.challenger.dataset import (
    FEATURES,
    held_out_storm,
    history_storms,
    load_world,
    stack,
    storm_sample,
)
from muster.challenger.model import ChallengerModel, Comparison, TrainedChallenger, baseline
from muster.challenger.promotion import (
    PROPOSED_EVENT,
    NotPromotable,
    calibration_error,
    check,
    propose,
    register,
)
from muster.challenger.train import build_model, metrics
from muster.config import REPO_ROOT, Settings
from muster.db import create_fresh_engine
from muster.hazard.ensemble import StormInput, compute_exposure
from muster.ingest.contracts import SyntheticStormFile
from muster.ingest.loader import PUBLISHED_VERSION, load_gold
from muster.main import create_app
from muster.models import Advisory, AuditEvent, ModelVersion, PackageItem, Score, ShadowScore
from muster.models_config import PromotionRule, load_models_config
from muster.network import load_network
from muster.risk.model import AssetFeatures, RiskModel, asset_features
from muster.risk.score import RuleBasedModel
from muster.scoring_config import load_scoring_config
from tests.conftest import SeededFactory, SeededScenario
from tests.conftest import test_settings as settings_in
from tests.test_challenger import FAST, history_slice

MODELS = load_models_config(REPO_ROOT / "config" / "models.yaml")
SCORING = load_scoring_config(REPO_ROOT / "config" / "scoring.yaml")
RULE = MODELS.promotion
ASSETS = 196


@pytest.fixture(scope="module")
def trained(tmp_path_factory: pytest.TempPathFactory) -> TrainedChallenger:
    """A challenger trained on three storms of the history (fast, the same discipline), with
    its comparison on Storm Delta measured as `make train` does."""

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    engine = create_fresh_engine(tmp_path_factory.mktemp("train") / "train.sqlite")
    with Session(engine) as session:
        load_gold(session, settings.data_dir)
        world = load_world(session, SCORING)
        storms: list[SyntheticStormFile] = history_slice()[:3]
        samples = [
            storm_sample(s, i, world, SCORING, FAST) for i, s in enumerate(history_storms(storms))
        ]
        delta = storm_sample(held_out_storm(session, "Storm Delta"), 0, world, SCORING, FAST)
    engine.dispose()
    features, failed, _, groups = stack(samples)
    model = build_model(features, failed, groups, FAST)
    held_out = Comparison(
        challenger=metrics(model.predict_proba(delta.features)[:, 1], delta.failed, SCORING),
        champion=metrics(delta.champion_p, delta.failed, SCORING),
    )
    return TrainedChallenger("challenger-test", model, baseline(features), "Storm Delta", held_out)


def passing(trained: TrainedChallenger) -> TrainedChallenger:
    """The same model, with a held-out comparison that beats the champion on every criterion."""
    champion = trained.held_out.champion
    better = replace(
        trained.held_out.challenger,
        brier=champion.brier - 2 * RULE.min_brier_improvement,
        top_capture=champion.top_capture + 2 * RULE.min_top_capture_gain,
        reliability=[
            replace(b, observed_rate=b.mean_predicted)
            for b in trained.held_out.challenger.reliability
        ],
    )
    return replace(trained, held_out=Comparison(challenger=better, champion=champion))


def failing_margin(trained: TrainedChallenger) -> TrainedChallenger:
    """Well calibrated and better on Brier, but its top-decile capture misses the margin."""
    good = passing(trained).held_out
    short = replace(
        good.challenger,
        top_capture=good.champion.top_capture + RULE.min_top_capture_gain / 2,
    )
    return replace(trained, held_out=Comparison(challenger=short, champion=good.champion))


def with_challenger(
    make_seeded: SeededFactory, trained: TrainedChallenger
) -> AbstractContextManager[tuple[SeededScenario, ChallengerModel]]:
    """A seeded scenario whose challenger is registered in shadow and scores every advisory."""

    @contextmanager
    def scenario() -> Iterator[tuple[SeededScenario, ChallengerModel]]:
        with make_seeded() as seeded:
            seeded.challenger = register(seeded.session, trained)
            yield seeded, seeded.challenger

    return scenario()


def scores(session: Session, advisory_no: int) -> list[Score]:
    query = select(Score).where(Score.advisory_no == advisory_no).order_by(col(Score.rank))
    return list(session.exec(query))


def shadow_scores(session: Session, advisory_no: int) -> list[ShadowScore]:
    query = select(ShadowScore).where(ShadowScore.advisory_no == advisory_no)
    return list(session.exec(query))


def assets_at(seeded: SeededScenario) -> Sequence[AssetFeatures]:

    world = load_world(seeded.session, SCORING)
    advisory = seeded.session.get(Advisory, 1)
    assert advisory is not None
    storm = StormInput(
        advisory_no=1,
        hours_to_landfall=advisory.hours_to_landfall,
        track=advisory.track,
        cone_radius_km=advisory.cone_radius_km,
        landfall=(advisory.landfall_x_km, advisory.landfall_y_km),
        peak_surge_m=advisory.peak_surge_m,
    )
    exposures = compute_exposure(storm, world.sites, world.coastline, world.land, SCORING.hazard)
    return asset_features(exposures, load_network(seeded.session), advisory.issued_at.year)


def test_the_rules_and_the_challenger_both_implement_the_risk_model(
    seeded: SeededScenario, trained: TrainedChallenger
) -> None:
    assets = assets_at(seeded)
    rules = RuleBasedModel(
        PUBLISHED_VERSION,
        versions.latest_curves(seeded.session).curves,
        SCORING.risk.condition_theta_reduction_per_step,
    )
    challenger = ChallengerModel(7, trained)
    models: list[RiskModel] = [rules, challenger]
    for model in models:
        predictions = model.predict(assets)
        assert [p.asset_id for p in predictions] == [a.asset.id for a in assets]
        assert all(0.0 <= p.p_fail <= 1.0 for p in predictions)
        assert {p.version for p in predictions} == {model.version}
    assert set(rules.predict(assets)[0].factors) == {"wind", "flood"}
    features = challenger.predict(assets)[0].factors["features"]
    assert {f["feature"] for f in features} == set(FEATURES)
    assert [f["contribution"] for f in features] == sorted(
        (f["contribution"] for f in features), reverse=True
    )


def test_the_challenger_scores_every_advisory_in_shadow_with_its_model_version(
    make_seeded: SeededFactory, trained: TrainedChallenger
) -> None:
    with with_challenger(make_seeded, trained) as (seeded, challenger):
        seeded.issue_until(2)
        version = challenger.version
        for advisory_no in (1, 2):
            shadow = shadow_scores(seeded.session, advisory_no)
            assert len(shadow) == ASSETS
            assert {s.model_version for s in shadow} == {version}
            assert sorted(s.rank for s in shadow) == list(range(1, ASSETS + 1))
            ranked = {s.asset_id: s for s in scores(seeded.session, advisory_no)}
            assert {s.model_version for s in ranked.values()} == {PUBLISHED_VERSION}
            assert all("model" not in s.factors for s in ranked.values())
        stored = seeded.session.get(ModelVersion, version)
        assert stored is not None and (stored.kind, stored.status) == ("challenger", "shadow")


def test_unapproved_challenger_scores_never_reach_the_ranking_or_the_package(
    make_seeded: SeededFactory, trained: TrainedChallenger
) -> None:
    """With the challenger in shadow (even proposed), the scores, ranks and decision packages
    are exactly those of a scenario without it."""

    def outcome(seeded: SeededScenario) -> tuple[list[Any], list[Any]]:
        seeded.issue_until(3)
        ranked = [
            (s.advisory_no, s.asset_id, s.rank, s.p_fail, s.risk, s.model_version)
            for n in (1, 2, 3)
            for s in scores(seeded.session, n)
        ]
        items = seeded.session.exec(select(PackageItem).order_by(col(PackageItem.id)))
        return ranked, [(i.advisory_no, i.rule_id, i.entity_id, i.kind) for i in items]

    with make_seeded() as plain:
        without = outcome(plain)
    with with_challenger(make_seeded, passing(trained)) as (shadowed, challenger):
        propose(shadowed.session, challenger, RULE)  # proposed, not approved
        with_shadow = outcome(shadowed)
        assert shadow_scores(shadowed.session, 3)

    assert with_shadow == without


def test_a_challenger_failing_the_margin_is_never_proposed(
    seeded: SeededScenario, trained: TrainedChallenger
) -> None:
    challenger = register(seeded.session, failing_margin(trained))
    result = check("Storm Delta", challenger.trained.held_out, RULE)
    assert not result.passed
    assert [c.name for c in result.criteria if not c.passed] == ["top_capture_gain"]

    with pytest.raises(NotPromotable, match="top_capture_gain"):
        propose(seeded.session, challenger, RULE)

    version = seeded.session.get(ModelVersion, challenger.version)
    assert version is not None and version.status == "shadow"
    events = select(AuditEvent).where(AuditEvent.type == PROPOSED_EVENT)
    assert not seeded.session.exec(events).all()


def miscalibrated(trained: TrainedChallenger) -> TrainedChallenger:
    """Beats the champion on both margins, but every bin is off by twice the allowed error."""
    good = passing(trained).held_out
    gap = 2 * RULE.max_calibration_error
    bins = [
        replace(b, observed_rate=p + gap if p + gap <= 1 else p - gap)
        if (p := b.mean_predicted) is not None
        else b
        for b in good.challenger.reliability
    ]
    off = replace(good.challenger, reliability=bins)
    return replace(trained, held_out=Comparison(challenger=off, champion=good.champion))


def test_each_criterion_of_the_rule_can_block_a_proposal(trained: TrainedChallenger) -> None:
    def failed(candidate: TrainedChallenger, rule: PromotionRule = RULE) -> list[str]:
        result = check("Storm Delta", candidate.held_out, rule)
        return [c.name for c in result.criteria if not c.passed]

    assert failed(passing(trained)) == []
    assert failed(failing_margin(trained)) == ["top_capture_gain"]
    assert failed(miscalibrated(trained)) == ["calibration_error"]
    stricter = RULE.model_copy(update={"min_brier_improvement": 1.0})
    assert failed(passing(trained), stricter) == ["brier_improvement"]


def test_calibration_error_weights_each_bin_by_its_assets(trained: TrainedChallenger) -> None:
    perfect = passing(trained).held_out.challenger
    assert calibration_error(perfect) == 0.0
    bins = [b for b in trained.held_out.challenger.reliability if b.count]
    expected = sum(
        b.count * abs((b.mean_predicted or 0) - (b.observed_rate or 0)) for b in bins
    ) / sum(b.count for b in bins)
    assert calibration_error(trained.held_out.challenger) == pytest.approx(expected)


def test_the_rules_stay_champion_until_a_person_approves_the_proposed_challenger(
    make_seeded: SeededFactory, trained: TrainedChallenger
) -> None:
    with with_challenger(make_seeded, passing(trained)) as (seeded, challenger):
        with pytest.raises(versions.NotProposed):  # in shadow: nothing to approve yet
            versions.approve(seeded.session, challenger.version, "planning")

        proposed = propose(seeded.session, challenger, RULE)
        assert proposed.status == "proposed"
        seeded.issue_until(1)
        assert {s.model_version for s in scores(seeded.session, 1)} == {PUBLISHED_VERSION}
        assert versions.champion(seeded.session).id == PUBLISHED_VERSION

        versions.approve(seeded.session, challenger.version, "planning")
        assert versions.champion(seeded.session).id == challenger.version
        seeded.issue_until(2)

        ranked = scores(seeded.session, 2)
        assert {s.model_version for s in ranked} == {challenger.version}
        assert all(s.factors["model"]["model_version"] == challenger.version for s in ranked)
        assert all(s.risk == pytest.approx(s.p_fail * s.consequence) for s in ranked)
        assert not shadow_scores(seeded.session, 2)  # the champion is not its own shadow

        log = seeded.session.exec(select(AuditEvent).order_by(col(AuditEvent.id))).all()
        types = [e.type for e in log]
        assert types.index(PROPOSED_EVENT) < types.index(versions.APPROVED_EVENT)
        approval = next(e for e in log if e.type == versions.APPROVED_EVENT)
        assert approval.actor == "human"


def test_the_app_loads_the_saved_challenger_and_scores_in_shadow(
    client: TestClient,
) -> None:
    body = client.get("/challenger").json()
    assert body["model_version"]["kind"] == "challenger"
    assert body["model_version"]["status"] == "shadow"
    assert body["model_version"]["in_use"] is False
    assert body["promotion"]["storm"] == "Storm Delta"
    assert {c["name"] for c in body["promotion"]["criteria"]} == {
        "brier_improvement",
        "top_capture_gain",
        "calibration_error",
    }

    # Under 2 seconds with shadow scoring: test_storm_map times every advance with this model.
    for _ in range(3):
        assert client.post("/advisories/next").status_code == 200

    engine: Any = client.app.state.engine  # type: ignore[attr-defined]
    with Session(engine) as session:
        assert len(shadow_scores(session, 3)) == ASSETS
        assert {s.model_version for s in scores(session, 3)} == {PUBLISHED_VERSION}


def test_proposing_through_the_api_follows_the_rule_and_approval_is_the_model_version_path(
    client: TestClient,
) -> None:
    status = client.get("/challenger").json()
    version_id = status["model_version"]["id"]

    refused = client.post(f"/model-versions/{version_id}/approve", json={"role": "planning"})
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "not_proposed"

    assert status["promotion"]["passed"]  # the saved challenger passes on Storm Delta
    response = client.post("/challenger/propose")
    assert response.status_code == 200
    assert response.json()["status"] == "proposed"
    assert client.post("/challenger/propose").json()["error"]["code"] == "already_proposed"
    approved = client.post(f"/model-versions/{version_id}/approve", json={"role": "planning"})
    assert approved.json()["in_use"] is True


def test_without_a_saved_challenger_the_app_runs_without_shadow_scoring(tmp_path: Path) -> None:
    settings = settings_in(tmp_path).model_copy(
        update={"challenger_model_path": tmp_path / "missing.pkl"}
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/challenger").status_code == 404
        assert client.post("/challenger/propose").status_code == 404
        assert client.post("/advisories/next").status_code == 200
        versions_listed = client.get("/model-versions").json()
        assert [v["kind"] for v in versions_listed] == ["curves"]


def test_a_later_approval_replaces_the_champion_and_the_audit_names_it(
    make_seeded: SeededFactory, trained: TrainedChallenger
) -> None:
    """The latest approval wins, of either kind: approving calibrated curves after the
    challenger makes the rules champion again, says so in the audit log, and the displaced
    challenger goes back to scoring in shadow."""
    with with_challenger(make_seeded, passing(trained)) as (seeded, challenger):
        propose(seeded.session, challenger, RULE)
        versions.approve(seeded.session, challenger.version, "planning")
        seeded.issue_until(1)
        assert {s.model_version for s in scores(seeded.session, 1)} == {challenger.version}

        calibrated = calibration.run(seeded.session, SCORING).proposed
        assert calibrated.id is not None
        versions.approve(seeded.session, calibrated.id, "director")
        assert versions.champion(seeded.session).id == calibrated.id
        seeded.issue_until(2)

        assert {s.model_version for s in scores(seeded.session, 2)} == {calibrated.id}
        assert {s.model_version for s in shadow_scores(seeded.session, 2)} == {challenger.version}
        approvals = seeded.session.exec(
            select(AuditEvent)
            .where(AuditEvent.type == versions.APPROVED_EVENT)
            .order_by(col(AuditEvent.id))
        ).all()
        assert [e.payload["replaces"] for e in approvals] == [PUBLISHED_VERSION, challenger.version]
        assert f"replaces model version {challenger.version}" in approvals[-1].summary


def test_the_challenger_is_registered_once(
    seeded: SeededScenario, trained: TrainedChallenger
) -> None:
    challenger = register(seeded.session, trained)
    assert register(seeded.session, trained).version == challenger.version


def test_proposing_a_challenger_that_fails_the_rule_answers_409_naming_the_criteria(
    tmp_path: Path,
) -> None:
    strict = tmp_path / "models.yaml"
    config = MODELS.model_copy(
        update={"promotion": RULE.model_copy(update={"min_brier_improvement": 1.0})}
    )
    strict.write_text(yaml.safe_dump(config.model_dump(mode="json")))
    settings = settings_in(tmp_path).model_copy(update={"models_config_path": strict})
    with TestClient(create_app(settings)) as client:
        status = client.get("/challenger").json()
        assert not status["promotion"]["passed"]

        response = client.post("/challenger/propose")
        assert response.status_code == 409
        error = response.json()["error"]
        assert error["code"] == "not_promotable"
        assert "brier_improvement" in error["message"]
        assert client.get("/challenger").json()["model_version"]["status"] == "shadow"
