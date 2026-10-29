"""Chooses the provider at startup from settings (LLM_PROVIDER, LLM_MODEL, ANTHROPIC_API_KEY).
Prompts are not loaded here: the tasks that own them load them (app/agent/draft.py and
app/copilot/chat.py)."""

import anthropic

from app.config import Settings
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.azure_openai import AzureOpenAIProvider
from app.llm.provider import LLMProvider
from app.llm.template import TemplateProvider
from app.scoring_config import ScoringConfig


class LLMConfigError(RuntimeError):
    pass


def build_provider(settings: Settings, config: ScoringConfig) -> LLMProvider:
    if settings.llm_provider == "template":
        return TemplateProvider.from_config(config)
    if settings.llm_provider == "azure_openai":
        return AzureOpenAIProvider()
    key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else ""
    if not key.strip():
        raise LLMConfigError(
            "LLM_PROVIDER=anthropic needs ANTHROPIC_API_KEY: set it in backend/.env, "
            "or run with LLM_PROVIDER=template for the offline demo."
        )
    client = anthropic.Anthropic(api_key=key, timeout=settings.llm_timeout_s, max_retries=1)
    return AnthropicProvider(client, settings.llm_model)
