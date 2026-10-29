"""The provider interface (plan section 4): Anthropic, template, and an Azure OpenAI stub."""

from typing import Protocol

from app.llm.schemas import DraftRequest, DraftResult


class LLMProvider(Protocol):
    name: str
    model: str | None
    prompt_version: str | None  # None when no prompt is used (template)

    def draft_sitrep(self, request: DraftRequest) -> DraftResult: ...
