"""Version snapshots with coalescing.

Autosave fires on every pause in typing, so one snapshot per save would bury the useful
history under noise. Instead, consecutive saves by the same author within
COALESCE_WINDOW update the latest "edit" snapshot in place. Snapshots of other kinds
(created, imported, baseline, restored) are never overwritten.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentVersion

COALESCE_WINDOW = timedelta(minutes=10)


def _aware(dt: datetime) -> datetime:
    # SQLite returns naive datetimes even for timezone-aware columns.
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _latest(db: Session, doc_id: str) -> DocumentVersion | None:
    stmt = (
        select(DocumentVersion)
        .where(DocumentVersion.document_id == doc_id)
        .order_by(DocumentVersion.id.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def _snapshot(doc: Document, kind: str, author_id: int | None, **extra) -> DocumentVersion:
    now = datetime.now(UTC)
    return DocumentVersion(
        document_id=doc.id,
        version=doc.version,
        kind=kind,
        title=doc.title,
        content_html=doc.content_html,
        author_id=author_id,
        created_at=extra.pop("created_at", now),
        updated_at=now,
        **extra,
    )


def record_initial(db: Session, doc: Document, kind: str) -> None:
    """For a freshly created/imported document (after flush, so doc.id exists)."""
    db.add(_snapshot(doc, kind, doc.owner_id))


def ensure_baseline(db: Session, doc: Document) -> None:
    """Documents created before history existed get their current state captured
    before the first change, so nothing that was there is lost."""
    if _latest(db, doc.id) is None:
        db.add(_snapshot(doc, "baseline", doc.owner_id, created_at=_aware(doc.updated_at)))
        db.flush()


def record_edit(db: Session, doc: Document, author_id: int) -> None:
    latest = _latest(db, doc.id)
    now = datetime.now(UTC)
    if (
        latest is not None
        and latest.kind == "edit"
        and latest.author_id == author_id
        and now - _aware(latest.updated_at) < COALESCE_WINDOW
    ):
        latest.version = doc.version
        latest.title = doc.title
        latest.content_html = doc.content_html
        latest.updated_at = now
        return
    db.add(_snapshot(doc, "edit", author_id))


def record_restore(db: Session, doc: Document, author_id: int, restored_from: int) -> None:
    db.add(_snapshot(doc, "restored", author_id, restored_from=restored_from))
