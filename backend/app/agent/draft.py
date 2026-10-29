"""Draft situation report. Template version: deterministic, built from the findings and the
changes. Ticket 07 adds the LLM provider behind the same shape."""

from typing import Any

from app.models import Advisory, PackageItem

PROMPT_VERSION = "template-v1"


def template_draft(
    advisory: Advisory, level: str | None, changes: dict[str, Any], items: list[PackageItem]
) -> dict[str, Any]:
    gaps = [i for i in items if i.kind == "gap"]
    conflicts = [i for i in items if i.kind == "conflict"]
    shift = changes.get("landfall_shift")
    situation = (
        f"Advisory {advisory.advisory_no}, {advisory.hours_to_landfall} h to landfall; "
        f"activation level {level or 'none'}."
    )
    if shift:
        situation += (
            f" The forecast landfall moved {round(shift['distance_km'])} km {shift['direction']}."
        )
    paragraphs = [{"text": situation, "clause_ids": [], "asset_ids": []}]
    for item in conflicts:
        paragraphs.append(
            {
                "text": f"Conflict at {item.entity_id}: {item.proposed_action}",
                "clause_ids": [item.rule_id, "P-4.7", "P-8.2"],
                "asset_ids": [item.entity_id] if item.entity_id != "event" else [],
            }
        )
    for item in gaps:
        paragraphs.append(
            {
                "text": f"{item.rule_id}: {item.proposed_action}.",
                "clause_ids": [item.rule_id],
                "asset_ids": [item.entity_id]
                if item.entity_id not in ("event",) and not item.entity_id.startswith("STG-")
                else [],
            }
        )
    return {
        "status": "DRAFT",
        "provider": "template",
        "prompt_version": PROMPT_VERSION,
        "sections": [{"heading": "Situation and playbook actions", "paragraphs": paragraphs}],
    }
