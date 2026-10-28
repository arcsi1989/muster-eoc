"""Loads the gold files into the database, row by row against their contracts.

Rows that break a contract (or reference an unknown entity) are rejected into the quality report
instead of failing the load; every file gets a lineage row with its hash and row counts. A file
that is missing, or whose single object breaks its contract, stops the load: the app can't run
without it.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError
from sqlmodel import Session

from app.ingest.contracts import (
    AdvisoryRecord,
    AssetRecord,
    CoastlineFile,
    Contract,
    DependencyRecord,
    FacilityRecord,
    FragilityCurveRecord,
    InitialStateFile,
    LineStringGeometry,
    PolygonGeometry,
    StagingAreaRecord,
)
from app.models import (
    Advisory,
    Asset,
    Coastline,
    Dependency,
    Facility,
    FragilityCurve,
    Lineage,
    OpState,
    QualityIssue,
    ScenarioState,
    StagingArea,
)

INITIAL_STATE_SOURCE = "initial_state"


class GoldDataMissing(RuntimeError):
    pass


@dataclass(frozen=True)
class RowIssue:
    row: int  # index in the file
    record_id: str | None
    reason: str


@dataclass
class FileReport:
    file: str
    sha256: str
    rows_ok: int = 0
    issues: list[RowIssue] = field(default_factory=list)

    def reject(self, row: int, record_id: str | None, reason: str) -> None:
        """Moves a row that passed its contract into the issues (duplicate, dangling reference)."""
        self.issues.append(RowIssue(row, record_id, reason))
        self.rows_ok -= 1


def _reason(error: ValidationError) -> str:
    first = error.errors()[0]
    where = ".".join(str(p) for p in first["loc"]) or "row"
    return f"{where}: {first['msg']}"


class GoldLoader:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.reports: list[FileReport] = []

    def _read(self, relative: str) -> tuple[Any, FileReport]:
        path = self.data_dir / relative
        if not path.is_file():
            raise GoldDataMissing(f"{path} not found; run `make data` first")
        raw = path.read_bytes()
        report = FileReport(file=relative, sha256=hashlib.sha256(raw).hexdigest())
        self.reports.append(report)
        return json.loads(raw), report

    def rows[C: Contract](
        self, relative: str, contract: type[C]
    ) -> tuple[list[tuple[int, C]], FileReport]:
        """Valid rows with their index in the file, and the file's report."""
        data, report = self._read(relative)
        valid: list[tuple[int, C]] = []
        for index, row in enumerate(data):
            record_id = row.get("id") if isinstance(row, dict) else None
            try:
                valid.append((index, contract.model_validate(row)))
            except ValidationError as error:
                report.issues.append(RowIssue(index, record_id, _reason(error)))
        report.rows_ok = len(valid)
        return valid, report

    def single[C: Contract](self, relative: str, contract: type[C]) -> C:
        data, report = self._read(relative)
        try:
            record = contract.model_validate(data)
        except ValidationError as error:
            raise GoldDataMissing(f"{relative} breaks its contract: {_reason(error)}") from error
        report.rows_ok = 1
        return record


class HasId(Protocol):
    id: str


def _unique_by_id[R: HasId](
    rows: list[tuple[int, R]], report: FileReport, seen: set[str]
) -> list[R]:
    kept: list[R] = []
    for index, record in rows:
        if record.id in seen:
            report.reject(index, record.id, f"id: duplicate id {record.id}")
        else:
            seen.add(record.id)
            kept.append(record)
    return kept


def load_gold(session: Session, data_dir: Path) -> None:
    """Validates the gold files against their contracts and loads them into the database."""
    loader = GoldLoader(data_dir)
    now = datetime.now(UTC)

    asset_ids: set[str] = set()
    assets: list[AssetRecord] = []
    for relative in ("assets.json", "assets_rejected_example.json"):
        records, report = loader.rows(relative, AssetRecord)
        assets += _unique_by_id(records, report, asset_ids)

    facility_records, facility_report = loader.rows("critical_facilities.json", FacilityRecord)
    facility_ids: set[str] = set()
    facilities = _unique_by_id(facility_records, facility_report, facility_ids)

    staging_records, staging_report = loader.rows("staging_areas.json", StagingAreaRecord)
    staging_ids: set[str] = set()
    staging = _unique_by_id(staging_records, staging_report, staging_ids)

    dependency_records, dependency_report = loader.rows("dependencies.json", DependencyRecord)
    dependencies: list[DependencyRecord] = []
    for index, dep in dependency_records:
        targets = asset_ids if dep.to_kind == "asset" else facility_ids
        if dep.from_id not in asset_ids:
            dependency_report.reject(index, None, f"from_id: unknown asset {dep.from_id}")
        elif dep.to_id not in targets:
            dependency_report.reject(index, None, f"to_id: unknown {dep.to_kind} {dep.to_id}")
        else:
            dependencies.append(dep)

    curve_rows, _ = loader.rows("fragility_curves.json", FragilityCurveRecord)
    curves = [curve for _, curve in curve_rows]
    initial_state = loader.single("initial_state.json", InitialStateFile)
    coastline = loader.single("coastline.geojson", CoastlineFile)

    advisory_paths = sorted((data_dir / "advisories").glob("adv_*.json"))
    if not advisory_paths:
        raise GoldDataMissing(f"no advisories in {data_dir / 'advisories'}; run `make data` first")
    advisories = [loader.single(f"advisories/{p.name}", AdvisoryRecord) for p in advisory_paths]

    session.add_all(Asset(**a.model_dump()) for a in assets)
    session.add_all(Facility(**f.model_dump()) for f in facilities)
    session.add_all(StagingArea(**s.model_dump()) for s in staging)
    session.add_all(Dependency(**d.model_dump()) for d in dependencies)
    session.add_all(FragilityCurve(**c.model_dump()) for c in curves)

    known_entities = asset_ids | staging_ids
    session.add_all(
        OpState(entity=entity, key=key, value=value, set_by=INITIAL_STATE_SOURCE, set_at=now)
        for entity, flags in initial_state.entities.items()
        if entity in known_entities
        for key, value in flags.items()
    )
    session.add_all(
        OpState(entity="event", key=key, value=value, set_by=INITIAL_STATE_SOURCE, set_at=now)
        for key, value in initial_state.event.items()
    )

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

    for report in loader.reports:
        session.add(
            Lineage(
                file=report.file,
                sha256=report.sha256,
                loaded_at=now,
                rows_ok=report.rows_ok,
                rows_rejected=len(report.issues),
            )
        )
        session.add_all(
            QualityIssue(file=report.file, row=i.row, record_id=i.record_id, reason=i.reason)
            for i in report.issues
        )
    session.commit()
