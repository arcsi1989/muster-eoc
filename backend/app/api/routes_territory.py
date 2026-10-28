from dataclasses import asdict

from fastapi import APIRouter
from sqlmodel import col, select

from app.api.schemas import (
    AssetOut,
    CoastlineOut,
    FacilityOut,
    LineageOut,
    PointOut,
    StagingAreaOut,
)
from app.deps import SessionDep
from app.errors import NotFound
from app.ingest.lineage import lineage_report
from app.models import Asset, Coastline, Facility, StagingArea

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
    row = session.get(Coastline, 1)
    if row is None:
        raise NotFound("coastline not loaded")
    return CoastlineOut(
        coastline=[PointOut(x_km=x, y_km=y) for x, y in row.coastline],
        land=[PointOut(x_km=x, y_km=y) for x, y in row.land],
    )


@router.get("/lineage", response_model=list[LineageOut])
def list_lineage(session: SessionDep) -> list[LineageOut]:
    """Every loaded gold file with its hash, row counts and rejected rows."""
    return [LineageOut.model_validate(asdict(entry)) for entry in lineage_report(session)]
