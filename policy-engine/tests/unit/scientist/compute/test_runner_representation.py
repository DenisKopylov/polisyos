"""Actual MethodBackend emits selected historical representation audit artifacts."""

from __future__ import annotations

from polisyos.core.artifacts import load_core_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod
from polisyos.foundry.methods.selection.registry import MethodRegistry, registry_scope
from polisyos.foundry.validation.method_quality import normalize_foundry_method_report
from polisyos.ir.observation.contract_compilers import BoundsEstimationInput
from polisyos.method_requirement import MethodValidityRequirementSpec
from polisyos.scientist.compute.runner import MethodBackend


def test_backend_selected_registry_persists_fresh_readable_compatibility_audit(tmp_path):
    # This real producer deliberately uses a registry different from the ambient
    # owner, proving dispatch does not guess the selecting registry later.
    registry = MethodRegistry._create_fresh()
    registry.register(BoundsEngineMethod)
    store = FileSystemCAS(tmp_path)
    requirement = MethodValidityRequirementSpec(
        requirement_id="native-bounds",
        run_id="native-run",
        claim_id="effect",
        identification_class="bounds",
        method_expectations=["causal_effect_estimation"],
        facet_refs=["mode"],
        source_precondition_refs=["policy-mode"],
        requires_runtime_assumption_gates=False,
        requires_method_output=False,
        requires_uncertainty_envelope=False,
        requires_limitation_refs=False,
        metadata={
            "explicit_identification_mode_facets": [
                {
                    "facet_ref": "mode",
                    "identification_mode": "bounds_only",
                }
            ]
        },
    )
    backend = MethodBackend(
        store_factory=lambda _: store,
        registry_provider=lambda: registry,
        dispatcher_provider=lambda: MethodDispatcher(enable_runtime_selection=False),
    )
    with registry_scope() as ambient:
        assert ambient.get_entry(BoundsEngineMethod.signature.fqn) is None
        executed = backend.run(
            cas_root=tmp_path,
            method_fqn=BoundsEngineMethod.signature.fqn,
            method_version=None,
            input_state=BoundsEstimationInput(outcome=[0.1, 0.3, 0.8, 0.9], treatment=[0, 0, 1, 1]),
            method_params={"use_auto_bounds": False},
            seed=3,
            method_requirements=[requirement],
        )
    fresh = FileSystemCAS(tmp_path)
    evidence = load_core_json_artifact(fresh, executed.exec_artifacts.evidence_ref)
    report_ref = ArtifactRef.model_validate(evidence["foundry_method_report_ref"])
    assert report_ref.manifest_profile_sha256 is not None
    report = load_core_json_artifact(fresh, report_ref)
    manifest = fresh.get_manifest(report_ref)
    source = next(item for item in manifest.inputs if item.role == "method_result")
    assert source.artifact_id == executed.exec_artifacts.result_ref.artifact_id
    assert (
        source.manifest_profile_sha256 == executed.exec_artifacts.result_ref.manifest_profile_sha256
    )
    assert report["execution_result_ref"] == executed.exec_artifacts.result_ref.model_dump(
        mode="json"
    )
    assert report["method_requirement_statuses"] == {"native-bounds": "satisfied"}
    assert report["status"] == "fail"  # Scientific evidence was never supplied.
    assert report["representation_projection_scope"] == "historical_compatibility_audit_only"
    assert report["runtime_authority_envelope"]["authority_role"] == "historical_audit_projection"
    assert "method_validity" in report["runtime_authority_envelope"]["may_not_use_for"]
    assert "causal_identification" in report["runtime_authority_envelope"]["may_not_use_for"]
    summary = report["candidate_methods"][0]["representation_compatibility"][0]
    assert summary["identification_established"] is False
    assert report["candidate_methods"][0]["method_id"] == BoundsEngineMethod.signature.fqn
    # JSON readback carries audit declarations, not a new live observation.
    reopened = normalize_foundry_method_report(report)
    assert reopened["method_requirement_statuses"] == {"native-bounds": "missing"}
    assert reopened["runtime_authority_envelope"] == report["runtime_authority_envelope"]
    assert reopened["runtime_authority_envelope"]["authority_role"] == "historical_audit_projection"

    for removed in (
        ("representation_projection_scope",),
        ("runtime_authority_envelope",),
        ("representation_projection_scope", "runtime_authority_envelope"),
    ):
        stripped = {key: value for key, value in report.items() if key not in removed}
        reconstructed = normalize_foundry_method_report(stripped)
        assert reconstructed["runtime_authority_envelope"] == report["runtime_authority_envelope"]
        assert (
            reconstructed["representation_projection_scope"]
            == "historical_compatibility_audit_only"
        )
