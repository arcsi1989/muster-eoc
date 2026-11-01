import logging
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter
from fastapi.sse import EventSourceResponse, ServerSentEvent

from muster.api.schemas import (
    AttemptOut,
    ChatIn,
    ChatOut,
    CitationOut,
    StepOut,
    ToolCallOut,
    WorkOut,
)
from muster.copilot.chat import CopilotAnswer, Step, StepObserver, answer, stream_answer
from muster.deps import (
    LLMConfigDep,
    LLMDep,
    PlaybookDep,
    ScoringConfigDep,
    SessionDep,
)
from muster.errors import AppError
from muster.llm.config import LLMConfig
from muster.llm.schemas import ChatTurn, attempt_tokens

log = logging.getLogger(__name__)

router = APIRouter(prefix="/copilot")


def _attempt(attempt: dict[str, Any]) -> AttemptOut:
    tokens_in, tokens_out = attempt_tokens(attempt)
    return AttemptOut.model_validate(
        attempt
        | {
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "problems": attempt.get("problems", []),
            "error": attempt.get("error"),
        }
    )


def _chat_out(result: CopilotAnswer, prices: LLMConfig) -> ChatOut:
    tokens_in, tokens_out = result.tokens
    return ChatOut(
        answer=result.text,
        citations=[CitationOut(id=c.id, kind=c.kind) for c in result.citations],
        provider=result.provider,
        fallback=result.fallback,
        tools_used=result.tools_used,
        advisory=result.advisory,
        work=WorkOut(
            tool_calls=[
                ToolCallOut(name=c.name, args=c.args, result=c.result) for c in result.tool_calls
            ],
            attempts=[_attempt(a) for a in result.attempts],
            retries=max(0, len(result.attempts) - 1),
            validated=result.validated,
            provider=result.provider,
            model=result.model,
            prompt_version=result.prompt_version,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            cost_usd=prices.attempts_cost_usd(result.attempts),
            fallback=result.fallback,
            fallback_reason=result.fallback_reason,
        ),
    )


def _step_out(step: Step) -> StepOut:
    return StepOut.model_validate(step, from_attributes=True)


def _error(code: str, message: str) -> ServerSentEvent:
    return ServerSentEvent(event="error", data={"error": {"code": code, "message": message}})


@router.post("/chat", response_model=ChatOut)
def chat(
    body: ChatIn,
    session: SessionDep,
    playbook: PlaybookDep,
    llm: LLMDep,
    config: ScoringConfigDep,
    prices: LLMConfigDep,
) -> ChatOut:
    """A follow-up question, answered from read-only tools with cited asset and clause IDs."""
    history = [ChatTurn(t.role, t.content) for t in body.history]
    return _chat_out(answer(session, playbook, llm, body.message, history, config), prices)


@router.post("/chat/stream", response_class=EventSourceResponse, response_model=None)
def chat_stream(
    body: ChatIn,
    session: SessionDep,
    playbook: PlaybookDep,
    llm: LLMDep,
    config: ScoringConfigDep,
    prices: LLMConfigDep,
) -> Iterator[ServerSentEvent]:
    """The same answer as server-sent events: a `step` event for each step as it happens (tool
    call, validation, retry, fallback), then one `answer` event with the validated answer and how
    it was reached (a `ChatOut`), or one `error` event. The answer text is sent only in the
    `answer` event, after validation."""
    history = [ChatTurn(t.role, t.content) for t in body.history]

    def turn(on_step: StepObserver) -> CopilotAnswer:
        return answer(session, playbook, llm, body.message, history, config, on_step=on_step)

    try:
        for item in stream_answer(turn):
            if isinstance(item, Step):
                yield ServerSentEvent(event="step", data=_step_out(item))
            else:
                yield ServerSentEvent(event="answer", data=_chat_out(item, prices))
    except AppError as error:
        yield _error(error.code, str(error))
    except Exception:  # noqa: BLE001 - never send a stack trace (B6); logged here
        log.exception("copilot_stream_failed")
        yield _error(AppError.code, "the copilot could not answer")
