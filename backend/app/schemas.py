from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.models import ShareRole

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    if not _EMAIL_RE.match(value):
        raise ValueError("Invalid email address")
    return value


Email = Annotated[str, Field(max_length=320), AfterValidator(_normalize_email)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class LoginIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str


class DemoUserOut(BaseModel):
    email: str
    name: str


class DocumentCreate(BaseModel):
    title: Title = "Untitled document"
    content_html: str = ""


class DocumentUpdate(BaseModel):
    title: Title | None = None
    content_html: str | None = None
    base_version: int = Field(ge=1)


class ShareOut(BaseModel):
    user: UserOut
    role: ShareRole


class DocumentSummary(BaseModel):
    id: str
    title: str
    role: str
    owner: UserOut
    updated_at: datetime


class DocumentOut(DocumentSummary):
    content_html: str
    version: int
    created_at: datetime
    shares: list[ShareOut] | None = None  # only populated for the owner


class DocumentList(BaseModel):
    owned: list[DocumentSummary]
    shared: list[DocumentSummary]


class ShareIn(BaseModel):
    email: Email
    role: ShareRole
