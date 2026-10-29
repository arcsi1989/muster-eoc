"""Alerts on sudden changes in the ranking (plan section 3)."""

from dataclasses import dataclass
from typing import Literal

from app.scoring_config import AlertConfig

AlertKind = Literal["risk_threshold", "top_n_entry", "rank_jump"]


@dataclass(frozen=True)
class RankedRisk:
    asset_id: str
    risk: float
    rank: int


@dataclass(frozen=True)
class RaisedAlert:
    asset_id: str
    kind: AlertKind
    message: str


def raise_alerts(
    current: list[RankedRisk], previous: dict[str, RankedRisk], config: AlertConfig, top_n: int
) -> list[RaisedAlert]:
    """Risk crossing the threshold, entering the top N, or rising rank_jump+ places into the top
    rank_jump_within. At the first advisory (no previous) only threshold crossings are raised: the
    top N is initial."""
    alerts = []
    for now in current:
        before = previous.get(now.asset_id)
        if now.risk >= config.risk_threshold and (
            before is None or before.risk < config.risk_threshold
        ):
            alerts.append(
                RaisedAlert(
                    now.asset_id,
                    "risk_threshold",
                    f"Risk {now.risk:,.0f} crossed the threshold of {config.risk_threshold:,.0f}",
                )
            )
        if before is None:
            continue
        if now.rank <= top_n < before.rank:
            alerts.append(
                RaisedAlert(
                    now.asset_id,
                    "top_n_entry",
                    f"Entered the top {top_n} (rank {before.rank} → {now.rank})",
                )
            )
        if before.rank - now.rank >= config.rank_jump and now.rank <= config.rank_jump_within:
            alerts.append(
                RaisedAlert(
                    now.asset_id,
                    "rank_jump",
                    f"Rose {before.rank - now.rank} places (rank {before.rank} → {now.rank})",
                )
            )
    return alerts
