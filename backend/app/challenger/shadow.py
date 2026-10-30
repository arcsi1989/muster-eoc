"""What the stored shadow scores say beside the champion's (CR-03 C2): the challenger's view of an
asset, and the assets it ranks in the top N that the champion does not. Read only: shadow scores
never drive the ranking, the playbook check or the package."""

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, col, select

from app.models import Asset, ShadowScore
from app.replay import service


@dataclass(frozen=True)
class ShadowView:
    asset_id: str
    model_version: int
    rank: int
    p_fail: float
    top_features: list[dict[str, Any]]  # the largest contributions first


@dataclass(frozen=True)
class Disagreement:
    asset_name: str
    challenger: ShadowView
    champion_rank: int
    champion_p_fail: float


def _view(score: ShadowScore, shown: int) -> ShadowView:
    return ShadowView(
        asset_id=score.asset_id,
        model_version=score.model_version,
        rank=score.rank,
        p_fail=score.p_fail,
        top_features=score.factors["features"][:shown],
    )


def view(
    session: Session, asset_id: str, advisory_no: int, model_version: int, shown: int
) -> ShadowView | None:
    """The challenger's score of an asset at an advisory; None when it did not run in shadow."""
    score = session.get(ShadowScore, (asset_id, advisory_no, model_version))
    return None if score is None else _view(score, shown)


def disagreements(
    session: Session, advisory_no: int, model_version: int, top_n: int, shown: int
) -> list[Disagreement]:
    """The assets the challenger ranks in its top N and the champion does not, by the
    challenger's rank; empty when it did not run in shadow (it is the champion)."""
    champion = {s.asset_id: s for s in service.ranked_scores(session, advisory_no)}
    query = (
        select(ShadowScore, Asset)
        .join(Asset, col(Asset.id) == col(ShadowScore.asset_id))
        .where(
            ShadowScore.advisory_no == advisory_no,
            ShadowScore.model_version == model_version,
            ShadowScore.rank <= top_n,
        )
        .order_by(col(ShadowScore.rank))
    )
    return [
        Disagreement(
            asset_name=asset.name,
            challenger=_view(s, shown),
            champion_rank=champion[s.asset_id].rank,
            champion_p_fail=champion[s.asset_id].p_fail,
        )
        for s, asset in session.exec(query)
        if champion[s.asset_id].rank > top_n
    ]
