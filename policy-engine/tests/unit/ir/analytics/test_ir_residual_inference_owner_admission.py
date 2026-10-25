from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.bayesian.protocols import canonical_draws_artifact
from polisyos.ir.analytics import causal as causal_module
from polisyos.ir.analytics import metric_validation_report as metric_module
from polisyos.ir.analytics import negative_certificate as negative_module
from polisyos.ir.analytics import network_generative as network_module
from polisyos.ir.analytics import posterior_summary as posterior_module
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    DataReadinessReport,
    ProofBundle,
    load_causal_effect_report,
    load_data_readiness_report,
    load_proof_bundle,
    persist_causal_effect_report,
    persist_data_readiness_report,
    persist_proof_bundle,
)
from polisyos.ir.analytics.metric_validation_report import (
    FamilyAdjustment,
    MetricValidationReport,
    load_metric_validation_report,
    persist_metric_validation_report,
)
from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    NegativeCertificate,
    load_negative_certificate,
    persist_negative_certificate,
)
from polisyos.ir.analytics.network_generative import (
    CausalBlockBridge,
    load_causal_block_bridge,
    persist_causal_block_bridge,
)
from polisyos.ir.analytics.posterior_summary import (
    PosteriorPointRole,
    PosteriorSummaryV11,
    load_posterior_summary,
    persist_posterior_summary,
    summarize_posterior_draw_artifact,
)
from polisyos.ir.artifacts import get_json_artifact, put_json_artifact
from polisyos.ir.artifacts.io import _get_owned_json_artifact_with_bytes
from polisyos.ir.migrations import base as migrations_base
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    CausalBlockBridgeRef,
    CausalEffectReportRef,
)


def _causal_report() -> CausalEffectReport:
    return CausalEffectReport(
        method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
        estimand="policy.employment.effect",
        point_estimate=0.2,
        confidence_interval=(0.1, 0.3),
        inference_method="asymptotic",
        sample_size=10,
        n_treated=5,
        n_control=5,
        pre_periods=2,
        post_periods=2,
    )


def _proof_bundle() -> ProofBundle:
    return ProofBundle(
        proof_status="oracle_needed",
        proof_stratum="A2_oracle_backed",
        theorem_family="candidate",
        completeness_regime="heuristic_backed",
        implementation_coverage="candidate_only",
    )


def _readiness_report() -> DataReadinessReport:
    return DataReadinessReport(
        decision="pass",
        can_compile_estimation=True,
        can_run_estimation=True,
        sample_size=10,
    )


def _metric_report() -> MetricValidationReport:
    return MetricValidationReport(
        report_id="metric-validation-candidate",
        dataset_id="policy-dataset",
        task="effect_estimation",
        checked_at="2026-10-24T12:00:00Z",
        family_adjustment=FamilyAdjustment(
            method="holm",
            alpha=0.05,
            hypotheses_total=1,
            error_rate_target="FWER",
        ),
        comparisons=(),
    )


def _block_bridge() -> CausalBlockBridge:
    return CausalBlockBridge(
        cluster_id=0,
        node_to_block={"unit-a": 0},
        positivity_passed=True,
    )


def _negative_certificate() -> NegativeCertificate:
    return NegativeCertificate(
        blocking_type=BlockingType.HEDGE_STRUCTURE,
        blocking_description="A hedge blocks the candidate query.",
    )


def _posterior_summary(store: FileSystemCAS) -> tuple[PosteriorSummaryV11, ArtifactRefModel]:
    evidence_payload = {"evidence": "candidate"}
    evidence_raw_ref = put_json_artifact(
        store,
        evidence_payload,
        kind="scientist.method_evidence",
        schema_name="polisyos.scientist.MethodExecutionEvidence",
        schema_version="0.1.0",
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    evidence_ref = ArtifactRefModel.model_validate(evidence_raw_ref)
    artifact_ref, artifact_payload, artifact_hash, _layout = canonical_draws_artifact(
        {"theta": np.asarray([[1.0, 2.0, 3.0]], dtype=np.float64)},
        method_name="ir_residual_inference_owner_admission",
        sampler_kernel="hmc",
        stage="posterior",
    )
    summary = summarize_posterior_draw_artifact(
        artifact_ref=artifact_ref,
        artifact_payload=artifact_payload,
        artifact_hash=artifact_hash,
        credible_mass=0.9,
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
        source_method_evidence_ref=evidence_ref,
    )
    return summary, evidence_ref


def test_all_residual_typed_families_round_trip_through_fresh_cas_readers(
    tmp_path: Path,
) -> None:
    store_root = tmp_path / "residual-families"
    store = ensure_ir_artifact_store(FileSystemCAS(store_root))
    causal_report = _causal_report()
    assert causal_report.schema_version == "1.1"
    default_profile_ref = persist_causal_effect_report(store, causal_report)
    assert default_profile_ref.manifest_profile_sha256 is None

    array_bridge = CausalBlockBridge(
        cluster_id=np.asarray([0, 0, 1, 1], dtype=int),
        node_to_block={"unit-a": 0, "unit-b": 0, "unit-c": 1, "unit-d": 1},
    )
    refs: dict[str, Any] = {
        "causal": persist_causal_effect_report(
            store,
            causal_report,
            return_selected_profile=True,
        ),
        "proof": persist_proof_bundle(store, _proof_bundle()),
        "readiness": persist_data_readiness_report(store, _readiness_report()),
        "negative": persist_negative_certificate(store, _negative_certificate()),
        "metric": persist_metric_validation_report(store, _metric_report()),
        "block": persist_causal_block_bridge(store, _block_bridge()),
        "array_block": persist_causal_block_bridge(store, array_bridge),
    }
    summary, evidence_ref = _posterior_summary(store)
    refs["posterior"] = persist_posterior_summary(
        store,
        summary,
        source_method_evidence_ref=evidence_ref,
    )
    assert all(ref.manifest_profile_sha256 for ref in refs.values())

    fresh_store = ensure_ir_artifact_store(FileSystemCAS(store_root))
    assert load_causal_effect_report(fresh_store, refs["causal"]) == causal_report
    assert load_causal_effect_report(fresh_store, default_profile_ref) == causal_report
    assert load_proof_bundle(fresh_store, refs["proof"]) == _proof_bundle()
    assert load_data_readiness_report(fresh_store, refs["readiness"]) == _readiness_report()
    assert load_negative_certificate(fresh_store, refs["negative"]) == _negative_certificate()
    assert load_metric_validation_report(fresh_store, refs["metric"]) == _metric_report()
    loaded_bridge = load_causal_block_bridge(fresh_store, refs["block"])
    assert int(loaded_bridge.cluster_id) == 0
    assert loaded_bridge.node_to_block == {"unit-a": 0}
    loaded_array_bridge = load_causal_block_bridge(fresh_store, refs["array_block"])
    assert np.array_equal(loaded_array_bridge.cluster_id, array_bridge.cluster_id)
    assert loaded_array_bridge.node_to_block == array_bridge.node_to_block
    assert loaded_array_bridge.block_support == array_bridge.block_support
    assert loaded_array_bridge.positivity_passed is array_bridge.positivity_passed
    assert loaded_array_bridge.aggregate_exposures == array_bridge.aggregate_exposures
    assert loaded_array_bridge.warnings == array_bridge.warnings
    assert load_posterior_summary(fresh_store, refs["posterior"]) == summary

    assert fresh_store.get_manifest(refs["causal"]).artifact_schema.version == "1.1"
    assert get_json_artifact(fresh_store, refs["causal"])["schema_version"] == "1.1"
    assert fresh_store.get_manifest(refs["proof"]).artifact_schema.version == "1.0"
    assert get_json_artifact(fresh_store, refs["proof"])["schema_version"] == "1.1"
    assert fresh_store.get_manifest(refs["posterior"]).inputs[0].manifest_profile_sha256 == (
        evidence_ref.manifest_profile_sha256
    )
    envelope = load_causal_effect_report(fresh_store, refs["causal"]).to_uncertainty_envelope()
    assert envelope is not None
    assert envelope.gate_eligible is False

    read = _get_owned_json_artifact_with_bytes(
        fresh_store,
        refs["causal"],
        owner=causal_module._CAUSAL_EFFECT_REPORT_OWNER,
    )
    assert read.value == causal_report
    assert read.raw_bytes == fresh_store.get_bytes(refs["causal"])
    assert read.admission.source_registration.payload_version == "1.1"

    owner_cases = (
        ("causal", causal_module._CAUSAL_EFFECT_REPORT_OWNER, "1.1", "1.1"),
        ("proof", causal_module._PROOF_BUNDLE_OWNER, "1.0", "1.1"),
        ("readiness", causal_module._DATA_READINESS_REPORT_OWNER, "1.0", "1.0"),
        ("negative", negative_module._NEGATIVE_CERTIFICATE_OWNER, "1.0", None),
        ("metric", metric_module._METRIC_VALIDATION_REPORT_OWNER, "1.0", "1.0"),
        ("block", network_module._CAUSAL_BLOCK_BRIDGE_OWNER, "1.0", None),
        ("array_block", network_module._CAUSAL_BLOCK_BRIDGE_OWNER, "1.0", None),
        ("posterior", posterior_module._POSTERIOR_SUMMARY_OWNER, "1.1", "1.1"),
    )
    for ref_name, owner, manifest_version, payload_version in owner_cases:
        ref = refs[ref_name]
        owner_read = _get_owned_json_artifact_with_bytes(
            fresh_store,
            ref,
            owner=owner,
        )
        registration = owner_read.admission.source_registration
        assert ref.kind == owner.kind
        assert ref.media_type == owner.media_type
        assert registration.schema_name == owner.registry_key
        assert registration.schema_version == manifest_version
        assert registration.payload_version == payload_version
        assert owner_read.raw_bytes == fresh_store.get_bytes(ref)


def test_causal_report_1_0_is_a_readable_source_supported_predecessor(tmp_path: Path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "causal-predecessor"))
    predecessor = _causal_report().model_copy(update={"schema_version": "1.0"})
    raw_ref = put_json_artifact(
        store,
        predecessor.model_dump(mode="json"),
        kind="ir.causal_effect_report",
        schema_name="ir.causal_effect_report",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    ref = CausalEffectReportRef.model_validate(raw_ref)
    fresh_store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "causal-predecessor"))
    assert load_causal_effect_report(fresh_store, ref) == predecessor


def test_unknown_equal_numeric_tuple_stays_opaque_and_typed_reader_refuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "unknown-equal-tuple"))
    unknown = _causal_report().model_copy(update={"schema_version": "9.9"})
    raw_ref = put_json_artifact(
        store,
        unknown.model_dump(mode="json"),
        kind="ir.causal_effect_report",
        schema_name="ir.causal_effect_report",
        schema_version="9.9",
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    ref = CausalEffectReportRef.model_validate(raw_ref)
    assert get_json_artifact(store, ref)["schema_version"] == "9.9"
    with pytest.raises(ValueError, match="ir_owned_artifact_representation_unregistered"):
        load_causal_effect_report(store, ref)

    original_put = FileSystemCAS.put_json
    put_calls = 0

    def count_put(
        target: FileSystemCAS,
        payload: object,
        opts: object,
        canon_spec: object = None,
        *,
        return_selected_profile: bool = False,
    ) -> object:
        nonlocal put_calls
        put_calls += 1
        return original_put(
            target,
            payload,
            opts=opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )

    monkeypatch.setattr(FileSystemCAS, "put_json", count_put)
    with pytest.raises(ValueError, match="ir_owned_artifact_write_override_unregistered"):
        persist_causal_effect_report(
            store,
            unknown,
            schema_name="ir.causal_effect_report",
            schema_version="9.9",
            return_selected_profile=True,
        )
    assert put_calls == 0


def test_registered_manifest_with_mismatched_payload_tuple_refuses_typed_use(
    tmp_path: Path,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "payload-manifest-mismatch"))
    mismatched = _causal_report().model_copy(update={"schema_version": "1.0"})
    raw_ref = put_json_artifact(
        store,
        mismatched.model_dump(mode="json"),
        kind="ir.causal_effect_report",
        schema_name="ir.causal_effect_report",
        schema_version="1.1",
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    ref = CausalEffectReportRef.model_validate(raw_ref)
    assert get_json_artifact(store, ref)["schema_version"] == "1.0"
    with pytest.raises(ValueError, match="ir_owned_artifact_representation_unreadable"):
        load_causal_effect_report(store, ref)


def test_same_kind_wrong_profile_and_selected_view_mutation_refuse_without_owner_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "profile-mutation"))
    bridge = _block_bridge()
    owned_ref = persist_causal_block_bridge(store, bridge)
    owner_payload = bridge.model_dump(mode="json")
    wrong_profile_raw_ref = put_json_artifact(
        store,
        owner_payload,
        kind="ir.causal_block_bridge",
        schema_name="ir.causal_block_bridge",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=True),
        return_selected_profile=True,
    )
    wrong_profile_ref = CausalBlockBridgeRef.model_validate(wrong_profile_raw_ref)
    assert wrong_profile_ref.artifact_id == owned_ref.artifact_id
    assert wrong_profile_ref.manifest_profile_sha256 != owned_ref.manifest_profile_sha256
    assert get_json_artifact(store, wrong_profile_ref) == owner_payload

    mutated_ref = owned_ref.model_copy(
        update={"manifest_profile_sha256": wrong_profile_ref.manifest_profile_sha256}
    )
    assert mutated_ref.artifact_id == owned_ref.artifact_id

    def refuses_wrong_profile(ref: CausalBlockBridgeRef) -> bool:
        try:
            load_causal_block_bridge(store, ref)
        except ValueError as exc:
            return "ir_owned_artifact_profile_refused" in str(exc)
        return False

    assert refuses_wrong_profile(wrong_profile_ref)
    assert refuses_wrong_profile(mutated_ref)

    owned_read = _get_owned_json_artifact_with_bytes(
        store,
        owned_ref,
        owner=network_module._CAUSAL_BLOCK_BRIDGE_OWNER,
    )
    assert owned_read.value.node_to_block == bridge.node_to_block
    assert owned_read.raw_bytes == store.get_bytes(owned_ref)

    def without_owner_admission(
        candidate_store: Any,
        candidate_ref: Any,
        *,
        owner: Any,
    ) -> CausalBlockBridge:
        return CausalBlockBridge.model_validate(get_json_artifact(candidate_store, candidate_ref))

    with monkeypatch.context() as bypass:
        bypass.setattr(network_module, "_get_owned_json_artifact", without_owner_admission)
        assert not refuses_wrong_profile(mutated_ref)


def test_registered_nondefault_same_owner_wire_tuple_uses_shared_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = {
        artifact: dict(versions) for artifact, versions in migrations_base._SCHEMA_REGISTRY.items()
    }
    monkeypatch.setattr(migrations_base, "_SCHEMA_REGISTRY", registry)
    owner = metric_module._METRIC_VALIDATION_REPORT_OWNER
    wire_policy_ref, wire_policy_revision = owner.accepted_wire_policies[0]
    migrations_base.register_schema_version(
        owner.registry_key,
        "1.2",
        compatibility=migrations_base.CompatibilityMode.NONE,
        notes=("Test extension reuses the existing owner wire law.",),
    )
    migrations_base.register_ir_representation(
        registry_key=owner.registry_key,
        owner_ref=owner.contract_id,
        dto_abi=owner.dto_fqn,
        wire_policy_ref=wire_policy_ref,
        wire_policy_revision=wire_policy_revision,
        schema_name=owner.registry_key,
        schema_version="1.2",
        payload_version="1.0",
        profile_ref=None,
        readable=True,
        writable=True,
        current=False,
        default_write=False,
    )

    store_root = tmp_path / "registered-extension"
    store = ensure_ir_artifact_store(FileSystemCAS(store_root))
    report = _metric_report()
    ref = persist_metric_validation_report(store, report, schema_version="1.2")
    fresh_store = ensure_ir_artifact_store(FileSystemCAS(store_root))
    read = _get_owned_json_artifact_with_bytes(
        fresh_store,
        ref,
        owner=owner,
    )
    assert read.admission.source_registration.schema_version == "1.2"
    assert read.admission.source_registration.payload_version == "1.0"
    assert read.value == report
    assert load_metric_validation_report(fresh_store, ref) == report
