"""The supply network: which asset feeds which asset or critical facility."""

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import Asset, Dependency, Facility


@dataclass(frozen=True)
class Feed:
    to_id: str
    to_kind: str  # asset | facility


@dataclass(frozen=True)
class Network:
    assets: dict[str, Asset]
    facilities: dict[str, Facility]
    feeds: dict[str, list[Feed]]  # from asset id -> what it feeds directly
    fed_by: dict[str, list[str]]  # asset or facility id -> the assets that feed it

    def direct_assets(self, asset_id: str) -> list[Asset]:
        return [self.assets[f.to_id] for f in self.feeds.get(asset_id, []) if f.to_kind == "asset"]

    def direct_facilities(self, asset_id: str) -> list[Facility]:
        return [
            self.facilities[f.to_id]
            for f in self.feeds.get(asset_id, [])
            if f.to_kind == "facility"
        ]

    def treatment_plants_fed(self, asset_id: str) -> list[Asset]:
        """Directly fed treatment plants: they count as critical facilities (plan section 2.1)."""
        return [a for a in self.direct_assets(asset_id) if a.type == "treatment_plant"]

    def treatment_plants_reached(self, asset_id: str) -> list[str]:
        """Treatment plants fed directly or one hop through a pumping station (plan 2.4)."""
        reached = [a.id for a in self.treatment_plants_fed(asset_id)]
        for station in self.direct_assets(asset_id):
            if station.type == "pump_station":
                reached += [a.id for a in self.treatment_plants_fed(station.id)]
        return sorted(set(reached))

    def serves_treatment_plant(self, asset_id: str) -> bool:
        """A pumping station that feeds a treatment plant (P-4.3, P-4.5)."""
        return self.assets[asset_id].type == "pump_station" and bool(
            self.treatment_plants_fed(asset_id)
        )

    def describe(self, entity_id: str) -> tuple[str, str] | None:
        """(kind, name) of an asset or facility; None if unknown."""
        if entity_id in self.assets:
            return "asset", self.assets[entity_id].name
        if entity_id in self.facilities:
            return "facility", self.facilities[entity_id].name
        return None

    def feeds_facility_types(self, asset_id: str) -> set[str]:
        """Critical facility types the asset supplies: directly, or one hop through a pumping
        station to the treatment plant (plan section 2.4). The treatment plant counts as one."""
        types = {f.type for f in self.direct_facilities(asset_id)}
        if self.treatment_plants_reached(asset_id):
            types.add("treatment_plant")
        return types


def load_network(session: Session) -> Network:
    feeds: dict[str, list[Feed]] = {}
    fed_by: dict[str, list[str]] = {}
    for dep in session.exec(select(Dependency)):
        feeds.setdefault(dep.from_id, []).append(Feed(dep.to_id, dep.to_kind))
        fed_by.setdefault(dep.to_id, []).append(dep.from_id)
    return Network(
        assets={a.id: a for a in session.exec(select(Asset))},
        facilities={f.id: f for f in session.exec(select(Facility))},
        feeds=feeds,
        fed_by=fed_by,
    )
