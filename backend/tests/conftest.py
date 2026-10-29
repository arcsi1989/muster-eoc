from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.provider import LLMProvider
from app.main import create_app

ClientFactory = Callable[..., AbstractContextManager[TestClient]]


def test_settings(tmp_path: Path) -> Settings:
    # _env_file=None: tests never read a local .env (CODING_STANDARDS T2).
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        database_path=tmp_path / "test.sqlite",
        checkpoint_path=tmp_path / "checkpoints.sqlite",
    )


@pytest.fixture
def make_client(tmp_path: Path) -> ClientFactory:
    """A client whose app uses the given provider instead of the one in settings."""

    @contextmanager
    def factory(llm: LLMProvider | None = None) -> Iterator[TestClient]:
        with TestClient(create_app(test_settings(tmp_path), llm)) as test_client:
            yield test_client

    return factory


@pytest.fixture
def client(make_client: ClientFactory) -> Iterator[TestClient]:
    with make_client() as test_client:
        yield test_client
