"""Read side of the data quality report: loaded files with their rejected rows."""

from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, col, select

from app.ingest.loader import RowIssue
from app.models import Lineage, QualityIssue


@dataclass(frozen=True)
class FileLineage:
    file: str
    sha256: str
    loaded_at: datetime
    rows_ok: int
    rows_rejected: int
    issues: list[RowIssue]


def lineage_report(session: Session) -> list[FileLineage]:
    issues: dict[str, list[RowIssue]] = {}
    for issue in session.exec(select(QualityIssue).order_by(col(QualityIssue.row))):
        issues.setdefault(issue.file, []).append(RowIssue(issue.row, issue.record_id, issue.reason))
    return [
        FileLineage(
            file=entry.file,
            sha256=entry.sha256,
            loaded_at=entry.loaded_at,
            rows_ok=entry.rows_ok,
            rows_rejected=entry.rows_rejected,
            issues=issues.get(entry.file, []),
        )
        for entry in session.exec(select(Lineage).order_by(col(Lineage.file)))
    ]
