"""Version history, restore and diff."""

from datetime import UTC, datetime, timedelta

import pytest

from app.diff import html_to_text, word_diff


def _versions(client, doc_id):
    r = client.get(f"/api/documents/{doc_id}/versions")
    assert r.status_code == 200, r.text
    return r.json()


def _save(client, doc_id, html, base):
    r = client.patch(f"/api/documents/{doc_id}", json={"content_html": html, "base_version": base})
    assert r.status_code == 200, r.text
    return r.json()


# ---------- pure diff ----------

def test_html_to_text_keeps_block_boundaries():
    assert html_to_text("<h1>Title</h1><p>One <strong>two</strong></p><ul><li>a</li><li>b</li></ul>") == (
        "Title\nOne two\na\nb"
    )


def test_word_diff_marks_insertions_and_deletions():
    ops = word_diff("<p>ship on Friday</p>", "<p>ship on Monday please</p>")
    assert ("delete", "Friday") in ops
    assert ("insert", "Monday please") in ops
    assert ops[0] == ("equal", "ship on ")
    # Re-assembling equal+delete gives old text; equal+insert gives new text.
    assert "".join(t for op, t in ops if op != "insert") == "ship on Friday"
    assert "".join(t for op, t in ops if op != "delete") == "ship on Monday please"


def test_word_diff_identical():
    assert word_diff("<p>same</p>", "<p>same</p>") == [("equal", "same")]


# ---------- snapshots ----------

def test_new_document_has_created_snapshot(alice):
    doc = alice.post("/api/documents", json={"title": "T"}).json()
    vs = _versions(alice, doc["id"])
    assert [v["kind"] for v in vs] == ["created"]
    assert vs[0]["author"]["email"] == "alice@ajaia.test"


def test_import_snapshot_kind(alice):
    doc = alice.post("/api/documents/import", files={"file": ("n.txt", b"hello", "text/plain")}).json()
    assert [v["kind"] for v in _versions(alice, doc["id"])] == ["imported"]


def test_rapid_saves_by_same_author_coalesce(alice):
    doc = alice.post("/api/documents", json={"title": "T"}).json()
    _save(alice, doc["id"], "<p>a</p>", 1)
    _save(alice, doc["id"], "<p>ab</p>", 2)
    _save(alice, doc["id"], "<p>abc</p>", 3)
    vs = _versions(alice, doc["id"])
    # newest first: one coalesced "edit" on top of the immutable "created" snapshot
    assert [v["kind"] for v in vs] == ["edit", "created"]
    assert vs[0]["version"] == 4


def test_different_author_starts_new_snapshot(alice, bob):
    doc = alice.post("/api/documents", json={"title": "T"}).json()
    alice.put(f"/api/documents/{doc['id']}/shares", json={"email": "bob@ajaia.test", "role": "editor"})
    _save(alice, doc["id"], "<p>alice</p>", 1)
    _save(bob, doc["id"], "<p>bob</p>", 2)
    authors = [v["author"]["email"] for v in _versions(alice, doc["id"])]
    assert authors == ["bob@ajaia.test", "alice@ajaia.test", "alice@ajaia.test"]


def test_saves_outside_window_create_new_snapshot(app, alice):
    from app import versions as versions_mod

    doc = alice.post("/api/documents", json={"title": "T"}).json()
    _save(alice, doc["id"], "<p>one</p>", 1)
    # Age the latest snapshot past the coalescing window.
    with app.state.sessionmaker() as db:
        from sqlalchemy import select

        from app.models import DocumentVersion

        latest = db.scalars(
            select(DocumentVersion).where(DocumentVersion.document_id == doc["id"]).order_by(DocumentVersion.id.desc())
        ).first()
        latest.updated_at = datetime.now(UTC) - versions_mod.COALESCE_WINDOW - timedelta(seconds=1)
        db.commit()
    _save(alice, doc["id"], "<p>two</p>", 2)
    assert [v["kind"] for v in _versions(alice, doc["id"])] == ["edit", "edit", "created"]


def test_preexisting_document_gets_baseline_on_first_edit(app, alice):
    """Docs created before history existed must not lose their pre-edit state."""
    from app.models import Document, User
    from sqlalchemy import select

    with app.state.sessionmaker() as db:
        owner = db.scalar(select(User).where(User.email == "alice@ajaia.test"))
        legacy = Document(owner_id=owner.id, title="Legacy", content_html="<p>old</p>")
        db.add(legacy)
        db.commit()
        doc_id = legacy.id
    assert _versions(alice, doc_id) == []
    _save(alice, doc_id, "<p>new</p>", 1)
    vs = _versions(alice, doc_id)
    assert [v["kind"] for v in vs] == ["edit", "baseline"]
    preview = alice.get(f"/api/documents/{doc_id}/versions/{vs[1]['id']}").json()
    assert preview["content_html"] == "<p>old</p>"


# ---------- preview + restore ----------

@pytest.fixture()
def history(app, alice):
    """A doc with two distinct snapshots: 'created' (empty) and an edit."""
    doc = alice.post("/api/documents", json={"title": "Plan"}).json()
    saved = _save(alice, doc["id"], "<p>ship on Friday</p>", 1)
    return doc["id"], saved


def test_preview_includes_diff_against_current(alice, history):
    doc_id, _ = history
    created = _versions(alice, doc_id)[-1]
    p = alice.get(f"/api/documents/{doc_id}/versions/{created['id']}").json()
    assert p["content_html"] == ""
    # Diff answers "what would restoring this version do": current → snapshot.
    assert ("delete", "ship on Friday") in [tuple(x) for x in p["diff"]]
    assert p["stats"] == {"added": 0, "removed": 3}


def test_restore(alice, history):
    doc_id, saved = history
    created = _versions(alice, doc_id)[-1]
    r = alice.post(
        f"/api/documents/{doc_id}/versions/{created['id']}/restore", json={"base_version": saved["version"]}
    )
    assert r.status_code == 200, r.text
    assert r.json()["content_html"] == ""
    assert r.json()["version"] == saved["version"] + 1
    top = _versions(alice, doc_id)[0]
    assert top["kind"] == "restored"
    assert top["restored_from"] == created["version"]


def test_restore_requires_current_version(alice, history):
    doc_id, _ = history
    created = _versions(alice, doc_id)[-1]
    r = alice.post(f"/api/documents/{doc_id}/versions/{created['id']}/restore", json={"base_version": 1})
    assert r.status_code == 409


def test_history_permissions(alice, bob, carol, history):
    doc_id, saved = history
    alice.put(f"/api/documents/{doc_id}/shares", json={"email": "bob@ajaia.test", "role": "viewer"})
    vid = _versions(alice, doc_id)[-1]["id"]
    # Viewers can browse history but not restore.
    assert len(_versions(bob, doc_id)) == 2
    assert bob.get(f"/api/documents/{doc_id}/versions/{vid}").status_code == 200
    assert (
        bob.post(f"/api/documents/{doc_id}/versions/{vid}/restore", json={"base_version": saved["version"]}).status_code
        == 403
    )
    # No access → 404.
    assert carol.get(f"/api/documents/{doc_id}/versions").status_code == 404
    assert carol.get(f"/api/documents/{doc_id}/versions/{vid}").status_code == 404


def test_version_ids_are_scoped_to_their_document(alice, history):
    doc_id, _ = history
    vid = _versions(alice, doc_id)[-1]["id"]
    other = alice.post("/api/documents", json={"title": "Other"}).json()
    assert alice.get(f"/api/documents/{other['id']}/versions/{vid}").status_code == 404
    assert (
        alice.post(f"/api/documents/{other['id']}/versions/{vid}/restore", json={"base_version": 1}).status_code
        == 404
    )
