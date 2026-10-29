"""Azure OpenAI stub: the interface leaves room for it (decisions.md, 2026-10-28)."""

from typing import Any

from app.llm.schemas import (
    ChatResult,
    ChatTurn,
    DraftRequest,
    DraftResult,
    LLMUnavailable,
    Prompt,
    ToolRunner,
)


class AzureOpenAIProvider:
    name = "azure_openai"
    model: str | None = None

    def draft_sitrep(self, request: DraftRequest, prompt: Prompt) -> DraftResult:
        raise LLMUnavailable("the Azure OpenAI provider is a stub in this prototype")

    def chat(
        self,
        question: str,
        history: list[ChatTurn],
        tools: list[dict[str, Any]],
        run_tool: ToolRunner,
        prompt: Prompt,
    ) -> ChatResult:
        raise LLMUnavailable("the Azure OpenAI provider is a stub in this prototype")
