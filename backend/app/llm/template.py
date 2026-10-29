"""Deterministic provider: the demo runs with no network (CLAUDE.md hard rule)."""

from app.llm.schemas import (
    DraftItem,
    DraftRequest,
    DraftResult,
    Paragraph,
    Section,
    SitrepDraft,
)


def _asset_ids(item: DraftItem) -> list[str]:
    return [item.entity_id] if item.entity_is_citable else []


class TemplateProvider:
    name = "template"
    model: str | None = None
    prompt_version: str | None = None

    def draft_sitrep(self, request: DraftRequest) -> DraftResult:
        situation = (
            f"Advisory {request.advisory_no}, {request.hours_to_landfall} h to landfall; "
            f"activation level {request.activation_level or 'none'}."
        )
        shift = request.changes.get("landfall_shift")
        if shift:
            distance = round(shift["distance_km"])
            situation += f" The forecast landfall moved {distance} km {shift['direction']}."
        named = request.top_assets[: request.template_top_assets]
        top = ", ".join(a["id"] for a in named)
        overview = [Paragraph(text=situation, clause_ids=[], asset_ids=[])]
        if top:
            overview.append(
                Paragraph(
                    text=f"Highest risk assets: {top}.",
                    clause_ids=[],
                    asset_ids=[a["id"] for a in named],
                )
            )
        conflicts = [
            Paragraph(
                text=f"Conflict at {i.entity_id}, citing {', '.join(i.cites)}: {i.action}",
                clause_ids=list(i.cites),
                asset_ids=_asset_ids(i),
            )
            for i in request.items
            if i.kind == "conflict"
        ]
        gaps = [
            Paragraph(
                text=f"{i.rule_id}{' (overdue)' if i.overdue else ''}: {i.action}.",
                clause_ids=[i.rule_id],
                asset_ids=_asset_ids(i),
            )
            for i in request.items
            if i.kind == "gap"
        ]
        sections = [Section(heading="Situation", paragraphs=overview)]
        if conflicts:
            sections.append(
                Section(heading="Conflicts for the Incident Commander", paragraphs=conflicts)
            )
        if gaps:
            sections.append(Section(heading="Playbook actions", paragraphs=gaps))
        return DraftResult(SitrepDraft(sections=sections), self.name, None, 0, {})
