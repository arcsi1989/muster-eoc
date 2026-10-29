"""The template copilot: a fixed set of questions answered through the same tools, so the demo
works offline (plan section 5): why ranked, top risks, what depends on X, what clause Y says."""

import re
from typing import Any

from app.ids import ASSET_ID, CLAUSE_ID
from app.llm.schemas import ChatResult, ToolRunner

DEPENDS = re.compile(r"depend|feeds?\b|supplies|supplied|upstream|downstream", re.IGNORECASE)
TOP = re.compile(r"\btop\b|highest|most at risk|riskiest", re.IGNORECASE)
HELP = (
    "I can answer, offline: why an asset is ranked where it is "
    '("Why is PS-14 ranked where it is?"), the top risks ("What are the top risks?"), '
    'what depends on an asset ("What depends on SUB-07?") and what a clause says '
    '("What does P-4.2 say?").'
)


def _pct(p: float) -> str:
    return f"{round(p * 100)}%"


def why_ranked(data: dict[str, Any]) -> str:
    e, c = data["exposure"], data["consequence"]
    wind, flood = data["fragility"]["wind"], data["fragility"]["flood"]
    downstream = round(sum(a["customers"] for a in c["downstream_assets"]))
    facilities = ", ".join(f["id"] for f in c["facilities"]) or "none"
    total = round(c["total"])
    p_fail, p_wind, p_flood = _pct(data["p_fail"]), _pct(data["p_wind"]), _pct(data["p_flood"])
    text = (
        f"{data['asset_id']} {data['name']} is ranked {data['rank']} at advisory "
        f"{data['advisory']}. Its failure probability is {p_fail} "
        f"(wind {p_wind}, flood {p_flood}): "
        f"wind {e['wind_p50_mph']}/{e['wind_p90_mph']} mph (P50/P90) against a median capacity "
        f"of {wind['theta_adjusted']:.0f} mph, flood {e['flood_depth_p50_m']}/"
        f"{e['flood_depth_p90_m']} m against {flood['theta_adjusted']:.2f} m. Its consequence is "
        f"{total:,} customer-equivalents ({c['own_customers']:,} own customers, {downstream:,} "
        f"downstream, critical facilities: {facilities}), so risk = {p_fail} × {total:,} = "
        f"{data['risk']:,}."
    )
    if data["condition_score"] > 1:
        text += f" Its condition score of {data['condition_score']} lowers its capacity."
    if data["confidence"] != "high":
        text += f" Confidence is {data['confidence']}: {'; '.join(data['confidence_reasons'])}."
    return text


def top_risks(data: dict[str, Any]) -> str:
    rows = "; ".join(
        f"{a['rank']}. {a['asset_id']} {a['name']} "
        f"(risk {a['risk']:,}, failure probability {_pct(a['p_fail'])})"
        for a in data["assets"]
    )
    return f"Top risks at advisory {data['advisory']}: {rows}."


def dependencies(data: dict[str, Any]) -> str:
    feeds = ", ".join(f"{d['id']} {d['name']}" for d in data["feeds"]) or "nothing"
    fed_by = ", ".join(f"{d['id']} {d['name']}" for d in data["fed_by"]) or "no upstream asset"
    types = ", ".join(data["feeds_facility_types"]) or "no critical facility"
    return (
        f"{data['asset_id']} {data['name']} feeds {feeds}. It is fed by {fed_by}. "
        f"Critical facilities supplied: {types}."
    )


def clause(data: dict[str, Any]) -> str:
    c = data["clauses"][0]
    return f"{c['id']} {c['title']} ({c['section']}): {c['text']}"


def template_chat(question: str, run_tool: ToolRunner, top_n: int) -> ChatResult:
    asset = ASSET_ID.search(question)
    clause_id = CLAUSE_ID.search(question)
    used: list[str] = []

    def call(name: str, args: dict[str, Any]) -> dict[str, Any]:
        used.append(name)
        return run_tool(name, args)

    if clause_id and not asset:
        data = call("search_playbook", {"query": clause_id.group(0).upper()})
        text = data.get("error") or clause(data)
    elif asset and DEPENDS.search(question):
        data = call("get_dependencies", {"asset_id": asset.group(0).upper()})
        text = data.get("error") or dependencies(data)
    elif asset:  # "why is X ranked", or any other question about one asset
        data = call("explain_score", {"asset_id": asset.group(0).upper(), "advisory": None})
        text = data.get("error") or why_ranked(data)
    elif TOP.search(question):
        data = call("list_top_risks", {"advisory": None, "n": top_n})
        text = data.get("error") or top_risks(data)
    else:
        text = HELP
    return ChatResult(str(text), used, None, None, 0, {})
