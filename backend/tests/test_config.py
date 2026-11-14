import pytest

from app.config import normalize_database_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Neon / Heroku-style URLs are rewritten to use the psycopg 3 driver.
        (
            "postgres://u:p@ep-x.neon.tech/db?sslmode=require",
            "postgresql+psycopg://u:p@ep-x.neon.tech/db?sslmode=require",
        ),
        (
            "postgresql://u:p@host:5432/db?sslmode=require&channel_binding=require",
            "postgresql+psycopg://u:p@host:5432/db?sslmode=require&channel_binding=require",
        ),
        # Already explicit, or not Postgres: untouched.
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("sqlite:///./data/ajaia.db", "sqlite:///./data/ajaia.db"),
        ("  sqlite:///x.db  ", "sqlite:///x.db"),
    ],
)
def test_normalize_database_url(raw, expected):
    assert normalize_database_url(raw) == expected


def test_from_env_normalizes(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h/db")
    monkeypatch.setenv("SECRET_KEY", "x")
    assert Settings.from_env().database_url == "postgresql+psycopg://u:p@h/db"
