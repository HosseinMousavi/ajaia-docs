"""Live presence indicators and PDF export."""

import io

from pypdf import PdfReader

from app.presence import PresenceTracker


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


# ---------- tracker unit tests ----------

def test_tracker_reports_others_and_expires():
    clock = FakeClock()
    p = PresenceTracker(ttl_seconds=15, clock=clock)
    p.heartbeat("d1", user_id=1, name="Alice", email="a@x", editing=False)
    others = p.heartbeat("d1", user_id=2, name="Bob", email="b@x", editing=True)
    assert others == [{"id": 1, "name": "Alice", "email": "a@x", "editing": False}]
    assert p.heartbeat("d1", user_id=1, name="Alice", email="a@x", editing=False) == [
        {"id": 2, "name": "Bob", "email": "b@x", "editing": True}
    ]
    clock.t += 16
    assert p.heartbeat("d1", user_id=1, name="Alice", email="a@x", editing=False) == []


def test_tracker_is_per_document_and_leave_works():
    p = PresenceTracker(ttl_seconds=15, clock=FakeClock())
    p.heartbeat("d1", user_id=1, name="A", email="a", editing=False)
    assert p.heartbeat("d2", user_id=2, name="B", email="b", editing=False) == []
    p.heartbeat("d1", user_id=2, name="B", email="b", editing=False)
    p.leave("d1", 2)
    assert p.heartbeat("d1", user_id=1, name="A", email="a", editing=False) == []


def test_tracker_prunes_empty_documents():
    clock = FakeClock()
    p = PresenceTracker(ttl_seconds=15, clock=clock)
    p.heartbeat("d1", user_id=1, name="A", email="a", editing=False)
    clock.t += 100
    p.heartbeat("d2", user_id=1, name="A", email="a", editing=False)
    assert "d1" not in p._docs  # no unbounded growth


# ---------- presence API ----------

def test_presence_api_shows_collaborators(alice, bob, carol):
    doc = alice.post("/api/documents", json={"title": "Live"}).json()
    alice.put(f"/api/documents/{doc['id']}/shares", json={"email": "bob@ajaia.test", "role": "editor"})
    url = f"/api/documents/{doc['id']}/presence"
    assert alice.post(url, json={"editing": False}).json() == {"others": []}
    others = bob.post(url, json={"editing": True}).json()["others"]
    assert [o["email"] for o in others] == ["alice@ajaia.test"]
    seen_by_alice = alice.post(url, json={"editing": False}).json()["others"]
    assert seen_by_alice == [{"id": seen_by_alice[0]["id"], "name": "Bob Rivera", "email": "bob@ajaia.test", "editing": True}]
    # Leaving removes you immediately.
    assert bob.delete(url).status_code == 204
    assert alice.post(url, json={"editing": False}).json() == {"others": []}
    # No access → 404, and nothing leaks.
    assert carol.post(url, json={"editing": False}).status_code == 404


def test_viewer_cannot_claim_editing(alice, bob):
    doc = alice.post("/api/documents", json={"title": "Live"}).json()
    alice.put(f"/api/documents/{doc['id']}/shares", json={"email": "bob@ajaia.test", "role": "viewer"})
    url = f"/api/documents/{doc['id']}/presence"
    bob.post(url, json={"editing": True})
    assert alice.post(url, json={"editing": False}).json()["others"][0]["editing"] is False


# ---------- PDF ----------

def test_export_pdf(alice):
    doc = alice.post("/api/documents", json={"title": "Board memo"}).json()
    alice.patch(
        f"/api/documents/{doc['id']}",
        json={"content_html": "<h2>Summary</h2><p><strong>Revenue</strong> grew.</p><ul><li>Item one</li></ul>", "base_version": 1},
    )
    r = alice.get(f"/api/documents/{doc['id']}/export", params={"format": "pdf"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert 'filename="Board memo.pdf"' in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF")
    text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(r.content)).pages)
    for expected in ("Board memo", "Summary", "Revenue", "Item one"):
        assert expected in text


def test_export_pdf_escapes_title(alice):
    doc = alice.post("/api/documents", json={"title": "<b>A & B</b>"}).json()
    r = alice.get(f"/api/documents/{doc['id']}/export", params={"format": "pdf"})
    assert r.status_code == 200
    text = PdfReader(io.BytesIO(r.content)).pages[0].extract_text()
    assert "<b>A & B</b>" in text


def test_export_rejects_unknown_format(alice):
    doc = alice.post("/api/documents", json={"title": "x"}).json()
    assert alice.get(f"/api/documents/{doc['id']}/export", params={"format": "exe"}).status_code == 422
