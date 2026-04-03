"""Public backends pdf module API."""
from __future__ import annotations

from ..errors import DocUnsupportedMimeError


def normalize_pdf_to_text_v1(_: bytes) -> str:
    """Normalize pdf to text v 1 helper."""
    raise DocUnsupportedMimeError(
        "PDF normalization is not available in the core MVP; install optional deps."
    )


__all__ = ["normalize_pdf_to_text_v1"]
