"""Grounded generation: the one place that runs an LLM task (the situation report, the copilot) as
attempt -> validate -> retry -> template fallback, and keeps the attempt log in one format for
every task (L7, L9). Validation and fallback are deterministic; the task's validator decides
whether a result is grounded, never the model."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from muster.llm.provider import LLMProvider
from muster.llm.schemas import LLMUnavailable, Prompt
from muster.tracing import instrument

log = logging.getLogger(__name__)

FALLBACK_LABEL = "template (fallback)"  # the provider shown when the template replaced a result


@dataclass(frozen=True)
class GenerationEvent:
    """One step of a generation as it happens, for a task that shows its progress: an attempt
    starts, its result is being validated, it was validated (no problems) or rejected, the
    provider failed, or the fallback template takes over (`reason` says why)."""

    kind: Literal["attempt", "validating", "validated", "rejected", "failed", "fallback"]
    attempt: int  # 1 for the first try; the fallback carries the number of the last try
    provider: str
    problems: tuple[str, ...] = ()
    reason: str | None = None


Observer = Callable[[GenerationEvent], None]


def _ignore(_: GenerationEvent) -> None:
    """The observer of a task that does not show its progress."""


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
    observe: Observer = _ignore,
) -> GroundedOutcome[R]:
    """Calls `provider` with the task's `prompt` up to `attempts` times, sending each retry the
    problems the validator found in the last result. If no result passes, or the provider
    raises, the result comes from `fallback`, unvalidated: it is deterministic and built from
    the same request. `rejected` is the task's words for a failed validation, in front of the
    problems in the fallback reason. The whole generation is one span named after `task`.
    `observe` is told each step as it happens; it never changes the outcome."""
    with instrument.generation(task) as span:
        outcome = _generate(provider, fallback, prompt, call, validate, attempts, rejected, observe)
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
    observe: Observer,
) -> GroundedOutcome[R]:
    tries: list[dict[str, Any]] = []
    feedback: list[str] = []
    for number in range(1, attempts + 1):
        observe(GenerationEvent("attempt", number, provider.name))
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
            observe(GenerationEvent("failed", number, provider.name, reason=attempt["error"]))
            break
        observe(GenerationEvent("validating", number, provider.name))
        problems = validate(result)
        if problems:
            observe(GenerationEvent("rejected", number, provider.name, tuple(problems)))
        else:
            observe(GenerationEvent("validated", number, provider.name))
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
    observe(GenerationEvent("fallback", len(tries), FALLBACK_LABEL, reason=reason))
    result = call(fallback, prompt, [])
    return GroundedOutcome(result, FALLBACK_LABEL, True, result.prompt_version, tries, reason)
