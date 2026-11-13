def test_create_rename_edit_and_reopen(alice):
    created = alice.post("/api/documents", json={"title": "Q4 plan"})
    assert created.status_code == 201
    doc = created.json()
    assert doc["title"] == "Q4 plan"
    assert doc["role"] == "owner"
    assert doc["version"] == 1

    html = "<h1>Plan</h1><p><strong>Bold</strong> <em>it</em> <u>under</u></p><ul><li>one</li></ul><ol><li>two</li></ol>"
    patched = alice.patch(
        f"/api/documents/{doc['id']}",
        json={"title": "Q4 plan v2", "content_html": html, "base_version": 1},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["version"] == 2

    reopened = alice.get(f"/api/documents/{doc['id']}").json()
    assert reopened["title"] == "Q4 plan v2"
    # Formatting survives the round-trip.
    for tag in ("<h1>", "<strong>", "<em>", "<u>", "<ul>", "<ol>", "<li>"):
        assert tag in reopened["content_html"]


def test_default_title_when_missing(alice):
    doc = alice.post("/api/documents", json={}).json()
    assert doc["title"] == "Untitled document"


def test_title_validation(alice):
    assert alice.post("/api/documents", json={"title": "   "}).status_code == 422
    assert alice.post("/api/documents", json={"title": "x" * 201}).status_code == 422


def test_content_size_limit(alice, settings):
    doc = alice.post("/api/documents", json={"title": "big"}).json()
    huge = "<p>" + "a" * (settings.max_content_bytes + 10) + "</p>"
    resp = alice.patch(f"/api/documents/{doc['id']}", json={"content_html": huge, "base_version": 1})
    assert resp.status_code == 413


def test_stale_version_conflict(alice):
    doc = alice.post("/api/documents", json={"title": "t"}).json()
    ok = alice.patch(f"/api/documents/{doc['id']}", json={"content_html": "<p>a</p>", "base_version": 1})
    assert ok.status_code == 200
    stale = alice.patch(f"/api/documents/{doc['id']}", json={"content_html": "<p>b</p>", "base_version": 1})
    assert stale.status_code == 409
    assert stale.json()["current_version"] == 2
    assert alice.get(f"/api/documents/{doc['id']}").json()["content_html"] == "<p>a</p>"


def test_script_and_handlers_are_stripped_on_save(alice):
    doc = alice.post("/api/documents", json={"title": "xss"}).json()
    evil = '<p onclick="steal()">hi<script>alert(1)</script><a href="javascript:alert(1)">x</a><img src=x onerror=alert(1)></p>'
    saved = alice.patch(f"/api/documents/{doc['id']}", json={"content_html": evil, "base_version": 1}).json()
    out = saved["content_html"].lower()
    for bad in ("<script", "onclick", "javascript:", "onerror", "<img"):
        assert bad not in out
    assert "hi" in out


def test_delete_owner_only(alice):
    doc = alice.post("/api/documents", json={"title": "temp"}).json()
    assert alice.delete(f"/api/documents/{doc['id']}").status_code == 204
    assert alice.get(f"/api/documents/{doc['id']}").status_code == 404


def test_export_markdown(alice):
    doc = alice.post("/api/documents", json={"title": "Notes"}).json()
    alice.patch(
        f"/api/documents/{doc['id']}",
        json={"content_html": "<h2>Hi</h2><p><strong>b</strong></p><ul><li>x</li></ul>", "base_version": 1},
    )
    resp = alice.get(f"/api/documents/{doc['id']}/export", params={"format": "md"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert 'filename="Notes.md"' in resp.headers["content-disposition"]
    assert "## Hi" in resp.text
    assert "**b**" in resp.text
