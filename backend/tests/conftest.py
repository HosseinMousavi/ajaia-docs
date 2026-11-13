from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

DEMO_PASSWORD = "demo1234"


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        secret_key="test-secret-key-not-for-prod",
        seed_demo_users=True,
        seed_sample_content=False,
        max_upload_bytes=64 * 1024,
        max_content_bytes=32 * 1024,
        static_dir=None,
    )


@pytest.fixture()
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture()
def anon(app) -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def login(app) -> Iterator[Callable[[str], TestClient]]:
    """Return a factory producing an authenticated client per user (isolated cookie jars)."""
    clients: list[TestClient] = []

    def _login(email: str) -> TestClient:
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        resp = client.post("/api/auth/login", json={"email": email, "password": DEMO_PASSWORD})
        assert resp.status_code == 200, resp.text
        return client

    yield _login
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture()
def alice(login) -> TestClient:
    return login("alice@ajaia.test")


@pytest.fixture()
def bob(login) -> TestClient:
    return login("bob@ajaia.test")


@pytest.fixture()
def carol(login) -> TestClient:
    return login("carol@ajaia.test")
