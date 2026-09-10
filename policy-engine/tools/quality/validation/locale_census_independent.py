"""Independent strict text parser for the current locale string-leaf census.

This verifier is independently allocated from Lex's JSON/tree implementation.
It consumes JSON object/string grammar directly, with no shared parsing, decoding,
flattening or file-discovery helpers. It establishes structural observations only;
W5-K06 forbids treating them as translation or legal-equivalence evidence.
"""

from __future__ import annotations

import os
from pathlib import Path


class _CatalogueText:
    """Read the admitted object/string grammar without a generic JSON decoder."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.position = 0
        self.leaves: dict[tuple[str, ...], str] = {}

    def _space(self) -> None:
        while self.position < len(self.text) and self.text[self.position] in " \t\r\n":
            self.position += 1

    def _consume(self, token: str) -> None:
        self._space()
        if not self.text.startswith(token, self.position):
            raise ValueError(f"ambiguous: expected {token!r} at {self.position}")
        self.position += len(token)

    def _hex_unit(self) -> int:
        chunk = self.text[self.position : self.position + 4]
        if len(chunk) != 4 or any(char not in "0123456789abcdefABCDEF" for char in chunk):
            raise ValueError("ambiguous: malformed Unicode escape")
        self.position += 4
        return int(chunk, 16)

    def _string(self) -> str:
        self._consume('"')
        decoded: list[str] = []
        escapes = {
            '"': '"',
            "\\": "\\",
            "/": "/",
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
        }
        while self.position < len(self.text):
            char = self.text[self.position]
            self.position += 1
            if char == '"':
                return "".join(decoded)
            if ord(char) < 0x20 or 0xD800 <= ord(char) <= 0xDFFF:
                raise ValueError("ambiguous: invalid string code point")
            if char != "\\":
                decoded.append(char)
                continue
            if self.position == len(self.text):
                raise ValueError("ambiguous: unfinished escape")
            escape = self.text[self.position]
            self.position += 1
            if escape in escapes:
                decoded.append(escapes[escape])
                continue
            if escape != "u":
                raise ValueError("ambiguous: unknown escape")
            value = self._hex_unit()
            if 0xD800 <= value <= 0xDBFF:
                if self.text[self.position : self.position + 2] != "\\u":
                    raise ValueError("ambiguous: unpaired high surrogate")
                self.position += 2
                low = self._hex_unit()
                if not 0xDC00 <= low <= 0xDFFF:
                    raise ValueError("ambiguous: invalid low surrogate")
                value = 0x10000 + ((value - 0xD800) << 10) + low - 0xDC00
            elif 0xDC00 <= value <= 0xDFFF:
                raise ValueError("ambiguous: unpaired low surrogate")
            decoded.append(chr(value))
        raise ValueError("ambiguous: unterminated string")

    def _object(self, prefix: tuple[str, ...]) -> None:
        self._consume("{")
        self._space()
        if self.text.startswith("}", self.position):
            raise ValueError(f"ambiguous: empty object at {prefix!r}")
        keys: set[str] = set()
        while True:
            key = self._string()
            if key in keys:
                raise ValueError(f"ambiguous: duplicate key at {prefix + (key,)!r}")
            keys.add(key)
            self._consume(":")
            self._space()
            path = prefix + (key,)
            if self.text.startswith("{", self.position):
                self._object(path)
            elif self.text.startswith('"', self.position):
                self.leaves[path] = self._string()
            else:
                raise ValueError(f"ambiguous: nonstring/array leaf at {path!r}")
            self._space()
            if self.text.startswith("}", self.position):
                self.position += 1
                return
            self._consume(",")

    def read(self) -> dict[tuple[str, ...], str]:
        """Read the complete text, refusing trailing or unclassified content."""
        self._object(())
        self._space()
        if self.position != len(self.text):
            raise ValueError("ambiguous: trailing content")
        return self.leaves


def read_locale_catalogues(directory: Path) -> dict[str, dict[tuple[str, ...], str]]:
    """Enumerate every directory member and return exact decoded string leaves.

    Args:
        directory: The complete direct-file locale denominator to inspect.

    Returns:
        Filename to exact tuple-path/string maps; no source copies are persisted.

    Raises:
        ValueError: Any member is unreadable, unsupported or ambiguous.
    """
    try:
        with os.scandir(directory) as entries:
            members = sorted(entries, key=lambda entry: entry.name)
        if not members:
            raise ValueError("ambiguous: empty catalogue directory")
        output = {}
        for member in members:
            if not member.is_file(follow_symlinks=False) or not member.name.endswith(".json"):
                raise ValueError(f"ambiguous: unexpected member {member.name}")
            raw = Path(member.path).read_bytes()
            try:
                output[member.name] = _CatalogueText(raw.decode("utf-8")).read()
            except (UnicodeError, ValueError, RecursionError) as exc:
                raise ValueError(f"ambiguous: {member.name}: {exc}") from exc
        return output
    except OSError as exc:
        raise ValueError(f"ambiguous: cannot enumerate/read catalogue: {exc}") from exc
