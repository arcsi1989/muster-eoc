"""Produces the draft situation report: the configured provider, citation validation, retries,
then the template draft (plan section 4, decisions.md)."""

import logging
import time
from dataclasses import dataclass, replace
from typing import Any

from app.agent.citations import citation_problems
from app.llm.provider import LLMProvider
from app.llm.schemas import DraftRequest, DraftResult, Grounding, LLMUnavailable
from app.llm.template import TemplateProvider

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DraftOutcome:
    result: DraftResult
    fallback: bool  # the template draft replaced a provider's draft
    prompt_version: str | None
    attempts: list[dict[str, Any]]  # each try: provider, model, latency, usage, problems or error
    fallback_reason: str | None


def produce_draft(
    provider: LLMProvider, request: DraftRequest, grounding: Grounding, retries: int
) -> DraftOutcome:
    template = TemplateProvider()
    if isinstance(provider, TemplateProvider):
        return DraftOutcome(template.draft_sitrep(request), False, None, [], None)

    attempts: list[dict[str, Any]] = []
    feedback: list[str] = []
    for _ in range(1 + retries):
        started = time.monotonic()
        attempt: dict[str, Any] = {
            "provider": provider.name,
            "model": provider.model,
            "prompt_version": provider.prompt_version,
        }
        try:
            result = provider.draft_sitrep(replace(request, feedback=feedback))
        except Exception as error:  # noqa: BLE001 - any provider failure serves the template (L9)
            known = isinstance(error, LLMUnavailable)
            attempt |= {
                "latency_ms": round((time.monotonic() - started) * 1000),
                "error": str(error) if known else "unexpected provider error",
            }
            attempts.append(attempt)
            log.warning("llm_unavailable %s", attempt, exc_info=not known)
            break
        problems = citation_problems(result.draft, grounding.clauses, grounding.assets)
        attempts.append(
            attempt
            | {
                "model": result.model,
                "latency_ms": result.latency_ms,
                "usage": result.usage,
                "problems": problems,
            }
        )
        if not problems:
            return DraftOutcome(result, False, provider.prompt_version, attempts, None)
        feedback = problems
    last = attempts[-1]
    reason = last.get("error") or "citations failed validation: " + "; ".join(
        last.get("problems", [])
    )
    return DraftOutcome(template.draft_sitrep(request), True, None, attempts, reason)
