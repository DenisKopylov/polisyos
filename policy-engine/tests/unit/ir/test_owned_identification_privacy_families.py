from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    FileSystemCAS,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.data_forge.read_api.academic import (
    RetainedSKGSnapshotChunk,
    RetainedSKGSnapshotV11,
    RetainedSKGSourceBinding,
    retained_skg_source_binding,
)
from polisyos.ir.analytics import parameters as parameter_api
from polisyos.ir.analytics import privacy_transportability as privacy_api
from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation,
    register_owner_representations,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.parameters import (
    ContextAdaptiveParameterBundle,
    ContextAdaptiveParameterBundleV11,
    ContextAdaptiveParameterBundleV12,
    load_context_adaptive_parameter_bundle,
    persist_context_adaptive_parameter_bundle,
    persist_context_adaptive_parameter_bundle_v1_1,
    persist_context_adaptive_parameter_bundle_v1_2,
)
from polisyos.ir.analytics.partial_identification import (
    BoundsBundle,
    BoundsTighteningLog,
    TighteningStatus,
    load_bounds_bundle,
    load_bounds_tightening_log,
    persist_bounds_bundle,
    persist_bounds_tightening_log,
)
from polisyos.ir.analytics.privacy_transportability import (
    DPMechanismScope,
    PrivacyAwareTransportCertificate,
    PrivacyObservedMode,
    load_privacy_aware_transport_certificate,
    persist_privacy_aware_transport_certificate,
)
from polisyos.ir.analytics.proof_composability import (
    ProofComposabilityCertificate,
    ProofComposabilityStatus,
    ProofWitnessIndex,
    load_proof_composability_certificate,
    load_proof_witness_index,
    persist_proof_composability_certificate,
    persist_proof_witness_index,
)
from polisyos.ir.analytics.transportability import TransportabilityStatus
from polisyos.ir.artifacts import ArtifactID, ArtifactStore, InputRef, put_json_artifact
from polisyos.ir.artifacts.io import _put_owned_json_artifact
from polisyos.ir.migrations import base as migrations_base
from polisyos.ir.migrations.base import CompatibilityMode, get_ir_owner_registry_snapshot
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation
from polisyos.ir.registry.refs import BoundsBundleRef

_OWNER_TUPLES = {
    (
        "ir.analytics.ir_context_adaptive_parameter_bundle.owner.v1",
        "ir.context_adaptive_parameter_bundle",
        "ir.context_adaptive_parameter_bundle",
        "1.0",
        "1.0",
    ),
    (
        "ir.analytics.ir_context_adaptive_parameter_bundle.owner.v1",
        "ir.context_adaptive_parameter_bundle",
        "ir.context_adaptive_parameter_bundle",
        "1.1",
        "1.1",
    ),
    (
        "ir.analytics.ir_context_adaptive_parameter_bundle.owner.v1",
        "ir.context_adaptive_parameter_bundle",
        "ir.context_adaptive_parameter_bundle",
        "1.2",
        "1.2",
    ),
    (
        "ir.analytics.ir.bounds_bundle.owner.v1",
        "ir.bounds_bundle",
        "ir.bounds_bundle",
        "1.0",
        "1.0",
    ),
    (
        "ir.analytics.ir.bounds_tightening_log.owner.v1",
        "ir.bounds_tightening_log",
        "ir.bounds_tightening_log",
        "1.0",
        "1.0",
    ),
    (
        "ir.analytics.ir.privacy_aware_transport_certificate.owner.v1",
        "ir.privacy_aware_transport_certificate",
        "ir.privacy_aware_transport_certificate",
        "1.0",
        "1.0",
    ),
    (
        "ir.analytics.ir.proof_witness_index.owner.v1",
        "ir.proof_witness_index",
        "ir.proof_witness_index",
        "1.0",
        "1.0",
    ),
    (
        "ir.analytics.ir.proof_composability_certificate.owner.v1",
        "ir.proof_composability_certificate",
        "ir.proof_composability_certificate",
        "1.0",
        "1.0",
    ),
}


def _persisted_parameter_source_binding(
    cas: FileSystemCAS, store: ArtifactStore
) -> RetainedSKGSourceBinding:
    chunk_bytes = b"selected source descriptor bytes"
    chunk_ref = cas.put_bytes(
        chunk_bytes,
        ArtifactWriteOptions(
            kind="scientist.skg_source_chunk",
            media_type="application/octet-stream",
            schema=SchemaInfo(name="scientist.skg_source_chunk", version="1.0"),
            producer=ProducerInfo(component="tests.ir.parameters", version="1.0"),
        ),
        return_selected_profile=True,
    )
    snapshot = RetainedSKGSnapshotV11(
        schema_version="1.1",
        source_reference="duckdb://captured/unseen-resource#v1",
        source_sha256=hashlib.sha256(chunk_bytes).hexdigest(),
        byte_size=len(chunk_bytes),
        source_binding_schema_version="academic.skg_source_binding.v2",
        query_version="skg-query-read.v3",
        source_version_id=1,
        version_identity_kind="content_digest",
        chunks=(RetainedSKGSnapshotChunk(ref=chunk_ref, byte_size=len(chunk_bytes)),),
    )
    payload = put_json_artifact(
        store,
        snapshot.model_dump(mode="json"),
        kind="scientist.skg_source_snapshot",
        schema_name="scientist.skg_source_snapshot",
        schema_version="1.1",
        inputs=[input_ref_from_artifact_ref(chunk_ref, role="source_chunk:0")],
        return_selected_profile=True,
    )
    descriptor = ArtifactRef.model_validate(payload)
    return retained_skg_source_binding(store, descriptor)


def _store(tmp_path: Path) -> ArtifactStore:
    return ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))


class _CountingStore:
    def __init__(self, store: ArtifactStore) -> None:
        self._store = store
        self.put_calls = 0
        self.payload_reads = 0

    def __getattr__(self, name: str) -> object:
        return getattr(self._store, name)

    def get_bytes(self, selector: object) -> bytes:
        self.payload_reads += 1
        return self._store.get_bytes(selector)

    def put_json(
        self,
        obj: object,
        opts: object,
        canon_spec: object = None,
        *,
        return_selected_profile: bool = False,
    ) -> object:
        self.put_calls += 1
        return self._store.put_json(
            obj,
            opts=opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )


def test_the_four_families_register_exact_manifest_payload_tuples() -> None:
    snapshot = get_ir_owner_registry_snapshot()
    family_owners = {item[0] for item in _OWNER_TUPLES}
    owner_rows = [row for row in snapshot.representation_records if row.owner_ref in family_owners]
    rows = {
        (row.owner_ref, row.registry_key, row.schema_name, row.schema_version, row.payload_version)
        for row in owner_rows
    }
    assert rows == _OWNER_TUPLES
    assert all(
        snapshot.schema_rules[(row.registry_key, row.schema_version)].mode is CompatibilityMode.NONE
        for row in owner_rows
    )


def test_nondefault_parameter_representation_roundtrips_through_fresh_cas_reader(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    bundle = ContextAdaptiveParameterBundleV11(
        target_context=ContextProfile(context_id="unseen-resource:municipal-climate"),
        simulation_domain="policy-resource:municipal-climate",
        selected_cross_graph_profile_ref=None,
    )
    graph_input = InputRef(
        artifact_id=ArtifactID.from_sha256_hex("a" * 64),
        role="causal_graph",
    )

    ref = persist_context_adaptive_parameter_bundle_v1_1(
        store,
        bundle,
        inputs=[graph_input],
    )
    fresh_store = _store(tmp_path)
    loaded = load_context_adaptive_parameter_bundle(fresh_store, ref)

    assert ref.manifest_profile_sha256 is not None
    assert type(loaded) is ContextAdaptiveParameterBundleV11
    assert loaded == bundle
    assert fresh_store.get_manifest(ref).artifact_schema.version == "1.1"


@pytest.fixture
def isolated_parameter_registry() -> Iterator[None]:
    """Restore only the parameter schema rows changed by the nondefault-writer test."""
    registry_key = parameter_api._SCHEMA_NAME
    with migrations_base._REGISTRY_LOCK:
        before = dict(migrations_base._SCHEMA_REGISTRY.get(registry_key, {}))
    try:
        yield
    finally:
        with migrations_base._REGISTRY_LOCK:
            if before:
                migrations_base._SCHEMA_REGISTRY[registry_key] = before
            else:
                migrations_base._SCHEMA_REGISTRY.pop(registry_key, None)


def test_late_registered_nondefault_parameter_tuple_uses_public_writer_and_fresh_reader(
    tmp_path: Path,
    isolated_parameter_registry: None,
) -> None:
    store = _store(tmp_path)
    cas = FileSystemCAS(tmp_path / "cas")
    profile_ref = parameter_api._PARAMETER_PROFILE_REFS[parameter_api._PARAMETER_POLICY_1_2]
    policy = parameter_api._PARAMETER_POLICY_1_2
    register_owner_representations(
        parameter_api._PARAMETER_OWNER,
        (
            OwnedJSONRepresentation(
                schema_name=parameter_api._SCHEMA_NAME,
                schema_version="1.3",
                payload_version="1.2",
                wire_policy_ref=policy[0],
                wire_policy_revision=policy[1],
                profile_ref=profile_ref,
                compatibility=CompatibilityMode.NONE,
                notes=parameter_api._PARAMETER_COMPATIBILITY_NOTES,
                readable=True,
                writable=True,
                current=False,
                default_write=False,
                readable_from=(),
            ),
        ),
    )
    binding = _persisted_parameter_source_binding(cas, store)
    bundle = ContextAdaptiveParameterBundleV12(
        target_context=ContextProfile(context_id="unseen-resource:regional-housing"),
        simulation_domain="policy-resource:regional-housing",
        selected_cross_graph_profile_ref=None,
        skg_snapshot_ref=binding.source_reference,
        skg_version_id=binding.source_version_id,
        selected_skg_source=binding,
    )
    inputs = [
        InputRef(
            artifact_id=ArtifactID.from_sha256_hex("a" * 64),
            role="causal_graph",
        ),
        InputRef(
            artifact_id=binding.descriptor_ref.artifact_id,
            role="skg_source_snapshot",
            manifest_profile_sha256=binding.descriptor_ref.manifest_profile_sha256,
        ),
    ]

    ref = persist_context_adaptive_parameter_bundle_v1_2(
        store,
        bundle,
        inputs=inputs,
        schema_version="1.3",
    )
    assert ref.manifest_profile_sha256 is not None
    fresh_bundle = load_context_adaptive_parameter_bundle(_store(tmp_path), ref)

    assert type(fresh_bundle) is ContextAdaptiveParameterBundleV12
    assert fresh_bundle == bundle
    assert _store(tmp_path).get_manifest(ref).artifact_schema.version == "1.3"


def test_bounds_bundle_and_tightening_log_roundtrip_through_fresh_cas_reader(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    bounds = BoundsBundle(
        estimand_type="unseen-resource:regional-energy-access",
        metadata={"resource_id": "regional-energy-access-v3"},
    )
    log = BoundsTighteningLog(
        class_name="unseen-resource:regional-energy-access",
        class_spec_hash="sha256:unseen-class-spec",
        status=TighteningStatus.NOT_RUN,
        metadata={"resource_id": "regional-energy-access-v3"},
    )

    bounds_ref = persist_bounds_bundle(store, bounds)
    log_ref = persist_bounds_tightening_log(store, log)
    assert bounds_ref.manifest_profile_sha256 is not None
    assert log_ref.manifest_profile_sha256 is not None
    fresh_store = _store(tmp_path)

    assert load_bounds_bundle(fresh_store, bounds_ref) == bounds
    assert load_bounds_tightening_log(fresh_store, log_ref) == log


def test_privacy_certificate_preserves_unseen_domain_grammar_through_cas(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    resource_domain = "jurisdiction:future-policy-resource/v2"
    certificate = PrivacyAwareTransportCertificate(
        certificate_id="candidate-new-resource",
        query="P(outcome|do(intervention))",
        selection_diagram_ref="artifact:selection:new-resource",
        latent_transport_status=TransportabilityStatus.PARTIALLY_IDENTIFIED,
        privacy_observed_mode=PrivacyObservedMode.INTERVAL,
        source_domains=("jurisdiction:source-resource/v2",),
        target_domain=resource_domain,
        dp_scope=(
            DPMechanismScope(
                domain_id=resource_domain,
                mechanism_id="central-gaussian-release-v2",
                mechanism_family="gaussian",
                privacy_model="central",
                epsilon=1.0,
                delta=1e-6,
            ),
        ),
    )

    ref = persist_privacy_aware_transport_certificate(store, certificate)
    assert ref.manifest_profile_sha256 is not None
    loaded = load_privacy_aware_transport_certificate(_store(tmp_path), ref)

    assert loaded == certificate
    assert loaded.target_domain == resource_domain


def test_proof_artifact_families_roundtrip_through_fresh_cas_readers(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    index = ProofWitnessIndex(
        metadata={"resource_id": "unseen-resource:local-housing"},
    )
    certificate = ProofComposabilityCertificate(
        status=ProofComposabilityStatus.UNKNOWN,
        source_fragment_id="unseen-resource:local-housing",
        checked_query="P(eligibility|do(policy))",
        metadata={"resource_id": "unseen-resource:local-housing"},
    )

    index_ref = persist_proof_witness_index(store, index)
    certificate_ref = persist_proof_composability_certificate(store, certificate)
    assert index_ref.manifest_profile_sha256 is not None
    assert certificate_ref.manifest_profile_sha256 is not None
    fresh_store = _store(tmp_path)

    assert load_proof_witness_index(fresh_store, index_ref) == index
    assert load_proof_composability_certificate(fresh_store, certificate_ref) == certificate


def test_malformed_constructed_dto_refuses_before_cas_write(tmp_path: Path) -> None:
    store = _CountingStore(_store(tmp_path))
    malformed = ProofComposabilityCertificate.model_construct(
        schema_version="1.0",
        status=ProofComposabilityStatus.UNKNOWN,
        source_fragment_id="",
        checked_query="P(Y|do(X))",
    )

    with pytest.raises(CanonViolation, match="ir_owned_artifact_source_invalid"):
        persist_proof_composability_certificate(store, malformed)
    assert store.put_calls == 0


@pytest.mark.parametrize("malformed_inputs", [False, 0, {}])
def test_malformed_present_lineage_refuses_before_cas_write(
    tmp_path: Path,
    malformed_inputs: object,
) -> None:
    store = _CountingStore(_store(tmp_path))

    with pytest.raises((CanonViolation, TypeError, ValueError)):
        persist_proof_witness_index(
            store,
            ProofWitnessIndex(),
            inputs=malformed_inputs,  # type: ignore[arg-type]
        )
    assert store.put_calls == 0


@pytest.mark.parametrize("malformed_version", [False, 0, ""])
def test_present_malformed_payload_version_refuses_before_cas_write(
    tmp_path: Path,
    malformed_version: object,
) -> None:
    store = _CountingStore(_store(tmp_path))
    valid = ProofComposabilityCertificate(
        status=ProofComposabilityStatus.UNKNOWN,
        source_fragment_id="source-fragment",
        checked_query="P(Y|do(X))",
    )
    malformed = valid.model_copy(update={"schema_version": malformed_version})

    with pytest.raises(CanonViolation, match="ir_owned_artifact_payload_version_invalid"):
        persist_proof_composability_certificate(store, malformed)
    assert store.put_calls == 0


def test_wrong_owner_canonical_profile_refuses_before_cas_write(tmp_path: Path) -> None:
    store = _CountingStore(_store(tmp_path))
    certificate = PrivacyAwareTransportCertificate(
        certificate_id="candidate",
        query="P(Y|do(X))",
        selection_diagram_ref="artifact:selection:profile",
        latent_transport_status=TransportabilityStatus.IDENTIFIED,
        privacy_observed_mode=PrivacyObservedMode.BLOCKED,
        target_domain="domain:profile",
        blocking_reasons=("privacy basis absent",),
    )

    with pytest.raises(CanonViolation, match="ir_owned_artifact_profile_refused"):
        _put_owned_json_artifact(
            store,
            certificate.model_dump(mode="json"),
            owner=privacy_api._PRIVACY_TRANSPORT_CERTIFICATE_OWNER,
            schema_name="ir.privacy_aware_transport_certificate",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=True),
        )
    assert store.put_calls == 0


def test_unregistered_schema_override_refuses_before_cas_write(tmp_path: Path) -> None:
    store = _CountingStore(_store(tmp_path))
    certificate = PrivacyAwareTransportCertificate(
        certificate_id="candidate",
        query="P(Y|do(X))",
        selection_diagram_ref="artifact:selection:1",
        latent_transport_status=TransportabilityStatus.IDENTIFIED,
        privacy_observed_mode=PrivacyObservedMode.BLOCKED,
        target_domain="domain:1",
        blocking_reasons=("privacy basis absent",),
    )

    with pytest.raises(CanonViolation, match="ir_owned_artifact_write_override_unregistered"):
        persist_privacy_aware_transport_certificate(
            store,
            certificate,
            schema_name="ir.unregistered_private_payload",
            schema_version="1.0",
        )
    assert store.put_calls == 0


def test_historical_parameter_writer_roundtrips_through_same_owned_loader(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    bundle = ContextAdaptiveParameterBundle(
        target_context=ContextProfile(context_id="unseen-resource:historical-v1"),
        simulation_domain="policy-resource:historical-v1",
    )

    ref = persist_context_adaptive_parameter_bundle(store, bundle)
    assert ref.manifest_profile_sha256 is not None
    loaded = load_context_adaptive_parameter_bundle(_store(tmp_path), ref)

    assert type(loaded) is ContextAdaptiveParameterBundle
    assert loaded == bundle


def test_malformed_present_selector_is_rejected_before_payload_fetch(
    tmp_path: Path,
) -> None:
    ref = persist_bounds_bundle(
        _store(tmp_path),
        BoundsBundle(estimand_type="unseen-resource:selector"),
    )
    malformed_ref = ref.model_copy(update={"manifest_profile_sha256": "sha256:bad"})
    store = _CountingStore(_store(tmp_path))

    with pytest.raises(CanonViolation, match="ir_artifact_view_selector_invalid"):
        load_bounds_bundle(store, malformed_ref)
    assert store.payload_reads == 0


def test_unregistered_bounds_version_is_rejected_before_payload_fetch(
    tmp_path: Path,
) -> None:
    backing_store = _store(tmp_path)
    payload = BoundsBundle(estimand_type="unseen-resource:unknown-version").model_dump(mode="json")
    payload["schema_version"] = "9.9"
    raw_ref = put_json_artifact(
        backing_store,
        payload,
        kind="ir.bounds_bundle",
        schema_name="ir.bounds_bundle",
        schema_version="9.9",
        canon_spec=CanonSpec(forbid_floats=False),
    )
    ref = BoundsBundleRef.model_validate(raw_ref)
    store = _CountingStore(_store(tmp_path))

    rejected: CanonViolation | None = None
    try:
        load_bounds_bundle(store, ref)
    except CanonViolation as exc:
        rejected = exc
    else:
        assert store.payload_reads == 0, "owner admission was removed after payload fetch"
        pytest.fail("an unregistered bounds representation was accepted")
    assert rejected is not None
    assert "ir_owned_artifact_representation_unregistered" in str(rejected)
    assert store.payload_reads == 0


def test_owner_writer_pins_selected_profile_when_same_payload_has_other_default_view(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    bundle = BoundsBundle(estimand_type="unseen-resource:competing-canon-profile")
    payload = bundle.model_dump(mode="json")
    alternate_ref = put_json_artifact(
        store,
        payload,
        kind="ir.bounds_bundle",
        schema_name="ir.bounds_bundle",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False, max_depth=64),
        return_selected_profile=True,
    )
    owner_ref = persist_bounds_bundle(store, bundle)
    assert str(owner_ref.artifact_id) == alternate_ref["artifact_id"]
    assert owner_ref.manifest_profile_sha256 is not None
    assert owner_ref.manifest_profile_sha256 != alternate_ref["manifest_profile_sha256"]

    selected_manifest = store.get_manifest_by_profile(
        owner_ref.artifact_id,
        owner_ref.manifest_profile_sha256,
    )
    assert selected_manifest.canon.max_depth == 128
    assert store.get_manifest(owner_ref.artifact_id).canon.max_depth == 64

    fresh_store = _CountingStore(_store(tmp_path))
    assert load_bounds_bundle(fresh_store, owner_ref) == bundle
    assert fresh_store.payload_reads == 1

    wrong_profile_ref = owner_ref.model_copy(
        update={"manifest_profile_sha256": alternate_ref["manifest_profile_sha256"]}
    )
    wrong_profile_store = _CountingStore(_store(tmp_path))
    with pytest.raises(CanonViolation, match="ir_owned_artifact_profile_refused"):
        load_bounds_bundle(wrong_profile_store, wrong_profile_ref)
    assert wrong_profile_store.payload_reads == 0
