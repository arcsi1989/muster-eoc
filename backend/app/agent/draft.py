"""Produces the draft situation report through grounded generation: the draft request validator
accepts only drafts that cite what the request shows (plan section 4, decisions.md)."""

from dataclasses import replace

from app.agent.citations import citation_problems
from app.llm.grounded import GroundedOutcome, generate
from app.llm.provider import LLMProvider
from app.llm.schemas import DraftRequest, DraftResult


def produce_draft(
    provider: LLMProvider, fallback: LLMProvider, request: DraftRequest, attempts: int
) -> GroundedOutcome[DraftResult]:
    return generate(
        provider,
        fallback,
        lambda p, feedback: p.draft_sitrep(replace(request, feedback=feedback)),
        lambda result: citation_problems(result.draft, request),
        attempts,
        rejected="citations failed validation",
    )
