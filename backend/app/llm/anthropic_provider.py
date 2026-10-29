"""Claude via the Anthropic SDK: structured output, server-side refusal fallback, timeouts.

Sonnet 5.5 accepts no sampling parameters, so there is no temperature: the structured schema
and the citation validator keep the draft on the rails (decisions.md).
"""

import json
import logging
import time
from dataclasses import asdict

import anthropic

from app.llm.schemas import DraftRequest, DraftResult, LLMUnavailable, SitrepDraft

log = logging.getLogger(__name__)
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        client: anthropic.Anthropic,
        model: str,
        system_prompt: str,
        prompt_version: str,
        max_tokens: int,
    ) -> None:
        self._client = client
        self.model: str | None = model
        self.prompt_version: str | None = prompt_version
        self._system = system_prompt
        self._max_tokens = max_tokens

    def draft_sitrep(self, request: DraftRequest) -> DraftResult:
        data = {k: v for k, v in asdict(request).items() if k != "feedback"}
        content = (
            "<findings>\n"
            + json.dumps(data, indent=1, default=str)
            + "\n</findings>\n\nWrite the draft situation report from the findings above."
        )
        if request.feedback:
            content += "\n\nYour previous draft was rejected:\n- " + "\n- ".join(request.feedback)
        started = time.monotonic()
        try:
            response = self._client.beta.messages.parse(
                model=self.model or "",
                max_tokens=self._max_tokens,
                system=self._system,
                messages=[{"role": "user", "content": content}],
                output_format=SitrepDraft,
                output_config={"effort": "low"},  # a short narrative over prepared findings
                fallbacks="default",
                betas=[FALLBACK_BETA],
            )
        except anthropic.APITimeoutError as error:
            raise LLMUnavailable("the model call timed out") from error
        except anthropic.RateLimitError as error:
            raise LLMUnavailable("rate limited by the model provider") from error
        except anthropic.APIStatusError as error:
            log.warning("llm_error status=%s message=%s", error.status_code, error.message)
            raise LLMUnavailable(f"model provider error {error.status_code}") from error
        except anthropic.APIConnectionError as error:
            raise LLMUnavailable("could not reach the model provider") from error
        latency_ms = round((time.monotonic() - started) * 1000)
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        log.info("llm_call model=%s latency_ms=%s usage=%s", response.model, latency_ms, usage)
        if response.stop_reason == "refusal":
            raise LLMUnavailable("the model declined the request")
        if response.parsed_output is None:
            raise LLMUnavailable(f"no structured output (stop reason {response.stop_reason})")
        return DraftResult(response.parsed_output, self.name, response.model, latency_ms, usage)
