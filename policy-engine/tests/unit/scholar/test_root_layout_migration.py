"""Prove the Scholar root facade survives owner-module consolidation."""

from __future__ import annotations

import polisyos.scholar as scholar
from polisyos.core.contracts import (
    EnrichmentReportV1 as CoreFacadeEnrichmentReportV1,
)
from polisyos.core.contracts import (
    EnrichResultV1 as CoreFacadeEnrichResultV1,
)
from polisyos.core.contracts import (
    KnowledgeBundlePayloadV1 as CoreFacadeKnowledgeBundlePayloadV1,
)
from polisyos.core.contracts.scholar import (
    EnrichmentReportV1,
    EnrichResultV1,
    KnowledgeBundlePayloadV1,
)
from polisyos.scholar.orchestrator.errors import ScholarAcquireError
from polisyos.scholar.orchestrator.policies import ScholarPolicy
from polisyos.scholar.orchestrator.provenance import ScholarFabricCitation


def test_all_supported_root_exports_resolve_and_reuse_canonical_owner_objects() -> None:
    assert len(scholar.__all__) == 30
    assert all(getattr(scholar, name) is not None for name in scholar.__all__)

    assert scholar.ScholarAcquireError is ScholarAcquireError
    assert scholar.ScholarPolicy is ScholarPolicy
    assert scholar.ScholarFabricCitation is ScholarFabricCitation
    assert scholar.EnrichResultV1 is EnrichResultV1
    assert scholar.EnrichmentReportV1 is EnrichmentReportV1
    assert scholar.KnowledgeBundlePayloadV1 is KnowledgeBundlePayloadV1
    assert CoreFacadeEnrichResultV1 is EnrichResultV1
    assert CoreFacadeEnrichmentReportV1 is EnrichmentReportV1
    assert CoreFacadeKnowledgeBundlePayloadV1 is KnowledgeBundlePayloadV1


def test_bundle_payload_contract_keeps_serialization_and_extra_field_refusal() -> None:
    payload = KnowledgeBundlePayloadV1.model_validate(
        {
            "bundle_id": "bundle-layout-migration",
            "summary": {"doc_count": 1},
            "freshness": {"staleness_threshold_seconds": 3600},
        }
    )
    dumped = payload.model_dump(mode="json")
    assert dumped["schema_version"] == "1.0"
    assert dumped["bundle_id"] == "bundle-layout-migration"

    try:
        KnowledgeBundlePayloadV1.model_validate(
            {"bundle_id": "bundle-layout-migration", "unexpected": True}
        )
    except ValueError:
        pass
    else:
        raise AssertionError("the moved persisted contract must continue rejecting extra fields")


def test_shared_stage_error_keeps_stage_and_source_identity() -> None:
    error = ScholarAcquireError("source refused", source_identity="source:abc")
    assert error.stage == "acquire"
    assert error.source_identity == "source:abc"
