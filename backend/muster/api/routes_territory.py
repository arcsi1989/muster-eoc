from dataclasses import asdict

from fastapi import APIRouter
from sqlmodel import col, select

from muster import territory
from muster.api.schemas import (
    AssetOut,
    CoastlineOut,
    DistrictOut,
    FacilityOut,
    LineageOut,
    PointOut,
    StagingAreaOut,
)
from muster.deps import SessionDep
from muster.ingest.lineage import lineage_report
from muster.models import Asset, Facility, StagingArea

router = APIRouter()


@router.get("/assets", response_model=list[AssetOut])
def list_assets(session: SessionDep) -> list[AssetOut]:
    assets = session.exec(select(Asset).order_by(col(Asset.id))).all()
    return [AssetOut.model_validate(a, from_attributes=True) for a in assets]


@router.get("/facilities", response_model=list[FacilityOut])
def list_facilities(session: SessionDep) -> list[FacilityOut]:
    facilities = session.exec(select(Facility).order_by(col(Facility.id))).all()
    return [FacilityOut.model_validate(f, from_attributes=True) for f in facilities]


@router.get("/staging-areas", response_model=list[StagingAreaOut])
def list_staging_areas(session: SessionDep) -> list[StagingAreaOut]:
    areas = session.exec(select(StagingArea).order_by(col(StagingArea.id))).all()
    return [StagingAreaOut.model_validate(s, from_attributes=True) for s in areas]


@router.get("/coastline", response_model=CoastlineOut)
def get_coastline(session: SessionDep) -> CoastlineOut:
    row = territory.coastline(session)
    return CoastlineOut(
        coastline=[PointOut(x_km=x, y_km=y) for x, y in row.coastline],
        land=[PointOut(x_km=x, y_km=y) for x, y in row.land],
    )


@router.get("/districts", response_model=list[DistrictOut])
def list_districts(session: SessionDep) -> list[DistrictOut]:
    return [
        DistrictOut(
            name=d.name,
            west_km=d.west_km,
            east_km=d.east_km,
            label=PointOut(x_km=d.label[0], y_km=d.label[1]),
            boundary=[PointOut(x_km=x, y_km=y) for x, y in d.boundary],
        )
        for d in territory.district_layers(session)
    ]


@router.get("/lineage", response_model=list[LineageOut])
def list_lineage(session: SessionDep) -> list[LineageOut]:
    """Every loaded gold file with its hash, row counts and rejected rows."""
    return [LineageOut.model_validate(asdict(entry)) for entry in lineage_report(session)]
