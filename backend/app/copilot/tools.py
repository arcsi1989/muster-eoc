"""The copilot's tools (plan section 5): read-only views over the same domain functions the
screens use. They return plain data and the asset and clause IDs it contains, so answers can
cite only what a tool returned. Coordinates, elevation and the dependency graph are restricted
(CR-03 C1): the copilot filters every result before the model sees it, and the dependency tools
show only the critical facilities an asset supports."""

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlmodel import Session, col, select

from app import advisory_context
from app.errors import AppError
from app.ids import CLAUSE_ID
from app.models import DecisionPackage, PackageItem, Score
from app.network import load_network
from app.playbook import service as playbook_service
from app.playbook.service import Playbook
from app.risk.explain import explain_asset
from app.scoring_config import CopilotConfig

ALL_PHASES = float("inf")  # search every clause, whatever the lead time


@dataclass
class ToolOutput:
    data: dict[str, Any]
    asset_ids: set[str] = field(default_factory=set)
    clause_ids: set[str] = field(default_factory=set)
    other_ids: set[str] = field(default_factory=set)  # facilities, staging areas: never chips


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


ADVISORY = {
    "type": ["integer", "null"],
    "description": "Advisory number; null for the current one.",
}
ASSET = {"type": "string", "description": "Asset ID, e.g. SUB-07 or PS-14."}

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "list_top_risks",
        "description": "The highest-risk assets at an advisory, by rank, with failure probability, "
        "consequence, risk and confidence.",
        "input_schema": _schema(
            {"advisory": ADVISORY, "n": {"type": "integer"}}, ["advisory", "n"]
        ),
    },
    {
        "name": "get_asset",
        "description": "An asset's static data: type, district, distance to coast, install year, "
        "condition, last inspection, customers.",
        "input_schema": _schema({"asset_id": ASSET}, ["asset_id"]),
    },
    {
        "name": "explain_score",
        "description": "Why an asset ranks where it does: exposure, fragility, condition "
        "adjustment, consequence components, confidence.",
        "input_schema": _schema(
            {"asset_id": ASSET, "advisory": ADVISORY}, ["asset_id", "advisory"]
        ),
    },
    {
        "name": "get_dependencies",
        "description": "The critical facilities an asset supports (hospitals, shelters) and "
        "whether it serves the treatment plant.",
        "input_schema": _schema({"asset_id": ASSET}, ["asset_id"]),
    },
    {
        "name": "search_playbook",
        "description": "Playbook clauses matching a query, or one clause by its ID (e.g. P-4.2).",
        "input_schema": _schema({"query": {"type": "string"}}, ["query"]),
    },
    {
        "name": "get_decision_package",
        "description": "The decision package at an advisory: each gap's proposed action and each "
        "conflict, with its status and who decided it.",
        "input_schema": _schema({"advisory": ADVISORY}, ["advisory"]),
    },
    {
        "name": "get_findings",
        "description": "Playbook findings at an advisory, optionally only open, satisfied "
        "or conflict.",
        "input_schema": _schema(
            {
                "advisory": ADVISORY,
                "status": {
                    "anyOf": [
                        {"type": "string", "enum": ["open", "satisfied", "conflict"]},
                        {"type": "null"},
                    ],
                },
            },
            ["advisory", "status"],
        ),
    },
]


class ToolError(Exception):
    """A tool could not answer (unknown asset, no advisory yet): returned to the model as text."""


class CopilotTools:
    def __init__(self, session: Session, playbook: Playbook, config: CopilotConfig) -> None:
        self._session = session
        self._playbook = playbook
        self._config = config
        self._handlers: dict[str, Callable[..., ToolOutput]] = {
            d["name"]: getattr(self, d["name"]) for d in TOOL_DEFINITIONS
        }

    def _advisory(self, advisory: int | None) -> int:
        number = advisory or advisory_context.current_advisory_no(self._session)
        if number < 1:
            raise ToolError("no advisory has been issued yet")
        return number

    def run(self, name: str, args: dict[str, Any]) -> ToolOutput:
        if name not in self._handlers:
            raise ToolError(f"unknown tool {name}")
        try:
            return self._handlers[name](**args)
        except AppError as error:
            raise ToolError(str(error)) from error

    def list_top_risks(self, advisory: int | None, n: int) -> ToolOutput:
        number = self._advisory(advisory)
        network = load_network(self._session)
        top = self._session.exec(
            select(Score)
            .where(
                Score.advisory_no == number,
                Score.rank <= max(1, min(n, self._config.top_risks_max)),
            )
            .order_by(col(Score.rank))
        ).all()
        rows = [
            {
                "asset_id": s.asset_id,
                "name": network.assets[s.asset_id].name,
                "rank": s.rank,
                "p_fail": round(s.p_fail, 3),
                "consequence": round(s.consequence),
                "risk": round(s.risk),
                "confidence": s.confidence,
            }
            for s in top
        ]
        return ToolOutput({"advisory": number, "assets": rows}, asset_ids={s.asset_id for s in top})

    def get_asset(self, asset_id: str) -> ToolOutput:
        asset = load_network(self._session).assets.get(asset_id)
        if asset is None:
            raise ToolError(f"unknown asset {asset_id}")
        # Its coordinates and elevation are restricted: the copilot's filter drops them.
        return ToolOutput(asset.model_dump(mode="json"), asset_ids={asset_id})

    def explain_score(self, asset_id: str, advisory: int | None) -> ToolOutput:
        number = self._advisory(advisory)
        e = explain_asset(self._session, asset_id, number)
        c = e.factors["consequence"]
        # The consequence components without the assets it feeds (restricted): their customers
        # as one number, and the critical facilities it supports.
        consequence = {
            "own_customers": c["own_customers"],
            "downstream_customers": sum(a["customers"] for a in c["downstream_assets"]),
            "facilities": [
                {"id": f["id"], "type": f["type"], "weight": f["weight"]} for f in c["facilities"]
            ],
            "total": c["total"],
        }
        data = {
            "asset_id": asset_id,
            "name": e.asset.name,
            "advisory": number,
            "rank": e.score.rank,
            "risk": round(e.score.risk),
            "p_fail": round(e.score.p_fail, 3),
            "p_wind": round(e.score.p_wind, 3),
            "p_flood": round(e.score.p_flood, 3),
            "condition_score": e.asset.condition_score,
            "exposure": e.exposure.model_dump(mode="json", exclude={"advisory_no", "site_kind"}),
            "fragility": {"wind": e.factors["wind"], "flood": e.factors["flood"]},
            "consequence": consequence,
            "confidence": e.score.confidence,
            "confidence_reasons": e.score.confidence_reasons,
        }
        plants = {f["id"] for f in consequence["facilities"] if f["type"] == "treatment_plant"}
        return ToolOutput(
            data,
            asset_ids={asset_id} | plants,
            other_ids={f["id"] for f in consequence["facilities"]} - plants,
        )

    def get_dependencies(self, asset_id: str) -> ToolOutput:
        """Narrowed to the critical facilities the asset supports and whether it serves the
        treatment plant: no upstream feeders, no asset-to-asset edges (CR-03 C1)."""
        network = load_network(self._session)
        if asset_id not in network.assets:
            raise ToolError(f"unknown asset {asset_id}")
        facilities = [
            {"id": f.id, "type": f.type, "name": f.name}
            for f in network.direct_facilities(asset_id)
        ]
        data = {
            "asset_id": asset_id,
            "name": network.assets[asset_id].name,
            "critical_facilities": facilities,
            "serves_treatment_plant": network.serves_treatment_plant(asset_id),
            "feeds_facility_types": sorted(network.feeds_facility_types(asset_id)),
        }
        return ToolOutput(data, asset_ids={asset_id}, other_ids={f["id"] for f in facilities})

    def search_playbook(self, query: str) -> ToolOutput:
        wanted = query.strip().upper()
        if CLAUSE_ID.fullmatch(wanted):
            clauses = [c for c in self._playbook.clauses if c.id == wanted]
            if not clauses:
                raise ToolError(f"the playbook has no clause {wanted}")
        else:
            n = self._config.search_results
            clauses = self._playbook.index.search([query], ALL_PHASES, n, n)
        return ToolOutput(
            {"clauses": [asdict(c) for c in clauses]}, clause_ids={c.id for c in clauses}
        )

    def get_decision_package(self, advisory: int | None) -> ToolOutput:
        number = self._advisory(advisory)
        package = self._session.get(DecisionPackage, number)
        if package is None:
            raise ToolError(f"no decision package for advisory {number}")
        items = self._session.exec(
            select(PackageItem).where(PackageItem.advisory_no == number)
        ).all()
        rows = [
            {
                "rule_id": i.rule_id,
                "entity_id": i.entity_id,
                "kind": i.kind,
                "proposed_action": i.proposed_action,
                "status": i.status,
                "decided_by": i.decided_by,
                "reason": i.reason,
            }
            for i in items
        ]
        network = load_network(self._session)
        return ToolOutput(
            {"advisory": number, "status": package.status, "items": rows},
            asset_ids={i.entity_id for i in items if i.entity_id in network.assets},
            clause_ids={i.rule_id for i in items},
            other_ids={i.entity_id for i in items if i.entity_id not in network.assets},
        )

    def get_findings(self, advisory: int | None, status: str | None) -> ToolOutput:
        number = self._advisory(advisory)
        if status not in (None, "open", "satisfied", "conflict"):
            raise ToolError(f"unknown status {status}")
        views = playbook_service.finding_views(self._session, self._playbook, number, status)  # type: ignore[arg-type]
        network = load_network(self._session)
        rows = [
            {
                "rule_id": v.finding.rule_id,
                "title": v.title,
                "entity_id": v.finding.entity_id,
                "entity_name": v.entity_name,
                "status": v.finding.status,
                "overdue": v.finding.overdue,
                "cites": v.finding.cites,
            }
            for v in views
        ]
        return ToolOutput(
            {"advisory": number, "findings": rows},
            asset_ids={v.finding.entity_id for v in views if v.finding.entity_id in network.assets},
            clause_ids={c for v in views for c in v.finding.cites},
            other_ids={
                v.finding.entity_id for v in views if v.finding.entity_id not in network.assets
            },
        )
