"""Convert uploaded files into sanitized HTML for a new document."""

from __future__ import annotations

import html
import io
import zipfile
from pathlib import PurePath

import mammoth
import markdown as md

from app.sanitize import sanitize_html

SUPPORTED_EXTENSIONS: tuple[str, ...] = (".txt", ".md", ".markdown", ".docx")


class ImportError_(Exception):
    """Raised for files we recognise but cannot convert (maps to 422)."""


class UnsupportedFileType(Exception):
    """Raised for extensions outside the allowlist (maps to 415)."""


def title_from_filename(filename: str) -> str:
    stem = PurePath(filename or "").stem.strip()
    return (stem or "Imported document")[:200]


def _decode_text(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportError_("File is not valid UTF-8 text.") from exc
    if "\x00" in text:
        raise ImportError_("File appears to be binary, not text.")
    return text


def _txt_to_html(text: str) -> str:
    paragraphs = [p for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    return "".join(
        "<p>" + "<br>".join(html.escape(line) for line in para.split("\n")) + "</p>" for para in paragraphs
    )


def _docx_to_html(data: bytes) -> str:
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise ImportError_("File is not a valid .docx document.")
    try:
        result = mammoth.convert_to_html(io.BytesIO(data))
    except Exception as exc:  # mammoth raises a variety of errors on malformed input
        raise ImportError_("Could not read .docx content.") from exc
    return result.value


def file_to_html(filename: str, data: bytes) -> str:
    ext = PurePath(filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileType(f"Unsupported file type. Supported: {', '.join(SUPPORTED_EXTENSIONS)}")
    if not data:
        raise ImportError_("File is empty.")

    match ext:
        case ".txt":
            raw = _txt_to_html(_decode_text(data))
        case ".md" | ".markdown":
            raw = md.markdown(_decode_text(data), extensions=["sane_lists"])
        case ".docx":
            raw = _docx_to_html(data)
        case _:  # pragma: no cover - guarded above
            raise UnsupportedFileType(ext)
    return sanitize_html(raw)
