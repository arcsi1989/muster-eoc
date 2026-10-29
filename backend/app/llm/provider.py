"""The provider interface (plan section 4): Anthropic, template, and an Azure OpenAI stub."""

from typing import Any, Protocol

from app.llm.schemas import ChatResult, ChatTurn, DraftRequest, DraftResult, ToolRunner


class LLMProvider(Protocol):
    name: str
    model: str | None
    prompt_version: str | None  # None when no prompt is used (template)

    def draft_sitrep(self, request: DraftRequest) -> DraftResult: ...

    def chat(
        self,
        question: str,
        history: list[ChatTurn],
        tools: list[dict[str, Any]],
        run_tool: ToolRunner,
    ) -> ChatResult: ...
