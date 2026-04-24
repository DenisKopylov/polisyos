from __future__ import annotations

import asyncio
import json
import sys
import types
from dataclasses import dataclass

import polisyos.academic.batch.fulltext_resolver as resolver
from polisyos.academic.batch.fulltext_resolver import (
    fetch_full_text_result_for_work,
    load_resolved_fulltext_cache,
    reconstruct_abstract,
)


@dataclass
class _FakeResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    url: str

    async def read(self) -> bytes:
        return self.body

    async def json(self, content_type=None):  # type: ignore[no-untyped-def]
        return json.loads(self.body.decode("utf-8"))


class _FakeResponseContext:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeResponse:
        return self._response

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None


class _FakeSession:
    def __init__(self, responses: dict[str, _FakeResponse]) -> None:
        self._responses = responses

    def get(self, url: str, **_: object) -> _FakeResponseContext:
        if url in self._responses:
            return _FakeResponseContext(self._responses[url])
        for key, response in self._responses.items():
            if url.startswith(key):
                return _FakeResponseContext(response)
        raise KeyError(url)


def test_reconstruct_abstract_prefers_direct_abstract() -> None:
    work = {
        "abstract": "Direct abstract text.",
        "abstract_inverted_index": {"wrong": [0], "order": [1]},
    }
    assert reconstruct_abstract(work) == "Direct abstract text."


def test_fetch_full_text_result_invalid_url_falls_back_with_error_class() -> None:
    work = {
        "abstract": "Fallback abstract.",
        "open_access": {"oa_url": "https://"},
        "best_oa_location": {"pdf_url": "ftp://example.com/paper.pdf"},
    }

    result = asyncio.run(fetch_full_text_result_for_work(work))

    assert result.source_kind == "abstract_fallback"
    assert result.text == "Fallback abstract."
    assert result.fetch_error_class == "invalid_url"


def test_fetch_full_text_result_follows_redirect_placeholder_target() -> None:
    work = {
        "abstract": "Fallback abstract.",
        "open_access": {"oa_url": "https://doi.org/example"},
    }
    session = _FakeSession(
        {
            "https://doi.org/example": _FakeResponse(
                status=200,
                headers={"Content-Type": "text/html"},
                body=(
                    b'<html><head><meta http-equiv="refresh" content="0; url=https://publisher.example/article"></head>'
                    b"<body>Redirecting</body></html>"
                ),
                url="https://doi.org/example",
            ),
            "https://publisher.example/article": _FakeResponse(
                status=200,
                headers={"Content-Type": "text/html"},
                body=b"<html><body>We use panel data and results show the policy increased compliance.</body></html>",
                url="https://publisher.example/article",
            ),
        }
    )

    result = asyncio.run(fetch_full_text_result_for_work(work, session=session))

    assert result.source_kind == "fulltext_html"
    assert "results show" in result.text.lower()
    assert result.source_url == "https://publisher.example/article"
    assert result.fetch_error_class == ""


def test_fetch_full_text_result_redirect_placeholder_without_target_falls_back() -> None:
    work = {
        "abstract": "Fallback abstract.",
        "open_access": {"oa_url": "https://doi.org/example"},
    }
    session = _FakeSession(
        {
            "https://doi.org/example": _FakeResponse(
                status=200,
                headers={"Content-Type": "text/html"},
                body=b"<html><body>Redirecting</body></html>",
                url="https://doi.org/example",
            ),
        }
    )

    result = asyncio.run(fetch_full_text_result_for_work(work, session=session))

    assert result.source_kind == "abstract_fallback"
    assert result.text == "Fallback abstract."
    assert result.fetch_error_class == "redirect_placeholder"


def test_fetch_full_text_result_discovers_pdf_from_landing_page(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    work = {
        "abstract": "Fallback abstract.",
        "best_oa_location": {"landing_page_url": "https://publisher.example/article"},
    }
    monkeypatch.setattr(
        resolver,
        "_extract_pdf_text",
        lambda raw_bytes: "Methods Results Conclusion full text recovered from PDF.",
    )
    session = _FakeSession(
        {
            "https://publisher.example/article": _FakeResponse(
                status=200,
                headers={"Content-Type": "text/html"},
                body=(
                    b'<html><head><meta name="citation_pdf_url" content="https://publisher.example/paper.pdf"></head>'
                    b"<body>Article landing page</body></html>"
                ),
                url="https://publisher.example/article",
            ),
            "https://publisher.example/paper.pdf": _FakeResponse(
                status=200,
                headers={"Content-Type": "application/pdf"},
                body=b"%PDF-1.4 not-a-real-pdf",
                url="https://publisher.example/paper.pdf",
            ),
        }
    )

    result = asyncio.run(fetch_full_text_result_for_work(work, session=session))

    assert result.source_kind == "fulltext_pdf"
    assert "recovered from pdf" in result.text.lower()
    assert result.source_url == "https://publisher.example/paper.pdf"
    assert result.fetch_error_class == ""


def test_fetch_full_text_result_skips_html_disguised_as_pdf(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    work = {
        "abstract": "Fallback abstract.",
        "best_oa_location": {"pdf_url": "https://publisher.example/paper.pdf"},
    }
    monkeypatch.setattr(
        resolver,
        "_extract_pdf_text",
        lambda raw_bytes: (_ for _ in ()).throw(AssertionError("should not parse fake pdf")),
    )
    session = _FakeSession(
        {
            "https://publisher.example/paper.pdf": _FakeResponse(
                status=200,
                headers={"Content-Type": "application/pdf"},
                body=b"<!DOCTYPE html><html><body>sign in to access</body></html>",
                url="https://publisher.example/paper.pdf",
            ),
        }
    )

    result = asyncio.run(fetch_full_text_result_for_work(work, session=session))

    assert result.source_kind == "abstract_fallback"
    assert result.text == "Fallback abstract."
    assert result.fetch_error_class == "html_disguised_as_pdf"


def test_extract_pdf_text_parses_reader_pages(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class _FakePage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class _FakePdfReader:
        def __init__(self, _buffer) -> None:  # type: ignore[no-untyped-def]
            self.pages = [_FakePage("Page 1 coefficient 0.18"), _FakePage("Page 2 SE 0.04")]

    monkeypatch.setitem(sys.modules, "pypdf", types.SimpleNamespace(PdfReader=_FakePdfReader))

    text = resolver._extract_pdf_text(b"%PDF-1.4 fake")

    assert "coefficient 0.18" in text
    assert "SE 0.04" in text


def test_v7_metadata_pdf_candidate_recovers_fulltext(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    work = {
        "id": "https://openalex.org/W1",
        "abstract": "Fallback abstract.",
        "doi": "10.1234/abc",
    }
    monkeypatch.setattr(
        resolver,
        "_extract_pdf_text",
        lambda raw_bytes: (
            "Abstract. Introduction. Methods. Results. Conclusion. "
            "Recovered from metadata PDF with enough text to pass the usability threshold."
        ),
    )
    session = _FakeSession(
        {
            "https://api.unpaywall.org/v2/10.1234%2Fabc?email=test@example.org": _FakeResponse(
                status=200,
                headers={"Content-Type": "application/json"},
                body=(
                    b"{"
                    b'"best_oa_location":{"url_for_pdf":"https://publisher.example/from-unpaywall.pdf"},'
                    b'"oa_locations":[]'
                    b"}"
                ),
                url="https://api.unpaywall.org/v2/10.1234%2Fabc?email=test@example.org",
            ),
            "https://api.crossref.org/works/10.1234%2Fabc": _FakeResponse(
                status=404,
                headers={"Content-Type": "application/json"},
                body=b"{}",
                url="https://api.crossref.org/works/10.1234%2Fabc",
            ),
            "https://publisher.example/from-unpaywall.pdf": _FakeResponse(
                status=200,
                headers={"Content-Type": "application/pdf"},
                body=b"%PDF-1.4 fake",
                url="https://publisher.example/from-unpaywall.pdf",
            ),
        }
    )

    result = asyncio.run(
        fetch_full_text_result_for_work(
            work,
            session=session,
            acquisition_mode="v7_http_metadata",
            metadata_resolvers_enabled=True,
            unpaywall_email="test@example.org",
            metadata_timeout_seconds=5,
            min_usable_chars=100,
            min_soft_usable_chars=60,
        )
    )

    assert result.source_kind == "fulltext_pdf"
    assert "recovered from metadata pdf" in result.text.lower()
    assert any(attempt.attempt_kind == "metadata" for attempt in result.attempts)
    assert result.metadata_cache_rows


def test_v7_metadata_no_result_continues_with_seed_candidates() -> None:
    work = {
        "id": "https://openalex.org/W2",
        "abstract": "Fallback abstract.",
        "doi": "10.9999/miss",
        "best_oa_location": {"landing_page_url": "https://publisher.example/article"},
    }
    session = _FakeSession(
        {
            "https://api.unpaywall.org/v2/10.9999%2Fmiss?email=test@example.org": _FakeResponse(
                status=404,
                headers={"Content-Type": "application/json"},
                body=b"{}",
                url="https://api.unpaywall.org/v2/10.9999%2Fmiss?email=test@example.org",
            ),
            "https://api.crossref.org/works/10.9999%2Fmiss": _FakeResponse(
                status=404,
                headers={"Content-Type": "application/json"},
                body=b"{}",
                url="https://api.crossref.org/works/10.9999%2Fmiss",
            ),
            "https://publisher.example/article": _FakeResponse(
                status=200,
                headers={"Content-Type": "text/html"},
                body=(
                    b"<html><body>Abstract. Introduction. Methods. Results show treatment effects."
                    b" Discussion. Conclusion. This article studies compliance outcomes in detail.</body></html>"
                ),
                url="https://publisher.example/article",
            ),
        }
    )

    result = asyncio.run(
        fetch_full_text_result_for_work(
            work,
            session=session,
            acquisition_mode="v7_http_metadata",
            metadata_resolvers_enabled=True,
            unpaywall_email="test@example.org",
            metadata_timeout_seconds=5,
            min_usable_chars=80,
            min_soft_usable_chars=60,
        )
    )

    assert result.source_kind == "fulltext_html"
    assert result.source_url == "https://publisher.example/article"
    assert any(attempt.attempt_kind == "metadata" for attempt in result.attempts)


def test_v7_prefers_discovered_pdf_over_short_html_shell(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    work = {
        "id": "https://openalex.org/W3",
        "abstract": "Fallback abstract.",
        "best_oa_location": {"landing_page_url": "https://publisher.example/article"},
    }
    monkeypatch.setattr(
        resolver,
        "_extract_pdf_text",
        lambda raw_bytes: (
            "Abstract. Introduction. Methods. Results. Conclusion. "
            "Recovered from discovered PDF with enough text to pass the usability threshold."
        ),
    )
    session = _FakeSession(
        {
            "https://publisher.example/article": _FakeResponse(
                status=200,
                headers={"Content-Type": "text/html"},
                body=(
                    b'<html><head><meta name="citation_pdf_url" content="https://publisher.example/paper.pdf"></head>'
                    b"<body>Article landing page</body></html>"
                ),
                url="https://publisher.example/article",
            ),
            "https://publisher.example/paper.pdf": _FakeResponse(
                status=200,
                headers={"Content-Type": "application/pdf"},
                body=b"%PDF-1.4 fake",
                url="https://publisher.example/paper.pdf",
            ),
        }
    )

    result = asyncio.run(
        fetch_full_text_result_for_work(
            work,
            session=session,
            acquisition_mode="v7_http_metadata",
            metadata_resolvers_enabled=False,
            min_usable_chars=100,
            min_soft_usable_chars=60,
        )
    )

    assert result.source_kind == "fulltext_pdf"
    assert result.source_url == "https://publisher.example/paper.pdf"
    assert any(
        attempt.fetch_error_class == "landing_page_without_pdf" for attempt in result.attempts
    )


def test_v7_prefers_discovered_pdf_over_repository_shell(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    work = {
        "id": "https://openalex.org/Wshell",
        "abstract": "Fallback abstract.",
        "best_oa_location": {"landing_page_url": "https://repo.example/item"},
    }
    monkeypatch.setattr(
        resolver,
        "_extract_pdf_text",
        lambda raw_bytes: (
            "Abstract. Introduction. Methods. Results. Table 2 reports coefficient 0.18 "
            "with SE = 0.04. Conclusion."
        ),
    )
    session = _FakeSession(
        {
            "https://repo.example/item": _FakeResponse(
                status=200,
                headers={"Content-Type": "text/html"},
                body=(
                    b'<html><head><meta name="citation_pdf_url" content="https://repo.example/preprint.pdf"></head>'
                    b"<body>IRIS - Institutional Research Information System Scheda breve Scheda completa "
                    b"Catalogo dei prodotti della ricerca scientifica File in questo prodotto "
                    b"Visualizza/Apri Pubblicazioni consigliate social impact "
                    b"Abstract We investigate the effects of reform on firm performance.</body></html>"
                ),
                url="https://repo.example/item",
            ),
            "https://repo.example/preprint.pdf": _FakeResponse(
                status=200,
                headers={"Content-Type": "application/pdf"},
                body=b"%PDF fake",
                url="https://repo.example/preprint.pdf",
            ),
        }
    )

    result = asyncio.run(
        fetch_full_text_result_for_work(
            work,
            session=session,
            acquisition_mode="v7_http_metadata",
            metadata_resolvers_enabled=False,
            min_usable_chars=100,
            min_soft_usable_chars=60,
        )
    )

    assert result.source_kind == "fulltext_pdf"
    assert result.source_url == "https://repo.example/preprint.pdf"
    assert any(
        attempt.fetch_error_class == "repository_shell_with_pdf" for attempt in result.attempts
    )


def test_v7_uses_semantic_scholar_in_configured_order(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    work = {
        "id": "https://openalex.org/W4",
        "abstract": "Fallback abstract.",
        "doi": "10.1111/semscholar",
    }
    monkeypatch.setattr(
        resolver,
        "_extract_pdf_text",
        lambda raw_bytes: (
            "Abstract. Introduction. Methods. Results. Conclusion. "
            "Recovered from Semantic Scholar PDF."
        ),
    )
    session = _FakeSession(
        {
            "https://api.semanticscholar.org/graph/v1/paper/DOI:10.1111%2Fsemscholar?fields=openAccessPdf,url,externalIds": _FakeResponse(
                status=200,
                headers={"Content-Type": "application/json"},
                body=(
                    b"{"
                    b'"openAccessPdf":{"url":"https://publisher.example/from-s2.pdf"},'
                    b'"url":"https://publisher.example/from-s2"'
                    b"}"
                ),
                url="https://api.semanticscholar.org/graph/v1/paper/DOI:10.1111%2Fsemscholar?fields=openAccessPdf,url,externalIds",
            ),
            "https://publisher.example/from-s2.pdf": _FakeResponse(
                status=200,
                headers={"Content-Type": "application/pdf"},
                body=b"%PDF fake",
                url="https://publisher.example/from-s2.pdf",
            ),
        }
    )

    result = asyncio.run(
        fetch_full_text_result_for_work(
            work,
            session=session,
            acquisition_mode="v7_http_metadata",
            metadata_resolvers_enabled=True,
            metadata_resolver_order=("semanticscholar", "crossref"),
            semantic_scholar_api_key="demo-key",
            min_usable_chars=80,
            min_soft_usable_chars=60,
        )
    )

    assert result.source_kind == "fulltext_pdf"
    assert "semantic scholar pdf" in result.text.lower()
    assert any(
        attempt.source_kind.startswith("metadata_semanticscholar") for attempt in result.attempts
    )


def test_fulltext_precleaner_strips_boilerplate_and_reference_tail() -> None:
    work = {
        "abstract": "Fallback abstract.",
        "best_oa_location": {"landing_page_url": "https://publisher.example/article-clean"},
    }
    session = _FakeSession(
        {
            "https://publisher.example/article-clean": _FakeResponse(
                status=200,
                headers={"Content-Type": "text/html"},
                body=(
                    b"<html><body>Cookie Policy Accept cookies navigation header. "
                    b"Abstract This study uses panel data. Introduction Methods Results show tax effects. "
                    b"Discussion Conclusion. References "
                    + (b"citation item " * 300)
                    + b"</body></html>"
                ),
                url="https://publisher.example/article-clean",
            ),
        }
    )

    result = asyncio.run(
        fetch_full_text_result_for_work(
            work,
            session=session,
            min_usable_chars=80,
            min_soft_usable_chars=60,
        )
    )

    assert result.source_kind == "fulltext_html"
    assert "cookie policy" not in result.text.lower()
    assert "accept cookies" not in result.text.lower()
    assert "references" not in result.text.lower()
    assert "results show tax effects" in result.text.lower()


def test_shared_resolved_cache_reuses_previous_result(tmp_path) -> None:
    work = {
        "id": "https://openalex.org/W5",
        "doi": "10.2222/cache",
        "abstract": "Fallback abstract.",
        "best_oa_location": {"landing_page_url": "https://publisher.example/cache"},
    }
    session = _FakeSession(
        {
            "https://publisher.example/cache": _FakeResponse(
                status=200,
                headers={"Content-Type": "text/html"},
                body=(
                    b"<html><body>Abstract Introduction Methods Results show cached full text is usable. "
                    b"Discussion Conclusion.</body></html>"
                ),
                url="https://publisher.example/cache",
            )
        }
    )
    cache_path = tmp_path / "resolved_fulltext_cache.jsonl"
    resolved_cache = {}

    first = asyncio.run(
        fetch_full_text_result_for_work(
            work,
            session=session,
            resolved_cache=resolved_cache,
            cache_ttl_days=30,
            min_usable_chars=80,
            min_soft_usable_chars=60,
        )
    )
    assert first.cache_hit is False
    assert first.resolved_cache_row is not None
    with open(cache_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(first.resolved_cache_row) + "\n")

    loaded_cache = load_resolved_fulltext_cache(cache_path, ttl_days=30)
    second = asyncio.run(
        fetch_full_text_result_for_work(
            work,
            session=_FakeSession({}),
            resolved_cache=loaded_cache,
            cache_ttl_days=30,
        )
    )

    assert second.cache_hit is True
    assert second.text == first.text
    assert any(attempt.attempt_kind == "shared_cache" for attempt in second.attempts)
