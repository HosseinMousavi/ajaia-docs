"""Word-level diff between two HTML documents, for the version-history preview."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from html.parser import HTMLParser

_BLOCK_TAGS = {"p", "h1", "h2", "h3", "li", "blockquote", "pre", "br", "hr", "ul", "ol"}
_TOKEN = re.compile(r"\n|[^\S\n]+|[^\s]+")

Op = tuple[str, str]  # ("equal" | "insert" | "delete", text)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def _newline(self) -> None:
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_starttag(self, tag, attrs):
        if tag in _BLOCK_TAGS:
            self._newline()

    def handle_endtag(self, tag):
        if tag in _BLOCK_TAGS:
            self._newline()

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html or "")
    parser.close()
    lines = (re.sub(r"[^\S\n]+", " ", line).strip() for line in "".join(parser.parts).split("\n"))
    return "\n".join(line for line in lines if line)


def word_diff(old_html: str, new_html: str) -> list[Op]:
    a = _TOKEN.findall(html_to_text(old_html))
    b = _TOKEN.findall(html_to_text(new_html))
    ops: list[Op] = []

    def emit(op: str, tokens: list[str]) -> None:
        text = "".join(tokens)
        if not text:
            return
        if ops and ops[-1][0] == op:
            ops[-1] = (op, ops[-1][1] + text)
        else:
            ops.append((op, text))

    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            emit("equal", a[i1:i2])
        else:
            emit("delete", a[i1:i2])
            emit("insert", b[j1:j2])
    return ops


def diff_stats(ops: list[Op]) -> dict[str, int]:
    count = lambda kind: sum(len(t.split()) for op, t in ops if op == kind)  # noqa: E731
    return {"added": count("insert"), "removed": count("delete")}
