"""The territory's static map layers: the coastline and the districts with their boundaries."""

from dataclasses import dataclass

from sqlmodel import Session, col, select

from muster.errors import NotFound
from muster.geo import Point, boundary_inland
from muster.models import Coastline, District


def coastline(session: Session) -> Coastline:
    row = session.get(Coastline, 1)
    if row is None:
        raise NotFound("coastline not loaded")
    return row


@dataclass(frozen=True)
class DistrictLayer:
    name: str
    west_km: float
    east_km: float
    label: Point  # where the maps write its name
    boundary: list[Point]  # where it meets its western neighbour; [] for the westernmost


def district_layers(session: Session) -> list[DistrictLayer]:
    """The districts west to east, each with its label and its boundary with its western
    neighbour, drawn from the coast to the land's northern edge."""
    coast = coastline(session)
    line = [(x, y) for x, y in coast.coastline]
    land = [(x, y) for x, y in coast.land]
    districts = session.exec(select(District).order_by(col(District.west_km))).all()
    return [
        DistrictLayer(
            name=d.name,
            west_km=d.west_km,
            east_km=d.east_km,
            label=(d.label_x_km, d.label_y_km),
            boundary=boundary_inland(d.west_km, line, land) if i > 0 else [],
        )
        for i, d in enumerate(districts)
    ]
