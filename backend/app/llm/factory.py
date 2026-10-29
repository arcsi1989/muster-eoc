"""Chooses the provider at startup from settings (LLM_PROVIDER, LLM_MODEL, ANTHROPIC_API_KEY)."""

from pathlib import Path

import anthropic

from app.config import Settings
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.azure_openai import AzureOpenAIProvider
from app.llm.provider import LLMProvider
from app.llm.template import TemplateProvider

PROMPTS = Path(__file__).resolve().parents[1] / "agent" / "prompts"
SITREP_PROMPT = PROMPTS / "sitrep_v1.md"  # its version is its name: sitrep-v1


class LLMConfigError(RuntimeError):
    pass


def prompt_version(path: Path) -> str:
    return path.stem.replace("_", "-")


def build_provider(settings: Settings, max_tokens: int) -> LLMProvider:
    if settings.llm_provider == "template":
        return TemplateProvider()
    if settings.llm_provider == "azure_openai":
        return AzureOpenAIProvider()
    key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else ""
    if not key.strip():
        raise LLMConfigError(
            "LLM_PROVIDER=anthropic needs ANTHROPIC_API_KEY: set it in backend/.env, "
            "or run with LLM_PROVIDER=template for the offline demo."
        )
    client = anthropic.Anthropic(api_key=key, timeout=settings.llm_timeout_s, max_retries=1)
    return AnthropicProvider(
        client,
        settings.llm_model,
        SITREP_PROMPT.read_text(),
        prompt_version(SITREP_PROMPT),
        max_tokens,
    )
