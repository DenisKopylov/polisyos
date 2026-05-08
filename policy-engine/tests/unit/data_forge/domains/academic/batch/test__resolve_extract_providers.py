from __future__ import annotations

from polisyos.data_forge.domains.academic.batch import _resolve_extract_providers as providers
from polisyos.data_forge.domains.academic.batch import resolve_extract as facade


def test_resolve_extract_provider_helpers_keep_empty_response_contract() -> None:
    response = providers._empty_provider_response(error_class="provider_timeout")
    assert response.error_class == "provider_timeout"
    assert facade._empty_provider_response(error_class="parse_error").parse_status == "empty"

