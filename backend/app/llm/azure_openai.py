"""Azure OpenAI stub: the interface leaves room for it (decisions.md, 2026-10-28)."""

from app.llm.schemas import DraftRequest, DraftResult, LLMUnavailable


class AzureOpenAIProvider:
    name = "azure_openai"
    model: str | None = None
    prompt_version: str | None = None

    def draft_sitrep(self, request: DraftRequest) -> DraftResult:
        raise LLMUnavailable("the Azure OpenAI provider is a stub in this prototype")
