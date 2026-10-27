from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.http.services.control.nl_pipeline import (
    NaturalLanguagePipelineRefusalError,
    _normalize_runtime_quality_same_input_closure,
    _register_runtime_quality_selected_output_ref,
)
from polisyos.runtime.quality.report_registry import (
    _runtime_quality_report_reuse_closure_matches,
)

CITATION_KIND = "scientist.citation_faithfulness_report"
CITATION_REF_KEY = "citation_faithfulness_report_ref"


def _artifact_ref(
    *,
    artifact_id: str = "sha256:" + "a" * 64,
    kind: str = CITATION_KIND,
    media_type: str = "application/json",
    profile: str | None = "sha256:" + "b" * 64,
) -> ArtifactRef:
    return ArtifactRef.model_validate(
        {
            "artifact_id": artifact_id,
            "kind": kind,
            "media_type": media_type,
            "manifest_profile_sha256": profile,
        }
    )


def test_selected_output_registration_keeps_exact_ref_and_matching_id() -> None:
    selected_ref = _artifact_ref()
    runtime_refs: dict[str, str] = {}
    selected_refs: dict[str, ArtifactRef] = {}

    artifact_id = _register_runtime_quality_selected_output_ref(
        ref_key=CITATION_REF_KEY,
        selected_ref=selected_ref,
        runtime_quality_refs=runtime_refs,
        runtime_quality_artifact_refs=selected_refs,
        expected_kind=CITATION_KIND,
        expected_media_type="application/json",
    )

    assert artifact_id == str(selected_ref.artifact_id)
    assert runtime_refs == {CITATION_REF_KEY: str(selected_ref.artifact_id)}
    assert selected_refs == {CITATION_REF_KEY: selected_ref}
    assert selected_refs[CITATION_REF_KEY] is selected_ref


@pytest.mark.parametrize(
    ("selected_ref", "expected_artifact_id", "expected_kind", "expected_media_type"),
    [
        pytest.param(
            _artifact_ref(profile=None),
            None,
            CITATION_KIND,
            "application/json",
            id="profileless-default-view",
        ),
        pytest.param(
            _artifact_ref(),
            "sha256:" + "d" * 64,
            CITATION_KIND,
            "application/json",
            id="artifact-id-does-not-match-selected-view",
        ),
        pytest.param(
            _artifact_ref(kind="scientist.source_quality_report"),
            None,
            CITATION_KIND,
            "application/json",
            id="wrong-kind",
        ),
        pytest.param(
            _artifact_ref(media_type="application/octet-stream"),
            None,
            CITATION_KIND,
            "application/json",
            id="wrong-media-type",
        ),
    ],
)
def test_selected_output_registration_refuses_incomplete_or_mismatched_views(
    selected_ref: ArtifactRef,
    expected_artifact_id: str | None,
    expected_kind: str,
    expected_media_type: str,
) -> None:
    runtime_refs: dict[str, str] = {}
    selected_refs: dict[str, ArtifactRef] = {}

    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        _register_runtime_quality_selected_output_ref(
            ref_key=CITATION_REF_KEY,
            selected_ref=selected_ref,
            runtime_quality_refs=runtime_refs,
            runtime_quality_artifact_refs=selected_refs,
            expected_kind=expected_kind,
            expected_media_type=expected_media_type,
            expected_artifact_id=expected_artifact_id,
        )

    assert runtime_refs == {}
    assert selected_refs == {}


def test_same_input_closure_normalizes_typed_defaults_and_compares_all_fields() -> None:
    closure = {
        "closure_id": "run-1:runtime_quality",
        "status": "not_closed",
        "policy_intent_ref": "sha256:" + "1" * 64,
        "run_id": "run-1",
        "job_id": "job-1",
        "tenant_id": "tenant-1",
        "cell_id": "cell-1",
        "time_context_ref": None,
        "production_data_manifest_ref": "sha256:" + "2" * 64,
        "legal_snapshot_ref": None,
        "effective_mode_ref": "runtime-mode:research",
        "evidence_input_refs": ["sha256:" + "3" * 64],
        "closure_sha256": None,
    }

    normalized = _normalize_runtime_quality_same_input_closure(closure)
    assert normalized["method_plan_ref"] is None
    assert normalized["provider_mode_ref"] is None
    assert normalized["degradation_ledger_ref"] is None
    basis = SimpleNamespace(authority_envelope={"same_input_closure": normalized})
    assert _runtime_quality_report_reuse_closure_matches(basis, normalized)

    changed = _normalize_runtime_quality_same_input_closure(
        {**closure, "method_plan_ref": "sha256:" + "4" * 64}
    )
    assert changed["method_plan_ref"] == "sha256:" + "4" * 64
    assert not _runtime_quality_report_reuse_closure_matches(basis, changed)

    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        _normalize_runtime_quality_same_input_closure(
            {**closure, "undeclared_closure_ref": "sha256:" + "5" * 64}
        )
