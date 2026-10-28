from collections.abc import Iterator

from fastapi import Request
from sqlmodel import Session

from app.playbook.activation import ActivationLevel


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


def get_activation_levels(request: Request) -> list[ActivationLevel]:
    levels: list[ActivationLevel] = request.app.state.activation_levels
    return levels
