from __future__ import annotations

from polisyos.data_forge.domains.academic.batch import _resolve_extract_io as io
from polisyos.data_forge.domains.academic.batch import resolve_extract as facade


def test_resolve_extract_io_helpers_are_reexported() -> None:
    assert io._terminal_state("published") is True
    assert facade._retryable_state("retryable_failed") is True
