from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    ArtifactTenantContextInfo,
    CanonInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.runtime.http.services.control.artifacts import (
    AUTHORITY_ENVELOPE_ARTIFACT_KIND,
    verify_runtime_authority_artifact_identity,
    write_authority_artifact,
    write_runtime_authority_artifact,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.attestation import deserialize_attestation_record
from polisyos.runtime.quality.authority import (
    EvidenceAuthorityEnvelope,
    GovernanceMetadata,
    authority_envelope_ownership_issues,
)
from polisyos.runtime.quality.authority_reconciliation import (
    AuthorityReconciliationError,
    reconcile_authority_event,
    reconcile_authority_ref,
    resolve_authority_diagnostic_event_ref,
)
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog


def _runtime_context(source_ref: str) -> dict[str, object]:
    return {
        "evidence_id": "evidence-policy-grounding",
        "evidence_class": "authority_bearing",
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "owner": "team-runtime",
        "reader_contract": "runtime_quality.policy_grounding.reader",
        "reader_contract_version": "1.0",
        "tenant_id": "tenant-1",
        "cell_id": "cell-a",
        "run_id": "run-wave-2",
        "job_id": "job-wave-2",
        "trace_id": "trace-wave-2",
        "span_id": "span-policy-grounding",
        "parent_span_id": "span-parent",
        "requested_execution_profile": "production",
        "effective_execution_profile": "production",
        "phase": "policy_grounding",
        "generated_at": "2026-05-15T09:30:00+00:00",
        "as_of_time": "2026-05-15T09:30:00+00:00",
        "same_input_closure": {
            "closure_id": "closure-wave-2",
            "status": "closed",
            "run_id": "run-wave-2",
            "job_id": "job-wave-2",
            "tenant_id": "tenant-1",
            "cell_id": "cell-a",
            "evidence_input_refs": [source_ref],
            "closure_sha256": "1" * 64,
        },
        "input_refs": [source_ref],
        "effective_mode_ref": "sha256:" + "2" * 64,
        "degradation_ledger_ref": "sha256:" + "3" * 64,
        "validation_status": "pass",
        "blocking_status": "non_blocking",
        "governance": GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime",
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="runtime_owner_required",
        ),
    }


def _opts(source_ref: str) -> PutOptions:
    return PutOptions(
        kind="scientist.policy_grounding_matrix",
        media_type="application/json",
        schema=SchemaInfo(name="polisyos.scientist.PolicyGroundingMatrix", version="1.0"),
        producer=ProducerInfo(
            component="polisyos.runtime.quality.policy_grounding_matrix",
            version="2026.05.15+hds-wave2",
        ),
        governance=ArtifactGovernanceInfo(classification="internal"),
        inputs=[
            InputRef.model_validate({"artifact_id": source_ref, "role": "policy_grounding_input"})
        ],
    )


def _stores(tmp_path) -> tuple[FileSystemCAS, RuntimeDiagnosticEventLog]:
    artifact_store = FileSystemCAS(tmp_path / "cas").for_tenant(
        "tenant-1",
        cell_id="cell-a",
    )
    control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control.sqlite3",
    )
    event_log = RuntimeDiagnosticEventLog(
        store=control_store,
        artifact_store=artifact_store,
    )
    return artifact_store, event_log


def test_runtime_authority_writer_appends_durable_event_and_reconciles(tmp_path) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )

    result = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        {"status": "pass", "claims": [{"claim_id": "claim-1"}]},
        _opts(str(source_ref.artifact_id)),
        **_runtime_context(str(source_ref.artifact_id)),
    )

    records = event_log.list_events(run_id="run-wave-2", job_id="job-wave-2")
    assert len(records) == 1
    assert records[0].event.payload_ref == str(result.cas_ref.artifact_id)
    assert str(result.cas_ref.artifact_id).startswith("sha256:")

    report = reconcile_authority_ref(
        artifact_store=artifact_store,
        event_log=event_log,
        cas_ref=str(result.cas_ref.artifact_id),
        expected_tenant_id="tenant-1",
        expected_cell_id="cell-a",
        expected_run_id="run-wave-2",
        expected_job_id="job-wave-2",
    )

    assert report.status == "pass"
    assert report.cas_ref == str(result.cas_ref.artifact_id)
    assert report.durable_event_id == records[0].event.event_id


def test_runtime_authority_writer_preserves_selected_envelope_profile_and_lineage(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_payload = {"source": "profiled-runtime-input"}
    artifact_store.put_json(
        source_payload,
        PutOptions(
            kind="runtime.input",
            media_type="application/json",
            schema=SchemaInfo(name="runtime.input", version="legacy-default"),
        ),
    )
    source_ref = artifact_store.put_json(
        source_payload,
        PutOptions(
            kind="runtime.input",
            media_type="application/json",
            schema=SchemaInfo(name="runtime.input", version="selected-profile"),
        ),
    )
    assert source_ref.manifest_profile_sha256 is not None
    source_input = InputRef(
        artifact_id=source_ref.artifact_id,
        role="policy_grounding_input",
        manifest_profile_sha256=source_ref.manifest_profile_sha256,
    )
    opts = replace(
        _opts(str(source_ref.artifact_id)),
        inputs=[source_input],
    )
    payload = {"status": "pass", "claims": [{"claim_id": "claim-profiled-envelope"}]}
    context = _runtime_context(str(source_ref.artifact_id))
    original_put_json = artifact_store.put_json
    envelope_puts: list[object] = []
    sibling_refs: list[object] = []
    payload_default_refs: list[object] = []

    def _put_with_sibling_view(obj, write_options, canon_spec=None):
        if write_options.kind == opts.kind and not payload_default_refs:
            payload_default_refs.append(
                original_put_json(
                    obj,
                    replace(
                        write_options,
                        schema=SchemaInfo(
                            name=write_options.schema.name,
                            version=f"{write_options.schema.version}.default-sibling",
                        ),
                        authority=None,
                    ),
                    canon_spec,
                )
            )
        if write_options.kind == AUTHORITY_ENVELOPE_ARTIFACT_KIND and not sibling_refs:
            sibling_options = replace(
                write_options,
                schema=SchemaInfo(
                    name=write_options.schema.name,
                    version=f"{write_options.schema.version}.sibling",
                ),
            )
            sibling_refs.append(original_put_json(obj, sibling_options, canon_spec))
        ref = original_put_json(obj, write_options, canon_spec)
        if write_options.kind == AUTHORITY_ENVELOPE_ARTIFACT_KIND:
            envelope_puts.append(ref)
        return ref

    monkeypatch.setattr(artifact_store, "put_json", _put_with_sibling_view)

    first = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        payload,
        opts,
        **context,
    )

    assert first.authority_envelope_ref.manifest_profile_sha256 is not None
    assert first.cas_ref.manifest_profile_sha256 is not None
    assert first.diagnostic_event_ref.manifest_profile_sha256 is not None
    assert len(payload_default_refs) == 1
    assert payload_default_refs[0].artifact_id == first.cas_ref.artifact_id
    assert payload_default_refs[0].manifest_profile_sha256 is None
    assert artifact_store.get_manifest(payload_default_refs[0]).authority is None
    assert artifact_store.verify(first.cas_ref).ok
    selected_readback = verify_runtime_authority_artifact_identity(
        artifact_store,
        artifact_id=first.cas_ref,
        opts=opts,
        expected_context=first.identity_context,
    )
    assert selected_readback.cas_ref == first.cas_ref
    with pytest.raises(ValueError, match="post-write identity readback missing"):
        verify_runtime_authority_artifact_identity(
            artifact_store,
            artifact_id=payload_default_refs[0],
            opts=opts,
            expected_context=first.identity_context,
        )
    assert len(envelope_puts) == len(sibling_refs) == 1
    assert first.authority_envelope_ref == envelope_puts[0]
    assert sibling_refs[0].artifact_id == first.authority_envelope_ref.artifact_id
    assert sibling_refs[0].manifest_profile_sha256 is None
    envelope_manifest = artifact_store.get_manifest(first.authority_envelope_ref)
    assert envelope_manifest.inputs == [source_input]
    payload_manifest = artifact_store.get_manifest(first.cas_ref)
    assert payload_manifest.inputs == [source_input]
    assert payload_manifest.authority is not None
    assert (
        payload_manifest.authority.authority_envelope_manifest_profile_sha256
        == first.authority_envelope_ref.manifest_profile_sha256
    )
    assert (
        payload_manifest.authority.diagnostic_event_manifest_profile_sha256
        == first.diagnostic_event_ref.manifest_profile_sha256
    )
    authority_envelope = from_canonical_bytes(
        artifact_store.get_bytes(first.authority_envelope_ref)
    )
    assert (
        authority_envelope["runtime_event_manifest_profile_sha256"]
        == first.diagnostic_event_ref.manifest_profile_sha256
    )
    event_manifest = artifact_store.get_manifest(first.diagnostic_event_ref)
    assert event_manifest.inputs == [source_input]
    assert artifact_store.verify(first.diagnostic_event_ref).ok

    assert artifact_store.verify(first.authority_envelope_ref).ok

    reused = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        payload,
        opts,
        **context,
    )

    assert reused.authority_envelope_ref == first.authority_envelope_ref
    assert reused.cas_ref == first.cas_ref


def test_runtime_authority_reader_rejects_same_schema_foreign_tenant_envelope_view(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_store = FileSystemCAS(tmp_path / "cas")
    control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control.sqlite3",
    )
    event_log = RuntimeDiagnosticEventLog(
        store=control_store,
        artifact_store=artifact_store,
    )
    source_ref = artifact_store.put_json(
        {"source": "foreign-manifest-profile-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    opts = _opts(str(source_ref.artifact_id))
    context = _runtime_context(str(source_ref.artifact_id))
    original_put_json = artifact_store.put_json
    foreign_refs = []

    def _put_with_foreign_tenant_view(obj, write_options, canon_spec=None):
        if write_options.kind == AUTHORITY_ENVELOPE_ARTIFACT_KIND and not foreign_refs:
            foreign_options = replace(
                write_options,
                tenant_context=ArtifactTenantContextInfo(
                    tenant_id="tenant-foreign",
                    cell_id="cell-foreign",
                ),
            )
            foreign_refs.append(original_put_json(obj, foreign_options, canon_spec))
        return original_put_json(obj, write_options, canon_spec)

    monkeypatch.setattr(artifact_store, "put_json", _put_with_foreign_tenant_view)
    result = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        {"status": "pass", "claims": [{"claim_id": "claim-foreign-view-control"}]},
        opts,
        **context,
    )

    assert len(foreign_refs) == 1
    foreign_default_ref = foreign_refs[0]
    assert foreign_default_ref.artifact_id == result.authority_envelope_ref.artifact_id
    foreign_default_manifest = artifact_store.get_manifest(foreign_default_ref)
    foreign_profile = artifact_manifest_profile_sha256(foreign_default_manifest)
    foreign_manifest = artifact_store.get_manifest_by_profile(
        foreign_default_ref.artifact_id,
        foreign_profile,
    )
    assert foreign_manifest == foreign_default_manifest
    foreign_ref = ArtifactRef(
        artifact_id=foreign_default_ref.artifact_id,
        kind=foreign_manifest.kind,
        media_type=foreign_manifest.media_type,
        manifest_profile_sha256=foreign_profile,
    )
    assert artifact_store.get_bytes(foreign_ref) == artifact_store.get_bytes(
        result.authority_envelope_ref
    )
    selected_manifest = artifact_store.get_manifest(result.authority_envelope_ref)
    assert foreign_profile != artifact_manifest_profile_sha256(selected_manifest)
    assert selected_manifest.kind == foreign_manifest.kind == AUTHORITY_ENVELOPE_ARTIFACT_KIND
    assert selected_manifest.media_type == foreign_manifest.media_type == "application/json"
    assert selected_manifest.artifact_schema is not None
    assert foreign_manifest.artifact_schema == selected_manifest.artifact_schema
    assert foreign_manifest.tenant_context == ArtifactTenantContextInfo(
        tenant_id="tenant-foreign",
        cell_id="cell-foreign",
    )
    assert selected_manifest.tenant_context == ArtifactTenantContextInfo(
        tenant_id="tenant-1",
        cell_id="cell-a",
    )

    original_get_manifest = artifact_store.get_manifest
    payload_manifest = original_get_manifest(result.cas_ref)
    assert payload_manifest.authority is not None
    linked_authority = payload_manifest.authority.model_copy(
        update={"authority_envelope_manifest_profile_sha256": foreign_profile}
    )
    linked_payload_manifest = payload_manifest.model_copy(update={"authority": linked_authority})

    class _LinkedForeignManifestStore:
        def __getattr__(self, name):
            return getattr(artifact_store, name)

        def get_manifest(self, selector):
            selector_id = str(getattr(selector, "artifact_id", selector))
            if selector_id == str(result.cas_ref.artifact_id):
                return linked_payload_manifest
            return original_get_manifest(selector)

    with pytest.raises(ValueError, match="existing authority identity mismatch"):
        verify_runtime_authority_artifact_identity(
            _LinkedForeignManifestStore(),
            artifact_id=result.cas_ref.artifact_id,
            opts=opts,
            expected_context=result.identity_context,
        )


def test_runtime_authority_writer_binds_effective_canon_to_fresh_reader(tmp_path) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "effective-canon-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    opts = _opts(str(source_ref.artifact_id))
    context = _runtime_context(str(source_ref.artifact_id))
    selected_spec = CanonSpec(forbid_floats=False)
    selected_canon = CanonInfo.from_spec(selected_spec)

    with pytest.raises(TypeError, match="authority canon_spec must be a CanonSpec"):
        write_runtime_authority_artifact(
            artifact_store,
            event_log,
            {"status": "malformed-canon-spec"},
            opts,
            **context,
            canon_spec={"forbid_floats": False},
        )

    with pytest.raises(ValueError, match="forbid_floats"):
        write_runtime_authority_artifact(
            artifact_store,
            event_log,
            {"status": "malformed-canon-metadata"},
            replace(opts, canon={"forbid_floats": "not-a-boolean"}),
            **context,
            canon_spec=selected_spec,
        )

    profile_spec = CanonSpec(forbid_floats=False, max_depth=256)
    profile_canon = CanonInfo.from_spec(profile_spec)
    before_mismatch = set(artifact_store.iter_artifact_ids())
    with pytest.raises(ValueError, match="canonicalization spec"):
        write_runtime_authority_artifact(
            artifact_store,
            event_log,
            {"status": "mismatched-canon"},
            replace(opts, canon=profile_canon.model_dump(mode="python")),
            **context,
            canon_spec=selected_spec,
        )
    assert set(artifact_store.iter_artifact_ids()) == before_mismatch
    assert event_log.list_events(run_id="run-wave-2", job_id="job-wave-2") == []

    selected_opts = replace(opts, canon=selected_canon.model_dump(mode="python"))
    payload = {"status": "pass", "claims": [{"claim_id": "custom-canon"}]}
    result = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        payload,
        selected_opts,
        **context,
        canon_spec=selected_spec,
    )
    assert result.identity_context.manifest_canon == selected_canon
    assert artifact_store.get_manifest(result.cas_ref).canon == selected_canon
    assert artifact_store.get_manifest(result.authority_envelope_ref).canon == selected_canon
    assert artifact_store.get_manifest(result.diagnostic_event_ref).canon == selected_canon
    reread = verify_runtime_authority_artifact_identity(
        artifact_store,
        artifact_id=result.cas_ref,
        opts=selected_opts,
        expected_context=result.identity_context,
    )
    assert reread.cas_ref == result.cas_ref

    mismatched_reader_opts = replace(opts, canon=profile_canon)
    with pytest.raises(ValueError, match="canonicalization identity mismatch"):
        verify_runtime_authority_artifact_identity(
            artifact_store,
            artifact_id=result.cas_ref,
            opts=mismatched_reader_opts,
            expected_context=result.identity_context,
        )

    alternate_profile_opts = replace(opts, canon=profile_canon.model_dump(mode="python"))
    alternate_profile_result = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        payload,
        alternate_profile_opts,
        **context,
        canon_spec=profile_spec,
    )
    assert alternate_profile_result.cas_ref.artifact_id == result.cas_ref.artifact_id
    assert alternate_profile_result.cas_ref.manifest_profile_sha256 != (
        result.cas_ref.manifest_profile_sha256
    )
    assert alternate_profile_result.identity_context.manifest_canon == profile_canon
    assert artifact_store.get_manifest(alternate_profile_result.cas_ref).canon == profile_canon
    assert artifact_store.get_manifest(
        alternate_profile_result.authority_envelope_ref
    ).canon == profile_canon
    assert artifact_store.get_manifest(
        alternate_profile_result.diagnostic_event_ref
    ).canon == profile_canon
    assert verify_runtime_authority_artifact_identity(
        artifact_store,
        artifact_id=alternate_profile_result.cas_ref,
        opts=alternate_profile_opts,
        expected_context=alternate_profile_result.identity_context,
    ).cas_ref == alternate_profile_result.cas_ref

    persisted_envelope = from_canonical_bytes(
        artifact_store.get_bytes(result.authority_envelope_ref)
    )
    legacy_envelope_payload = dict(persisted_envelope)
    legacy_envelope_payload.pop("runtime_event_manifest_profile_sha256", None)
    legacy_envelope = EvidenceAuthorityEnvelope.model_validate(legacy_envelope_payload)
    assert "runtime_event_manifest_profile_sha256" not in legacy_envelope.model_dump(
        mode="json"
    )
    assert to_canonical_bytes(legacy_envelope.model_dump(mode="json")) == to_canonical_bytes(
        legacy_envelope_payload
    )


def test_runtime_authority_reader_rejects_default_canon_envelope_view(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "forged-canon-profile-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    opts = _opts(str(source_ref.artifact_id))
    context = _runtime_context(str(source_ref.artifact_id))
    selected_spec = CanonSpec(forbid_floats=False)
    original_put_json = artifact_store.put_json
    default_refs: list[ArtifactRef] = []

    def _put_with_default_canon_view(obj, write_options, canon_spec=None):
        if write_options.kind == AUTHORITY_ENVELOPE_ARTIFACT_KIND and not default_refs:
            default_spec = CanonSpec()
            default_options = replace(
                write_options,
                canon=CanonInfo.from_spec(default_spec),
            )
            default_refs.append(original_put_json(obj, default_options, default_spec))
        return original_put_json(obj, write_options, canon_spec)

    monkeypatch.setattr(artifact_store, "put_json", _put_with_default_canon_view)
    result = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        {"status": "pass", "claims": [{"claim_id": "canon-profile-control"}]},
        opts,
        **context,
        canon_spec=selected_spec,
    )
    assert len(default_refs) == 1

    default_manifest = artifact_store.get_manifest(default_refs[0])
    default_profile = artifact_manifest_profile_sha256(default_manifest)
    forged_manifest = artifact_store.get_manifest_by_profile(
        default_refs[0].artifact_id,
        default_profile,
    )
    forged_ref = ArtifactRef(
        artifact_id=default_refs[0].artifact_id,
        kind=forged_manifest.kind,
        media_type=forged_manifest.media_type,
        manifest_profile_sha256=default_profile,
    )
    selected_manifest = artifact_store.get_manifest(result.authority_envelope_ref)
    assert artifact_store.verify(forged_ref).ok
    assert artifact_store.get_bytes(forged_ref) == artifact_store.get_bytes(
        result.authority_envelope_ref
    )
    assert forged_manifest.canon == CanonInfo.from_spec(CanonSpec())
    assert selected_manifest.canon == CanonInfo.from_spec(selected_spec)
    assert forged_manifest.kind == selected_manifest.kind == AUTHORITY_ENVELOPE_ARTIFACT_KIND
    assert forged_manifest.media_type == selected_manifest.media_type == "application/json"
    assert forged_manifest.artifact_schema == selected_manifest.artifact_schema
    assert forged_manifest.tenant_context == selected_manifest.tenant_context
    assert default_profile != artifact_manifest_profile_sha256(selected_manifest)

    original_get_manifest = artifact_store.get_manifest
    payload_manifest = original_get_manifest(result.cas_ref)
    assert payload_manifest.authority is not None
    forged_authority = payload_manifest.authority.model_copy(
        update={"authority_envelope_manifest_profile_sha256": default_profile}
    )
    linked_payload_manifest = payload_manifest.model_copy(update={"authority": forged_authority})

    class _LinkedDefaultCanonManifestStore:
        def __getattr__(self, name):
            return getattr(artifact_store, name)

        def get_manifest(self, selector):
            selector_id = str(getattr(selector, "artifact_id", selector))
            if selector_id == str(result.cas_ref.artifact_id):
                return linked_payload_manifest
            return original_get_manifest(selector)

    with pytest.raises(ValueError, match="existing authority identity mismatch"):
        verify_runtime_authority_artifact_identity(
            _LinkedDefaultCanonManifestStore(),
            artifact_id=result.cas_ref.artifact_id,
            opts=opts,
            expected_context=result.identity_context,
        )


def test_runtime_authority_writer_links_cas_writer_attestation(tmp_path) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )

    result = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        {"status": "pass", "claims": [{"claim_id": "claim-1"}]},
        _opts(str(source_ref.artifact_id)),
        **_runtime_context(str(source_ref.artifact_id)),
    )

    envelope = from_canonical_bytes(
        artifact_store.get_bytes(result.authority_envelope_ref.artifact_id)
    )
    attestation_ref = envelope["attestation_ref"]
    attestation = deserialize_attestation_record(
        from_canonical_bytes(artifact_store.get_bytes(attestation_ref))
    )

    assert attestation.trust_boundary_id == "cas_writer"
    assert attestation.producer_identity.owner == "team-runtime"
    assert attestation.environment_identity.tenant_id == "tenant-1"
    assert attestation.consumer_verification == "verified"
    assert attestation.tamper_check_status == "pass"


def test_runtime_authority_writer_rejects_existing_cas_without_durable_event(
    tmp_path,
) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    payload = {"status": "pass", "claims": [{"claim_id": "claim-1"}]}
    context = _runtime_context(str(source_ref.artifact_id))
    write_authority_artifact(
        artifact_store,
        payload,
        _opts(str(source_ref.artifact_id)),
        **context,
    )

    with pytest.raises(AuthorityReconciliationError) as error:
        write_runtime_authority_artifact(
            artifact_store,
            event_log,
            payload,
            _opts(str(source_ref.artifact_id)),
            **context,
        )

    assert error.value.code == "authority_orphan_cas"
    assert event_log.list_events(run_id="run-wave-2", job_id="job-wave-2") == []


def test_runtime_authority_writer_reuses_existing_cas_only_after_reconciliation(
    tmp_path,
) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    payload = {"status": "pass", "claims": [{"claim_id": "claim-1"}]}
    context = _runtime_context(str(source_ref.artifact_id))
    first = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        payload,
        _opts(str(source_ref.artifact_id)),
        **context,
    )

    second = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        payload,
        _opts(str(source_ref.artifact_id)),
        **context,
    )

    assert second == first
    records = event_log.list_events(run_id="run-wave-2", job_id="job-wave-2")
    assert len(records) == 1

    other_source = artifact_store.put_json(
        {"source": "other-runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    other_source_ref = str(other_source.artifact_id)
    base_context = _runtime_context(str(source_ref.artifact_id))
    mutations: tuple[tuple[PutOptions, dict[str, object]], ...] = (
        (_opts(other_source_ref), {**base_context, "input_refs": [other_source_ref]}),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "tenant_id": "tenant-other"},
        ),
        (_opts(str(source_ref.artifact_id)), {**base_context, "cell_id": "cell-b"}),
        (_opts(str(source_ref.artifact_id)), {**base_context, "run_id": "run-other"}),
        (_opts(str(source_ref.artifact_id)), {**base_context, "job_id": "job-other"}),
        (_opts(str(source_ref.artifact_id)), {**base_context, "trace_id": "trace-other"}),
        (_opts(str(source_ref.artifact_id)), {**base_context, "span_id": "span-other"}),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "parent_span_id": "parent-other"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "requested_execution_profile": "diagnostic"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "effective_execution_profile": "diagnostic"},
        ),
        (_opts(str(source_ref.artifact_id)), {**base_context, "phase": "other-phase"}),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "generated_at": "2026-05-15T09:31:00+00:00"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "as_of_time": "2026-05-15T09:31:00+00:00"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {
                **base_context,
                "same_input_closure": {
                    **base_context["same_input_closure"],  # type: ignore[dict-item]
                    "closure_id": "closure-other",
                },
            },
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "effective_mode_ref": "sha256:" + "4" * 64},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "validation_status": "blocked"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "blocking_status": "blocking"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {
                **base_context,
                "governance": base_context["governance"].model_copy(  # type: ignore[union-attr]
                    update={"review_status": "runtime_rejected"}
                ),
            },
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "degradation_ledger_ref": "sha256:" + "5" * 64},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "schema_compatibility_ref": "sha256:" + "6" * 64},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "semantic_binding_ref": "sha256:" + "7" * 64},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "redaction_policy_ref": "sha256:" + "8" * 64},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "event_id": "evt-other"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "event_source": "runtime.other"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "event_type": "runtime.other.event.v1"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "event_subject": "runtime/other"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "state_before": "queued"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "state_after": "rejected"},
        ),
    )
    for mutated_opts, mutated_context in mutations:
        with pytest.raises(ValueError, match="existing authority identity mismatch"):
            write_runtime_authority_artifact(
                artifact_store,
                event_log,
                payload,
                mutated_opts,
                **mutated_context,
            )


def test_runtime_authority_writer_binds_the_exact_generated_attestation(
    tmp_path,
) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    arbitrary_ref = artifact_store.put_json(
        {"not": "a-cas-writer-attestation"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    payload = {"status": "pass", "claims": [{"claim_id": "claim-1"}]}
    context = _runtime_context(str(source_ref.artifact_id))

    with pytest.raises(ValueError, match="attestation identity mismatch"):
        write_runtime_authority_artifact(
            artifact_store,
            event_log,
            payload,
            _opts(str(source_ref.artifact_id)),
            **{
                **context,
                "attestation_ref": str(arbitrary_ref.artifact_id),
            },
        )

    produced = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        payload,
        _opts(str(source_ref.artifact_id)),
        **context,
    )
    reused = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        payload,
        _opts(str(source_ref.artifact_id)),
        **context,
    )
    envelope = from_canonical_bytes(
        artifact_store.get_bytes(produced.authority_envelope_ref.artifact_id)
    )
    attestation_id = ArtifactID.model_validate(envelope["attestation_ref"])
    attestation_manifest = artifact_store.get_manifest(attestation_id)
    assert reused == produced
    assert attestation_manifest.kind == "runtime_quality.trust_boundary_attestation"


def test_runtime_authority_writer_propagates_backend_programmer_faults(
    tmp_path,
) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )

    class FaultingStore:
        def has(self, artifact_id: ArtifactID) -> bool:
            del artifact_id
            raise RuntimeError("backend programmer fault")

        def __getattr__(self, name: str) -> object:
            return getattr(artifact_store, name)

    with pytest.raises(RuntimeError, match="backend programmer fault"):
        write_runtime_authority_artifact(
            FaultingStore(),
            event_log,
            {"status": "pass", "claims": [{"claim_id": "claim-1"}]},
            _opts(str(source_ref.artifact_id)),
            **_runtime_context(str(source_ref.artifact_id)),
        )


def test_runtime_authority_writer_rejects_relabelled_same_bytes(tmp_path) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    payload = {"status": "pass", "claims": [{"claim_id": "claim-1"}]}
    context = _runtime_context(str(source_ref.artifact_id))
    wrong_opts = replace(
        _opts(str(source_ref.artifact_id)),
        kind="runtime.wrong-kind",
        schema=SchemaInfo(name="runtime.WrongSchema", version="1.0"),
    )
    write_runtime_authority_artifact(
        artifact_store,
        event_log,
        payload,
        wrong_opts,
        **context,
    )

    with pytest.raises(ValueError, match="existing authority identity mismatch"):
        write_runtime_authority_artifact(
            artifact_store,
            event_log,
            payload,
            _opts(str(source_ref.artifact_id)),
            **context,
        )


def test_exact_event_identity_reconciliation_is_page_position_independent(tmp_path) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    result = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        {"status": "pass", "claims": [{"claim_id": "claim-exact-event"}]},
        _opts(str(source_ref.artifact_id)),
        **_runtime_context(str(source_ref.artifact_id)),
    )
    target = event_log.list_events(run_id="run-wave-2", job_id="job-wave-2")[0]

    class PageCappedEventLog:
        def __init__(self, exact_records: list[object] | None = None) -> None:
            self._exact_records = [target] if exact_records is None else exact_records
            self.queries: list[tuple[str | None, int]] = []

        def list_events(
            self,
            *,
            event_id: str | None = None,
            run_id: str | None = None,
            job_id: str | None = None,
            limit: int = 500,
        ) -> list[object]:
            del run_id, job_id
            self.queries.append((event_id, limit))
            if event_id == target.event.event_id:
                return self._exact_records
            return []

    report = reconcile_authority_ref(
        artifact_store=artifact_store,
        event_log=PageCappedEventLog(),
        cas_ref=str(result.cas_ref.artifact_id),
        expected_run_id="run-wave-2",
        expected_job_id="job-wave-2",
    )

    assert report.status == "pass"
    assert report.durable_event_id == target.event.event_id

    exact_log = PageCappedEventLog()
    event_report = reconcile_authority_event(
        artifact_store=artifact_store,
        event_log=exact_log,
        event_id=target.event.event_id,
    )
    assert event_report.status == "pass"
    assert exact_log.queries == [
        (target.event.event_id, 2),
        (target.event.event_id, 2),
    ]

    with pytest.raises(AuthorityReconciliationError) as event_collision:
        reconcile_authority_event(
            artifact_store=artifact_store,
            event_log=PageCappedEventLog([target, target]),
            event_id=target.event.event_id,
        )
    assert event_collision.value.code == "authority_event_collision"

    duplicate_log = PageCappedEventLog([target, target])
    with pytest.raises(AuthorityReconciliationError) as duplicate_error:
        reconcile_authority_ref(
            artifact_store=artifact_store,
            event_log=duplicate_log,
            cas_ref=str(result.cas_ref.artifact_id),
        )
    assert duplicate_error.value.code == "authority_event_collision"

    changed = replace(
        target,
        event=target.event.model_copy(update={"trace_id": "trace-substituted"}),
    )
    changed_log = PageCappedEventLog([changed])
    with pytest.raises(AuthorityReconciliationError) as changed_error:
        reconcile_authority_ref(
            artifact_store=artifact_store,
            event_log=changed_log,
            cas_ref=str(result.cas_ref.artifact_id),
        )
    assert changed_error.value.code == "authority_payload_mismatch"

    wrong_row = replace(target, payload_ref="sha256:" + "f" * 64)
    wrong_row_log = PageCappedEventLog([wrong_row])
    with pytest.raises(AuthorityReconciliationError) as row_error:
        reconcile_authority_ref(
            artifact_store=artifact_store,
            event_log=wrong_row_log,
            cas_ref=str(result.cas_ref.artifact_id),
        )
    assert row_error.value.code == "authority_payload_mismatch"

    changed_artifact_ref = "sha256:" + "e" * 64
    changed_artifacts = replace(
        target,
        event=target.event.model_copy(update={"artifact_refs": (changed_artifact_ref,)}),
    )
    linked_event_bytes = to_canonical_bytes(changed_artifacts.event.model_dump(mode="json"))
    authority_manifest = artifact_store.get_manifest(result.cas_ref.artifact_id)
    linked_id = ArtifactID.model_validate(authority_manifest.authority.diagnostic_event_ref)

    class ChangedArtifactRefsStore:
        def has(self, artifact_id):
            return artifact_store.has(artifact_id)

        def verify(self, artifact_id):
            return artifact_store.verify(artifact_id)

        def get_bytes(self, artifact_id):
            if artifact_id == linked_id:
                return linked_event_bytes
            return artifact_store.get_bytes(artifact_id)

        def get_manifest(self, artifact_id):
            return artifact_store.get_manifest(artifact_id)

    with pytest.raises(AuthorityReconciliationError) as artifact_refs_error:
        reconcile_authority_ref(
            artifact_store=ChangedArtifactRefsStore(),
            event_log=PageCappedEventLog([changed_artifacts]),
            cas_ref=str(result.cas_ref.artifact_id),
        )
    assert artifact_refs_error.value.code == "authority_payload_mismatch"

    with pytest.raises(AuthorityReconciliationError) as missing_error:
        reconcile_authority_ref(
            artifact_store=artifact_store,
            event_log=PageCappedEventLog([]),
            cas_ref=str(result.cas_ref.artifact_id),
        )
    assert missing_error.value.code == "authority_orphan_cas"

    class WrongKindStore:
        def has(self, artifact_id):
            return artifact_store.has(artifact_id)

        def verify(self, artifact_id):
            return artifact_store.verify(artifact_id)

        def get_bytes(self, artifact_id):
            return artifact_store.get_bytes(artifact_id)

        def get_manifest(self, artifact_id):
            manifest = artifact_store.get_manifest(artifact_id)
            if artifact_id == linked_id:
                return manifest.model_copy(update={"kind": "runtime.wrong-kind"})
            return manifest

    with pytest.raises(AuthorityReconciliationError) as kind_error:
        reconcile_authority_ref(
            artifact_store=WrongKindStore(),
            event_log=PageCappedEventLog(),
            cas_ref=str(result.cas_ref.artifact_id),
        )
    assert kind_error.value.code == "authority_payload_mismatch"


def test_authority_ref_normalization_catches_only_expected_parse_failures(
    tmp_path,
    monkeypatch,
) -> None:
    artifact_store, event_log = _stores(tmp_path)
    for invalid_ref in ("sha256:not-a-digest", "cas://sha256/not-a-digest"):
        with pytest.raises(AuthorityReconciliationError) as invalid_error:
            reconcile_authority_ref(
                artifact_store=artifact_store,
                event_log=event_log,
                cas_ref=invalid_ref,
            )
        assert invalid_error.value.code == "authority_ref_not_cas"

    def programmer_fault(cls, value):
        del cls, value
        raise RuntimeError("artifact id programmer fault")

    monkeypatch.setattr(ArtifactID, "model_validate", classmethod(programmer_fault))
    for parseable_form in ("sha256:" + "1" * 64, "cas://sha256/" + "1" * 64):
        with pytest.raises(RuntimeError, match="artifact id programmer fault"):
            reconcile_authority_ref(
                artifact_store=artifact_store,
                event_log=event_log,
                cas_ref=parseable_form,
            )


def test_cas_artifact_without_durable_event_fails_serious_reconciliation(tmp_path) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    result = write_authority_artifact(
        artifact_store,
        {"status": "pass"},
        _opts(str(source_ref.artifact_id)),
        **_runtime_context(str(source_ref.artifact_id)),
    )

    with pytest.raises(AuthorityReconciliationError) as error:
        reconcile_authority_ref(
            artifact_store=artifact_store,
            event_log=event_log,
            cas_ref=str(result.cas_ref.artifact_id),
        )

    assert error.value.code == "authority_orphan_cas"


def test_durable_event_without_cas_artifact_fails_serious_reconciliation(tmp_path) -> None:
    artifact_store, event_log = _stores(tmp_path)
    missing_ref = "sha256:" + "9" * 64
    event_log.append(
        DiagnosticEvent(
            event_id="evt-missing-cas",
            event_source="polisyos.runtime.http.nl_pipeline",
            event_type="polisyos.runtime.diagnostic.cas_write.v1",
            event_time=datetime(2026, 5, 15, 9, 30, tzinfo=UTC),
            event_subject="run/run-wave-2/job/job-wave-2/phase/policy_grounding",
            schema_name="polisyos.runtime.quality.diagnostic_event",
            schema_version="1.0",
            trace_id="trace-wave-2",
            span_id="span-policy-grounding",
            parent_span_id="span-parent",
            run_id="run-wave-2",
            job_id="job-wave-2",
            tenant_id="tenant-1",
            cell_id="cell-a",
            producer_component="polisyos.runtime.quality.policy_grounding_matrix",
            producer_version="2026.05.15+hds-wave2",
            execution_profile="production",
            phase="policy_grounding",
            state_before=None,
            state_after="persisted",
            payload_ref=missing_ref,
            artifact_refs=(missing_ref,),
            input_refs=(),
            blocking_status="non_blocking",
            redaction_policy_ref=None,
            duplicate_of=None,
            dedupe_key="job-wave-2:policy_grounding:evidence-policy-grounding:cas_write",
            sampling_decision="always_record",
            sampling_rate=1.0,
        )
    )

    with pytest.raises(AuthorityReconciliationError) as error:
        reconcile_authority_event(
            artifact_store=artifact_store,
            event_log=event_log,
            event_id="evt-missing-cas",
        )

    assert error.value.code == "authority_cas_missing"



def test_runtime_authority_reader_rejects_foreign_tenant_event_profile(tmp_path, monkeypatch):
    artifact_store = FileSystemCAS(tmp_path / "cas")
    control_store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    event_log = RuntimeDiagnosticEventLog(store=control_store, artifact_store=artifact_store)
    source_ref = artifact_store.put_json(
        {"source": "foreign-event-profile-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    opts = _opts(str(source_ref.artifact_id))
    original_put_json = artifact_store.put_json
    foreign_refs = []

    def _put_with_foreign_event_view(obj, write_options, canon_spec=None):
        if (
            write_options.kind == "runtime_quality.diagnostic_event"
            and not foreign_refs
        ):
            foreign_options = replace(
                write_options,
                tenant_context=ArtifactTenantContextInfo(
                    tenant_id="tenant-foreign",
                    cell_id="cell-foreign",
                ),
            )
            foreign_refs.append(original_put_json(obj, foreign_options, canon_spec))
        return original_put_json(obj, write_options, canon_spec)

    monkeypatch.setattr(artifact_store, "put_json", _put_with_foreign_event_view)
    result = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        {"status": "pass", "claims": [{"claim_id": "foreign-event-view"}]},
        opts,
        **_runtime_context(str(source_ref.artifact_id)),
    )
    assert len(foreign_refs) == 1
    foreign = foreign_refs[0]
    selected = result.diagnostic_event_ref
    assert foreign.artifact_id == selected.artifact_id
    assert artifact_store.get_bytes(foreign) == artifact_store.get_bytes(selected)
    foreign_manifest = artifact_store.get_manifest(foreign)
    selected_manifest = artifact_store.get_manifest(selected)
    assert foreign_manifest.kind == selected_manifest.kind
    assert foreign_manifest.artifact_schema == selected_manifest.artifact_schema
    assert foreign_manifest.tenant_context != selected_manifest.tenant_context
    assert foreign.manifest_profile_sha256 != selected.manifest_profile_sha256

    payload_manifest = artifact_store.get_manifest(result.cas_ref)
    assert payload_manifest.authority is not None
    foreign_authority = payload_manifest.authority.model_copy(
        update={"diagnostic_event_manifest_profile_sha256": foreign.manifest_profile_sha256}
    )
    foreign_payload_manifest = payload_manifest.model_copy(update={"authority": foreign_authority})

    class _ForeignEventProfileStore:
        def __getattr__(self, name):
            return getattr(artifact_store, name)

        def get_manifest(self, selector):
            selector_id = str(getattr(selector, "artifact_id", selector))
            if selector_id == str(result.cas_ref.artifact_id):
                return foreign_payload_manifest
            return artifact_store.get_manifest(selector)

    with pytest.raises(AuthorityReconciliationError, match="authority_payload_mismatch"):
        reconcile_authority_ref(
            artifact_store=_ForeignEventProfileStore(),
            event_log=event_log,
            cas_ref=str(result.cas_ref.artifact_id),
        )


def test_authority_envelope_rejects_explicit_null_runtime_event_profile() -> None:
    from polisyos.core.security.quality_gates import (
        SECURITY_ASSURANCE_ARTIFACT_KIND,
        SECURITY_ASSURANCE_ARTIFACT_SCHEMA_NAME,
    )

    envelope = {
        "artifact_kind": SECURITY_ASSURANCE_ARTIFACT_KIND,
        "schema_name": SECURITY_ASSURANCE_ARTIFACT_SCHEMA_NAME,
        "phase": "security_assurance_report",
        "validation_status": "pass",
        "runtime_event_manifest_profile_sha256": "sha256:" + "a" * 64,
    }
    report_base = {
        "schema_version": "policyos.security_assurance_report.v1",
        "status": "pass",
    }
    for report in (
        {**report_base, "runtime_event_manifest_profile_sha256": None},
        {
            **report_base,
            "diagnostic_event": {"runtime_event_manifest_profile_sha256": None},
        },
    ):
        issues = authority_envelope_ownership_issues(
            envelope=envelope,
            report_key="security_assurance_report",
            report=report,
        )
        assert {issue["code"] for issue in issues} >= {
            "authority_report_runtime_event_profile_invalid",
            "authority_envelope_runtime_event_profile_mismatch",
        }

    # A genuinely absent legacy field remains a bounded compatibility case.
    assert authority_envelope_ownership_issues(
        envelope=envelope,
        report_key="security_assurance_report",
        report=report_base,
    ) == []


def test_runtime_authority_reader_rejects_same_byte_wrong_media_event_profile(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "wrong-media-event-profile-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    opts = _opts(str(source_ref.artifact_id))
    original_put_json = artifact_store.put_json
    wrong_media_refs: list[ArtifactRef] = []

    def _put_with_wrong_media_event_view(obj, write_options, canon_spec=None):
        if write_options.kind == "runtime_quality.diagnostic_event" and not wrong_media_refs:
            wrong_media_refs.append(
                original_put_json(
                    obj,
                    replace(write_options, media_type="text/plain"),
                    canon_spec,
                )
            )
        return original_put_json(obj, write_options, canon_spec)

    monkeypatch.setattr(artifact_store, "put_json", _put_with_wrong_media_event_view)
    result = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        {"status": "pass", "claims": [{"claim_id": "wrong-media-event-view"}]},
        opts,
        **_runtime_context(str(source_ref.artifact_id)),
    )
    assert len(wrong_media_refs) == 1
    wrong_media = wrong_media_refs[0]
    selected = result.diagnostic_event_ref
    assert wrong_media.artifact_id == selected.artifact_id
    assert wrong_media.manifest_profile_sha256 != selected.manifest_profile_sha256
    assert artifact_store.get_bytes(wrong_media) == artifact_store.get_bytes(selected)
    wrong_manifest = artifact_store.get_manifest(wrong_media)
    selected_manifest = artifact_store.get_manifest(selected)
    assert wrong_manifest.kind == selected_manifest.kind
    assert wrong_manifest.artifact_schema == selected_manifest.artifact_schema
    assert wrong_manifest.media_type == "text/plain"
    assert selected_manifest.media_type == "application/json"
    assert wrong_manifest.inputs == selected_manifest.inputs
    assert wrong_manifest.producer == selected_manifest.producer
    assert wrong_manifest.tenant_context == selected_manifest.tenant_context
    assert wrong_manifest.same_input_closure == selected_manifest.same_input_closure
    assert wrong_manifest.canon == selected_manifest.canon
    assert wrong_manifest.governance == selected_manifest.governance
    assert wrong_manifest.authority == selected_manifest.authority

    payload_manifest = artifact_store.get_manifest(result.cas_ref)
    assert payload_manifest.authority is not None
    wrong_authority = payload_manifest.authority.model_copy(
        update={"diagnostic_event_manifest_profile_sha256": wrong_media.manifest_profile_sha256}
    )
    wrong_payload_manifest = payload_manifest.model_copy(update={"authority": wrong_authority})

    class _WrongMediaEventProfileStore:
        def __getattr__(self, name):
            return getattr(artifact_store, name)

        def get_manifest(self, selector):
            selector_id = str(getattr(selector, "artifact_id", selector))
            if selector_id == str(result.cas_ref.artifact_id):
                return wrong_payload_manifest
            return artifact_store.get_manifest(selector)

    with pytest.raises(AuthorityReconciliationError, match="authority_payload_mismatch"):
        reconcile_authority_ref(
            artifact_store=_WrongMediaEventProfileStore(),
            event_log=event_log,
            cas_ref=str(result.cas_ref.artifact_id),
        )


def test_profileless_authority_event_ref_preserves_actual_v2_manifest_view(tmp_path):
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "historical-v2-event-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    result = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        {"status": "pass", "claims": [{"claim_id": "legacy-v2-event"}]},
        _opts(str(source_ref.artifact_id)),
        **_runtime_context(str(source_ref.artifact_id)),
    )
    event_id = result.diagnostic_event_ref.artifact_id
    current_manifest = artifact_store.get_manifest(result.diagnostic_event_ref)
    legacy_manifest = current_manifest.model_copy(update={"manifest_schema_version": "v2"})
    artifact_store._manifests.write(
        artifact_store._manifest_path_for_ref(event_id, None),
        ManifestLifecycle.to_bytes(legacy_manifest),
    )
    authority = artifact_store.get_manifest(result.cas_ref).authority
    assert authority is not None
    profileless_authority = authority.model_copy(
        update={"diagnostic_event_manifest_profile_sha256": None}
    )
    resolved = resolve_authority_diagnostic_event_ref(artifact_store, profileless_authority)
    assert resolved.manifest_profile_sha256 is None
    assert artifact_store.get_manifest(resolved).manifest_schema_version == "v2"
    event_bytes = artifact_store.get_bytes(result.diagnostic_event_ref)
    assert artifact_store.get_bytes(resolved) == event_bytes
    persisted_event = DiagnosticEvent.model_validate(from_canonical_bytes(event_bytes))
    records = event_log.list_events(event_id=persisted_event.event_id, limit=2)
    assert len(records) == 1
    assert records[0].event == persisted_event

    payload_manifest = artifact_store.get_manifest(result.cas_ref)
    assert payload_manifest.authority is not None
    profileless_payload_manifest = payload_manifest.model_copy(
        update={"authority": profileless_authority}
    )
    artifact_store._manifests.write(
        artifact_store._manifest_path_for_ref(result.cas_ref.artifact_id, None),
        ManifestLifecycle.to_bytes(profileless_payload_manifest),
    )

    report = reconcile_authority_ref(
        artifact_store=artifact_store,
        event_log=event_log,
        cas_ref=str(result.cas_ref.artifact_id),
    )
    assert report.status == "pass"
    assert report.durable_event_id == persisted_event.event_id
    assert artifact_store.get_bytes(resolved) == event_bytes
