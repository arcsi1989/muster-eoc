from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

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
