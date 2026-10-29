"""Azure OpenAI stub: the interface leaves room for it (decisions.md, 2026-10-28)."""

from typing import Any

from app.llm.schemas import (
    ChatResult,
    ChatTurn,
    DraftRequest,
    DraftResult,
    LLMUnavailable,
    ToolRunner,
)


class AzureOpenAIProvider:
    name = "azure_openai"
    model: str | None = None
    prompt_version: str | None = None

    def draft_sitrep(self, request: DraftRequest) -> DraftResult:
        raise LLMUnavailable("the Azure OpenAI provider is a stub in this prototype")

    def chat(
        self,
        question: str,
        history: list[ChatTurn],
        tools: list[dict[str, Any]],
        run_tool: ToolRunner,
    ) -> ChatResult:
        raise LLMUnavailable("the Azure OpenAI provider is a stub in this prototype")
