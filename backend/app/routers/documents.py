from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app import versions
from app.access import Permission, load_document, owned_documents, shared_documents
from app.deps import CurrentUser, DbSession
from app.exporters import to_markdown, to_pdf
from app.importers import ImportError_, UnsupportedFileType, file_to_html, title_from_filename
from app.models import Document, DocumentShare, User
from app.sanitize import sanitize_html
from app.schemas import (
    DocumentCreate,
    DocumentList,
    DocumentOut,
    DocumentSummary,
    DocumentUpdate,
    ShareIn,
    ShareOut,
    UserOut,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])


# ---------- serialization helpers ----------

def _summary(doc: Document, role: str) -> DocumentSummary:
    return DocumentSummary(
        id=doc.id, title=doc.title, role=role, owner=UserOut.model_validate(doc.owner), updated_at=doc.updated_at
    )


def _shares(doc: Document) -> list[ShareOut]:
    return [
        ShareOut(user=UserOut.model_validate(s.user), role=s.role)
        for s in sorted(doc.shares, key=lambda s: s.created_at)
    ]


def _full(doc: Document, role: str) -> DocumentOut:
    return DocumentOut(
        **_summary(doc, role).model_dump(),
        content_html=doc.content_html,
        version=doc.version,
        created_at=doc.created_at,
        shares=_shares(doc) if role == "owner" else None,
    )


def _clean_content(request: Request, html: str) -> str:
    if len(html.encode()) > request.app.state.settings.max_content_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Document content is too large")
    return sanitize_html(html)


# ---------- documents ----------

@router.get("", response_model=DocumentList)
def list_documents(user: CurrentUser, db: DbSession) -> DocumentList:
    return DocumentList(
        owned=[_summary(d, "owner") for d in owned_documents(db, user)],
        shared=[_summary(d, role) for d, role in shared_documents(db, user)],
    )


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(body: DocumentCreate, request: Request, user: CurrentUser, db: DbSession) -> DocumentOut:
    doc = Document(owner_id=user.id, title=body.title, content_html=_clean_content(request, body.content_html))
    db.add(doc)
    db.flush()
    versions.record_initial(db, doc, "created")
    db.commit()
    db.refresh(doc)
    return _full(doc, "owner")


@router.post("/import", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def import_document(file: UploadFile, request: Request, user: CurrentUser, db: DbSession) -> DocumentOut:
    limit = request.app.state.settings.max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"File exceeds the {limit // 1024} KB limit"
        )
    filename = file.filename or ""
    try:
        html = file_to_html(filename, data)
    except UnsupportedFileType as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    except ImportError_ as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    doc = Document(owner_id=user.id, title=title_from_filename(filename), content_html=html)
    db.add(doc)
    db.flush()
    versions.record_initial(db, doc, "imported")
    db.commit()
    db.refresh(doc)
    return _full(doc, "owner")


@router.get("/{doc_id}", response_model=DocumentOut, response_model_exclude_none=False)
def get_document(doc_id: str, user: CurrentUser, db: DbSession) -> DocumentOut:
    doc, role = load_document(db, doc_id, user, Permission.VIEW)
    return _full(doc, role)


@router.patch("/{doc_id}", response_model=DocumentOut)
def update_document(
    doc_id: str, body: DocumentUpdate, request: Request, user: CurrentUser, db: DbSession
) -> DocumentOut | JSONResponse:
    doc, role = load_document(db, doc_id, user, Permission.EDIT)
    if body.base_version != doc.version:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Document was modified by someone else", "current_version": doc.version},
        )
    new_content = _clean_content(request, body.content_html) if body.content_html is not None else None
    versions.ensure_baseline(db, doc)
    if body.title is not None:
        doc.title = body.title
    if new_content is not None:
        doc.content_html = new_content
    doc.version += 1
    versions.record_edit(db, doc, user.id)
    db.commit()
    db.refresh(doc)
    return _full(doc, role)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: str, user: CurrentUser, db: DbSession) -> Response:
    doc, _ = load_document(db, doc_id, user, Permission.MANAGE)
    db.delete(doc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


_UNSAFE_FILENAME = re.compile(r"[^\w\- .]+")


@router.get("/{doc_id}/export")
def export_document(
    doc_id: str, user: CurrentUser, db: DbSession, format: Literal["md", "pdf"] = "md"
) -> Response:
    doc, _ = load_document(db, doc_id, user, Permission.VIEW)
    safe_name = _UNSAFE_FILENAME.sub("_", doc.title).strip() or "document"
    if format == "pdf":
        content, media_type = to_pdf(doc.title, doc.content_html), "application/pdf"
    else:
        content, media_type = to_markdown(doc.title, doc.content_html), "text/markdown; charset=utf-8"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.{format}"'},
    )


# ---------- sharing ----------

@router.get("/{doc_id}/shares", response_model=list[ShareOut])
def list_shares(doc_id: str, user: CurrentUser, db: DbSession) -> list[ShareOut]:
    doc, _ = load_document(db, doc_id, user, Permission.MANAGE)
    return _shares(doc)


@router.put("/{doc_id}/shares", response_model=ShareOut)
def upsert_share(doc_id: str, body: ShareIn, user: CurrentUser, db: DbSession) -> ShareOut:
    doc, _ = load_document(db, doc_id, user, Permission.MANAGE)
    target = db.scalar(select(User).where(User.email == body.email))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user found with that email")
    if target.id == doc.owner_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You already own this document")
    share = db.scalar(
        select(DocumentShare).where(DocumentShare.document_id == doc.id, DocumentShare.user_id == target.id)
    )
    if share is None:
        share = DocumentShare(document_id=doc.id, user_id=target.id, role=body.role.value)
        db.add(share)
    else:
        share.role = body.role.value
    db.commit()
    return ShareOut(user=UserOut.model_validate(target), role=body.role)


@router.delete("/{doc_id}/shares/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share(doc_id: str, user_id: int, user: CurrentUser, db: DbSession) -> Response:
    doc, _ = load_document(db, doc_id, user, Permission.MANAGE)
    share = db.scalar(
        select(DocumentShare).where(DocumentShare.document_id == doc.id, DocumentShare.user_id == user_id)
    )
    if share is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share not found")
    db.delete(share)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
