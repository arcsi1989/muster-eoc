from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, select

from app.api.schemas import AssetOut, CoastlineOut, PointOut
from app.deps import get_session
from app.errors import NotFound
from app.models import Asset, Coastline

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/assets", response_model=list[AssetOut])
def list_assets(session: SessionDep) -> list[AssetOut]:
    assets = session.exec(select(Asset).order_by(col(Asset.id))).all()
    return [AssetOut.model_validate(a, from_attributes=True) for a in assets]


@router.get("/coastline", response_model=CoastlineOut)
def get_coastline(session: SessionDep) -> CoastlineOut:
    row = session.get(Coastline, 1)
    if row is None:
        raise NotFound("coastline not loaded")
    return CoastlineOut(
        coastline=[PointOut(x_km=x, y_km=y) for x, y in row.coastline],
        land=[PointOut(x_km=x, y_km=y) for x, y in row.land],
    )
