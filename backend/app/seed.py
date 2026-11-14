from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentShare, User
from app.security import hash_password
from app.versions import record_initial

DEMO_PASSWORD = "demo1234"
DEMO_USERS: tuple[tuple[str, str], ...] = (
    ("alice@ajaia.test", "Alice Chen"),
    ("bob@ajaia.test", "Bob Rivera"),
    ("carol@ajaia.test", "Carol Okafor"),
)

WELCOME_HTML = (
    "<h1>Welcome to Ajaia Docs</h1>"
    "<p>This document is owned by <strong>Alice</strong> and shared with <em>Bob</em> as an editor.</p>"
    "<h2>Try it</h2>"
    "<ul><li>Format text with the toolbar or <code>Cmd/Ctrl+B</code>, <code>I</code>, <code>U</code></li>"
    "<li>Rename the document by editing the title</li>"
    "<li>Share it from the <strong>Share</strong> button as viewer, commenter or editor</li>"
    "<li>Select text and add a comment; open <strong>History</strong> to compare and restore versions</li></ul>"
)


def seed_demo_data(db: Session, *, with_sample_content: bool = True) -> None:
    """Idempotent: creates demo users and one shared sample doc on an empty database."""
    if db.scalar(select(User).limit(1)) is not None:
        return
    pw_hash = hash_password(DEMO_PASSWORD)
    users = [User(email=e, name=n, password_hash=pw_hash) for e, n in DEMO_USERS]
    db.add_all(users)
    db.flush()
    if not with_sample_content:
        db.commit()
        return
    alice, bob, _ = users
    welcome = Document(owner_id=alice.id, title="Welcome to Ajaia Docs", content_html=WELCOME_HTML)
    db.add(welcome)
    db.flush()
    record_initial(db, welcome, "created")
    db.add(DocumentShare(document_id=welcome.id, user_id=bob.id, role="editor"))
    db.commit()
