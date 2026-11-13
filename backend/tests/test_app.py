from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _spa_client(tmp_path) -> TestClient:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>spa</html>")
    (static / "assets" / "app.js").write_text("console.log(1)")
    s = Settings(database_url=f"sqlite:///{tmp_path / 'a.db'}", secret_key="k", static_dir=str(static))
    return TestClient(create_app(s))


def test_health_and_security_headers(anon):
    r = anon.get("/api/health")
    assert r.json() == {"status": "ok"}
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


def test_spa_fallback_serves_index_but_not_for_api(tmp_path):
    with _spa_client(tmp_path) as c:
        assert c.get("/").text == "<html>spa</html>"
        assert c.get("/some/client/route").text == "<html>spa</html>"
        assert c.get("/assets/app.js").text == "console.log(1)"
        unknown_api = c.get("/api/nope")
        assert unknown_api.status_code == 404
        assert unknown_api.headers["content-type"].startswith("application/json")


def test_spa_does_not_serve_files_outside_static(tmp_path):
    (tmp_path / "secret.txt").write_text("top secret")
    with _spa_client(tmp_path) as c:
        r = c.get("/..%2Fsecret.txt")
        assert "top secret" not in r.text
