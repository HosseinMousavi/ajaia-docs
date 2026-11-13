"""Single choke point for document authorization.

Every route that touches a document resolves it through `load_document`, which
returns the document only if the caller has the required permission. Callers
without *any* access get `DocumentNotFound` (404) so existence is never leaked;
callers with access but an insufficient role get `PermissionDenied` (403).
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentShare, User


class Permission(StrEnum):
    VIEW = "view"
    EDIT = "edit"
    MANAGE = "manage"  # share, unshare, delete


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "owner": frozenset({Permission.VIEW, Permission.EDIT, Permission.MANAGE}),
    "editor": frozenset({Permission.VIEW, Permission.EDIT}),
    "viewer": frozenset({Permission.VIEW}),
}


class DocumentNotFound(Exception):
    pass


class PermissionDenied(Exception):
    pass


def resolve_role(db: Session, doc: Document, user: User) -> str | None:
    if doc.owner_id == user.id:
        return "owner"
    share = db.scalar(
        select(DocumentShare).where(DocumentShare.document_id == doc.id, DocumentShare.user_id == user.id)
    )
    return share.role if share else None


def load_document(db: Session, doc_id: str, user: User, needs: Permission) -> tuple[Document, str]:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise DocumentNotFound
    role = resolve_role(db, doc, user)
    if role is None:
        raise DocumentNotFound
    if needs not in ROLE_PERMISSIONS[role]:
        raise PermissionDenied
    return doc, role


def owned_documents(db: Session, user: User) -> list[Document]:
    stmt = select(Document).where(Document.owner_id == user.id).order_by(Document.updated_at.desc())
    return list(db.scalars(stmt))


def shared_documents(db: Session, user: User) -> list[tuple[Document, str]]:
    stmt = (
        select(Document, DocumentShare.role)
        .join(DocumentShare, DocumentShare.document_id == Document.id)
        .where(DocumentShare.user_id == user.id)
        .order_by(Document.updated_at.desc())
    )
    return [(doc, role) for doc, role in db.execute(stmt)]
