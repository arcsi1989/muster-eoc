from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from app.agent.cycle import AdvisoryCycle
from app.config import Settings
from app.llm.provider import LLMProvider
from app.playbook.activation import ActivationLevel
from app.playbook.service import Playbook
from app.scoring_config import ScoringConfig


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
ScoringConfigDep = Annotated[ScoringConfig, Depends(get_scoring_config)]
