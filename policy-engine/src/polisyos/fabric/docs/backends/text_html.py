"""Public backends text html module API."""
from __future__ import annotations

import re
from html.parser import HTMLParser

_BLOCK_TAGS = {
    "p",
    "div",
    "br",
    "li",
    "ul",
    "ol",
    "table",
    "thead",
    "tbody",
    "tr",
    "td",
    "th",
    "section",
    "article",
    "header",
    "footer",
    "nav",
    "blockquote",
    "pre",
    "hr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
}

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


class _VisibleTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._ignore_stack: list[str] = []
        self._heading_level: int | None = None

    def _last_char(self) -> str | None:
        for chunk in reversed(self._chunks):
            if chunk:
                return chunk[-1]
        return None

    def _append(self, text: str) -> None:
        if not text:
            return
        self._chunks.append(text)

    def _append_newline(self) -> None:
        if self._last_char() != "\n":
            self._chunks.append("\n")

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"script", "style"}:
            self._ignore_stack.append(tag)
            return
        if tag in _HEADING_TAGS:
            self._heading_level = int(tag[1])
            self._append_newline()
            self._append("#" * self._heading_level + " ")
            return
        if tag == "br":
            self._append_newline()
            return
        if tag in _BLOCK_TAGS:
            self._append_newline()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._ignore_stack:
            if tag == self._ignore_stack[-1]:
                self._ignore_stack.pop()
            return
        if tag in _HEADING_TAGS:
            self._heading_level = None
            self._append_newline()
            return
        if tag in _BLOCK_TAGS:
            self._append_newline()

    def handle_startendtag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag == "br":
            self._append_newline()
            return
        if tag in _BLOCK_TAGS:
            self._append_newline()

    def handle_data(self, data: str) -> None:
        if self._ignore_stack:
            return
        if not data:
            return
        cleaned = re.sub(r"\s+", " ", data)
        if not cleaned:
            return
        if cleaned == " ":
            last = self._last_char()
            if last is None or last.isspace():
                return
        self._append(cleaned)

    def get_text(self) -> str:
        return "".join(self._chunks)


def normalize_html_visible_text_v1(text: str) -> str:
    """Extract visible text using stdlib HTML parser."""
    if not isinstance(text, str):
        raise TypeError("text must be str")
    parser = _VisibleTextExtractor()
    parser.feed(text)
    parser.close()
    return parser.get_text()


__all__ = ["normalize_html_visible_text_v1"]
