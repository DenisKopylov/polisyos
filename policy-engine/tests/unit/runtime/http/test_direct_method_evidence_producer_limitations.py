from __future__ import annotations

from typing import Literal

import pytest
from unit.runtime.http.test_observational_method_runtime import (
    _direct_method_cas_case,
    _put_selected_json,
)

from polisyos.core.artifacts.canonical_profile import (
    read_core_json_artifact_bounded,
    read_core_manifest_profile_bounded,
)
from polisyos.core.contracts.runtime import _expected_content_admitted_limitations
from polisyos.runtime.http.services.control.run_lifecycle import (
    _validate_direct_method_execution_selection_artifacts,
)


@pytest.mark.parametrize(
    "source_protocol",
    ["method_input_envelope_v1", "legacy_hte_json_v1"],
)
@pytest.mark.parametrize(
    "producer_mutation",
    [
        "exact_producer_set",
        "missing_producer_limitation",
        "extra_admitted_limitation",
        "duplicate_producer_limitation",
    ],
)
def test_direct_method_evidence_limitations_match_exact_producer_scope(
    tmp_path,
    source_protocol: Literal["method_input_envelope_v1", "legacy_hte_json_v1"],
    producer_mutation: Literal[
        "exact_producer_set",
        "missing_producer_limitation",
        "extra_admitted_limitation",
        "duplicate_producer_limitation",
    ],
) -> None:
    """Bind evidence limitations to the producer while retaining selected owner caveats."""
    store, selection, limits = _direct_method_cas_case(tmp_path, protocol=source_protocol)
    expected_producer = _expected_content_admitted_limitations(
        source_protocol,
        source_access_revalidation_status=None,
    )
    expected_admitted = _expected_content_admitted_limitations(
        source_protocol,
        source_access_revalidation_status="not_established",
    )
    assert selection.limitations == expected_admitted
    assert "source_access_revalidation_not_established" in selection.limitations
    assert selection.limitations != expected_producer

    manifest_read = read_core_manifest_profile_bounded(
        store,
        selection.method_evidence_ref,
        max_manifest_bytes=limits.max_manifest_bytes,
    )
    evidence_read = read_core_json_artifact_bounded(
        store,
        selection.method_evidence_ref,
        limits=limits,
        manifest_read=manifest_read,
    )
    assert isinstance(evidence_read.value, dict)
    evidence_payload = dict(evidence_read.value)
    if producer_mutation == "exact_producer_set":
        evidence_payload["limitations"] = list(expected_producer)
    elif producer_mutation == "missing_producer_limitation":
        evidence_payload["limitations"] = [
            item for item in expected_producer if item != "scientific_validity_not_established"
        ]
    elif producer_mutation == "extra_admitted_limitation":
        evidence_payload["limitations"] = [
            *expected_producer,
            "source_access_revalidation_not_established",
        ]
    else:
        evidence_payload["limitations"] = [expected_producer[0], *expected_producer]

    evidence_manifest = manifest_read.manifest
    replacement_ref = _put_selected_json(
        store,
        evidence_payload,
        kind=evidence_manifest.kind,
        schema=evidence_manifest.artifact_schema,
        inputs=tuple(evidence_manifest.inputs),
        governance=evidence_manifest.governance,
        tenant_context=evidence_manifest.tenant_context,
    )
    replacement_selection = selection.model_copy(update={"method_evidence_ref": replacement_ref})
    persisted_replacement = read_core_json_artifact_bounded(
        store,
        replacement_ref,
        limits=limits,
    )
    assert isinstance(persisted_replacement.value, dict)
    assert persisted_replacement.value["limitations"] == evidence_payload["limitations"]

    if producer_mutation == "exact_producer_set":
        assert persisted_replacement.value["limitations"] == list(expected_producer)
        assert persisted_replacement.value["limitations"] != list(replacement_selection.limitations)
        _validate_direct_method_execution_selection_artifacts(
            store=store,
            selection=replacement_selection,
            limits=limits,
        )
    else:
        with pytest.raises(
            ValueError,
            match="direct_method_execution_evidence_content_mismatch",
        ):
            _validate_direct_method_execution_selection_artifacts(
                store=store,
                selection=replacement_selection,
                limits=limits,
            )
