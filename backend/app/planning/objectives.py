"""The IAP incident objectives (CR-02 C3): derived from the open findings by a template, a
standing safety objective and then one per theme, each citing its clause IDs. A model may only
reword them, through grounded generation: a wording that mentions a clause or site its objective
does not cite is rejected, and the template wording stands in. The citations always come from
the findings."""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.agent.prompts import load_prompt
from app.ids import CLAUSE_ID, ENTITY_ID, mentioned
from app.llm.grounded import GroundedOutcome, generate
from app.llm.provider import LLMProvider
from app.llm.schemas import IapObjective, ObjectivesRequest, ObjectivesResult, Prompt
from app.models import Finding
from app.playbook.package import actionable
from app.scoring_config import PlanningConfig


@dataclass(frozen=True)
class Theme:
    """One incident objective: what it protects, and the findings it answers by rule, each with
    the phrase it adds to the objective's text. A recurring rule is due again every operational
    period (its flag resets with each advisory), so the next period's plan always includes it."""

    protects: str
    rules: dict[str, str]
    recurring: tuple[str, ...] = ()


# Responder safety is the standing first objective (P-8.2): stop-work (P-4.7) and conflicts.
SAFETY = "Keep crews safe: no field work where stop-work applies"
SAFETY_CONFLICTS = ", and the Incident Commander decides each conflict"
SAFETY_CLAUSES = ("P-4.7", "P-8.2")
# Then supply to critical customers, then the networks and the EOC.
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
        recurring=("P-4.1", "P-7.1"),
    ),
)
MIN_OBJECTIVES = 3  # CR-02 C3: three to six incident objectives


def _joined(phrases: list[str]) -> str:
    return phrases[0] if len(phrases) == 1 else ", ".join(phrases[:-1]) + " and " + phrases[-1]


def _objective(text: str, findings: Sequence[Finding], clauses: Sequence[str] = ()) -> IapObjective:
    cited = set(clauses) | {f.rule_id for f in findings} | {c for f in findings for c in f.cites}
    sites = {f.entity_id for f in findings if f.entity_kind != "event"}
    return IapObjective(text=text, clause_ids=sorted(cited), entity_ids=sorted(sites))


def _theme_objectives(
    theme: Theme, open_findings: Sequence[Finding], by_hours: int, split: bool
) -> list[IapObjective]:
    """The theme's objective (none if nothing is due), or one per rule when `split`."""
    answered = [f for f in open_findings if f.rule_id in theme.rules]
    due = {f.rule_id for f in answered} | set(theme.recurring)
    rules = [rule for rule in theme.rules if rule in due]
    if not rules:
        return []
    groups = [[rule] for rule in rules] if split else [rules]
    return [
        _objective(
            f"{theme.protects}: {_joined([theme.rules[r] for r in group])} by T-{by_hours}",
            [f for f in answered if f.rule_id in group],
            group,
        )
        for group in groups
    ]


def objectives(findings: Sequence[Finding], by_hours: int) -> list[IapObjective]:
    """The objectives for the operational period that starts `by_hours` hours to landfall: the
    standing safety objective, then one per theme with an actionable finding or a recurring
    rule. While there are fewer than three, the last themes with several rules are split into
    one objective per rule. Raises KeyError for a finding no theme answers, so no rule is left
    out."""
    open_findings = [f for f in findings if actionable(f)]
    themed = {rule for theme in THEMES for rule in theme.rules}
    unthemed = sorted({f.rule_id for f in open_findings} - themed)
    if unthemed:
        raise KeyError(f"no IAP objective answers {', '.join(unthemed)}")
    conflicts = [f for f in open_findings if f.status == "conflict"]
    safety = _objective(SAFETY + (SAFETY_CONFLICTS if conflicts else ""), conflicts, SAFETY_CLAUSES)
    per_theme = [_theme_objectives(t, open_findings, by_hours, split=False) for t in THEMES]
    for index in reversed(range(len(THEMES))):
        if 1 + sum(len(o) for o in per_theme) >= MIN_OBJECTIVES:
            break
        per_theme[index] = _theme_objectives(THEMES[index], open_findings, by_hours, split=True)
    return [safety] + [o for theme in per_theme for o in theme]


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
