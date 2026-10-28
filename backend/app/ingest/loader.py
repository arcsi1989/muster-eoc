import json
from pathlib import Path

from pydantic import TypeAdapter
from sqlmodel import Session

from app.ingest.contracts import (
    AdvisoryRecord,
    AssetRecord,
    CoastlineFile,
    LineStringGeometry,
    PolygonGeometry,
)
from app.models import Advisory, Asset, Coastline, ScenarioState


class GoldDataMissing(RuntimeError):
    pass


def _read_json(path: Path) -> object:
    if not path.is_file():
        raise GoldDataMissing(f"{path} not found; run `make data` first")
    return json.loads(path.read_text())


def load_gold(session: Session, data_dir: Path) -> None:
    """Validates the gold files against their contracts and loads them into the database."""
    assets = TypeAdapter(list[AssetRecord]).validate_python(_read_json(data_dir / "assets.json"))
    coastline = CoastlineFile.model_validate(_read_json(data_dir / "coastline.geojson"))
    advisory_paths = sorted((data_dir / "advisories").glob("adv_*.json"))
    if not advisory_paths:
        raise GoldDataMissing(f"no advisories in {data_dir / 'advisories'}; run `make data` first")
    advisories = [AdvisoryRecord.model_validate(_read_json(p)) for p in advisory_paths]

    session.add_all(Asset(**a.model_dump()) for a in assets)
    session.add_all(
        Advisory(
            advisory_no=a.advisory_no,
            issued_at=a.issued_at,
            hours_to_landfall=a.hours_to_landfall,
            landfall_x_km=a.landfall.x_km,
            landfall_y_km=a.landfall.y_km,
            peak_surge_m=a.peak_surge_m,
            track=[p.model_dump() for p in a.track],
            cone_radius_km=a.cone_radius_km,
        )
        for a in advisories
    )
    line = next(
        f.geometry for f in coastline.features if isinstance(f.geometry, LineStringGeometry)
    )
    land = next(f.geometry for f in coastline.features if isinstance(f.geometry, PolygonGeometry))
    session.add(
        Coastline(
            coastline=[list(c) for c in line.coordinates],
            land=[list(c) for c in land.coordinates[0]],
        )
    )
    session.add(ScenarioState())
    session.commit()
