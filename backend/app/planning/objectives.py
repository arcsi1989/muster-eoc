"""The IAP incident objectives (CR-02 C3): derived from the open findings by a template, one per
theme, each citing its clause IDs. A model may only reword them, through grounded generation:
a wording that mentions a clause or site its objective does not cite is rejected, and the
template wording stands in. The citations always come from the findings."""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.agent.prompts import load_prompt
from app.ids import CLAUSE_ID, ENTITY_ID, mentioned
from app.llm.grounded import GroundedOutcome, generate
from app.llm.provider import LLMProvider
from app.llm.schemas import IapObjective, ObjectivesRequest, ObjectivesResult, Prompt
from app.models import Finding
from app.scoring_config import PlanningConfig


@dataclass(frozen=True)
class Theme:
    """One incident objective: what it protects, and the open findings it answers by rule, each
    with the phrase it adds to the objective's text."""

    protects: str
    rules: dict[str, str]


# Life safety first (P-8.2), then supply to critical customers, then the networks and the EOC.
SAFETY = (
    "Keep crews safe: no field work where stop-work applies, and the Incident Commander decides "
    "each conflict"
)
THEMES = (
    Theme(
        "Protect the water supply to the treatment plant",
        {
            "P-4.2": "pre-inspect the coastal pumping stations",
            "P-4.3": "fuel enough portable generators",
            "P-4.5": "assign generators to the at-risk pumping stations",
            "P-5.2": "confirm backup power at the flood-exposed pumping stations",
            "P-5.3": "ready treatment chemicals and a boil-water notice",
        },
    ),
    Theme(
        "Keep hospitals supplied",
        {"P-6.2": "confirm on-site backup where they depend on at-risk assets"},
    ),
    Theme(
        "Protect the power network",
        {
            "P-4.4": "inspect the poor-condition substations",
            "P-5.1": "install flood barriers at the exposed substations",
        },
    ),
    Theme(
        "Keep crews and equipment out of flood water",
        {"P-4.6": "leave the staging areas forecast to flood"},
    ),
    Theme(
        "Keep the EOC in step with the storm",
        {
            "P-2.5": "declare the proposed activation level",
            "P-4.1": "review the risk list",
            "P-7.1": "approve the situation report",
            "P-7.2": "notify the regulator",
        },
    ),
)
OPEN = ("open", "conflict")


def _joined(phrases: list[str]) -> str:
    return phrases[0] if len(phrases) == 1 else ", ".join(phrases[:-1]) + " and " + phrases[-1]


def _objective(text: str, findings: Sequence[Finding]) -> IapObjective:
    clauses = {f.rule_id for f in findings} | {c for f in findings for c in f.cites}
    sites = {f.entity_id for f in findings if f.entity_kind != "event"}
    return IapObjective(text=text, clause_ids=sorted(clauses), entity_ids=sorted(sites))


def objectives(findings: Sequence[Finding], by_hours: int) -> list[IapObjective]:
    """The objectives the open and conflicting `findings` call for, to be met by `by_hours`
    hours to landfall: a safety objective when there are conflicts, then one per theme with an
    open finding. Raises KeyError for a finding no theme answers, so no rule is left out."""
    open_findings = [f for f in findings if f.status in OPEN]
    themed = {rule for theme in THEMES for rule in theme.rules}
    unthemed = sorted({f.rule_id for f in open_findings} - themed)
    if unthemed:
        raise KeyError(f"no IAP objective answers {', '.join(unthemed)}")
    result = []
    conflicts = [f for f in open_findings if f.status == "conflict"]
    if conflicts:
        result.append(_objective(SAFETY, conflicts))
    for theme in THEMES:
        answered = [f for f in open_findings if f.rule_id in theme.rules]
        if answered:
            rules = {f.rule_id for f in answered}
            phrases = [phrase for rule, phrase in theme.rules.items() if rule in rules]
            text = f"{theme.protects}: {_joined(phrases)} by T-{by_hours}"
            result.append(_objective(text, answered))
    return result


def objectives_prompt(config: PlanningConfig) -> Prompt:
    return load_prompt("iap_objectives_v1", max_tokens=config.max_tokens)


def wording_problems(result: ObjectivesResult, request: ObjectivesRequest) -> list[str]:
    """Problems found; empty when there is one non-empty text per objective and each mentions
    only the clauses and sites its objective cites."""
    texts, wanted = result.wording.texts, request.objectives
    if len(texts) != len(wanted):
        return [f"expected {len(wanted)} objectives, got {len(texts)}"]
    problems = []
    for number, (text, objective) in enumerate(zip(texts, wanted, strict=True), start=1):
        if not text.strip():
            problems.append(f"objective {number} is empty")
        for clause in mentioned(CLAUSE_ID, text) - set(objective.clause_ids):
            problems.append(f"objective {number} mentions clause {clause}, which it does not cite")
        for site in mentioned(ENTITY_ID, text) - set(objective.entity_ids):
            problems.append(f"objective {number} mentions {site}, which it does not cite")
    return sorted(problems)


def reword(
    provider: LLMProvider,
    fallback: LLMProvider,
    prompt: Prompt,
    request: ObjectivesRequest,
    attempts: int,
) -> GroundedOutcome[ObjectivesResult]:
    """The provider's wording if it passes validation, else the template's (which keeps the
    wording)."""
    return generate(
        provider,
        fallback,
        prompt,
        lambda p, prompt, feedback: p.rephrase_objectives(
            replace(request, feedback=feedback), prompt
        ),
        lambda result: wording_problems(result, request),
        attempts,
        rejected="objective citations failed validation",
    )


def worded(
    request: ObjectivesRequest, outcome: GroundedOutcome[ObjectivesResult]
) -> list[IapObjective]:
    """The objectives with the outcome's wording and their own citations."""
    return [
        objective.model_copy(update={"text": text.strip()})
        for objective, text in zip(request.objectives, outcome.result.wording.texts, strict=True)
    ]
