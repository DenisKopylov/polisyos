from __future__ import annotations

import pytest

from polisyos.data_forge.domains.catalog.knowledge.country_codes import (
    COUNTRY_SCOPES,
    country_scope_members,
    iso2_to_iso3,
    iso2_to_numeric,
    normalize_country_code,
)


def test_country_forms_preserve_canonical_identity_and_unknown_scope_refusal() -> None:
    forms = ("AM", "am", "ARM", "051", "Armenia", "Hayastan")

    assert {normalize_country_code(value) for value in forms} == {"AM"}
    assert iso2_to_iso3("051") == "ARM"
    assert iso2_to_numeric("Hayastan") == "051"

    assert normalize_country_code("51") == ""
    assert normalize_country_code("Atlantis") == ""
    assert country_scope_members("") == COUNTRY_SCOPES["regional_extended"]
    with pytest.raises(ValueError, match="Unknown country scope"):
        country_scope_members("not-a-registered-scope")
