from app.security import hash_password, verify_password


def test_password_hash_roundtrip_and_salted():
    h1 = hash_password("s3cret!")
    h2 = hash_password("s3cret!")
    assert h1 != h2, "hashes must be salted"
    assert verify_password("s3cret!", h1)
    assert not verify_password("wrong", h1)
    assert not verify_password("s3cret!", "garbage")


def test_login_success_sets_httponly_cookie(anon):
    resp = anon.post("/api/auth/login", json={"email": "alice@ajaia.test", "password": "demo1234"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "alice@ajaia.test"
    assert "password_hash" not in body
    cookie_header = resp.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header


def test_login_is_case_insensitive_on_email(anon):
    resp = anon.post("/api/auth/login", json={"email": "  ALICE@ajaia.test ", "password": "demo1234"})
    assert resp.status_code == 200


def test_login_wrong_password_gives_generic_error(anon):
    bad_pw = anon.post("/api/auth/login", json={"email": "alice@ajaia.test", "password": "nope"})
    no_user = anon.post("/api/auth/login", json={"email": "ghost@ajaia.test", "password": "nope"})
    assert bad_pw.status_code == no_user.status_code == 401
    # Same message either way: no user enumeration via login.
    assert bad_pw.json()["detail"] == no_user.json()["detail"]


def test_protected_routes_require_auth(anon):
    assert anon.get("/api/auth/me").status_code == 401
    assert anon.get("/api/documents").status_code == 401
    assert anon.post("/api/documents", json={"title": "x"}).status_code == 401


def test_tampered_cookie_rejected(anon):
    anon.cookies.set("ajaia_session", "forged.value.here")
    assert anon.get("/api/auth/me").status_code == 401


def test_me_and_logout(alice):
    assert alice.get("/api/auth/me").json()["email"] == "alice@ajaia.test"
    assert alice.post("/api/auth/logout").status_code == 204
    assert alice.get("/api/auth/me").status_code == 401


def test_demo_users_listing_exposes_no_secrets(anon):
    users = anon.get("/api/auth/demo-users").json()
    emails = {u["email"] for u in users}
    assert {"alice@ajaia.test", "bob@ajaia.test", "carol@ajaia.test"} <= emails
    for u in users:
        assert set(u) == {"email", "name"}
