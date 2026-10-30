"""Grounded generation: the one place that runs an LLM task (the situation report, the copilot) as
attempt -> validate -> retry -> template fallback, and keeps the attempt log in one format for
every task (L7, L9). Validation and fallback are deterministic; the task's validator decides
whether a result is grounded, never the model."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from app.llm.provider import LLMProvider
from app.llm.schemas import LLMUnavailable, Prompt
from app.tracing import instrument

log = logging.getLogger(__name__)

FALLBACK_LABEL = "template (fallback)"  # the provider shown when the template replaced a result


class ProviderResult(Protocol):
    """What every provider result reports about its call."""

    @property
    def model(self) -> str | None: ...
    @property
    def prompt_version(self) -> str | None: ...
    @property
    def latency_ms(self) -> int: ...
    @property
    def usage(self) -> dict[str, int]: ...


@dataclass(frozen=True)
class GroundedOutcome[R: ProviderResult]:
    result: R
    provider: str  # the provider that produced the result, or FALLBACK_LABEL
    fallback: bool  # the fallback template replaced the configured provider's result
    prompt_version: str | None
    # each try: provider, model, prompt_version, latency_ms, then usage and problems, or error
    attempts: list[dict[str, Any]]
    fallback_reason: str | None


def generate[R: ProviderResult](
    provider: LLMProvider,
    fallback: LLMProvider,
    prompt: Prompt,
    call: Callable[[LLMProvider, Prompt, list[str]], R],
    validate: Callable[[R], list[str]],
    attempts: int,
    rejected: str,
    task: instrument.Task,
) -> GroundedOutcome[R]:
    """Calls `provider` with the task's `prompt` up to `attempts` times, sending each retry the
    problems the validator found in the last result. If no result passes, or the provider
    raises, the result comes from `fallback`, unvalidated: it is deterministic and built from
    the same request. `rejected` is the task's words for a failed validation, in front of the
    problems in the fallback reason. The whole generation is one span named after `task`."""
    with instrument.generation(task) as span:
        outcome = _generate(provider, fallback, prompt, call, validate, attempts, rejected)
        model = outcome.attempts[-1].get("model") if outcome.attempts else outcome.result.model
        instrument.record_generation(
            span,
            outcome.provider,
            model,
            outcome.attempts,
            outcome.fallback,
            outcome.fallback_reason,
        )
    return outcome


def _generate[R: ProviderResult](
    provider: LLMProvider,
    fallback: LLMProvider,
    prompt: Prompt,
    call: Callable[[LLMProvider, Prompt, list[str]], R],
    validate: Callable[[R], list[str]],
    attempts: int,
    rejected: str,
) -> GroundedOutcome[R]:
    tries: list[dict[str, Any]] = []
    feedback: list[str] = []
    for _ in range(attempts):
        started = time.monotonic()
        attempt: dict[str, Any] = {
            "provider": provider.name,
            "model": provider.model,
            "prompt_version": prompt.version,
        }
        try:
            result = call(provider, prompt, feedback)
        except Exception as error:  # noqa: BLE001 - any provider failure serves the template (L9)
            known = isinstance(error, LLMUnavailable)
            attempt |= {
                "latency_ms": round((time.monotonic() - started) * 1000),
                "error": str(error) if known else "unexpected provider error",
            }
            tries.append(attempt)
            log.warning("llm_unavailable %s", attempt, exc_info=not known)
            break
        problems = validate(result)
        tries.append(
            attempt
            | {
                "model": result.model,
                "prompt_version": result.prompt_version,  # None if the provider used no prompt
                "latency_ms": result.latency_ms,
                "usage": result.usage,
                "problems": problems,
            }
        )
        if not problems:
            return GroundedOutcome(result, provider.name, False, result.prompt_version, tries, None)
        feedback = problems
    last = tries[-1]
    reason = last.get("error") or f"{rejected}: " + "; ".join(last.get("problems", []))
    result = call(fallback, prompt, [])
    return GroundedOutcome(result, FALLBACK_LABEL, True, result.prompt_version, tries, reason)
