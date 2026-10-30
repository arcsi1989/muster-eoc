"""Claude via the Anthropic SDK: structured output, server-side refusal fallback, timeouts.

Sonnet 5.5 accepts no sampling parameters, so there is no temperature: the structured schema
and the citation validator keep the draft on the rails (decisions.md).
"""

import json
import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import anthropic
from pydantic import BaseModel

from app.llm.schemas import (
    ChatResult,
    ChatTurn,
    DraftRequest,
    DraftResult,
    LLMUnavailable,
    ObjectivesRequest,
    ObjectivesResult,
    ObjectiveWording,
    Prompt,
    SitrepDraft,
    ToolRunner,
)

log = logging.getLogger(__name__)
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@contextmanager
def _mapped_errors() -> Iterator[None]:
    """SDK errors become LLMUnavailable: the caller serves the template instead (L9)."""
    try:
        yield
    except anthropic.APITimeoutError as error:
        raise LLMUnavailable("the model call timed out") from error
    except anthropic.RateLimitError as error:
        raise LLMUnavailable("rate limited by the model provider") from error
    except anthropic.APIStatusError as error:
        log.warning("llm_error status=%s message=%s", error.status_code, error.message)
        raise LLMUnavailable(f"model provider error {error.status_code}") from error
    except anthropic.APIConnectionError as error:
        raise LLMUnavailable("could not reach the model provider") from error


def _call[T](fn: Callable[[], T]) -> T:
    with _mapped_errors():
        return fn()


def _content(tag: str, data: Any, task: str, rejected: str, feedback: list[str]) -> str:
    """The user message: the data inside its tags, the task, and why the last try was rejected."""
    content = f"<{tag}>\n{json.dumps(data, indent=1, default=str)}\n</{tag}>\n\n{task}"
    if feedback:
        content += f"\n\nYour previous {rejected} was rejected:\n- " + "\n- ".join(feedback)
    return content


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self._client = client
        self.model: str | None = model

    def _parse[O: BaseModel](
        self, prompt: Prompt, content: str, output: type[O]
    ) -> tuple[O, str, int, dict[str, int]]:
        """One structured-output call: the parsed output, the model that answered, the latency
        and the token usage."""
        started = time.monotonic()
        response = _call(
            lambda: self._client.beta.messages.parse(
                model=self.model or "",
                max_tokens=prompt.max_tokens,
                system=prompt.system,
                messages=[{"role": "user", "content": content}],
                output_format=output,
                output_config={"effort": "low"},  # short text over prepared, deterministic data
                fallbacks="default",
                betas=[FALLBACK_BETA],
            )
        )
        latency_ms = round((time.monotonic() - started) * 1000)
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        log.info(
            "llm_call model=%s prompt=%s latency_ms=%s usage=%s",
            response.model,
            prompt.version,
            latency_ms,
            usage,
        )
        if response.stop_reason == "refusal":
            raise LLMUnavailable("the model declined the request")
        if response.parsed_output is None:
            raise LLMUnavailable(f"no structured output (stop reason {response.stop_reason})")
        return response.parsed_output, response.model, latency_ms, usage

    def draft_sitrep(self, request: DraftRequest, prompt: Prompt) -> DraftResult:
        content = _content(
            "findings",
            request.shown(),
            "Write the draft situation report from the findings above.",
            "draft",
            request.feedback,
        )
        draft, model, latency_ms, usage = self._parse(prompt, content, SitrepDraft)
        return DraftResult(draft, self.name, model, prompt.version, latency_ms, usage)

    def rephrase_objectives(self, request: ObjectivesRequest, prompt: Prompt) -> ObjectivesResult:
        content = _content(
            "objectives",
            request.shown(),
            "Reword the incident objectives above.",
            "wording",
            request.feedback,
        )
        wording, model, latency_ms, usage = self._parse(prompt, content, ObjectiveWording)
        return ObjectivesResult(wording, self.name, model, prompt.version, latency_ms, usage)

    def chat(
        self,
        question: str,
        history: list[ChatTurn],
        tools: list[dict[str, Any]],
        run_tool: ToolRunner,
        prompt: Prompt,
    ) -> ChatResult:
        """Manual tool-use loop: the model calls read-only tools until it answers."""
        messages: list[Any] = [{"role": t.role, "content": t.content} for t in history]
        messages.append({"role": "user", "content": question})
        # JSON-schema tool definitions; the SDK's TypedDicts would only restate them
        strict_tools: Any = [{**tool, "strict": True} for tool in tools]
        used: list[str] = []
        usage = {"input_tokens": 0, "output_tokens": 0}
        started = time.monotonic()
        for _ in range(prompt.max_tool_rounds + 1):
            if prompt.deadline_s is not None and time.monotonic() - started > prompt.deadline_s:
                raise LLMUnavailable("no answer within the time limit")
            response = _call(
                lambda: self._client.beta.messages.create(
                    model=self.model or "",
                    max_tokens=prompt.max_tokens,
                    system=prompt.system,
                    messages=messages,
                    tools=strict_tools,
                    output_config={"effort": "low"},
                    fallbacks="default",
                    betas=[FALLBACK_BETA],
                )
            )
            usage["input_tokens"] += response.usage.input_tokens
            usage["output_tokens"] += response.usage.output_tokens
            if response.stop_reason == "refusal":
                raise LLMUnavailable("the model declined the request")
            if response.stop_reason != "tool_use":
                text = " ".join(b.text for b in response.content if b.type == "text").strip()
                latency_ms = round((time.monotonic() - started) * 1000)
                log.info(
                    "llm_chat model=%s prompt=%s latency_ms=%s usage=%s tools=%s",
                    response.model,
                    prompt.version,
                    latency_ms,
                    usage,
                    used,
                )
                return ChatResult(text, used, response.model, prompt.version, latency_ms, usage)
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    used.append(block.name)
                    output = run_tool(block.name, dict(block.input))
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(output, default=str),
                            "is_error": "error" in output,
                        }
                    )
            messages.append({"role": "user", "content": results})
        raise LLMUnavailable("no answer within the tool-call limit")
