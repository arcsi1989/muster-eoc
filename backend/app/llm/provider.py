"""The provider interface (plan section 4): Anthropic, template, and an Azure OpenAI stub.
Providers are transport only: the task hands them its prompt, they send it and return a result."""

from typing import Any, Protocol

from app.llm.schemas import (
    ChatResult,
    ChatTurn,
    DraftRequest,
    DraftResult,
    ObjectivesRequest,
    ObjectivesResult,
    Prompt,
    ToolRunner,
)


class LLMProvider(Protocol):
    name: str
    model: str | None

    def draft_sitrep(self, request: DraftRequest, prompt: Prompt) -> DraftResult: ...

    def chat(
        self,
        question: str,
        history: list[ChatTurn],
        tools: list[dict[str, Any]],
        run_tool: ToolRunner,
        prompt: Prompt,
    ) -> ChatResult: ...

    def rephrase_objectives(
        self, request: ObjectivesRequest, prompt: Prompt
    ) -> ObjectivesResult: ...
