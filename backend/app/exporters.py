"""Document export: Markdown and PDF.

Content is already allowlist-sanitized at write time (no images, scripts or external
resources), and the PDF renderer is additionally told not to fetch any URL.
"""

from __future__ import annotations

import html
import io

from markdownify import markdownify
from xhtml2pdf import pisa

_PDF_CSS = """
@page { size: letter; margin: 2.2cm 2.4cm; }
body { font-family: Helvetica; font-size: 11pt; line-height: 1.45; color: #1f2328; }
h1.doc-title { font-size: 20pt; margin: 0 0 14pt 0; padding-bottom: 6pt; border-bottom: 1px solid #d0d4da; }
h1 { font-size: 18pt; margin: 12pt 0 6pt 0; }
h2 { font-size: 14.5pt; margin: 12pt 0 4pt 0; }
h3 { font-size: 12.5pt; margin: 10pt 0 4pt 0; }
p { margin: 0 0 7pt 0; }
li { margin: 0 0 3pt 0; }
blockquote { margin: 6pt 0 6pt 12pt; padding-left: 8pt; color: #555; border-left: 3px solid #d0d4da; }
code, pre { font-family: Courier; background-color: #f2f3f5; }
a { color: #2f5bea; }
"""


def to_markdown(title: str, content_html: str) -> str:
    body = f"# {title}\n\n" if not content_html.lstrip().startswith("<h1") else ""
    return body + markdownify(content_html, heading_style="ATX", bullets="-").strip() + "\n"


def _no_fetch(uri: str, rel: str) -> str:
    return ""  # never load external resources while rendering


def to_pdf(title: str, content_html: str) -> bytes:
    doc = (
        "<html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title><style>{_PDF_CSS}</style></head><body>"
        f"<h1 class='doc-title'>{html.escape(title)}</h1>{content_html}</body></html>"
    )
    out = io.BytesIO()
    result = pisa.CreatePDF(doc, dest=out, encoding="utf-8", link_callback=_no_fetch)
    if result.err:
        raise RuntimeError("PDF rendering failed")
    return out.getvalue()
