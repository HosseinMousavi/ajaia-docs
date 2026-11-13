"""Access-control tests. These are the most important tests in the suite:
a document must never be visible to a user who was not granted access."""

import pytest


@pytest.fixture()
def alice_doc(alice):
    doc = alice.post("/api/documents", json={"title": "Alice private"}).json()
    alice.patch(
        f"/api/documents/{doc['id']}",
        json={"content_html": "<p>secret salary data</p>", "base_version": 1},
    )
    return doc


def test_unshared_document_is_invisible_to_other_users(alice_doc, bob):
    doc_id = alice_doc["id"]
    # 404 (not 403) so existence is not leaked.
    assert bob.get(f"/api/documents/{doc_id}").status_code == 404
    assert bob.patch(f"/api/documents/{doc_id}", json={"title": "pwn", "base_version": 2}).status_code == 404
    assert bob.delete(f"/api/documents/{doc_id}").status_code == 404
    assert bob.get(f"/api/documents/{doc_id}/export", params={"format": "md"}).status_code == 404
    assert bob.get(f"/api/documents/{doc_id}/shares").status_code == 404
    listing = bob.get("/api/documents").json()
    all_ids = {d["id"] for d in listing["owned"] + listing["shared"]}
    assert doc_id not in all_ids
    assert "secret salary data" not in str(listing)


def test_owned_vs_shared_listing(alice, alice_doc, bob):
    resp = alice.put(
        f"/api/documents/{alice_doc['id']}/shares", json={"email": "bob@ajaia.test", "role": "viewer"}
    )
    assert resp.status_code == 200, resp.text

    a = alice.get("/api/documents").json()
    b = bob.get("/api/documents").json()
    assert [d["id"] for d in a["owned"]] == [alice_doc["id"]]
    assert a["shared"] == []
    assert b["owned"] == []
    assert [d["id"] for d in b["shared"]] == [alice_doc["id"]]
    shared = b["shared"][0]
    assert shared["role"] == "viewer"
    assert shared["owner"]["email"] == "alice@ajaia.test"


def test_viewer_can_read_but_not_write(alice, alice_doc, bob):
    alice.put(f"/api/documents/{alice_doc['id']}/shares", json={"email": "bob@ajaia.test", "role": "viewer"})
    got = bob.get(f"/api/documents/{alice_doc['id']}")
    assert got.status_code == 200
    assert got.json()["role"] == "viewer"
    assert "shares" not in got.json() or got.json()["shares"] is None
    resp = bob.patch(f"/api/documents/{alice_doc['id']}", json={"content_html": "<p>x</p>", "base_version": 2})
    assert resp.status_code == 403


def test_editor_can_write_but_not_manage_or_delete(alice, alice_doc, bob, carol):
    alice.put(f"/api/documents/{alice_doc['id']}/shares", json={"email": "bob@ajaia.test", "role": "editor"})
    resp = bob.patch(
        f"/api/documents/{alice_doc['id']}", json={"content_html": "<p>bob edit</p>", "base_version": 2}
    )
    assert resp.status_code == 200
    assert "bob edit" in alice.get(f"/api/documents/{alice_doc['id']}").json()["content_html"]

    reshare = bob.put(
        f"/api/documents/{alice_doc['id']}/shares", json={"email": "carol@ajaia.test", "role": "editor"}
    )
    assert reshare.status_code == 403
    assert bob.delete(f"/api/documents/{alice_doc['id']}").status_code == 403
    assert carol.get(f"/api/documents/{alice_doc['id']}").status_code == 404


def test_role_change_and_revoke(alice, alice_doc, bob):
    url = f"/api/documents/{alice_doc['id']}/shares"
    alice.put(url, json={"email": "bob@ajaia.test", "role": "viewer"})
    alice.put(url, json={"email": "bob@ajaia.test", "role": "editor"})
    shares = alice.get(url).json()
    assert len(shares) == 1 and shares[0]["role"] == "editor"

    bob_id = shares[0]["user"]["id"]
    assert alice.delete(f"{url}/{bob_id}").status_code == 204
    assert bob.get(f"/api/documents/{alice_doc['id']}").status_code == 404
    assert bob.get("/api/documents").json()["shared"] == []


def test_share_validation(alice, alice_doc):
    url = f"/api/documents/{alice_doc['id']}/shares"
    assert alice.put(url, json={"email": "alice@ajaia.test", "role": "editor"}).status_code == 400
    assert alice.put(url, json={"email": "nobody@ajaia.test", "role": "editor"}).status_code == 404
    assert alice.put(url, json={"email": "bob@ajaia.test", "role": "admin"}).status_code == 422
    assert alice.put(url, json={"email": "not-an-email", "role": "viewer"}).status_code == 422


def test_deleting_document_removes_shares(alice, alice_doc, bob):
    alice.put(f"/api/documents/{alice_doc['id']}/shares", json={"email": "bob@ajaia.test", "role": "viewer"})
    alice.delete(f"/api/documents/{alice_doc['id']}")
    assert bob.get("/api/documents").json()["shared"] == []


def test_unknown_document_id_is_404(alice):
    assert alice.get("/api/documents/does-not-exist").status_code == 404


def test_sample_content_seeded_as_shared_doc(tmp_path):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    s = Settings(database_url=f"sqlite:///{tmp_path / 'seed.db'}", secret_key="k", seed_sample_content=True)
    with TestClient(create_app(s)) as c:
        c.post("/api/auth/login", json={"email": "bob@ajaia.test", "password": "demo1234"})
        shared = c.get("/api/documents").json()["shared"]
        assert [d["title"] for d in shared] == ["Welcome to Ajaia Docs"]
        assert shared[0]["role"] == "editor"
