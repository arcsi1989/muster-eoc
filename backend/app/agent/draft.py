"""Produces the draft situation report through grounded generation: the draft request validator
accepts only drafts that cite what the request shows (plan section 4, decisions.md). This task
owns the situation report prompt."""

from dataclasses import replace
from pathlib import Path

from app.agent.citations import citation_problems
from app.llm.grounded import GroundedOutcome, generate
from app.llm.provider import LLMProvider
from app.llm.schemas import DraftRequest, DraftResult, Prompt
from app.scoring_config import DraftConfig

PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "sitrep_v2.md"


def sitrep_prompt(config: DraftConfig) -> Prompt:
    return Prompt.from_file(PROMPT_FILE, max_tokens=config.max_tokens)


def produce_draft(
    provider: LLMProvider,
    fallback: LLMProvider,
    prompt: Prompt,
    request: DraftRequest,
    attempts: int,
) -> GroundedOutcome[DraftResult]:
    return generate(
        provider,
        fallback,
        prompt,
        lambda p, prompt, feedback: p.draft_sitrep(replace(request, feedback=feedback), prompt),
        lambda result: citation_problems(result.draft, request),
        attempts,
        rejected="citations failed validation",
    )
