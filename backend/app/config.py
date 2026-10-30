from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_dir: Path = REPO_ROOT / "data" / "gold"
    playbook_rules_path: Path = REPO_ROOT / "data" / "playbook" / "playbook_rules.yaml"
    playbook_path: Path = REPO_ROOT / "docs" / "playbook.md"
    database_path: Path = REPO_ROOT / "data" / "runtime" / "sgw.sqlite"
    checkpoint_path: Path = REPO_ROOT / "data" / "runtime" / "checkpoints.sqlite"
    scoring_config_path: Path = REPO_ROOT / "config" / "scoring.yaml"
    llm_config_path: Path = REPO_ROOT / "config" / "llm.yaml"
    models_config_path: Path = REPO_ROOT / "config" / "models.yaml"
    challenger_model_path: Path = REPO_ROOT / "data" / "models" / "challenger.pkl"  # make train
    # The latest evaluation (make eval), recorded as an audit event at startup; None: none.
    eval_results_path: Path | None = REPO_ROOT / "docs" / "eval" / "results.json"

    # LLM (decisions.md): template by default and in tests; make dev reads backend/.env.
    llm_provider: Literal["anthropic", "template", "azure_openai"] = "template"
    llm_model: str = "claude-sonnet-5-5"
    llm_timeout_s: float = 30.0
    anthropic_api_key: SecretStr | None = None

    # Tracing (decisions.md): spans go to the trace_span table; also to this OTLP/HTTP endpoint
    # (Langfuse, Jaeger) when set, which needs the optional extra: uv sync --extra otlp.
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_timeout_s: float = 10.0  # B7: each export to the endpoint


@lru_cache
def get_settings() -> Settings:
    return Settings()
