"""Consequence of an asset failing, in customer-equivalents (plan section 3, one hop)."""

from dataclasses import dataclass, field

from app.network import Network


@dataclass(frozen=True)
class DownstreamAsset:
    id: str
    customers: float  # its customers divided by the number of assets that feed it
    feeders: int


@dataclass(frozen=True)
class WeightedFacility:
    id: str
    type: str
    weight: float  # its policy weight divided by the number of assets that feed it
    feeders: int


@dataclass(frozen=True)
class Consequence:
    own_customers: int
    downstream_assets: list[DownstreamAsset] = field(default_factory=list)
    facilities: list[WeightedFacility] = field(default_factory=list)

    @property
    def total(self) -> float:
        return (
            self.own_customers
            + sum(a.customers for a in self.downstream_assets)
            + sum(f.weight for f in self.facilities)
        )


def consequence(asset_id: str, network: Network, weights: dict[str, float]) -> Consequence:
    """Own customers, plus the customers of directly dependent assets, plus the policy weight of
    each directly fed critical facility (the treatment plant counts as one), one hop.

    A dependent asset or facility with several feeders shares its customers and weight among
    them, so each customer is counted once across the network (docs/decisions.md)."""

    def feeders(target_id: str) -> int:
        return max(1, len(network.fed_by.get(target_id, [])))

    downstream = sorted(network.direct_assets(asset_id), key=lambda a: a.id)
    facilities = [
        WeightedFacility(f.id, f.type, weights.get(f.type, 0.0) / feeders(f.id), feeders(f.id))
        for f in network.direct_facilities(asset_id)
    ]
    facilities += [
        WeightedFacility(
            a.id,
            "treatment_plant",
            weights.get("treatment_plant", 0.0) / feeders(a.id),
            feeders(a.id),
        )
        for a in network.treatment_plants_fed(asset_id)
    ]
    return Consequence(
        own_customers=network.assets[asset_id].customers_served,
        downstream_assets=[
            DownstreamAsset(a.id, a.customers_served / feeders(a.id), feeders(a.id))
            for a in downstream
        ],
        facilities=sorted(facilities, key=lambda f: f.id),
    )
