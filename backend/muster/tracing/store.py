"""Where the spans go, and the run trace read back from them.

The app installs one OpenTelemetry tracer provider per process (the API allows only one). It
always exports to the trace_span table of the running app, and also to an OTLP/HTTP endpoint
when OTEL_EXPORTER_OTLP_ENDPOINT is set, so tracing needs no new service. A demo run is the
scenario since the backend started or was last reset; the reset clears the table with the rest
of the scenario and begins a new run."""

import json
import logging
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import StatusCode
from sqlalchemy import Engine
from sqlmodel import Session, col, delete, select

from muster import advisory_context
from muster.llm.config import LLMConfig
from muster.models import SpanStatus, TraceSpan
from muster.tracing import instrument as keys

log = logging.getLogger(__name__)


class _TableExporter(SpanExporter):
    """Writes each finished span of the app's own (a cycle node or a generation, not the spans
    libraries such as FastAPI add) to the trace_span table of the app that is running, if any."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._engine: Engine | None = None
        self._config: LLMConfig | None = None
        self.run_id = ""

    def attach(self, engine: Engine | None, config: LLMConfig | None) -> None:
        with self._lock:
            self._engine, self._config = engine, config
            self.run_id = uuid4().hex

    def new_run(self) -> None:
        with self._lock:
            self.run_id = uuid4().hex

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        with self._lock:
            if self._engine is None or self._config is None:
                return SpanExportResult.SUCCESS  # no app running: the spans are dropped
            with Session(self._engine) as session:
                current = advisory_context.current_advisory_no(session) or None
                ours = [s for s in spans if s.attributes and keys.KIND in s.attributes]
                session.add_all(_row(s, self.run_id, current, self._config) for s in ours)
                session.commit()
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        self.attach(None, None)


_table = _TableExporter()
_installed = threading.Lock()
_provider: TracerProvider | None = None


def start(
    engine: Engine, config: LLMConfig, otlp_endpoint: str | None, otlp_timeout_s: float
) -> None:
    """Sends spans to this app's trace_span table, from now on, in a new run."""
    global _provider
    with _installed:
        if _provider is None:
            _provider = TracerProvider()
            _provider.add_span_processor(SimpleSpanProcessor(_table))
            if otlp_endpoint:
                otlp = _otlp(otlp_endpoint, otlp_timeout_s)
                _provider.add_span_processor(BatchSpanProcessor(otlp))
            trace.set_tracer_provider(_provider)
    _table.attach(engine, config)


def stop() -> None:
    """The app is shutting down: spans are no longer stored."""
    _table.attach(None, None)
    if _provider is not None:
        _provider.force_flush()  # the OTLP batch, if any


def _otlp(endpoint: str, timeout_s: float) -> SpanExporter:
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    except ImportError as error:
        raise RuntimeError(
            "OTEL_EXPORTER_OTLP_ENDPOINT is set but the OTLP exporter is not installed: "
            "run uv sync --extra otlp, or unset the variable."
        ) from error
    url = endpoint.rstrip("/") + "/v1/traces"
    exporter: SpanExporter = OTLPSpanExporter(endpoint=url, timeout=timeout_s)
    return exporter


def clear(session: Session) -> None:
    """Deletes every stored span and begins a new demo run (scenario reset)."""
    session.exec(delete(TraceSpan))
    _table.new_run()


def _time(nanoseconds: int | None) -> datetime:
    return datetime.fromtimestamp((nanoseconds or 0) / 1e9, tz=UTC)


def _row(span: ReadableSpan, run_id: str, current: int | None, config: LLMConfig) -> TraceSpan:
    values: Any = span.attributes or {}  # the attribute values instrument.py set
    attempts: list[dict[str, Any]] = json.loads(values.get(keys.ATTEMPTS, "[]"))
    status: SpanStatus
    if span.status.status_code is StatusCode.ERROR:
        status = "error"
    else:
        status = "paused" if values.get(keys.PAUSED) else "ok"
    context = span.get_span_context()
    return TraceSpan(
        run_id=run_id,
        trace_id=format(context.trace_id if context else 0, "032x"),
        span_id=format(context.span_id if context else 0, "016x"),
        parent_span_id=format(span.parent.span_id, "016x") if span.parent else None,
        advisory_no=values.get(keys.ADVISORY, current),
        kind=values[keys.KIND],  # export stores only spans with a kind
        node=values.get(keys.NODE, span.name),
        started_at=_time(span.start_time),
        ended_at=_time(span.end_time),
        duration_ms=((span.end_time or 0) - (span.start_time or 0)) / 1e6,
        status=status,
        provider=values.get(keys.PROVIDER),
        model=values.get(keys.MODEL),
        tokens_in=values.get(keys.TOKENS_IN, 0),
        tokens_out=values.get(keys.TOKENS_OUT, 0),
        cost_usd=config.attempts_cost(attempts),
        retries=values.get(keys.RETRIES, 0),
        fallback=values.get(keys.FALLBACK, False),
        fallback_reason=values.get(keys.FALLBACK_REASON),
        validation=values.get(keys.VALIDATION),
        attempts=attempts,
    )


@dataclass(frozen=True)
class TraceTotals:
    latency_ms: float  # outermost spans only: a generation inside a node is in the node's time
    tokens_in: int
    tokens_out: int
    cost_usd: float  # the spans with a cost estimate
    unpriced_spans: int  # spans with tokens but no price in llm.yaml
    retries: int
    fallbacks: int


@dataclass(frozen=True)
class RunTrace:
    run_id: str
    advisory_no: int
    spans: list[TraceSpan]
    advisory_totals: TraceTotals
    run_totals: TraceTotals


def _totals(spans: Sequence[TraceSpan]) -> TraceTotals:
    ids = {s.span_id for s in spans}
    return TraceTotals(
        latency_ms=sum(s.duration_ms for s in spans if s.parent_span_id not in ids),
        tokens_in=sum(s.tokens_in for s in spans),
        tokens_out=sum(s.tokens_out for s in spans),
        cost_usd=sum(s.cost_usd or 0.0 for s in spans),
        unpriced_spans=sum(1 for s in spans if s.cost_usd is None),
        retries=sum(s.retries for s in spans),
        fallbacks=sum(1 for s in spans if s.fallback),
    )


def run_trace(session: Session, advisory_no: int) -> RunTrace:
    """An advisory's spans in the order they started, with totals for the advisory and for the
    whole demo run."""
    run = list(
        session.exec(
            select(TraceSpan)
            .where(TraceSpan.run_id == _table.run_id)
            .order_by(col(TraceSpan.started_at), col(TraceSpan.id))
        )
    )
    spans = [s for s in run if s.advisory_no == advisory_no]
    return RunTrace(_table.run_id, advisory_no, spans, _totals(spans), _totals(run))
