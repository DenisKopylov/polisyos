from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.ir.analytics.applicability import (
    ApplicabilityEntitySelector,
    IdSelector,
    NormApplicability,
    TimeWindow,
)
from polisyos.ir.linker import LinkIssueCode, validate_norm_applicability_refs
from polisyos.ir.registry_fragments import ConceptRegistry, RegistryBundle


def test_time_window_ordering() -> None:
    with pytest.raises(ValidationError):
        TimeWindow(valid_from="2024-01-01", valid_to="2023-12-31")


def test_id_selector_rejects_invalid_id() -> None:
    with pytest.raises(ValidationError):
        IdSelector(any_of=["Invalid-ID"])


def test_id_selector_rejects_duplicates() -> None:
    with pytest.raises(ValidationError):
        IdSelector(any_of=["valid_id", "valid_id"])


def test_applicability_unknown_concept_emits_issue() -> None:
    applicability = NormApplicability(
        subject=ApplicabilityEntitySelector(concepts=IdSelector(any_of=["missing_concept"]))
    )

    registries = RegistryBundle(
        concepts=ConceptRegistry(concepts={"known_concept": {"concept_id": "known_concept"}})
    )

    issues = validate_norm_applicability_refs(
        applicability, registries, path_prefix=["norm_pack", "norms", 0, "applicability"]
    )
    assert any(issue.code == LinkIssueCode.UNKNOWN_CONCEPT for issue in issues)
