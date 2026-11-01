from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from muster.agent.cycle import AdvisoryCycle
from muster.challenger.model import ChallengerModel
from muster.config import Settings
from muster.llm.config import LLMConfig
from muster.llm.provider import LLMProvider
from muster.models_config import ModelsConfig
from muster.playbook.activation import ActivationLevel
from muster.playbook.service import Playbook
from muster.scoring_config import ScoringConfig


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def get_playbook(request: Request) -> Playbook:
    playbook: Playbook = request.app.state.playbook
    return playbook


def get_activation_levels(request: Request) -> list[ActivationLevel]:
    return get_playbook(request).levels


PlaybookDep = Annotated[Playbook, Depends(get_playbook)]


def get_scoring_config(request: Request) -> ScoringConfig:
    config: ScoringConfig = request.app.state.scoring_config
    return config


def get_cycle(request: Request) -> AdvisoryCycle:
    cycle: AdvisoryCycle = request.app.state.cycle
    return cycle


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


CycleDep = Annotated[AdvisoryCycle, Depends(get_cycle)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_llm(request: Request) -> LLMProvider:
    llm: LLMProvider = request.app.state.llm
    return llm


LLMDep = Annotated[LLMProvider, Depends(get_llm)]


def get_llm_config(request: Request) -> LLMConfig:
    """The model prices from config/llm.yaml, for cost estimates."""
    config: LLMConfig = request.app.state.llm_config
    return config


LLMConfigDep = Annotated[LLMConfig, Depends(get_llm_config)]
ScoringConfigDep = Annotated[ScoringConfig, Depends(get_scoring_config)]


def get_challenger(request: Request) -> ChallengerModel | None:
    """The challenger loaded at startup, in shadow unless approved; None without `make train`."""
    challenger: ChallengerModel | None = request.app.state.challenger
    return challenger


def get_models_config(request: Request) -> ModelsConfig:
    config: ModelsConfig = request.app.state.models_config
    return config


ChallengerDep = Annotated[ChallengerModel | None, Depends(get_challenger)]
ModelsConfigDep = Annotated[ModelsConfig, Depends(get_models_config)]
