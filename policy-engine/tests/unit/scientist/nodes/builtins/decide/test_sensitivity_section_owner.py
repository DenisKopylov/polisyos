"""Selected sensitivity evidence stays owner-bound through packet projection."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo, artifact_ref_identity_key
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir.analytics.sensitivity import (
    SensitivityAnalysisBundle,
    SensitivityAnalysisBundleRef,
    SensitivityAnalysisIndex,
    SensitivityResult,
    load_sensitivity_analysis_bundle,
    persist_sensitivity_analysis_bundle,
    persist_sensitivity_result,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.basis_sections import (
    _build_sensitivity_section,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.serialization import (
    _sensitivity_analysis_bundle_ref_from_packet,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF,
    ARTIFACT_SENSITIVITY_RESULT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext


def _refs(store: FileSystemCAS) -> tuple[ArtifactRef, ArtifactRef]:
    ir_store = ensure_ir_artifact_store(store)
    bundle = SensitivityAnalysisBundle(
        bundle_id="synthetic-sensitivity",
        indices=[SensitivityAnalysisIndex(name="synthetic", estimate=0.5, standard_error=0.1)],
    )
    selected_bundle = persist_sensitivity_analysis_bundle(ir_store, bundle)
    selected_result = persist_sensitivity_result(
        ir_store, SensitivityResult(e_value=1.8, is_robust=True, interpretation="synthetic")
    )
    return (
        ArtifactRef.model_validate(selected_bundle.model_dump(mode="json")),
        ArtifactRef.model_validate(selected_result.model_dump(mode="json")),
    )


def _foreign_schema(store: FileSystemCAS, ref: ArtifactRef) -> ArtifactRef:
    manifest = store.get_manifest(ref)
    foreign = store.put_bytes(
        store.get_bytes(ref),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=SchemaInfo(name="foreign.sensitivity_evidence", version="1.0"),
            canon=manifest.canon,
        ),
        return_selected_profile=True,
    )
    assert foreign.artifact_id == ref.artifact_id
    assert foreign.manifest_profile_sha256 != ref.manifest_profile_sha256
    assert store.verify(foreign).ok
    return foreign


@pytest.mark.parametrize("selection", ["bundle", "result"])
def test_packet_sensitivity_preserves_actual_selected_owner_profile(
    tmp_path, selection: str
) -> None:
    store = FileSystemCAS(tmp_path)
    bundle_ref, result_ref = _refs(store)
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    ref = bundle_ref if selection == "bundle" else result_ref
    key = (
        ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF
        if selection == "bundle"
        else ARTIFACT_SENSITIVITY_RESULT_REF
    )
    section = _build_sensitivity_section(ctx, {key: ref})
    assert section is not None
    bundle_selection = _sensitivity_analysis_bundle_ref_from_packet({"sensitivity": section})
    assert bundle_selection is not None
    assert bundle_selection.manifest_profile_sha256 is not None
    loaded = load_sensitivity_analysis_bundle(
        ensure_ir_artifact_store(store),
        SensitivityAnalysisBundleRef.model_validate(bundle_selection.model_dump(mode="json")),
    )
    assert loaded.indices
    if selection == "bundle":
        assert artifact_ref_identity_key(bundle_selection) == artifact_ref_identity_key(bundle_ref)
    else:
        manifest = store.get_manifest(ArtifactRef.model_validate(bundle_selection.model_dump()))
        assert any(
            edge.manifest_profile_sha256 == result_ref.manifest_profile_sha256
            for edge in manifest.inputs
        )


@pytest.mark.parametrize("selection", ["bundle", "result"])
@pytest.mark.parametrize("corruption", ["missing_profile", "foreign_schema"])
def test_packet_sensitivity_never_projects_unadmitted_payload(
    tmp_path, selection: str, corruption: str
) -> None:
    store = FileSystemCAS(tmp_path)
    bundle_ref, result_ref = _refs(store)
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    ref = bundle_ref if selection == "bundle" else result_ref
    invalid = (
        ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
        if corruption == "missing_profile"
        else _foreign_schema(store, ref)
    )
    key = (
        ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF
        if selection == "bundle"
        else ARTIFACT_SENSITIVITY_RESULT_REF
    )
    refs = {key: invalid}
    if selection == "bundle":
        refs[ARTIFACT_SENSITIVITY_RESULT_REF] = result_ref
    packet: dict[str, object] = {}
    section = _build_sensitivity_section(ctx, refs, packet_payload=packet)
    assert section is not None
    assert section["parse_warning"]
    assert "content" not in section
    assert "sensitivity_analysis_bundle" not in section
    assert packet.get("degraded_paths")
