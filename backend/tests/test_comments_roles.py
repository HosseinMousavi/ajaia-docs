"""Commenter role + threaded comments."""

import pytest


@pytest.fixture()
def doc(alice):
    d = alice.post("/api/documents", json={"title": "Spec"}).json()
    alice.patch(f"/api/documents/{d['id']}", json={"content_html": "<p>The launch date is Friday.</p>", "base_version": 1})
    return d


def _share(owner, doc_id, email, role):
    r = owner.put(f"/api/documents/{doc_id}/shares", json={"email": email, "role": role})
    assert r.status_code == 200, r.text


def _url(doc, suffix=""):
    return f"/api/documents/{doc['id']}/comments{suffix}"


# ---------- role matrix ----------

def test_commenter_role_can_comment_but_not_edit(alice, bob, doc):
    _share(alice, doc["id"], "bob@ajaia.test", "commenter")
    got = bob.get(f"/api/documents/{doc['id']}").json()
    assert got["role"] == "commenter"
    assert bob.patch(f"/api/documents/{doc['id']}", json={"title": "x", "base_version": 2}).status_code == 403
    assert bob.post(_url(doc), json={"body": "Is Friday firm?", "quote": "Friday"}).status_code == 201
    assert bob.put(f"/api/documents/{doc['id']}/shares", json={"email": "carol@ajaia.test", "role": "viewer"}).status_code == 403


def test_viewer_can_read_comments_but_not_post(alice, bob, doc):
    alice.post(_url(doc), json={"body": "Owner note"})
    _share(alice, doc["id"], "bob@ajaia.test", "viewer")
    assert [t["body"] for t in bob.get(_url(doc)).json()] == ["Owner note"]
    assert bob.post(_url(doc), json={"body": "hi"}).status_code == 403


def test_editor_and_owner_can_comment(alice, bob, doc):
    _share(alice, doc["id"], "bob@ajaia.test", "editor")
    assert alice.post(_url(doc), json={"body": "a"}).status_code == 201
    assert bob.post(_url(doc), json={"body": "b"}).status_code == 201


def test_listing_shows_commenter_role(alice, bob, doc):
    _share(alice, doc["id"], "bob@ajaia.test", "commenter")
    assert bob.get("/api/documents").json()["shared"][0]["role"] == "commenter"


# ---------- threads ----------

def test_thread_with_replies_and_quote(alice, bob, doc):
    _share(alice, doc["id"], "bob@ajaia.test", "commenter")
    root = bob.post(_url(doc), json={"body": "  Is Friday firm?  ", "quote": "Friday"}).json()
    assert root["body"] == "Is Friday firm?"
    assert root["quote"] == "Friday"
    assert root["author"]["email"] == "bob@ajaia.test"
    reply = alice.post(_url(doc), json={"body": "Yes, locked.", "parent_id": root["id"], "quote": "ignored"}).json()
    assert reply["quote"] is None

    threads = alice.get(_url(doc)).json()
    assert len(threads) == 1
    assert threads[0]["id"] == root["id"]
    assert [r["body"] for r in threads[0]["replies"]] == ["Yes, locked."]


def test_no_nested_replies(alice, doc):
    root = alice.post(_url(doc), json={"body": "root"}).json()
    reply = alice.post(_url(doc), json={"body": "r1", "parent_id": root["id"]}).json()
    assert alice.post(_url(doc), json={"body": "r2", "parent_id": reply["id"]}).status_code == 400


def test_resolve_and_reopen(alice, bob, doc):
    _share(alice, doc["id"], "bob@ajaia.test", "commenter")
    root = alice.post(_url(doc), json={"body": "fix typo"}).json()
    assert bob.patch(_url(doc, f"/{root['id']}"), json={"resolved": True}).json()["resolved"] is True
    assert alice.get(_url(doc)).json()[0]["resolved"] is True
    assert alice.patch(_url(doc, f"/{root['id']}"), json={"resolved": False}).json()["resolved"] is False


def test_delete_rules(alice, bob, carol, doc):
    _share(alice, doc["id"], "bob@ajaia.test", "commenter")
    _share(alice, doc["id"], "carol@ajaia.test", "commenter")
    bobs = bob.post(_url(doc), json={"body": "bob's"}).json()
    carols = carol.post(_url(doc), json={"body": "carol's"}).json()
    # Can't delete someone else's comment...
    assert bob.delete(_url(doc, f"/{carols['id']}")).status_code == 403
    # ...but can delete your own, and the owner can moderate any.
    assert bob.delete(_url(doc, f"/{bobs['id']}")).status_code == 204
    assert alice.delete(_url(doc, f"/{carols['id']}")).status_code == 204
    assert alice.get(_url(doc)).json() == []


def test_deleting_root_removes_replies(alice, doc):
    root = alice.post(_url(doc), json={"body": "root"}).json()
    alice.post(_url(doc), json={"body": "reply", "parent_id": root["id"]})
    alice.delete(_url(doc, f"/{root['id']}"))
    assert alice.get(_url(doc)).json() == []


def test_comment_validation(alice, doc):
    assert alice.post(_url(doc), json={"body": "   "}).status_code == 422
    assert alice.post(_url(doc), json={"body": "x" * 2001}).status_code == 422
    assert alice.post(_url(doc), json={"body": "ok", "quote": "q" * 501}).status_code == 422
    assert alice.post(_url(doc), json={"body": "ok", "parent_id": 999999}).status_code == 404


def test_comment_body_is_plain_text_not_html(alice, doc):
    c = alice.post(_url(doc), json={"body": "<script>alert(1)</script>"}).json()
    # Stored verbatim as text; the UI renders it as text (React escapes), never as HTML.
    assert c["body"] == "<script>alert(1)</script>"


# ---------- isolation ----------

def test_comments_isolated_between_documents_and_users(alice, bob, carol, doc):
    root = alice.post(_url(doc), json={"body": "private"}).json()
    other = bob.post("/api/documents", json={"title": "Bob's"}).json()
    other_url = f"/api/documents/{other['id']}/comments"
    # Carol has no access at all → 404 everywhere.
    assert carol.get(_url(doc)).status_code == 404
    assert carol.post(_url(doc), json={"body": "x"}).status_code == 404
    # A comment id from doc A can't be reached through doc B's URL.
    assert bob.patch(f"{other_url}/{root['id']}", json={"resolved": True}).status_code == 404
    assert bob.delete(f"{other_url}/{root['id']}").status_code == 404
    # Can't attach a reply in doc B to a thread in doc A.
    assert bob.post(other_url, json={"body": "x", "parent_id": root["id"]}).status_code == 404


def test_deleting_document_deletes_comments(alice, doc):
    alice.post(_url(doc), json={"body": "x"})
    assert alice.delete(f"/api/documents/{doc['id']}").status_code == 204
    assert alice.get(_url(doc)).status_code == 404
