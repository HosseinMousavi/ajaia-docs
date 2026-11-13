import io

from docx import Document as DocxDocument


def _upload(client, name: str, data: bytes, mime: str = "application/octet-stream"):
    return client.post("/api/documents/import", files={"file": (name, data, mime)})


def test_import_txt_creates_editable_document(alice):
    resp = _upload(alice, "meeting notes.txt", b"Line one\nLine two\n\nNew para <b>not html</b>", "text/plain")
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["title"] == "meeting notes"
    assert doc["role"] == "owner"
    # Plain text is escaped, not interpreted as HTML.
    assert "&lt;b&gt;" in doc["content_html"]
    assert "<p>Line one" in doc["content_html"]
    assert alice.get("/api/documents").json()["owned"][0]["id"] == doc["id"]


def test_import_markdown_preserves_structure(alice):
    md = b"# Title\n\nSome **bold** and *italic*.\n\n- a\n- b\n\n1. one\n2. two\n\n<script>alert(1)</script>"
    doc = _upload(alice, "readme.md", md, "text/markdown").json()
    html = doc["content_html"]
    for tag in ("<h1>", "<strong>", "<em>", "<ul>", "<ol>"):
        assert tag in html
    assert "<script" not in html.lower()


def test_import_docx(alice):
    d = DocxDocument()
    d.add_heading("Quarterly Review", level=1)
    p = d.add_paragraph("Revenue was ")
    p.add_run("up").bold = True
    d.add_paragraph("first", style="List Bullet")
    buf = io.BytesIO()
    d.save(buf)
    resp = _upload(alice, "review.docx", buf.getvalue())
    assert resp.status_code == 201, resp.text
    html = resp.json()["content_html"]
    assert "<h1>Quarterly Review</h1>" in html
    assert "<strong>up</strong>" in html
    assert "<li>" in html


def test_rejects_unsupported_type(alice):
    resp = _upload(alice, "image.png", b"\x89PNG\r\n")
    assert resp.status_code == 415
    assert ".txt" in resp.json()["detail"]


def test_rejects_fake_docx(alice):
    assert _upload(alice, "fake.docx", b"this is not a zip").status_code == 422


def test_rejects_oversized_file(alice, settings):
    resp = _upload(alice, "big.txt", b"a" * (settings.max_upload_bytes + 1))
    assert resp.status_code == 413


def test_rejects_empty_and_non_utf8(alice):
    assert _upload(alice, "empty.txt", b"").status_code == 422
    assert _upload(alice, "bin.txt", b"\xff\xfe\x00\xd8bad").status_code == 422


def test_import_requires_auth(anon):
    assert _upload(anon, "a.txt", b"hi").status_code == 401
