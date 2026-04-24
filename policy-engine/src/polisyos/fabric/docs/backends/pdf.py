"""PDF normalization hook used by the document-ingestion pipeline."""

from __future__ import annotations

from ..errors import DocUnsupportedMimeError


def normalize_pdf_to_text_v1(_: bytes) -> str:
    """Raise an explicit unsupported error when PDF text extraction is not installed."""
    raise DocUnsupportedMimeError(
        "PDF normalization is not available in the core MVP; install optional deps."
    )


__all__ = ["normalize_pdf_to_text_v1"]
