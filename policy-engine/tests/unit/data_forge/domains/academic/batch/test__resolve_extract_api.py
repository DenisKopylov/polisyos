from __future__ import annotations

from polisyos.data_forge.domains.academic.batch import _resolve_extract_api as api
from polisyos.data_forge.domains.academic.batch import resolve_extract as facade


def test_resolve_extract_api_module_keeps_facade_entrypoint() -> None:
    assert callable(api.run_resolve_extract)
    assert callable(facade.run_resolve_extract)
    assert callable(facade._run_resolve_extract_pass)

