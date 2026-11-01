"""The template copilot: a fixed set of questions answered through the same tools, so the demo
works offline (plan section 5): why ranked, top risks, what depends on X, what clause Y says,
how bad the outage could be by district.
It declines any request to change something, and answers "will X fail" with a probability."""

import re
from typing import Any

from muster.ids import ASSET_ID, CLAUSE_ID
from muster.llm.schemas import ChatResult, ToolRunner

DEPENDS = re.compile(r"depend|feeds?\b|supplies|supplied|upstream|downstream", re.IGNORECASE)
# "How bad, where, and do we have enough?": the outage forecast (ticket 38).
OUTAGE = re.compile(
    r"how bad|customers? (?:out|affected)|outages?|enough (?:crews|generators)"
    r"|how many (?:crews|generators)|(?:crews|generators) (?:are )?(?:needed|short)",
    re.IGNORECASE,
)
TOP = re.compile(r"\btop\b|highest|most at risk|riskiest", re.IGNORECASE)
# A request to change something, which the copilot cannot do (CLAUDE.md hard rules).
ACT = re.compile(
    r"^\W*(?:please\s+|(?:can|could|would) you\s+)?"
    r"(?:dispatch|send|approve|reject|override|declare|mark|set|change|update|assign|close|"
    r"cancel|delete|decide)\b",
    re.IGNORECASE,
)
# A question whose honest answer is a probability, not a yes or no.
PREDICT = re.compile(r"\bwill\b.*\b(?:fail|survive|hold)\b|\bguarantee", re.IGNORECASE)
DECLINE = (
    "I cannot change anything: no decisions, approvals, dispatches or state. "
    "A person decides in the decision package."
)
# No example names a real ID: the answer cites only IDs a tool returned, and this one runs none.
HELP = (
    "I can answer, offline: why an asset is ranked where it is "
    '("Why is <asset ID> ranked where it is?"), the top risks ("What are the top risks?"), '
    'what depends on an asset ("What depends on <asset ID>?"), what a clause says '
    '("What does <clause ID> say?") and how bad the outage could be, by district '
    '("How bad, where, and do we have enough crews?").'
)


def _pct(p: float) -> str:
    return f"{round(p * 100)}%"


def why_ranked(data: dict[str, Any]) -> str:
    e, c = data["exposure"], data["consequence"]
    wind, flood = data["fragility"]["wind"], data["fragility"]["flood"]
    downstream = round(c["downstream_customers"])
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
    """From the narrowed result: the critical facilities only, never the assets around it."""
    facilities = ", ".join(f"{d['id']} {d['name']}" for d in data["critical_facilities"])
    plant = " It serves the treatment plant." if data["serves_treatment_plant"] else ""
    return (
        f"{data['asset_id']} {data['name']} supports "
        f"{facilities or 'no hospital or shelter directly'}.{plant}"
    )


def outage(data: dict[str, Any]) -> str:
    """The forecast district by district, each figure as P50 to P90, as the tool returned it."""

    def spread(figure: dict[str, int]) -> str:
        return f"{figure['p50']:,}–{figure['p90']:,}"

    rows = []
    for d in data["districts"]:
        short = d["crews_short_at_p90"]
        rows.append(
            f"{d['district']}: {spread(d['power_customers_out'])} power and "
            f"{spread(d['water_customers_out'])} water customers out; crews needed "
            f"{spread(d['crews_needed'])} against {d['crews_available']:,} available"
            + (f" ({short:,} short at P90)" if short else "")
            + f", generators needed {spread(d['generators_needed'])}"
        )
    return (
        f"Forecast at advisory {data['advisory']} (P50–P90 over the ensemble): "
        + "; ".join(rows)
        + f". The fuelled generator fleet for the whole territory is "
        f"{data['generators_fuelled_territory']:,}. A forecast, not a decision."
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

    if ACT.search(question):
        text = DECLINE
    elif clause_id and not asset:
        data = call("search_playbook", {"query": clause_id.group(0).upper()})
        text = data.get("error") or clause(data)
    elif asset and DEPENDS.search(question):
        data = call("get_dependencies", {"asset_id": asset.group(0).upper()})
        text = data.get("error") or dependencies(data)
    elif asset:  # "why is X ranked", or any other question about one asset
        data = call("explain_score", {"asset_id": asset.group(0).upper(), "advisory": None})
        text = data.get("error") or why_ranked(data)
        if PREDICT.search(question) and "error" not in data:
            text = (
                f"Nobody can say whether {data['asset_id']} will fail; the ranking gives a "
                f"probability, not a forecast. {text}"
            )
    elif TOP.search(question):  # before the forecast: "top risks for generators" is a ranking
        data = call("list_top_risks", {"advisory": None, "n": top_n})
        text = data.get("error") or top_risks(data)
    elif OUTAGE.search(question):
        data = call("get_outage_forecast", {"advisory": None})
        text = data.get("error") or outage(data)
    else:
        text = HELP
    return ChatResult(str(text), used, None, None, 0, {})
