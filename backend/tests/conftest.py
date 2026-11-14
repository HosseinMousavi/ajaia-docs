from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, normalize_database_url
from app.main import create_app

DEMO_PASSWORD = "demo1234"


# Set TEST_DATABASE_URL (e.g. postgresql://user@localhost/ajaia_test) to run the whole
# suite against Postgres instead of a throwaway SQLite file.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def _reset_postgres(url: str) -> None:
    from app.db import Base, make_engine
    from app import models  # noqa: F401  (register tables)

    engine = make_engine(url)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def database_url(tmp_path: Path) -> str:
    if TEST_DATABASE_URL:
        url = normalize_database_url(TEST_DATABASE_URL)
        _reset_postgres(url)
        return url
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture()
def settings(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
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
