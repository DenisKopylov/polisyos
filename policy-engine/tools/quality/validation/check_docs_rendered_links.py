#!/usr/bin/env python3
"""Check local files and HTML fragments in an already-built documentation site.

The checker reads an explicit emitted site tree; it never invokes MkDocs or
accesses the network. A complete pass covers local targets and HTML anchors in
the listed HTML/CSS reference forms. External URL liveness, browser behavior,
JavaScript-generated navigation, and non-HTML fragment semantics are outside
the measured property.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import posixpath
import re
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

from tools.lib.fs import measure_file_reads, measured_read_bytes
from tools.lib.imports import repo_root_from

URI_ATTRIBUTES = (
    "href",
    "src",
    "poster",
    "action",
    "formaction",
    "xlink:href",
    "data",
    "cite",
    "background",
    "manifest",
    "longdesc",
    "usemap",
    "profile",
    "codebase",
    "classid",
)
SUPPORTED_REFERENCE_FORMS = {
    "html_uri_attributes": list(URI_ATTRIBUTES),
    "html_other": [
        "srcset candidate URLs",
        "meta[http-equiv=refresh] content URL",
        "style attribute CSS url()/@import",
        "style element CSS url()/@import",
    ],
    "external_css": ["url()", "@import url()", "@import quoted URL"],
}
UNMEASURED_SCHEMES = {"blob", "data", "javascript", "mailto", "tel"}
HTML_SUFFIXES = {".html", ".htm"}
META_REFRESH_URL = re.compile(
    r"\burl\s*=\s*(?:\"(?P<double>[^\"]*)\"|"
    r"'(?P<single>[^']*)'|(?P<bare>[^;]*))",
    re.IGNORECASE,
)
CSS_NAME_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
UNRESOLVED_BY_CONSTRUCTION = [
    "HTML uses Python's standard-library HTMLParser, not HTML5 tree construction; malformed-markup recovery is not established.",
    "HTML URI attributes outside the explicit supported_reference_forms.html_uri_attributes allowlist are not interpreted.",
    "CSS URL-bearing constructs outside url() and @import (for example image-set()) are not interpreted.",
    "External HTTP(S) URL availability is not fetched or established.",
    "JavaScript, service-worker, browser-routing, and runtime-generated navigation are not scanned.",
    "CSS url(#id), SVG fragments, and other non-HTML fragment semantics are not resolved.",
    "This receipt binds the emitted files read by this checker, not their MkDocs source commit or build invocation.",
    "A post-read re-read detects observed drift during the scan but does not establish atomic snapshot semantics.",
    "The checker observes explicit file reads and directory enumeration only; imports and filesystem metadata operations are not process-wide audited.",
    "Origin comparison admits bounded ASCII DNS names, canonical dotted-decimal IPv4, and bracketed IPv6 only; non-ASCII, percent-encoded, and legacy/numeric IPv4 host forms are UNRUN because this checker has no browser-equivalent WHATWG/UTS46 normalizer.",
    "The smallest capability that closes the host-normalization boundary is a browser-equivalent URL normalizer; this no-dependency checker does not provide or import one.",
]


@dataclass(frozen=True)
class Reference:
    """One emitted URI value and its resolution context."""

    source: str
    line: int
    target: str
    kind: str
    base_url: str | None = None
    anchor_kind: str | None = None


class OriginNormalizationError(ValueError):
    """A URL authority form outside the checker's bounded origin grammar."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason


class PageParser(HTMLParser):
    """Collect emitted page IDs and URI values with source lines."""

    def __init__(self, source: str, page_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source
        self.page_url = page_url
        self.ids: set[str] = set()
        self.map_names: set[str] = set()
        self.references: list[Reference] = []
        self.issues: list[dict[str, Any]] = []
        self.base_href: str | None = None
        self.base_count = 0
        self._in_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        line = self.getpos()[0]
        names = [name.lower() for name, _value in attrs]
        values = {name.lower(): value or "" for name, value in attrs}
        if len(names) != len(set(names)):
            self.issues.append(
                {"source": self.source, "line": line, "reason": "duplicate-html-attribute"}
            )

        if values.get("id"):
            self.ids.add(values["id"])
        if tag.lower() == "a" and values.get("name"):
            self.ids.add(values["name"])
        if tag.lower() == "map" and values.get("name"):
            self.map_names.add(values["name"])

        if tag.lower() == "base" and "href" in values:
            self.base_count += 1
            if self.base_href is None:
                self.base_href = values["href"]
            self.references.append(
                Reference(
                    self.source,
                    line,
                    values["href"],
                    "html-base-href",
                    self.page_url,
                )
            )

        for name in URI_ATTRIBUTES:
            if name not in values or (tag.lower() == "base" and name == "href"):
                continue
            kind = f"html-{name}"
            anchor_kind = _anchor_kind(kind)
            self.references.append(
                Reference(self.source, line, values[name], kind, None, anchor_kind)
            )

        if "srcset" in values:
            try:
                for target in _split_srcset(values["srcset"]):
                    self.references.append(
                        Reference(self.source, line, target, "html-srcset", None, "html")
                    )
            except ValueError as exc:
                self.issues.append(
                    {
                        "source": self.source,
                        "line": line,
                        "reason": "unsupported-srcset-syntax",
                        "detail": str(exc),
                    }
                )

        if values.get("style"):
            css_refs, css_issues = _css_references(
                values["style"], self.source, line, "html-inline-style"
            )
            self.references.extend(css_refs)
            self.issues.extend(css_issues)

        if tag.lower() == "meta" and values.get("http-equiv", "").lower() == "refresh":
            content = values.get("content", "")
            match = META_REFRESH_URL.search(content)
            if match:
                target = next(
                    (value for value in match.groupdict().values() if value is not None), ""
                )
                self.references.append(
                    Reference(self.source, line, target.strip(), "html-meta-refresh", None, "html")
                )
            elif re.search(r"\burl\s*=", content, re.IGNORECASE):
                self.issues.append(
                    {
                        "source": self.source,
                        "line": line,
                        "reason": "unsupported-meta-refresh-syntax",
                    }
                )

        if tag.lower() == "style":
            self._in_style = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "style":
            self._in_style = False

    def handle_data(self, data: str) -> None:
        if self._in_style and data:
            css_refs, css_issues = _css_references(
                data, self.source, self.getpos()[0], "html-style-element"
            )
            self.references.extend(css_refs)
            self.issues.extend(css_issues)

    def effective_references(self) -> list[Reference]:
        """Return page refs rebased to the document's effective base URL."""
        if self.base_count > 1:
            self.issues.append(
                {
                    "source": self.source,
                    "line": 1,
                    "reason": "multiple-base-href-elements",
                }
            )
        effective_base = (
            urljoin(self.page_url, self.base_href) if self.base_href is not None else self.page_url
        )
        return [
            ref
            if ref.base_url is not None
            else Reference(
                ref.source,
                ref.line,
                ref.target,
                ref.kind,
                effective_base,
                ref.anchor_kind,
            )
            for ref in self.references
        ]


def _anchor_kind(kind: str) -> str | None:
    if kind in {"html-href", "html-xlink:href", "html-src", "html-srcset"}:
        return "html"
    if kind == "html-usemap":
        return "map"
    return None


def _line_at(text: str, starts: list[int], offset: int, line_base: int) -> int:
    low = 0
    high = len(starts)
    while low < high:
        middle = (low + high) // 2
        if starts[middle] <= offset:
            low = middle + 1
        else:
            high = middle
    return line_base + max(0, low - 1)


def _css_escape(text: str, index: int) -> tuple[str, int]:
    if index + 1 >= len(text):
        raise ValueError("trailing CSS escape")
    next_char = text[index + 1]
    if next_char in "\r\n\f":
        end = index + 2
        if next_char == "\r" and end < len(text) and text[end] == "\n":
            end += 1
        return "", end
    hex_end = index + 1
    while hex_end < len(text) and hex_end < index + 7 and text[hex_end] in "0123456789abcdefABCDEF":
        hex_end += 1
    if hex_end > index + 1:
        codepoint = int(text[index + 1 : hex_end], 16)
        if codepoint == 0 or codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
            value = "\ufffd"
        else:
            value = chr(codepoint)
        if hex_end < len(text) and text[hex_end].isspace():
            hex_end += 1
        return value, hex_end
    return next_char, index + 2


def _css_string(text: str, index: int) -> tuple[str, int]:
    quote_char = text[index]
    chars: list[str] = []
    index += 1
    while index < len(text):
        char = text[index]
        if char == quote_char:
            return "".join(chars), index + 1
        if char in "\r\n\f":
            raise ValueError("unescaped newline in CSS string")
        if char == "\\":
            value, index = _css_escape(text, index)
            chars.append(value)
            continue
        chars.append(char)
        index += 1
    raise ValueError("unterminated CSS string")


def _skip_css_trivia(text: str, index: int) -> int:
    while index < len(text):
        if text[index].isspace():
            index += 1
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise ValueError("unterminated CSS comment")
            index = end + 2
            continue
        break
    return index


def _css_identifier(text: str, index: int) -> tuple[str, int]:
    chars: list[str] = []
    while index < len(text):
        char = text[index]
        if char in CSS_NAME_CHARS or ord(char) > 127:
            chars.append(char)
            index += 1
        elif char == "\\":
            value, index = _css_escape(text, index)
            chars.append(value)
        else:
            break
    return "".join(chars), index


def _css_url_function(text: str, open_paren: int) -> tuple[str, int]:
    index = _skip_css_trivia(text, open_paren + 1)
    if index >= len(text):
        raise ValueError("unterminated CSS url()")
    if text[index] in "'\"":
        value, index = _css_string(text, index)
        index = _skip_css_trivia(text, index)
        if index >= len(text) or text[index] != ")":
            raise ValueError("unsupported content after quoted CSS url() value")
        return value, index + 1

    chars: list[str] = []
    saw_content = False
    trailing_space = False
    while index < len(text):
        char = text[index]
        if char == ")":
            return "".join(chars).strip(), index + 1
        if text.startswith("/*", index):
            raise ValueError("CSS comments inside an unquoted url() are unsupported")
        if char == "\\":
            value, index = _css_escape(text, index)
            if trailing_space and value:
                raise ValueError("escaped text after whitespace in unquoted CSS url()")
            chars.append(value)
            saw_content = saw_content or bool(value)
            continue
        if char in "'\"(\r\n\f":
            raise ValueError("unsupported character in unquoted CSS url()")
        if char.isspace():
            trailing_space = saw_content
            index += 1
            continue
        if trailing_space:
            raise ValueError("interior whitespace in unquoted CSS url()")
        chars.append(char)
        saw_content = True
        index += 1
    raise ValueError("unterminated CSS url()")


def _css_references(
    text: str, source: str, line_base: int, context: str
) -> tuple[list[Reference], list[dict[str, Any]]]:
    refs: list[Reference] = []
    issues: list[dict[str, Any]] = []
    line_starts = [0]
    line_starts.extend(index + 1 for index, char in enumerate(text) if char == "\n")
    index = 0
    while index < len(text):
        try:
            if text.startswith("/*", index):
                end = text.find("*/", index + 2)
                if end < 0:
                    raise ValueError("unterminated CSS comment")
                index = end + 2
                continue
            if text[index] in "'\"":
                _value, index = _css_string(text, index)
                continue
            if text[index] == "@":
                name, end = _css_identifier(text, index + 1)
                if name.lower() == "import":
                    target_at = _skip_css_trivia(text, end)
                    if target_at < len(text) and text[target_at] in "'\"":
                        target, after = _css_string(text, target_at)
                        refs.append(
                            Reference(
                                source,
                                _line_at(text, line_starts, index, line_base),
                                target,
                                f"css-{context}-import",
                            )
                        )
                        index = after
                        continue
                index = max(index + 1, end)
                continue
            if text[index] == "\\" or text[index] in CSS_NAME_CHARS or ord(text[index]) > 127:
                name, end = _css_identifier(text, index)
                if name.lower() == "url" and end < len(text):
                    if text[end] == "(":
                        target, after = _css_url_function(text, end)
                        refs.append(
                            Reference(
                                source,
                                _line_at(text, line_starts, index, line_base),
                                target,
                                f"css-{context}-url",
                            )
                        )
                        index = after
                        continue
                    if text[end].isspace() or text.startswith("/*", end):
                        next_char = _skip_css_trivia(text, end)
                        if next_char < len(text) and text[next_char] == "(":
                            raise ValueError(
                                "whitespace or comment between CSS url identifier and function"
                            )
                index = max(index + 1, end)
                continue
            index += 1
        except ValueError as exc:
            issues.append(
                {
                    "source": source,
                    "line": _line_at(text, line_starts, index, line_base),
                    "reason": "unsupported-css-reference-syntax",
                    "detail": str(exc),
                }
            )
            # Continue looking for later independent references while keeping the
            # receipt incomplete; a syntax issue can never become a green pass.
            next_close = text.find(")", index + 1)
            index = next_close + 1 if next_close >= 0 else len(text)
    return refs, issues


def _split_srcset(value: str) -> list[str]:
    """Split srcset URLs while keeping commas inside data URLs with the URL token."""
    refs: list[str] = []
    index = 0
    while index < len(value):
        while index < len(value) and (value[index].isspace() or value[index] == ","):
            index += 1
        if index >= len(value):
            break
        start = index
        while index < len(value) and not value[index].isspace():
            index += 1
        url_token = value[start:index]
        if "'" in url_token or '"' in url_token:
            raise ValueError("quoted srcset URL token")
        trailing_commas = len(url_token) - len(url_token.rstrip(","))
        url = url_token.rstrip(",")
        if url:
            refs.append(url)
        if trailing_commas:
            continue

        depth = 0
        while index < len(value):
            char = value[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(0, depth - 1)
            elif char == "," and depth == 0:
                index += 1
                break
            index += 1
    return refs


def _safe_name(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _walk_site(site_dir: Path) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Enumerate regular files without following symlinks or hiding errors."""
    file_kinds: dict[str, str] = {}
    issues: list[dict[str, Any]] = []
    pending = [site_dir]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                materialized = sorted(entries, key=lambda entry: entry.name)
        except OSError as exc:
            issues.append(
                {
                    "path": _safe_name(directory, site_dir),
                    "reason": "directory-enumeration-failed",
                    "error": type(exc).__name__,
                }
            )
            continue
        for entry in materialized:
            path = Path(entry.path)
            rel = path.relative_to(site_dir).as_posix()
            try:
                if entry.is_symlink():
                    file_kinds[rel] = "symlink"
                    try:
                        actual = path.resolve(strict=False)
                        if not actual.is_relative_to(site_dir.resolve(strict=False)):
                            reason = "symlink-target-outside-site-root"
                        else:
                            reason = "symlink-input-not-supported"
                    except OSError as exc:
                        reason = "symlink-target-unreadable"
                        issues.append({"path": rel, "reason": reason, "error": type(exc).__name__})
                        continue
                    issues.append({"path": rel, "reason": reason})
                elif entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                elif entry.is_file(follow_symlinks=False):
                    file_kinds[rel] = "file"
                else:
                    file_kinds[rel] = "special"
                    issues.append({"path": rel, "reason": "special-output-entry-not-supported"})
            except OSError as exc:
                file_kinds[rel] = "unreadable"
                issues.append(
                    {
                        "path": rel,
                        "reason": "directory-entry-inspection-failed",
                        "error": type(exc).__name__,
                    }
                )
    return file_kinds, issues


def _path_digest(paths: list[str]) -> str:
    digest = hashlib.sha256()
    encoded_paths = sorted(os.fsencode(path) for path in paths)
    for path in encoded_paths:
        digest.update(len(path).to_bytes(8, byteorder="big"))
        digest.update(path)
    return digest.hexdigest()


def _empty_summary() -> dict[str, Any]:
    """Return the stable summary shape for completed and unrun scans."""
    return {
        "enumerated_entry_count": 0,
        "regular_file_count": 0,
        "html_file_count": 0,
        "css_file_count": 0,
        "other_regular_file_count": 0,
        "symlink_entry_count": 0,
        "special_entry_count": 0,
        "unreadable_entry_count": 0,
        "file_type_counts_by_suffix": {},
        "reference_count": 0,
        "references_by_outcome": {},
        "missing_target_file_count": 0,
        "missing_html_fragment_count": 0,
        "unresolved_count": 0,
        "html_css_path_count": 0,
    }


def _make_receipt(
    *,
    site: dict[str, str],
    summary: dict[str, Any],
    path_set_sha256: str,
    read_receipt: dict[str, Any],
    enumeration: str,
    findings: list[dict[str, Any]],
    unresolved: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the common receipt envelope and apply verdict precedence."""
    complete = not unresolved
    verdict = "UNRUN" if not complete else "FAILED" if findings else "PASSED"
    summary["unresolved_count"] = len(unresolved)
    return {
        "schema": "policyos.docs-rendered-links.v1",
        "verdict": verdict,
        "complete": complete,
        "site": site,
        "summary": summary,
        "input_receipt": {
            "enumerated_path_set_sha256": path_set_sha256,
            "html_css_content_reads": read_receipt,
            "enumeration": enumeration,
            "supported_reference_forms": SUPPORTED_REFERENCE_FORMS,
        },
        "findings": findings,
        "unresolved": unresolved,
        "unresolved_by_construction": UNRESOLVED_BY_CONSTRUCTION,
    }


def _canonical_http_origin(parsed: Any) -> tuple[str, str, int]:
    """Return an origin under a bounded ASCII host grammar.

    ASCII DNS labels are case-insensitive, but a final dot remains part of the
    origin. Browser-specific IDNA and legacy numeric-host normalization are
    deliberately unresolved instead of being guessed by Python's IDNA codec.
    """
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise OriginNormalizationError(
            "malformed-url-authority", "origin scheme must be HTTP or HTTPS"
        )
    if parsed.username is not None or parsed.password is not None:
        raise OriginNormalizationError(
            "malformed-url-authority", "userinfo in an HTTP authority is unsupported"
        )
    try:
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise OriginNormalizationError("malformed-url-authority", "malformed host or port") from exc
    if parsed.netloc.endswith(":") and port is None:
        raise OriginNormalizationError("malformed-url-authority", "empty port is unsupported")
    if not hostname:
        raise OriginNormalizationError("malformed-url-authority", "HTTP authority has no hostname")
    if "%" in hostname:
        raise OriginNormalizationError(
            "unsupported-percent-encoded-host",
            "percent-encoded hostname requires browser-equivalent URL normalization",
        )
    if not hostname.isascii():
        raise OriginNormalizationError(
            "unsupported-non-ascii-host",
            "non-ASCII hostname requires browser-equivalent WHATWG/UTS46 normalization",
        )

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if ":" in hostname or parsed.netloc.startswith("["):
            raise OriginNormalizationError(
                "malformed-url-authority", "bracketed authority is not a valid IPv6 address"
            ) from None
        host_without_root_dot = hostname[:-1] if hostname.endswith(".") else hostname
        if not host_without_root_dot:
            raise OriginNormalizationError(
                "unsupported-ascii-host-grammar", "empty DNS hostname is unsupported"
            ) from None
        labels = host_without_root_dot.split(".")
        last_label = labels[-1]
        if re.fullmatch(r"[0-9]+|0[xX][0-9a-fA-F]*", last_label):
            raise OriginNormalizationError(
                "ambiguous-numeric-ipv4-host",
                "legacy or numeric IPv4 spelling requires browser-equivalent URL normalization",
            ) from None
        if len(host_without_root_dot) > 253 or any(
            len(label) > 63
            or not label
            or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
            for label in labels
        ):
            raise OriginNormalizationError(
                "unsupported-ascii-host-grammar",
                "ASCII hostname is outside the bounded DNS-label grammar",
            ) from None
        normalized_host = hostname.lower()
    else:
        if isinstance(address, ipaddress.IPv6Address):
            if not parsed.netloc.startswith("["):
                raise OriginNormalizationError(
                    "malformed-url-authority", "IPv6 authority must use brackets"
                )
            normalized_host = address.compressed
        else:
            if parsed.netloc.startswith("["):
                raise OriginNormalizationError(
                    "malformed-url-authority", "brackets are supported only for IPv6 literals"
                )
            normalized_host = str(address)
            if hostname != normalized_host:
                raise OriginNormalizationError(
                    "ambiguous-numeric-ipv4-host",
                    "noncanonical IPv4 spelling requires browser-equivalent URL normalization",
                )
    if port is None:
        port = 80 if scheme == "http" else 443
    return scheme, normalized_host, port


def _site_url_parts(site_url: str) -> tuple[str, tuple[str, str, int], str]:
    parsed = urlsplit(site_url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--site-url must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("--site-url must not include user info, query, or fragment")
    try:
        origin = _canonical_http_origin(parsed)
    except ValueError as exc:
        raise ValueError(f"--site-url has malformed authority: {exc}") from exc
    prefix = parsed.path or "/"
    if not prefix.startswith("/"):
        raise ValueError("--site-url path must be absolute")
    if not prefix.endswith("/"):
        prefix += "/"
    return (
        urlunsplit((parsed.scheme.lower(), parsed.netloc, prefix, "", "")),
        origin,
        prefix,
    )


def _public_url(site_url: str, relative_path: str, *, html_route: bool) -> str:
    if html_route and relative_path == "index.html":
        return site_url
    if html_route and relative_path.endswith("/index.html"):
        relative_path = relative_path[: -len("index.html")]
    return urljoin(site_url, quote(relative_path, safe="/:@-._~!$&'()*+,;="))


def _candidate_outputs(path: str) -> list[str]:
    decoded = unquote(path)
    if "\\" in decoded or "\x00" in decoded:
        raise ValueError("backslash or NUL in URL path")
    normalized = posixpath.normpath("/" + decoded).lstrip("/")
    if normalized in {"", "."}:
        normalized = ""
    if normalized == ".." or normalized.startswith("../"):
        raise ValueError("URL path escapes the site root")
    if decoded.endswith("/") or not normalized:
        return [f"{normalized + '/' if normalized else ''}index.html"]
    candidates = [normalized]
    if Path(normalized).suffix == "":
        candidates.extend((normalized + ".html", f"{normalized}/index.html"))
    return candidates


def _resolve_reference(
    ref: Reference,
    *,
    site_url: str,
    site_origin: tuple[str, str, int],
    site_prefix: str,
    file_kinds: dict[str, str],
    html_ids: dict[str, set[str]],
    map_names: dict[str, set[str]],
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    target = ref.target.strip()
    try:
        resolved = urljoin(ref.base_url or site_url, target)
        parsed = urlsplit(resolved)
    except ValueError as exc:
        return (
            "unrun",
            None,
            {
                "source": ref.source,
                "line": ref.line,
                "target": ref.target,
                "reason": "invalid-url-reference",
                "detail": str(exc),
            },
        )

    scheme = parsed.scheme.lower()
    if scheme in UNMEASURED_SCHEMES:
        return "nonlocal_scheme_unmeasured", None, None
    if scheme not in {"http", "https"}:
        return (
            "unrun",
            None,
            {
                "source": ref.source,
                "line": ref.line,
                "target": ref.target,
                "resolved_url": resolved,
                "reason": "unsupported-uri-scheme",
            },
        )
    try:
        resolved_origin = _canonical_http_origin(parsed)
    except ValueError as exc:
        reason = (
            exc.reason if isinstance(exc, OriginNormalizationError) else "malformed-url-authority"
        )
        return (
            "unrun",
            None,
            {
                "source": ref.source,
                "line": ref.line,
                "target": ref.target,
                "resolved_url": resolved,
                "reason": reason,
                "detail": str(exc),
            },
        )
    if resolved_origin != site_origin:
        return "external_unverified", None, None

    url_path = parsed.path or site_prefix
    if site_prefix != "/" and url_path == site_prefix[:-1]:
        url_path = site_prefix
    if not url_path.startswith(site_prefix):
        return (
            "unrun",
            None,
            {
                "source": ref.source,
                "line": ref.line,
                "target": ref.target,
                "resolved_url": resolved,
                "reason": "same-host-path-outside-site-base",
            },
        )
    decoded_path = unquote(url_path)
    normalized_decoded_path = posixpath.normpath(decoded_path)
    prefix_root = unquote(site_prefix).rstrip("/")
    if (
        prefix_root
        and normalized_decoded_path
        not in {
            prefix_root,
            prefix_root + "/",
        }
        and not normalized_decoded_path.startswith(prefix_root + "/")
    ):
        return (
            "unrun",
            None,
            {
                "source": ref.source,
                "line": ref.line,
                "target": ref.target,
                "resolved_url": resolved,
                "reason": "same-host-decoded-path-outside-site-base",
            },
        )
    relative_url_path = url_path[len(site_prefix) :]
    try:
        candidates = _candidate_outputs(relative_url_path)
    except ValueError as exc:
        return (
            "unrun",
            None,
            {
                "source": ref.source,
                "line": ref.line,
                "target": ref.target,
                "resolved_url": resolved,
                "reason": "unsupported-or-escaping-url-path",
                "detail": str(exc),
            },
        )

    output_path = next(
        (candidate for candidate in candidates if file_kinds.get(candidate) == "file"), None
    )
    if output_path is None:
        symlink_path = next(
            (candidate for candidate in candidates if file_kinds.get(candidate) == "symlink"), None
        )
        if symlink_path is not None:
            return (
                "unrun",
                None,
                {
                    "source": ref.source,
                    "line": ref.line,
                    "target": ref.target,
                    "resolved_url": resolved,
                    "target_output": symlink_path,
                    "reason": "target-is-symlink",
                },
            )
        return (
            "missing_target_file",
            {
                "kind": "missing_target_file",
                "source": ref.source,
                "line": ref.line,
                "target": ref.target,
                "expected_output": candidates[0],
            },
            None,
        )

    fragment = unquote(parsed.fragment)
    suffix = Path(output_path).suffix.lower()
    if fragment and suffix in HTML_SUFFIXES and ref.anchor_kind:
        if output_path not in html_ids:
            return (
                "unrun",
                None,
                {
                    "source": ref.source,
                    "line": ref.line,
                    "target": ref.target,
                    "target_output": output_path,
                    "fragment": fragment,
                    "reason": "target-html-anchor-index-unavailable",
                },
            )
        if ref.anchor_kind == "map":
            known = map_names.get(output_path, set())
        else:
            known = html_ids.get(output_path, set())
        if fragment not in known:
            return (
                "missing_html_fragment",
                {
                    "kind": "missing_html_fragment",
                    "source": ref.source,
                    "line": ref.line,
                    "target": ref.target,
                    "target_output": output_path,
                    "fragment": fragment,
                },
                None,
            )
    if fragment and suffix not in HTML_SUFFIXES:
        return "non_html_fragment_unmeasured", None, None
    if fragment and not ref.anchor_kind:
        return "fragment_semantics_unmeasured", None, None
    return "local_target_exists", None, None


def _validate_paths(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> tuple[Path, Path, Path, str, str, str]:
    repo_root = repo_root_from(__file__).resolve()
    build_root = (repo_root / "_build").resolve(strict=False)
    if not build_root.is_relative_to(repo_root):
        parser.error("repository _build path resolves outside the repository")

    def resolve_arg(value: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = repo_root / path
        return Path(os.path.abspath(path))

    site_arg = resolve_arg(args.site_dir)
    output_arg = resolve_arg(args.output)
    if not site_arg.is_relative_to(repo_root / "_build"):
        parser.error("--site-dir must be an explicit path under repository _build/")
    if not output_arg.is_relative_to(repo_root / "_build"):
        parser.error("--output must be an explicit path under repository _build/")
    output_real = output_arg.resolve(strict=False)
    if not output_real.is_relative_to(build_root):
        parser.error("--output path resolves outside repository _build/")
    site_real = site_arg.resolve(strict=False)
    if output_real == site_real or output_real.is_relative_to(site_real):
        parser.error("--output must be outside --site-dir")
    try:
        site_url, site_origin, site_prefix = _site_url_parts(args.site_url)
    except ValueError as exc:
        parser.error(str(exc))
    return repo_root, site_arg, output_real, site_url, site_origin, site_prefix


def _scan_site(
    site_dir: Path,
    site_url: str,
    site_origin: tuple[str, str, int],
    site_prefix: str,
    measurement: Any,
) -> dict[str, Any]:
    unresolved: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    refs: list[Reference] = []
    html_ids: dict[str, set[str]] = {}
    map_names: dict[str, set[str]] = {}
    initial_kinds: dict[str, str] = {}
    if not site_dir.is_dir():
        unresolved.append({"path": ".", "reason": "site-root-missing-or-unreadable"})
    else:
        initial_kinds, enumeration_issues = _walk_site(site_dir)
        unresolved.extend(enumeration_issues)

    html_paths = sorted(
        path
        for path, kind in initial_kinds.items()
        if kind == "file" and Path(path).suffix.lower() in HTML_SUFFIXES
    )
    css_paths = sorted(
        path
        for path, kind in initial_kinds.items()
        if kind == "file" and Path(path).suffix.lower() == ".css"
    )
    first_hashes: dict[str, tuple[int, str]] = {}

    for rel in html_paths:
        path = site_dir / rel
        try:
            raw = measured_read_bytes(path)
            digest = hashlib.sha256(raw).hexdigest()
            first_hashes[rel] = (len(raw), digest)
            text = raw.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            unresolved.append(
                {
                    "source": rel,
                    "line": 1,
                    "reason": "html-input-unreadable-or-invalid-utf8",
                    "error": type(exc).__name__,
                }
            )
            continue
        parser = PageParser(rel, _public_url(site_url, rel, html_route=True))
        try:
            parser.feed(text)
            parser.close()
            refs.extend(parser.effective_references())
            unresolved.extend(parser.issues)
            if not parser.issues:
                html_ids[rel] = parser.ids
                map_names[rel] = parser.map_names
        except Exception as exc:  # HTMLParser errors leave a named incomplete result.
            unresolved.append(
                {
                    "source": rel,
                    "line": parser.getpos()[0],
                    "reason": "html-parser-failed",
                    "error": type(exc).__name__,
                }
            )

    for rel in css_paths:
        path = site_dir / rel
        try:
            raw = measured_read_bytes(path)
            digest = hashlib.sha256(raw).hexdigest()
            first_hashes[rel] = (len(raw), digest)
            text = raw.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            unresolved.append(
                {
                    "source": rel,
                    "line": 1,
                    "reason": "css-input-unreadable-or-invalid-utf8",
                    "error": type(exc).__name__,
                }
            )
            continue
        css_refs, css_issues = _css_references(text, rel, 1, "external")
        page_url = _public_url(site_url, rel, html_route=False)
        refs.extend(
            Reference(ref.source, ref.line, ref.target, ref.kind, page_url, ref.anchor_kind)
            for ref in css_refs
        )
        unresolved.extend(css_issues)

    outcomes: Counter[str] = Counter()
    for ref in refs:
        outcome, finding, issue = _resolve_reference(
            ref,
            site_url=site_url,
            site_origin=site_origin,
            site_prefix=site_prefix,
            file_kinds=initial_kinds,
            html_ids=html_ids,
            map_names=map_names,
        )
        outcomes[outcome] += 1
        if finding is not None:
            findings.append(finding)
        if issue is not None:
            unresolved.append(issue)

    final_kinds, final_enumeration_issues = _walk_site(site_dir) if site_dir.is_dir() else ({}, [])
    unresolved.extend(final_enumeration_issues)
    if _path_digest(sorted(initial_kinds)) != _path_digest(sorted(final_kinds)):
        unresolved.append({"reason": "site-path-set-changed-during-scan"})
    if initial_kinds != final_kinds:
        unresolved.append({"reason": "site-entry-types-changed-during-scan"})

    for rel, (expected_size, expected_digest) in first_hashes.items():
        try:
            raw = measured_read_bytes(site_dir / rel)
        except OSError as exc:
            unresolved.append(
                {
                    "source": rel,
                    "line": 1,
                    "reason": "stability-reread-failed",
                    "error": type(exc).__name__,
                }
            )
            continue
        actual_digest = hashlib.sha256(raw).hexdigest()
        if len(raw) != expected_size or actual_digest != expected_digest:
            unresolved.append(
                {
                    "source": rel,
                    "line": 1,
                    "reason": "html-css-content-changed-during-scan",
                    "expected_bytes": expected_size,
                    "actual_bytes": len(raw),
                    "expected_sha256": expected_digest,
                    "actual_sha256": actual_digest,
                }
            )

    regular_paths = [path for path, kind in initial_kinds.items() if kind == "file"]
    type_counts = Counter(Path(path).suffix.lower() or "[no-extension]" for path in regular_paths)
    other_count = len(regular_paths) - len(html_paths) - len(css_paths)
    unresolved.sort(
        key=lambda row: (
            str(row.get("source", row.get("path", ""))),
            int(row.get("line", 0)),
            str(row.get("reason", "")),
        )
    )
    findings.sort(key=lambda row: (row["source"], row["line"], row["kind"], row["target"]))
    complete = not unresolved
    summary = _empty_summary()
    summary.update(
        {
            "enumerated_entry_count": len(initial_kinds),
            "regular_file_count": len(regular_paths),
            "html_file_count": len(html_paths),
            "css_file_count": len(css_paths),
            "other_regular_file_count": other_count,
            "symlink_entry_count": sum(kind == "symlink" for kind in initial_kinds.values()),
            "special_entry_count": sum(kind == "special" for kind in initial_kinds.values()),
            "unreadable_entry_count": sum(kind == "unreadable" for kind in initial_kinds.values()),
            "file_type_counts_by_suffix": dict(sorted(type_counts.items())),
            "reference_count": len(refs),
            "references_by_outcome": dict(sorted(outcomes.items())),
            "missing_target_file_count": sum(
                item["kind"] == "missing_target_file" for item in findings
            ),
            "missing_html_fragment_count": sum(
                item["kind"] == "missing_html_fragment" for item in findings
            ),
            "html_css_path_count": len(first_hashes),
        }
    )
    return _make_receipt(
        site={"site_dir": str(site_dir), "site_url": site_url, "site_base_path": site_prefix},
        summary=summary,
        path_set_sha256=_path_digest(sorted(initial_kinds)),
        read_receipt=measurement.snapshot(complete_verdict=complete),
        enumeration=(
            "recursive os.scandir under site_dir; summary counts non-directory entries, "
            "including symlinks and inspection failures; symlinks are not followed"
        ),
        findings=findings,
        unresolved=unresolved,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the standalone emitted-site checker CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-dir",
        required=True,
        help="Explicit emitted-site directory under repository _build/.",
    )
    parser.add_argument(
        "--site-url",
        required=True,
        help="Resolved MkDocs HTTP(S) site_url, including any path prefix.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Explicit JSON receipt path under repository _build/ and outside site-dir.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the bounded emitted-site link check and write one JSON receipt."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    repo_root, site_arg, output_path, site_url, site_origin, site_prefix = _validate_paths(
        args, parser
    )
    try:
        site_dir = site_arg.resolve(strict=False)
    except OSError as exc:
        site_dir = site_arg
        root_issue = {
            "path": ".",
            "reason": "site-root-resolution-failed",
            "error": type(exc).__name__,
        }
    else:
        build_root = (repo_root / "_build").resolve(strict=False)
        root_issue = (
            {"path": ".", "reason": "site-root-resolves-outside-build-root"}
            if not site_dir.is_relative_to(build_root)
            else None
        )

    if root_issue is not None:
        receipt = _make_receipt(
            site={
                "site_dir": _safe_name(site_arg, repo_root),
                "site_url": site_url,
                "site_base_path": site_prefix,
            },
            summary=_empty_summary(),
            path_set_sha256=_path_digest([]),
            read_receipt={
                "complete_verdict": False,
                "finding_coverage": "explicit file-reader operations only",
                "inputs": [],
                "unresolved_by_construction": [
                    "Site root was rejected before enumeration or file reads."
                ],
            },
            enumeration="not run",
            findings=[],
            unresolved=[root_issue],
        )
    else:
        with measure_file_reads(site_dir) as measurement:
            receipt = _scan_site(site_dir, site_url, site_origin, site_prefix, measurement)
            receipt["input_receipt"]["html_css_content_reads"] = measurement.snapshot(
                complete_verdict=receipt["complete"]
            )
            receipt["site"]["site_dir"] = _safe_name(site_dir, repo_root)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    summary = receipt["summary"]
    print(
        json.dumps(
            {
                "verdict": receipt["verdict"],
                "receipt": _safe_name(output_path, repo_root),
                "enumerated_entry_count": summary["enumerated_entry_count"],
                "regular_file_count": summary["regular_file_count"],
                "html_file_count": summary["html_file_count"],
                "css_file_count": summary["css_file_count"],
                "reference_count": summary["reference_count"],
                "missing_target_file_count": summary["missing_target_file_count"],
                "missing_html_fragment_count": summary["missing_html_fragment_count"],
                "unresolved_count": summary["unresolved_count"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if receipt["verdict"] == "UNRUN":
        return 2
    if receipt["verdict"] == "FAILED":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
