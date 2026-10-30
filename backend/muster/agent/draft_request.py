"""Assembles what the draft may see, and so cite: package items, changes, top assets,
retrieved clauses; and, quoted and never citable, the notes of blocked field tasks."""

from sqlmodel import Session, col, select

from muster import advisory_context
from muster.llm.schemas import DraftItem, DraftRequest, FieldNote, RetrievedClause, TopAsset
from muster.models import Advisory, Finding, PackageItem, Score
from muster.network import load_network
from muster.playbook.service import Playbook
from muster.replay.diff import AdvisoryChanges
from muster.scoring_config import DraftConfig

EVENT = "event"


def draft_request(
    session: Session,
    advisory: Advisory,
    playbook: Playbook,
    changes: AdvisoryChanges,
    config: DraftConfig,
) -> DraftRequest:
    """The request; a grounded draft cites only what it shows."""
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
    return DraftRequest(
        advisory_no=advisory.advisory_no,
        hours_to_landfall=advisory.hours_to_landfall,
        activation_level=advisory_context.at(session, playbook.levels, advisory).activation_level,
        changes=changes,
        items=draft_items,
        top_assets=[
            TopAsset(s.asset_id, network.assets[s.asset_id].name, s.rank, round(s.p_fail, 2))
            for s in top
        ],
        clauses=[RetrievedClause(c.id, c.title, c.text) for c in retrieved],
        field_reports=[
            FieldNote(i.rule_id, i.entity_id, i.blocked_note) for i in items if i.blocked_note
        ],
    )
