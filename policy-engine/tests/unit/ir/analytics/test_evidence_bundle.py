"""Tests for EvidenceBundle IR models."""

from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.evidence_bundle import (
    CompilationStep,
    DataProvenance,
    EstimationStep,
    EvidenceBundle,
    ProofStep,
    _validate_evidence_bundle_source,
    load_causal_evidence_bundle,
    load_causal_evidence_bundle_with_admission,
    persist_causal_evidence_bundle,
)
from polisyos.ir.artifacts import get_json_artifact, put_json_artifact
from polisyos.ir.migrations import negotiate_schema_version
from polisyos.ir.migrations.base import (
    CompatibilityMode,
    IRCompatibilityKind,
    ResolvedSchemaAdmission,
    get_ir_owner_registry_snapshot,
    register_ir_representation,
    register_schema_version,
)
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    BoundsBundleRef,
    DataReadinessReportRef,
    EvidenceBundleRef,
    KernelEstimatorSpecRef,
    NegativeCertificateRef,
    ProofBundleRef,
    TwinNetworkResultRef,
)

_LEGACY_EVIDENCE_BUNDLE_V1_FIELDS = frozenset(
    {
        "algorithm_version",
        "bounds_bundle_ref",
        "compilation_steps",
        "created_at",
        "data_provenance",
        "data_readiness_report_ref",
        "diagnostic_dashboard",
        "diagnostic_scores",
        "estimand_ast",
        "estimand_fingerprint",
        "estimation_steps",
        "graph_fingerprint",
        "identification_status",
        "kernel_estimator_spec_ref",
        "method_config",
        "negative_certificate_ref",
        "proof_bundle_ref",
        "proof_steps",
        "quality_report",
        "query_str",
        "run_id",
    }
)


class _LegacyEvidenceBundleV1(BaseModel):
    """Pinned strict 1.0 parser matching the catalog before the Twin field existed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    query_str: str
    estimand_ast: dict[str, Any] = Field(default_factory=dict)
    proof_steps: tuple[ProofStep, ...] = ()
    data_provenance: tuple[DataProvenance, ...] = ()
    diagnostic_scores: dict[str, float] = Field(default_factory=dict)
    method_config: dict[str, Any] = Field(default_factory=dict)
    identification_status: str = ""
    algorithm_version: str = ""
    created_at: str = ""
    graph_fingerprint: str = ""
    estimand_fingerprint: str = ""
    compilation_steps: tuple[CompilationStep, ...] = ()
    estimation_steps: tuple[EstimationStep, ...] = ()
    diagnostic_dashboard: dict[str, Any] | None = None
    quality_report: dict[str, Any] | None = None
    proof_bundle_ref: ProofBundleRef | None = None
    bounds_bundle_ref: BoundsBundleRef | None = None
    negative_certificate_ref: NegativeCertificateRef | None = None
    data_readiness_report_ref: DataReadinessReportRef | None = None
    kernel_estimator_spec_ref: KernelEstimatorSpecRef | None = None


def _legacy_evidence_bundle_v1_parser() -> type[_LegacyEvidenceBundleV1]:
    """Return the strict parser pinned to the committed pre-Twin field set."""
    assert set(_LegacyEvidenceBundleV1.model_fields) == _LEGACY_EVIDENCE_BUNDLE_V1_FIELDS
    assert set(EvidenceBundle.model_fields) - {"twin_network_result_ref"} == (
        _LEGACY_EVIDENCE_BUNDLE_V1_FIELDS
    )
    return _LegacyEvidenceBundleV1


def _read_with_legacy_v1_reader(store, ref):
    """Reproduce a pinned strict reader that only recognizes manifest schema 1.0."""
    schema = store.get_manifest(ref).artifact_schema
    version = schema.version if schema is not None else None
    if schema is None or schema.name != "ir.causal_evidence_bundle" or version != "1.0":
        raise ValueError(f"Unsupported schema version {version!r}; expected '1.0'")
    return _legacy_evidence_bundle_v1_parser().model_validate(get_json_artifact(store, ref))


class TestProofStep:
    def test_frozen_model(self):
        step = ProofStep(rule_name="RULE1", description="backdoor criterion applied")
        with pytest.raises((TypeError, Exception)):
            step.rule_name = "RULE2"

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            ProofStep(rule_name="R", description="d", nonexistent_field="oops")

    def test_defaults(self):
        step = ProofStep(rule_name="C_COMPONENT", description="c-component factorization")
        assert step.variables_affected == ()
        assert step.graph_subset == ""

    def test_all_fields(self):
        step = ProofStep(
            rule_name="RULE3",
            description="do-calculus rule 3",
            variables_affected=("X", "Y"),
            graph_subset="G[X,Y,Z]",
        )
        assert step.rule_name == "RULE3"
        assert step.variables_affected == ("X", "Y")

    def test_new_fields_default_to_empty_string(self):
        step = ProofStep(rule_name="RULE1", description="backdoor criterion applied")
        assert step.rule_formal_name == ""
        assert step.applicable_theorem == ""
        assert step.graph_state_before == ""
        assert step.graph_state_after == ""
        assert step.step_id == ""
        assert step.theorem_family == ""
        assert step.witness_ids == ()
        assert step.depends_on_steps == ()
        assert step.local_status == "unknown"
        assert step.invalidation_reason is None

    def test_new_fields_can_be_set(self):
        step = ProofStep(
            rule_name="RULE3",
            description="Removing do-operator via rule 3",
            rule_formal_name="do-calculus rule 3",
            applicable_theorem="do-calculus-R3",
            graph_state_before="G_X_intervened",
            graph_state_after="G_X_observed",
            step_id="s3",
            theorem_family="id_v1",
            input_expr_ref="artifact:expr:before",
            output_expr_ref="artifact:expr:after",
            witness_ids=("w1",),
            depends_on_steps=("s1", "s2"),
            local_status="valid",
        )
        assert step.rule_formal_name == "do-calculus rule 3"
        assert step.applicable_theorem == "do-calculus-R3"
        assert step.graph_state_before == "G_X_intervened"
        assert step.graph_state_after == "G_X_observed"
        assert step.step_id == "s3"
        assert step.local_status == "valid"
        assert step.witness_ids == ("w1",)

    def test_new_fields_round_trip_json(self):
        step = ProofStep(
            rule_name="HEDGE",
            description="Hedge found",
            rule_formal_name="hedge-certificate",
            applicable_theorem="ID-algorithm-step-4a",
            graph_state_before="G_full",
            graph_state_after="G_blocked",
            step_id="h1",
            theorem_family="id_v1",
            witness_ids=("w_hedge",),
            local_status="invalid",
            invalidation_reason="hedge_witness_broken",
        )
        data = step.model_dump(mode="json")
        restored = ProofStep.model_validate(data)
        assert restored.rule_formal_name == "hedge-certificate"
        assert restored.graph_state_after == "G_blocked"
        assert restored.step_id == "h1"
        assert restored.local_status == "invalid"
        assert restored.invalidation_reason == "hedge_witness_broken"


class TestDataProvenance:
    def test_frozen_model(self):
        dp = DataProvenance(dataset_ref="ds1")
        with pytest.raises((TypeError, Exception)):
            dp.dataset_ref = "ds2"

    def test_quality_score_bounded(self):
        with pytest.raises(Exception):
            DataProvenance(dataset_ref="ds1", quality_score=1.5)
        with pytest.raises(Exception):
            DataProvenance(dataset_ref="ds1", quality_score=-0.1)

    def test_valid_quality_score(self):
        dp = DataProvenance(dataset_ref="ds1", quality_score=0.8)
        assert dp.quality_score == 0.8

    def test_defaults(self):
        dp = DataProvenance(dataset_ref="ds1")
        assert dp.n_obs is None
        assert dp.domain == "source"
        assert dp.availability_status == "available"


class TestEvidenceBundle:
    def _minimal(self):
        return EvidenceBundle(run_id="run-001", query_str="P(Y|do(X))")

    def test_minimal_creation(self):
        bundle = self._minimal()
        assert bundle.run_id == "run-001"
        assert bundle.query_str == "P(Y|do(X))"

    def test_full_creation(self):
        step = ProofStep(rule_name="RULE1", description="backdoor")
        dp = DataProvenance(dataset_ref="ds1", n_obs=500)
        bundle = EvidenceBundle(
            run_id="run-002",
            query_str="P(Y|do(X),Z)",
            estimand_ast={"root": {}, "treatment": ["X"]},
            proof_steps=(step,),
            data_provenance=(dp,),
            diagnostic_scores={"overlap": 0.95},
            method_config={"method": "AIPW"},
            identification_status="IDENTIFIED",
            algorithm_version="id_v1",
            created_at="2026-03-15T10:00:00Z",
        )
        assert len(bundle.proof_steps) == 1
        assert bundle.identification_status == "IDENTIFIED"

    def test_to_summary_format(self):
        bundle = self._minimal()
        summary = bundle.to_summary()
        assert "run-001" in summary
        assert "P(Y|do(X))" in summary

    def test_to_summary_with_diagnostics(self):
        bundle = EvidenceBundle(
            run_id="r1",
            query_str="Q",
            diagnostic_scores={"overlap": 0.8, "positivity": 0.9},
        )
        summary = bundle.to_summary()
        assert "overlap" in summary

    def test_legacy_payload_defaults_twin_result_ref_to_none(self):
        legacy_payload = {"run_id": "legacy", "query_str": "P(Y|do(X))"}

        restored = EvidenceBundle.model_validate(legacy_payload)

        assert restored.twin_network_result_ref is None
        assert "twin_network_result_ref" not in legacy_payload

    def test_round_trip_json(self):
        step = ProofStep(rule_name="RULE2", description="d")
        bundle = EvidenceBundle(
            run_id="r3",
            query_str="P(Y|do(X))",
            proof_steps=(step,),
            identification_status="IDENTIFIED",
        )
        data = bundle.model_dump(mode="json")
        restored = EvidenceBundle.model_validate(data)
        assert restored.run_id == "r3"
        assert len(restored.proof_steps) == 1
        assert restored.proof_steps[0].rule_name == "RULE2"

    def test_estimand_ast_stored_as_dict(self):
        bundle = EvidenceBundle(
            run_id="r4",
            query_str="Q",
            estimand_ast={"schema_version": "1.0", "root": {}},
        )
        assert isinstance(bundle.estimand_ast, dict)

    def test_frozen_rejects_mutation(self):
        bundle = self._minimal()
        with pytest.raises((TypeError, Exception)):
            bundle.run_id = "mutated"

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            EvidenceBundle(run_id="r", query_str="q", secret_field="oops")

    def test_default_no_twin_writer_uses_v1_0_and_explicit_v1_1_remains_available(self, tmp_path):
        store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
        bundle = EvidenceBundle(run_id="current", query_str="P(Y|do(X))")

        legacy_ref = persist_causal_evidence_bundle(store, bundle)
        legacy_manifest = store.get_manifest(legacy_ref)
        legacy_payload = get_json_artifact(store, legacy_ref)

        assert legacy_manifest.artifact_schema.name == "ir.causal_evidence_bundle"
        assert legacy_manifest.artifact_schema.version == "1.0"
        assert set(legacy_payload) == _LEGACY_EVIDENCE_BUNDLE_V1_FIELDS
        legacy_admitted = load_causal_evidence_bundle_with_admission(store, legacy_ref)
        assert legacy_admitted.value == bundle
        assert legacy_admitted.admission.source_registration.schema_version == "1.0"
        assert legacy_admitted.raw_bytes == store.get_bytes(legacy_ref)
        assert legacy_admitted.manifest_profile_sha256 == legacy_ref.manifest_profile_sha256
        assert _read_with_legacy_v1_reader(store, legacy_ref).run_id == bundle.run_id
        assert load_causal_evidence_bundle(store, legacy_ref) == bundle

        # The optional current wire law remains available by exact explicit request.
        current_ref = persist_causal_evidence_bundle(store, bundle, schema_version="1.1")
        current_manifest = store.get_manifest(current_ref)
        current_payload = get_json_artifact(store, current_ref)
        assert current_manifest.artifact_schema.version == "1.1"
        assert set(current_payload) == _LEGACY_EVIDENCE_BUNDLE_V1_FIELDS | {
            "twin_network_result_ref"
        }
        assert current_payload["twin_network_result_ref"] is None
        assert load_causal_evidence_bundle(store, current_ref) == bundle
        with pytest.raises(ValueError, match="Unsupported schema version '1.1'"):
            _read_with_legacy_v1_reader(store, current_ref)
        decision = negotiate_schema_version("ir.causal_evidence_bundle", "1.0", "1.1")
        assert decision.can_read

    def test_retained_v1_0_representation_is_readable_and_unmodified(self, tmp_path):
        store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
        bundle = EvidenceBundle(run_id="legacy", query_str="P(Y|do(X))")
        legacy_payload = bundle.model_dump(mode="json", exclude={"twin_network_result_ref"})
        raw_ref = put_json_artifact(
            store,
            legacy_payload,
            kind="fabric.evidence_bundle",
            schema_name="ir.causal_evidence_bundle",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
        )
        ref = EvidenceBundleRef.model_validate(raw_ref)
        original_manifest = store.get_manifest(ref).model_dump(mode="json", by_alias=True)

        assert load_causal_evidence_bundle(store, ref) == bundle
        assert _read_with_legacy_v1_reader(store, ref).run_id == bundle.run_id
        assert store.get_manifest(ref).model_dump(mode="json", by_alias=True) == original_manifest
        assert store.get_manifest(ref).artifact_schema.version == "1.0"

    @pytest.mark.parametrize("schema_version", ["9.9"])
    def test_unregistered_writer_version_refuses_before_cas(
        self, tmp_path, monkeypatch, schema_version
    ):
        store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
        bundle = EvidenceBundle(run_id="override", query_str="P(Y|do(X))")

        def forbidden_write(*args, **kwargs):
            pytest.fail("non-writable EvidenceBundle row reached CAS emission")

        monkeypatch.setattr(FileSystemCAS, "put_json", forbidden_write)
        with pytest.raises(ValueError):
            persist_causal_evidence_bundle(store, bundle, schema_version=schema_version)

    def test_v1_0_old_writer_recipe_after_v1_1_publication_is_readable_without_restamp(
        self, tmp_path
    ):
        """Exercise the old-writer recipe after current publication in one CAS."""
        store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
        bundle = EvidenceBundle(run_id="rollback", query_str="P(Y|do(X))")

        current_ref = persist_causal_evidence_bundle(store, bundle, schema_version="1.1")
        assert store.get_manifest(current_ref).artifact_schema.version == "1.1"
        with pytest.raises(ValueError, match="Unsupported schema version '1.1'"):
            _read_with_legacy_v1_reader(store, current_ref)

        # Exact pre-upgrade writer recipe: strict v1.0 payload and manifest tuple.
        old_writer_payload = bundle.model_dump(mode="json", exclude={"twin_network_result_ref"})
        raw_ref = put_json_artifact(
            store,
            old_writer_payload,
            kind="fabric.evidence_bundle",
            schema_name="ir.causal_evidence_bundle",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
        )
        legacy_ref = EvidenceBundleRef.model_validate(raw_ref)
        original_manifest = store.get_manifest(legacy_ref).model_dump(mode="json", by_alias=True)

        old_read = _read_with_legacy_v1_reader(store, legacy_ref)
        assert old_read.run_id == bundle.run_id
        assert old_read.query_str == bundle.query_str
        admitted = load_causal_evidence_bundle_with_admission(store, legacy_ref)
        assert admitted.value == bundle
        assert admitted.admission.source_registration.schema_version == "1.0"
        assert admitted.admission.current_registration.schema_version == "1.1"
        assert (
            store.get_manifest(legacy_ref).model_dump(mode="json", by_alias=True)
            == original_manifest
        )

    def test_twin_reference_uses_v1_1_and_legacy_reader_refuses_it(self, tmp_path):
        store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
        twin_ref = TwinNetworkResultRef(artifact_id="sha256:" + "a" * 64)
        bundle = EvidenceBundle(
            run_id="with-twin",
            query_str="P(Y|do(X))",
            twin_network_result_ref=twin_ref,
        )

        ref = persist_causal_evidence_bundle(store, bundle)
        manifest = store.get_manifest(ref)
        payload = get_json_artifact(store, ref)

        assert manifest.artifact_schema.version == "1.1"
        assert set(payload) == _LEGACY_EVIDENCE_BUNDLE_V1_FIELDS | {"twin_network_result_ref"}
        assert payload["twin_network_result_ref"] == twin_ref.model_dump(mode="json")
        assert load_causal_evidence_bundle(store, ref) == bundle
        with pytest.raises(ValidationError, match="extra_forbidden"):
            _legacy_evidence_bundle_v1_parser().model_validate(payload)
        with pytest.raises(ValueError, match="Unsupported schema version '1.1'"):
            _read_with_legacy_v1_reader(store, ref)
        decision = negotiate_schema_version("ir.causal_evidence_bundle", "1.1", "1.0")
        assert not decision.can_read

    def test_v1_0_payload_with_new_twin_field_is_not_laundered(self, tmp_path):
        store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
        payload = EvidenceBundle(run_id="malformed", query_str="P(Y|do(X))").model_dump(mode="json")
        payload["twin_network_result_ref"] = None
        raw_ref = put_json_artifact(
            store,
            payload,
            kind="fabric.evidence_bundle",
            schema_name="ir.causal_evidence_bundle",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        )
        ref = EvidenceBundleRef.model_validate(raw_ref)

        # The DTO alone accepts null; the registered v1.0 source law forbids key presence.
        assert EvidenceBundle.model_validate(payload).twin_network_result_ref is None
        with pytest.raises(ValueError):
            load_causal_evidence_bundle(store, ref)

        snapshot = get_ir_owner_registry_snapshot()
        source = next(
            row
            for row in snapshot.representation_records
            if row.registry_key == "ir.causal_evidence_bundle" and row.schema_version == "1.0"
        )
        current = next(
            row
            for row in snapshot.representation_records
            if row.registry_key == "ir.causal_evidence_bundle" and row.current
        )
        admission = ResolvedSchemaAdmission(
            source_registration=source,
            current_registration=current,
            snapshot_revision=snapshot.revision,
            compatibility_kind=IRCompatibilityKind.DIRECT,
            profile_ref=source.profile_ref,
        )
        # The semantic no-Twin law rejects supplied key presence even when its value is null.
        with pytest.raises(ValueError, match="no-Twin wire law"):
            _validate_evidence_bundle_source(payload, admission)

    def test_registered_nondefault_schema_reuses_current_wire_law(self, tmp_path, monkeypatch):
        """A real registration and owner writer/reader route reuses the current law."""
        from polisyos.ir.migrations import base as migrations_base

        # Isolate this real API registration so later tests see the baseline registry.
        monkeypatch.setattr(
            migrations_base,
            "_SCHEMA_REGISTRY",
            {
                artifact: dict(versions)
                for artifact, versions in migrations_base._SCHEMA_REGISTRY.items()
            },
        )
        store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
        bundle = EvidenceBundle(run_id="nondefault", query_str="P(Y|do(X))")
        register_schema_version(
            "ir.causal_evidence_bundle",
            "1.2",
            compatibility=CompatibilityMode.BACKWARD,
            readable_versions=("1.0", "1.1"),
            additive_optional_fields=("twin_network_result_ref",),
            notes=("Exercise a registered nondefault family representation.",),
        )
        register_schema_version(
            "ir.causal_evidence_bundle",
            "1.2",
            compatibility=CompatibilityMode.BACKWARD,
            readable_versions=("1.0", "1.1"),
            additive_optional_fields=("twin_network_result_ref",),
            notes=("Exercise a registered nondefault family representation.",),
        )
        registered = register_ir_representation(
            registry_key="ir.causal_evidence_bundle",
            owner_ref="ir.analytics.causal_evidence_bundle",
            dto_abi="polisyos.ir.analytics.evidence_bundle.EvidenceBundle",
            wire_policy_ref="evidence-bundle-optional-twin-field",
            wire_policy_revision="1",
            schema_name="ir.causal_evidence_bundle",
            schema_version="1.2",
            payload_version=None,
            profile_ref=None,
            readable=True,
            writable=True,
            current=False,
            default_write=False,
        )
        assert (
            register_ir_representation(
                registry_key="ir.causal_evidence_bundle",
                owner_ref="ir.analytics.causal_evidence_bundle",
                dto_abi="polisyos.ir.analytics.evidence_bundle.EvidenceBundle",
                wire_policy_ref="evidence-bundle-optional-twin-field",
                wire_policy_revision="1",
                schema_name="ir.causal_evidence_bundle",
                schema_version="1.2",
                payload_version=None,
                profile_ref=None,
                readable=True,
                writable=True,
                current=False,
                default_write=False,
            )
            == registered
        )

        ref = persist_causal_evidence_bundle(store, bundle, schema_version="1.2")
        admitted = load_causal_evidence_bundle_with_admission(store, ref)

        assert admitted.value == bundle
        assert admitted.admission.source_registration == registered
        assert admitted.admission.source_registration.schema_version == "1.2"
        assert admitted.admission.current_registration.schema_version == "1.1"
        assert (
            admitted.admission.source_registration.wire_policy_ref,
            admitted.admission.source_registration.wire_policy_revision,
        ) == (
            admitted.admission.current_registration.wire_policy_ref,
            admitted.admission.current_registration.wire_policy_revision,
        )

    def test_owner_refuses_altered_canonical_profile_before_payload_read(
        self, tmp_path, monkeypatch
    ):
        store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
        bundle = EvidenceBundle(run_id="profile-mismatch", query_str="P(Y|do(X))")
        raw_ref = put_json_artifact(
            store,
            bundle.model_dump(mode="json"),
            kind="fabric.evidence_bundle",
            schema_name="ir.causal_evidence_bundle",
            schema_version="1.1",
            canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        )
        ref = EvidenceBundleRef.model_validate(raw_ref)

        def payload_read_forbidden(*args, **kwargs):
            pytest.fail("profile mismatch must be rejected before payload bytes are read")

        monkeypatch.setattr(FileSystemCAS, "get_bytes", payload_read_forbidden)
        with pytest.raises(ValueError):
            load_causal_evidence_bundle(store, ref)

    def test_generic_inspection_remains_opaque_for_unregistered_version(self, tmp_path):
        store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
        payload = EvidenceBundle(run_id="opaque", query_str="P(Y|do(X))").model_dump(mode="json")
        raw_ref = put_json_artifact(
            store,
            payload,
            kind="fabric.evidence_bundle",
            schema_name="ir.causal_evidence_bundle",
            schema_version="9.9",
            canon_spec=CanonSpec(forbid_floats=False),
        )
        ref = EvidenceBundleRef.model_validate(raw_ref)

        assert get_json_artifact(store, ref) == payload
        with pytest.raises(ValueError):
            load_causal_evidence_bundle(store, ref)

    @pytest.mark.parametrize(
        "schema_name", ["custom.causal_evidence_bundle", "", "ir.method_evidence"]
    )
    def test_noncanonical_schema_is_refused_before_write(self, tmp_path, monkeypatch, schema_name):
        store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
        bundle = EvidenceBundle(run_id="schema-mismatch", query_str="P(Y|do(X))")

        def forbidden_write(*args, **kwargs):
            pytest.fail("noncanonical EvidenceBundle reached artifact emission")

        monkeypatch.setattr(
            "polisyos.ir.analytics.evidence_bundle._put_owned_json_artifact", forbidden_write
        )
        with pytest.raises(ValueError, match="Unsupported causal EvidenceBundle schema name"):
            persist_causal_evidence_bundle(store, bundle, schema_name=schema_name)

    def test_persist_causal_evidence_bundle_round_trip(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        bundle = EvidenceBundle(
            run_id="r5",
            query_str="P(Y|do(X))",
            proof_steps=(ProofStep(rule_name="RULE1", description="backdoor"),),
            identification_status="identified",
        )

        ref = persist_causal_evidence_bundle(_ensure_ir_artifact_store(store), bundle)
        restored = load_causal_evidence_bundle(_ensure_ir_artifact_store(store), ref)

        assert restored == bundle
