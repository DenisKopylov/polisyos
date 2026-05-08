from __future__ import annotations

from polisyos.data_forge.domains.academic.batch import _resolve_extract_transformers as transformers
from polisyos.data_forge.domains.academic.batch import resolve_extract as facade


def test_resolve_extract_transformers_keep_numeric_closeness_behavior() -> None:
    assert transformers._values_close(1.0, 1.0000001) is True
    assert facade._values_close(None, 1.0) is False

