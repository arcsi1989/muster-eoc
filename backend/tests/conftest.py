from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    # _env_file=None: tests never read a local .env (CODING_STANDARDS T2).
    settings = Settings(_env_file=None, database_path=tmp_path / "test.sqlite")  # type: ignore[call-arg]
    with TestClient(create_app(settings)) as test_client:
        yield test_client
