"""Server-side HTML allowlist. Every piece of HTML that reaches storage passes through here,
regardless of whether it came from the editor or from a file import."""

from __future__ import annotations

import nh3

ALLOWED_TAGS: set[str] = {
    "p", "br", "hr",
    "strong", "b", "em", "i", "u", "s", "code", "pre", "blockquote",
    "h1", "h2", "h3",
    "ul", "ol", "li",
    "a",
}
ALLOWED_ATTRIBUTES: dict[str, set[str]] = {"a": {"href"}}
ALLOWED_URL_SCHEMES: set[str] = {"http", "https", "mailto"}


def sanitize_html(html: str) -> str:
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
        strip_comments=True,
    )
