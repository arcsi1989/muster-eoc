"""Why an asset ranks where it does at an advisory: the stored factors plus its dependencies."""

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session

from muster.errors import NotFound
from muster.models import Asset, Exposure, Score
from muster.network import load_network
from muster.replay import service


@dataclass(frozen=True)
class DependencyLink:
    id: str
    kind: str  # asset | facility
    name: str


@dataclass(frozen=True)
class Explanation:
    asset: Asset
    score: Score
    exposure: Exposure
    feeds: list[DependencyLink]
    fed_by: list[DependencyLink]

    @property
    def factors(self) -> dict[str, Any]:
        return self.score.factors

    def consequence_for_model(self) -> dict[str, Any]:
        """The consequence components a model may be shown (CR-03 C1): the customers of the
        assets it feeds as one number, not those assets (the dependency graph is restricted),
        and the critical facilities it feeds directly, the reason for their weight."""
        c = self.factors["consequence"]
        return {
            "own_customers": c["own_customers"],
            "downstream_customers": sum(a["customers"] for a in c["downstream_assets"]),
            "facilities": [
                {"id": f["id"], "type": f["type"], "weight": f["weight"]} for f in c["facilities"]
            ],
            "total": c["total"],
        }


def explain_asset(session: Session, asset_id: str, advisory_no: int) -> Explanation:
    network = load_network(session)
    if asset_id not in network.assets:
        raise NotFound(f"unknown asset {asset_id}")
    score = service.score(session, asset_id, advisory_no)
    exposure = service.exposure(session, asset_id, advisory_no)
    if exposure is None:
        raise NotFound(f"asset {asset_id} has no exposure at advisory {advisory_no}")

    def links(ids: list[str]) -> list[DependencyLink]:
        found = []
        for entity_id in ids:
            described = network.describe(entity_id)
            if described is not None:
                found.append(DependencyLink(entity_id, *described))
        return found

    return Explanation(
        asset=network.assets[asset_id],
        score=score,
        exposure=exposure,
        feeds=links([f.to_id for f in network.feeds.get(asset_id, [])]),
        fed_by=links(network.fed_by.get(asset_id, [])),
    )
