"""Opens the spans, through the OpenTelemetry API only: what receives them is configured at
startup (muster/tracing/store.py), and without that configuration they go nowhere. Attribute names
follow the OpenTelemetry GenAI conventions where one exists, so an OTLP backend reads them."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal

from langgraph.errors import GraphInterrupt
from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

from muster.llm.schemas import attempt_tokens
from muster.models import SpanKind, ValidationResult

ADVISORY = "sgw.advisory_no"
KIND = "sgw.kind"
NODE = "sgw.node"
PAUSED = "sgw.paused"
PROVIDER = "gen_ai.provider.name"
MODEL = "gen_ai.response.model"
TOKENS_IN = "gen_ai.usage.input_tokens"
TOKENS_OUT = "gen_ai.usage.output_tokens"
RETRIES = "sgw.retries"
FALLBACK = "sgw.fallback"
FALLBACK_REASON = "sgw.fallback_reason"
VALIDATION = "sgw.validation"
ATTEMPTS = "sgw.attempts"  # JSON: the attempt log of grounded generation

# The tasks that run through grounded generation; a span is named after its task.
Task = Literal["sitrep_draft", "copilot", "iap_objectives"]

_tracer = trace.get_tracer("muster")


@contextmanager
def _span(name: str, attributes: dict[str, Any]) -> Iterator[Span]:
    """A span that ends as an error only on a real failure: the cycle pausing for decisions
    (LangGraph's interrupt) is marked as a pause."""
    with _tracer.start_as_current_span(
        name, attributes=attributes, record_exception=False, set_status_on_exception=False
    ) as span:
        try:
            yield span
        except GraphInterrupt:
            span.set_attribute(PAUSED, True)
            raise
        except Exception as error:
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, type(error).__name__))
            raise


@contextmanager
def cycle_node(advisory_no: int, node: str) -> Iterator[None]:
    """The span of one advisory-cycle node."""
    kind: SpanKind = "cycle_node"
    with _span(f"cycle.{node}", {KIND: kind, NODE: node, ADVISORY: advisory_no}):
        yield


@contextmanager
def generation(task: Task) -> Iterator[Span]:
    """The span of one grounded generation (every attempt, retry and the fallback); a copilot
    turn is one. Its advisory is the current one, filled in when it is stored."""
    kind: SpanKind = "generation"
    with _span(f"generation.{task}", {KIND: kind, NODE: task}) as span:
        yield span


def record_generation(
    span: Span,
    provider: str,
    model: str | None,
    attempts: list[dict[str, Any]],
    fallback: bool,
    fallback_reason: str | None,
) -> None:
    """What a generation did: tokens summed over every attempt (a rejected attempt is paid for
    too), retries, whether the template replaced the result, and the validation result."""
    tokens = [attempt_tokens(a) for a in attempts]
    validation: ValidationResult
    if not fallback:
        validation = "passed"
    else:
        validation = "error" if attempts and "error" in attempts[-1] else "failed"
    attributes: dict[str, Any] = {
        PROVIDER: provider,
        TOKENS_IN: sum(i for i, _ in tokens),
        TOKENS_OUT: sum(o for _, o in tokens),
        RETRIES: max(len(attempts) - 1, 0),
        FALLBACK: fallback,
        VALIDATION: validation,
        ATTEMPTS: json.dumps(attempts, default=str),
    }
    if model is not None:
        attributes[MODEL] = model
    if fallback_reason is not None:
        attributes[FALLBACK_REASON] = fallback_reason
    span.set_attributes(attributes)
