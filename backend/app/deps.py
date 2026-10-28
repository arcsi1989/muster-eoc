from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from app.playbook.activation import ActivationLevel
from app.scoring_config import ScoringConfig


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def get_activation_levels(request: Request) -> list[ActivationLevel]:
    levels: list[ActivationLevel] = request.app.state.activation_levels
    return levels


def get_scoring_config(request: Request) -> ScoringConfig:
    config: ScoringConfig = request.app.state.scoring_config
    return config
