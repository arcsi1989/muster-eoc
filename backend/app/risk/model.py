"""The risk model interface (PRD PR4): what turns an asset's exposure to an advisory into a
failure probability. The rule-based score (fragility curves) and the challenger both implement
it. The approved champion drives the ranking; a challenger in shadow is only stored."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.hazard.ensemble import SiteExposure
from app.models import Asset
from app.network import Network


@dataclass(frozen=True)
class AssetFeatures:
    """What a risk model may know about an asset at an advisory, before the storm."""

    exposure: SiteExposure
    asset: Asset
    age_years: int
    critical_dependency: bool  # it supplies a critical facility, directly or one hop on


def asset_features(
    exposures: Sequence[SiteExposure], network: Network, age_year: int
) -> list[AssetFeatures]:
    """The features of every asset exposed; ages are counted to `age_year`."""
    return [
        AssetFeatures(
            exposure=e,
            asset=network.assets[e.site_id],
            age_years=age_year - network.assets[e.site_id].install_year,
            critical_dependency=bool(network.feeds_facility_types(e.site_id)),
        )
        for e in exposures
    ]


@dataclass(frozen=True)
class Prediction:
    asset_id: str
    p_fail: float
    factors: dict[str, Any]  # what drove p_fail, in the model's own terms
    version: int  # the model version that predicted it


class RiskModel(Protocol):
    @property
    def version(self) -> int: ...

    def predict(self, assets: Sequence[AssetFeatures]) -> list[Prediction]:
        """One prediction per asset, in the order given."""
        ...
