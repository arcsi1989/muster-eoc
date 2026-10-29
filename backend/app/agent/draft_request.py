"""Assembles what the draft may see and cite: package items, top assets, retrieved clauses."""

from typing import Any

from sqlmodel import Session, col, select

from app.llm.schemas import DraftItem, DraftRequest, Grounding, RetrievedClause
from app.models import Advisory, Finding, PackageItem, Score
from app.network import load_network
from app.playbook.activation import activation_level
from app.playbook.service import Playbook
from app.scoring_config import DraftConfig

EVENT = "event"


def draft_request(
    session: Session,
    advisory: Advisory,
    playbook: Playbook,
    changes: dict[str, Any],
    config: DraftConfig,
) -> tuple[DraftRequest, Grounding]:
    """The request, plus the clause and asset IDs a grounded draft may cite."""
    network = load_network(session)
    items = session.exec(
        select(PackageItem)
        .where(PackageItem.advisory_no == advisory.advisory_no)
        .order_by(col(PackageItem.id))
    ).all()
    findings = {
        f.id: f
        for f in session.exec(select(Finding).where(Finding.advisory_no == advisory.advisory_no))
    }
    top = session.exec(
        select(Score)
        .where(Score.advisory_no == advisory.advisory_no, Score.rank <= config.top_assets)
        .order_by(col(Score.rank))
    ).all()
    titles = {r.id: r.title for r in playbook.rulebook.rules}

    def entity_type(entity_id: str) -> str:
        asset = network.assets.get(entity_id)
        return asset.type.replace("_", " ") if asset else ""

    queries = sorted({f"{titles[i.rule_id]} {entity_type(i.entity_id)}" for i in items})
    retrieved = playbook.index.search(
        queries,
        advisory.hours_to_landfall,
        config.retrieval_per_query,
        config.retrieval_max_clauses,
    )
    draft_items = [
        DraftItem(
            rule_id=i.rule_id,
            entity_id=i.entity_id,
            entity_is_citable=i.entity_id != EVENT,
            kind=i.kind,
            action=i.proposed_action,
            cites=list(findings[i.finding_id].cites),
            overdue=findings[i.finding_id].overdue,
        )
        for i in items
    ]
    request = DraftRequest(
        advisory_no=advisory.advisory_no,
        hours_to_landfall=advisory.hours_to_landfall,
        activation_level=activation_level(advisory.hours_to_landfall, playbook.levels),
        changes=changes,
        items=draft_items,
        top_assets=[
            {
                "id": s.asset_id,
                "name": network.assets[s.asset_id].name,
                "rank": s.rank,
                "p_fail": round(s.p_fail, 2),
            }
            for s in top
        ],
        clauses=[RetrievedClause(c.id, c.title, c.text) for c in retrieved],
        template_top_assets=config.template_top_assets,
    )
    allowed_clauses = {c for i in draft_items for c in i.cites} | {c.id for c in retrieved}
    allowed_assets = {i.entity_id for i in draft_items if i.entity_is_citable}
    allowed_assets |= {s.asset_id for s in top}
    return request, Grounding(allowed_clauses, allowed_assets)
