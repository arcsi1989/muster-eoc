from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_dir: Path = REPO_ROOT / "data" / "gold"
    playbook_rules_path: Path = REPO_ROOT / "data" / "playbook" / "playbook_rules.yaml"
    playbook_path: Path = REPO_ROOT / "docs" / "playbook.md"
    database_path: Path = REPO_ROOT / "data" / "runtime" / "sgw.sqlite"
    scoring_config_path: Path = REPO_ROOT / "config" / "scoring.yaml"


@lru_cache
def get_settings() -> Settings:
    return Settings()
