"""Confidence in an asset's score (plan section 3): a data quality flag, never part of the score."""

from datetime import date
from typing import Literal

Confidence = Literal["high", "medium", "low"]


def confidence(
    elevation_imputed: bool,
    last_inspection: date,
    as_of: date,
    stale_years: float,
    imputation_neighbours: int,
) -> tuple[Confidence, list[str]]:
    """High by default; medium for a stale inspection; low for an imputed elevation."""
    reasons = []
    if elevation_imputed:
        reasons.append(
            f"elevation missing: imputed from the {imputation_neighbours} nearest assets"
        )
    if (as_of - last_inspection).days > stale_years * 365:
        reasons.append(f"last inspection over {stale_years:g} years ago ({last_inspection})")
    level: Confidence = "low" if elevation_imputed else "medium" if reasons else "high"
    return level, reasons
