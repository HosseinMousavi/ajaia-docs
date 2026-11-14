"""Collaboration features: comments, version history, presence.

Every route resolves the document through `access.load_document` first, and every child
record (comment, version) is looked up scoped to that document id, so an id from one
document can never be used through another document's URL.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app import versions
from app.access import Permission, can, load_document
from app.deps import CurrentUser, DbSession
from app.diff import diff_stats, word_diff
from app.models import Comment, DocumentVersion
from app.routers.documents import _full
from app.schemas import (
    CommentIn,
    CommentOut,
    CommentPatch,
    DocumentOut,
    PresenceIn,
    PresenceOut,
    RestoreIn,
    UserOut,
    VersionDetail,
    VersionOut,
)

router = APIRouter(prefix="/api/documents/{doc_id}", tags=["collaboration"])


# ---------- comments ----------

def _comment_out(c: Comment, with_replies: bool = True) -> CommentOut:
    return CommentOut(
        id=c.id,
        parent_id=c.parent_id,
        author=UserOut.model_validate(c.author),
        body=c.body,
        quote=c.quote,
        resolved=c.resolved,
        created_at=c.created_at,
        replies=[_comment_out(r, with_replies=False) for r in c.replies] if with_replies else [],
    )


def _get_comment(db, doc_id: str, comment_id: int) -> Comment:
    c = db.scalar(select(Comment).where(Comment.id == comment_id, Comment.document_id == doc_id))
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    return c


@router.get("/comments", response_model=list[CommentOut])
def list_comments(doc_id: str, user: CurrentUser, db: DbSession) -> list[CommentOut]:
    doc, _ = load_document(db, doc_id, user, Permission.VIEW)
    roots = db.scalars(
        select(Comment).where(Comment.document_id == doc.id, Comment.parent_id.is_(None)).order_by(Comment.id)
    ).unique()
    return [_comment_out(c) for c in roots]


@router.post("/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def create_comment(doc_id: str, body: CommentIn, user: CurrentUser, db: DbSession) -> CommentOut:
    doc, _ = load_document(db, doc_id, user, Permission.COMMENT)
    quote = body.quote or None
    if body.parent_id is not None:
        parent = _get_comment(db, doc.id, body.parent_id)
        if parent.parent_id is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Replies can't be nested")
        quote = None
    comment = Comment(document_id=doc.id, author_id=user.id, parent_id=body.parent_id, body=body.body, quote=quote)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return _comment_out(comment)


@router.patch("/comments/{comment_id}", response_model=CommentOut)
def update_comment(doc_id: str, comment_id: int, body: CommentPatch, user: CurrentUser, db: DbSession) -> CommentOut:
    doc, _ = load_document(db, doc_id, user, Permission.COMMENT)
    comment = _get_comment(db, doc.id, comment_id)
    if comment.parent_id is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only threads can be resolved")
    comment.resolved = body.resolved
    db.commit()
    db.refresh(comment)
    return _comment_out(comment)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(doc_id: str, comment_id: int, user: CurrentUser, db: DbSession) -> Response:
    doc, role = load_document(db, doc_id, user, Permission.VIEW)
    comment = _get_comment(db, doc.id, comment_id)
    if comment.author_id != user.id and role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only delete your own comments")
    db.delete(comment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- version history ----------

def _version_out(v: DocumentVersion) -> dict:
    return {
        "id": v.id,
        "version": v.version,
        "kind": v.kind,
        "title": v.title,
        "author": UserOut.model_validate(v.author) if v.author else None,
        "restored_from": v.restored_from,
        "created_at": v.created_at,
        "updated_at": v.updated_at,
    }


def _get_version(db, doc_id: str, version_id: int) -> DocumentVersion:
    v = db.scalar(
        select(DocumentVersion).where(DocumentVersion.id == version_id, DocumentVersion.document_id == doc_id)
    )
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    return v


@router.get("/versions", response_model=list[VersionOut])
def list_versions(doc_id: str, user: CurrentUser, db: DbSession) -> list[dict]:
    doc, _ = load_document(db, doc_id, user, Permission.VIEW)
    rows = db.scalars(
        select(DocumentVersion).where(DocumentVersion.document_id == doc.id).order_by(DocumentVersion.id.desc())
    )
    return [_version_out(v) for v in rows]


@router.get("/versions/{version_id}", response_model=VersionDetail)
def get_version(doc_id: str, version_id: int, user: CurrentUser, db: DbSession) -> dict:
    doc, _ = load_document(db, doc_id, user, Permission.VIEW)
    v = _get_version(db, doc.id, version_id)
    # "What would restoring this version change?" → diff from current to snapshot.
    ops = word_diff(doc.content_html, v.content_html)
    return {**_version_out(v), "content_html": v.content_html, "diff": ops, "stats": diff_stats(ops)}


@router.post("/versions/{version_id}/restore", response_model=DocumentOut)
def restore_version(
    doc_id: str, version_id: int, body: RestoreIn, user: CurrentUser, db: DbSession
) -> DocumentOut | JSONResponse:
    doc, role = load_document(db, doc_id, user, Permission.EDIT)
    snapshot = _get_version(db, doc.id, version_id)
    if body.base_version != doc.version:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Document was modified by someone else", "current_version": doc.version},
        )
    versions.ensure_baseline(db, doc)
    doc.title = snapshot.title
    doc.content_html = snapshot.content_html
    doc.version += 1
    versions.record_restore(db, doc, user.id, restored_from=snapshot.version)
    db.commit()
    db.refresh(doc)
    return _full(doc, role)


# ---------- presence ----------

@router.post("/presence", response_model=PresenceOut)
def heartbeat(doc_id: str, body: PresenceIn, request: Request, user: CurrentUser, db: DbSession) -> PresenceOut:
    doc, role = load_document(db, doc_id, user, Permission.VIEW)
    others = request.app.state.presence.heartbeat(
        doc.id, user_id=user.id, name=user.name, email=user.email, editing=body.editing and can(role, Permission.EDIT)
    )
    return PresenceOut(others=others)


@router.delete("/presence", status_code=status.HTTP_204_NO_CONTENT)
def leave(doc_id: str, request: Request, user: CurrentUser, db: DbSession) -> Response:
    doc, _ = load_document(db, doc_id, user, Permission.VIEW)
    request.app.state.presence.leave(doc.id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
