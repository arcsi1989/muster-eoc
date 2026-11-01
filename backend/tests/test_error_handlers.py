"""Every error reaches the client as {"error": {"code", "message"}} (CODING_STANDARDS B6, T4)."""

from pathlib import Path

from fastapi.testclient import TestClient

from muster.main import create_app
from tests import conftest


def test_a_method_the_route_does_not_allow_is_an_http_error(client: TestClient) -> None:
    response = client.post("/health")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "http_error"


def test_an_unexpected_error_is_a_generic_500_without_details(tmp_path: Path) -> None:
    app = create_app(conftest.test_settings(tmp_path))

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"error": {"code": "internal", "message": "internal error"}}
