from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pytest

from polisyos.core.artifacts import (
    ArtifactGovernanceInfo,
    ArtifactWriteOptions,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    read_core_json_artifact,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.runtime.http.services.control.artifacts import (
    _freeze_cas_writer_attestation_identity,
    _identity_context_from_fields,
    write_runtime_authority_artifact,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.authority import (
    GovernanceMetadata,
    runtime_quality_report_cas_admission_issues,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.report_registry import (
    _RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY,
    QUALITY_REPORT_RUNTIME_REFS,
    RUNTIME_QUALITY_OWNER_MARKER_SCHEMA,
    RUNTIME_QUALITY_OWNER_PRODUCER_VERSION,
    RUNTIME_QUALITY_REPORT_OWNER_CONTRACTS,
    _build_runtime_quality_report_publication_basis,
    _runtime_quality_report_publication_view,
    _runtime_quality_report_reuse_basis,
    _runtime_quality_report_reuse_closure_matches,
    _runtime_quality_report_source_payload,
    _runtime_quality_report_writer_payload,
    _RuntimeQualityReportPublicationBasis,
    runtime_quality_report_owner_contract,
    runtime_quality_report_owner_identity_issues,
    runtime_quality_report_owner_marker,
)
from polisyos.runtime.quality.scorecard import _authority_contract_gates

_OWNERLESS_REGISTERED_ROLES = {
    "hypothesis_ledger",
    "continuous_governance_stale",
    "continuous_governance_reissue",
    "continuous_governance_supersede",
    "continuous_governance_withdraw",
}


def _persist_report(
    tmp_path: Path,
    *,
    report_key: str,
    run_suffix: str,
    payload: dict[str, Any],
    artifact_kind_override: str | None = None,
    schema_name_override: str | None = None,
    schema_version_override: str | None = None,
    producer_component_override: str | None = None,
    derive_closure: bool = False,
    closure_inputs: list[InputRef] | None = None,
    closure_refs: dict[str, str] | None = None,
    authority_role: Literal["runtime_blocker", "producer_authority"] = "runtime_blocker",
) -> tuple[FileSystemCAS, Any, dict[str, Any], dict[str, Any]]:
    """Persist real CAS ownership as blocked evidence by default.

    A producer claim is used only by explicit refusal probes; this fixture never
    establishes complete same-input purpose admission or issues a verifier token.
    """
    ref_key = QUALITY_REPORT_RUNTIME_REFS[report_key]
    contract = runtime_quality_report_owner_contract(report_key, ref_key)
    assert contract is not None
    store = FileSystemCAS(tmp_path / f"cas-{run_suffix}").for_tenant(
        "tenant-1",
        cell_id="cell-a",
    )
    control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / f"control-{run_suffix}.sqlite3",
    )
    event_log = RuntimeDiagnosticEventLog(
        store=control_store,
        artifact_store=store,
    )
    source_ref = store.put_json(
        {"source": f"runtime-input-{run_suffix}"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    source_id = str(source_ref.artifact_id)
    job_id = f"job-owner-{run_suffix}"
    run_id = f"run-owner-{run_suffix}"
    write_inputs = [
        InputRef.model_validate({"artifact_id": source_id, "role": "runtime_quality_input"})
    ]
    write_inputs.extend(closure_inputs or [])
    marker = runtime_quality_report_owner_marker(report_key, ref_key)
    assert marker is not None
    persisted_payload = _runtime_quality_report_writer_payload(
        payload,
        report_key=report_key,
        ref_key=ref_key,
    )
    result = write_runtime_authority_artifact(
        store,
        event_log,
        persisted_payload,
        ArtifactWriteOptions(
            kind=artifact_kind_override or contract.artifact_kind,
            media_type=contract.media_type,
            schema=SchemaInfo(
                name=schema_name_override or contract.schema_name,
                version=schema_version_override or contract.schema_version,
            ),
            producer=ProducerInfo(
                component=producer_component_override or contract.producer_component,
                version=contract.producer_version,
            ),
            governance=ArtifactGovernanceInfo(classification="runtime_quality_evidence"),
            inputs=write_inputs,
        ),
        evidence_id=f"runtime_quality_ref#{ref_key}",
        evidence_class="authority_bearing",
        authority_role=authority_role,
        provenance_kind="runtime_emitted"
        if authority_role == "producer_authority"
        else "runtime_blocker",
        owner="team-runtime",
        reader_contract=f"runtime_quality.{report_key}.v1",
        reader_contract_version="1.0",
        tenant_id="tenant-1",
        cell_id="cell-a",
        run_id=run_id,
        job_id=job_id,
        trace_id=f"trace-owner-{run_suffix}",
        span_id=f"{report_key}:cas_write",
        parent_span_id="span-parent",
        requested_execution_profile="production",
        effective_execution_profile="production",
        phase=contract.phase,
        generated_at=datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        as_of_time=datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        same_input_closure=_test_same_input_closure(
            run_suffix=run_suffix,
            run_id=run_id,
            job_id=job_id,
            input_refs=[str(item.artifact_id) for item in write_inputs],
            derive=derive_closure,
            closure_refs=closure_refs,
        ),
        input_refs=[str(item.artifact_id) for item in write_inputs],
        effective_mode_ref="sha256:" + "2" * 64,
        degradation_ledger_ref="sha256:" + "3" * 64,
        validation_status="pass",
        blocking_status="non_blocking" if authority_role == "producer_authority" else "blocking",
        canon_spec=CanonSpec(forbid_floats=False) if derive_closure else None,
        governance=GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime",
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="runtime_owner_required",
        ),
    )
    selected_payload = read_core_json_artifact(
        store,
        result.cas_ref,
        manifest_profile_sha256=result.cas_ref.manifest_profile_sha256,
    ).value
    assert isinstance(selected_payload, dict)
    assert selected_payload == persisted_payload
    envelope = read_core_json_artifact(store, result.authority_envelope_ref).value
    assert isinstance(envelope, dict)
    basis = _build_runtime_quality_report_publication_basis(
        report_key=report_key,
        ref_key=ref_key,
        report_payload=payload,
        artifact_ref=result.cas_ref.model_dump(mode="json"),
        runtime_event_ref=str(result.diagnostic_event_ref.artifact_id),
        runtime_event_manifest_profile_sha256=(result.diagnostic_event_ref.manifest_profile_sha256),
        authority_envelope_ref=str(result.authority_envelope_ref.artifact_id),
        authority_envelope=envelope,
        manifest_ref=result.manifest_ref,
        payload_sha256=result.payload_sha256,
    )
    report = _runtime_quality_report_publication_view(basis)
    return store, result, report, dict(envelope)


def _runtime_payloads(report_key: str, result: Any) -> dict[str, Any]:
    ref_key = QUALITY_REPORT_RUNTIME_REFS[report_key]
    selected = result.cas_ref
    return {
        "runtime_quality_refs": {ref_key: str(selected.artifact_id)},
        "runtime_quality_artifact_refs": {
            ref_key: selected.model_dump(mode="json"),
        },
    }


def test_publication_view_recovers_only_its_exact_source_basis(tmp_path: Path) -> None:
    source_payload = {
        "status": "pass",
        "basis_fields": {"source": "materialized", "count": 3},
    }
    store, result, report, _envelope = _persist_report(
        tmp_path,
        report_key="fabric_retrieval_trace",
        run_suffix="source-basis",
        payload=source_payload,
    )
    recovered, basis = _runtime_quality_report_source_payload(
        report,
        report_key="fabric_retrieval_trace",
        ref_key="fabric_retrieval_trace_ref",
    )
    assert recovered == source_payload
    assert basis is not None
    writer_payload = _runtime_quality_report_writer_payload(
        recovered,
        report_key="fabric_retrieval_trace",
        ref_key="fabric_retrieval_trace_ref",
    )
    assert writer_payload == read_core_json_artifact(store, result.cas_ref).value
    assert "sha256:" + hashlib.sha256(
        to_canonical_bytes(writer_payload, CanonSpec(forbid_floats=False))
    ).hexdigest() == str(result.cas_ref.artifact_id)

    raw_source, raw_basis = _runtime_quality_report_source_payload(
        source_payload,
        report_key="fabric_retrieval_trace",
        ref_key="fabric_retrieval_trace_ref",
    )
    assert raw_source == source_payload
    assert raw_basis is None
    reused_basis = _runtime_quality_report_reuse_basis(
        source_payload,
        current_publication_view=report,
        report_key="fabric_retrieval_trace",
        ref_key="fabric_retrieval_trace_ref",
    )
    assert reused_basis == basis
    fresh_reused_basis = _runtime_quality_report_reuse_basis(
        report,
        current_publication_view=None,
        report_key="fabric_retrieval_trace",
        ref_key="fabric_retrieval_trace_ref",
    )
    assert fresh_reused_basis == basis
    with pytest.raises(ValueError, match="runtime_quality_publication_view_mismatch"):
        _runtime_quality_report_reuse_basis(
            {**report, "unbound_extra": True},
            current_publication_view=None,
            report_key="fabric_retrieval_trace",
            ref_key="fabric_retrieval_trace_ref",
        )

    changed_source = {**source_payload, "basis_fields": {"source": "changed", "count": 3}}
    assert (
        _runtime_quality_report_reuse_basis(
            changed_source,
            current_publication_view=report,
            report_key="fabric_retrieval_trace",
            ref_key="fabric_retrieval_trace_ref",
        )
        is None
    )
    for mutated_view in (
        {**report, "unbound_extra": True},
        {
            **report,
            "runtime_quality_publication_basis": {
                **report["runtime_quality_publication_basis"],
                "ref_key": "production_data_quality_report_ref",
            },
        },
    ):
        with pytest.raises(ValueError):
            _runtime_quality_report_source_payload(
                mutated_view,
                report_key="fabric_retrieval_trace",
                ref_key="fabric_retrieval_trace_ref",
            )


def _test_same_input_closure(
    *,
    run_suffix: str,
    run_id: str,
    job_id: str,
    input_refs: list[str],
    derive: bool,
    closure_refs: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build declared writer metadata; no complete input-purpose admission is claimed."""
    closure: dict[str, Any] = {
        "closure_id": f"closure-owner-{run_suffix}",
        "status": "closed",
        "run_id": run_id,
        "job_id": job_id,
        "tenant_id": "tenant-1",
        "cell_id": "cell-a",
        "evidence_input_refs": list(input_refs),
    }
    if closure_refs:
        closure.update(closure_refs)
    if not derive:
        closure["closure_sha256"] = "1" * 64
        return closure
    closure["effective_mode_ref"] = "sha256:" + "2" * 64
    closure["degradation_ledger_ref"] = "sha256:" + "3" * 64
    closure["closure_sha256"] = hashlib.sha256(
        to_canonical_bytes(closure, CanonSpec(forbid_floats=False))
    ).hexdigest()
    return closure


def test_publication_reentry_uses_fresh_cas_reader_and_rebuilt_current_identity(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts import ArtifactRef

    report_key = "fabric_retrieval_trace"
    ref_key = "fabric_retrieval_trace_ref"
    run_suffix = "fresh-reader"
    source_payload = {
        "status": "pass",
        "basis_fields": {"source": "fresh-reader", "count": 2},
    }
    _store, _result, report, _producer_envelope = _persist_report(
        tmp_path,
        report_key=report_key,
        run_suffix=run_suffix,
        payload=source_payload,
        derive_closure=True,
    )

    # This second client has no publisher-side dictionaries. It reads only persisted CAS
    # state and a complete basis-bearing view handed to the consumer.
    fresh_store = FileSystemCAS(tmp_path / f"cas-{run_suffix}").for_tenant(
        "tenant-1",
        cell_id="cell-a",
    )
    candidate = _runtime_quality_report_reuse_basis(
        report,
        current_publication_view=None,
        report_key=report_key,
        ref_key=ref_key,
    )
    assert candidate is not None
    selected_ref = ArtifactRef.model_validate(candidate.artifact_ref)
    assert fresh_store.verify(selected_ref).ok

    # Rebuild the current typed input by resolving the source operation in the fresh
    # reader. Do not reuse the first writer's AuthorityArtifactWriteResult context.
    source_ref = fresh_store.put_json(
        {"source": f"runtime-input-{run_suffix}"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    current_inputs = [
        InputRef.model_validate(
            {
                "artifact_id": str(source_ref.artifact_id),
                "role": "runtime_quality_input",
            }
        )
    ]
    contract = runtime_quality_report_owner_contract(report_key, ref_key)
    assert contract is not None
    write_options = ArtifactWriteOptions(
        kind=contract.artifact_kind,
        media_type=contract.media_type,
        schema=SchemaInfo(name=contract.schema_name, version=contract.schema_version),
        producer=ProducerInfo(
            component=contract.producer_component,
            version=contract.producer_version,
        ),
        governance=ArtifactGovernanceInfo(classification="runtime_quality_evidence"),
        inputs=current_inputs,
    )
    closure = _test_same_input_closure(
        run_suffix=run_suffix,
        run_id=f"run-owner-{run_suffix}",
        job_id=f"job-owner-{run_suffix}",
        input_refs=[str(item.artifact_id) for item in current_inputs],
        derive=True,
    )
    writer_payload = _runtime_quality_report_writer_payload(
        source_payload,
        report_key=report_key,
        ref_key=ref_key,
    )
    canon_spec = CanonSpec(forbid_floats=False)
    payload_bytes = to_canonical_bytes(writer_payload, canon_spec)
    output_artifact_id = "sha256:" + hashlib.sha256(payload_bytes).hexdigest()
    assert output_artifact_id == str(selected_ref.artifact_id)

    current_identity_fields: dict[str, Any] = {
        "evidence_id": f"runtime_quality_ref#{ref_key}",
        "evidence_class": "authority_bearing",
        "authority_role": "runtime_blocker",
        "provenance_kind": "runtime_blocker",
        "owner": "team-runtime",
        "reader_contract": f"runtime_quality.{report_key}.v1",
        "reader_contract_version": "1.0",
        "tenant_id": "tenant-1",
        "cell_id": "cell-a",
        "run_id": f"run-owner-{run_suffix}",
        "job_id": f"job-owner-{run_suffix}",
        "trace_id": f"trace-owner-{run_suffix}",
        "span_id": f"{report_key}:cas_write",
        "parent_span_id": "span-parent",
        "requested_execution_profile": "production",
        "effective_execution_profile": "production",
        "phase": contract.phase,
        "generated_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        "as_of_time": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        "same_input_closure": closure,
        "input_refs": [str(item.artifact_id) for item in current_inputs],
        "effective_mode_ref": "sha256:" + "2" * 64,
        "validation_status": "pass",
        "blocking_status": "blocking",
        "governance": GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime",
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="runtime_owner_required",
        ),
        "degradation_ledger_ref": "sha256:" + "3" * 64,
    }
    expected_identity_context = _identity_context_from_fields(
        write_options,
        current_identity_fields,
        canon_spec,
    )
    expected_identity_context, _ = _freeze_cas_writer_attestation_identity(
        expected_identity_context,
        cas_ref_value=output_artifact_id,
        manifest_ref=f"cas-manifest://{output_artifact_id}",
        payload_sha256=output_artifact_id.removeprefix("sha256:"),
        schema=write_options.schema,
        producer=write_options.producer,
    )

    admission_args = {
        "artifact_store": fresh_store,
        "selected_ref": selected_ref,
        "runtime_ref": output_artifact_id,
        "report_key": report_key,
        "ref_key": ref_key,
        "report": report,
        "envelope": candidate.authority_envelope,
        "expected_write_options": write_options,
        "expected_identity_context": expected_identity_context,
    }
    assert runtime_quality_report_cas_admission_issues(**admission_args) == []

    changed_scope = replace(expected_identity_context, cell_id="cell-other")
    assert "runtime_quality_current_identity_mismatch" in {
        str(issue["code"])
        for issue in runtime_quality_report_cas_admission_issues(
            **{**admission_args, "expected_identity_context": changed_scope}
        )
    }
    changed_input = current_inputs[0].model_copy(update={"role": "different_current_input"})
    changed_write_options = replace(write_options, inputs=[changed_input])
    assert "runtime_quality_current_identity_mismatch" in {
        str(issue["code"])
        for issue in runtime_quality_report_cas_admission_issues(
            **{**admission_args, "expected_write_options": changed_write_options}
        )
    }


def test_reentry_closure_builder_requires_current_profiled_owner_inputs(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts import artifact_ref_for_manifest
    from polisyos.runtime.http.services.control.nl_pipeline import (
        NaturalLanguagePipelineRefusalError,
        _persisted_runtime_quality_publication_times,
        _runtime_quality_closure_reference_values,
    )

    owner_specs = (
        (
            "policy_intent_ref",
            "policy_intent_envelope_ref",
            "policy_intent_envelope",
            "runtime.policy_intent_envelope",
            "polisyos.runtime.PolicyIntentEnvelope",
        ),
        (
            "production_data_manifest_ref",
            "production_data_payload_ref",
            "production_data_payload",
            "fabric.production_data_payload",
            "polisyos.fabric.ProductionDataPayload",
        ),
    )
    source_payload = {
        "status": "pass",
        "basis_fields": {"source": "profiled-reentry", "count": 1},
    }

    valid_suffix = "profiled-reentry-valid"
    valid_store = FileSystemCAS(tmp_path / f"cas-{valid_suffix}").for_tenant(
        "tenant-1",
        cell_id="cell-a",
    )
    valid_inputs: list[InputRef] = []
    valid_closure_refs: dict[str, str] = {}
    current_refs: dict[str, str] = {}
    for closure_field, ref_key, role, kind, schema_name in owner_specs:
        stored_ref = valid_store.put_json(
            {"current_owner": role},
            ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=schema_name, version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        selected_ref = artifact_ref_for_manifest(valid_store.get_manifest(stored_ref.artifact_id))
        assert selected_ref.manifest_profile_sha256 is not None
        valid_inputs.append(
            InputRef(
                artifact_id=selected_ref.artifact_id,
                role=role,
                manifest_profile_sha256=selected_ref.manifest_profile_sha256,
            )
        )
        valid_closure_refs[closure_field] = str(selected_ref.artifact_id)
        current_refs[ref_key] = str(selected_ref.artifact_id)

    valid_store, valid_result, _valid_report, _valid_envelope = _persist_report(
        tmp_path,
        report_key="fabric_retrieval_trace",
        run_suffix=valid_suffix,
        payload=source_payload,
        derive_closure=True,
        closure_inputs=valid_inputs,
        closure_refs=valid_closure_refs,
    )
    valid_manifest = valid_store.get_manifest(valid_result.cas_ref)
    valid_candidate = _persisted_runtime_quality_publication_times(
        valid_store,
        output_artifact_id=str(valid_result.cas_ref.artifact_id),
        artifact_kind="fabric.retrieval_trace",
        expected_inputs=valid_manifest.inputs,
    )
    assert valid_candidate is not None
    valid_payload = read_core_json_artifact(valid_store, valid_result.cas_ref).value
    assert valid_payload["runtime_authority_payload"] == runtime_quality_report_owner_marker(
        "fabric_retrieval_trace",
        "fabric_retrieval_trace_ref",
    )
    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        _runtime_quality_closure_reference_values(
            current_refs,
            candidate=valid_candidate,
            output_artifact_id=str(valid_result.cas_ref.artifact_id),
            ref_key="fabric_retrieval_trace_ref",
            current_inputs=valid_manifest.inputs,
            current_artifact_refs=None,
            artifact_store=valid_store,
        )

    assert _runtime_quality_closure_reference_values(
        {},
        candidate=valid_candidate,
        output_artifact_id=str(valid_result.cas_ref.artifact_id),
        ref_key="fabric_retrieval_trace_ref",
        current_inputs=valid_manifest.inputs,
        artifact_store=valid_store,
    ) == {
        "policy_intent_ref": valid_closure_refs["policy_intent_ref"],
        "production_data_manifest_ref": valid_closure_refs["production_data_manifest_ref"],
        "legal_snapshot_ref": None,
    }

    stale_suffix = "profiled-reentry-stale"
    stale_refs = {
        "policy_intent_ref": "sha256:" + "7" * 64,
        "production_data_manifest_ref": "sha256:" + "8" * 64,
    }
    stale_store, stale_result, _stale_report, _stale_envelope = _persist_report(
        tmp_path,
        report_key="fabric_retrieval_trace",
        run_suffix=stale_suffix,
        payload=source_payload,
        derive_closure=True,
        closure_refs=stale_refs,
    )
    stale_manifest = stale_store.get_manifest(stale_result.cas_ref)
    stale_candidate = _persisted_runtime_quality_publication_times(
        stale_store,
        output_artifact_id=str(stale_result.cas_ref.artifact_id),
        artifact_kind="fabric.retrieval_trace",
        expected_inputs=stale_manifest.inputs,
    )
    assert stale_candidate is not None
    stale_payload = read_core_json_artifact(stale_store, stale_result.cas_ref).value
    assert stale_payload["runtime_authority_payload"] == runtime_quality_report_owner_marker(
        "fabric_retrieval_trace",
        "fabric_retrieval_trace_ref",
    )
    assert tuple(item.role for item in stale_manifest.inputs) == ("runtime_quality_input",)
    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        _runtime_quality_closure_reference_values(
            {
                "policy_intent_envelope_ref": stale_refs["policy_intent_ref"],
                "production_data_payload_ref": stale_refs["production_data_manifest_ref"],
            },
            candidate=stale_candidate,
            output_artifact_id=str(stale_result.cas_ref.artifact_id),
            ref_key="fabric_retrieval_trace_ref",
            current_inputs=stale_manifest.inputs,
            current_artifact_refs={},
            artifact_store=stale_store,
        )


@pytest.mark.parametrize(
    ("report_key", "closure_field"),
    [
        ("production_data_quality", "production_data_manifest_ref"),
        ("normative_evidence", "legal_snapshot_ref"),
    ],
)
def test_current_owner_report_output_cannot_bind_source_closure_without_typed_input(
    tmp_path: Path,
    report_key: str,
    closure_field: str,
) -> None:
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _runtime_quality_closure_reference_values,
        _RuntimeQualityPublicationCandidate,
    )

    ref_key = QUALITY_REPORT_RUNTIME_REFS[report_key]
    contract = runtime_quality_report_owner_contract(report_key, ref_key)
    assert contract is not None
    suffix = f"current-closure-{report_key}"
    store, result, report_view, _envelope = _persist_report(
        tmp_path,
        report_key=report_key,
        run_suffix=suffix,
        payload={"status": "pass", "owner_source": report_key},
    )
    selected_ref = result.cas_ref
    selected_id = str(selected_ref.artifact_id)
    _source_payload, basis = _runtime_quality_report_source_payload(
        report_view,
        report_key=report_key,
        ref_key=ref_key,
    )
    assert basis is not None
    assert basis.artifact_ref == selected_ref.model_dump(mode="json")
    assert basis.runtime_event_ref == str(result.diagnostic_event_ref.artifact_id)
    assert basis.runtime_event_manifest_profile_sha256 == (
        result.diagnostic_event_ref.manifest_profile_sha256
    )
    assert store.verify(selected_ref).ok
    assert store.verify(result.diagnostic_event_ref).ok
    context = result.identity_context
    assert context.run_id == f"run-owner-{suffix}"
    assert context.job_id == f"job-owner-{suffix}"
    assert context.tenant_id == "tenant-1"
    assert context.cell_id == "cell-a"
    assert context.phase == contract.phase
    current_refs = {ref_key: selected_id}
    current_artifact_refs = {ref_key: selected_ref}
    candidate = _RuntimeQualityPublicationCandidate(
        context.generated_at,
        context.as_of_time,
        None,
        None,
        None,
        None,
    )
    result_refs = _runtime_quality_closure_reference_values(
        current_refs,
        candidate=candidate,
        output_artifact_id="sha256:" + "f" * 64,
        ref_key="decision_artifact_quality_report_ref",
        current_inputs=(),
        current_artifact_refs=current_artifact_refs,
        artifact_store=store,
        current_report_verifier=lambda _ref_key, _expected_ref: True,
    )
    assert result_refs[closure_field] is None

    projected_candidate = candidate._replace(**{closure_field: selected_id})
    with pytest.raises(RuntimeError, match="runtime_quality_same_input_identity_not_established"):
        _runtime_quality_closure_reference_values(
            current_refs,
            candidate=projected_candidate,
            output_artifact_id="sha256:" + "f" * 64,
            ref_key="decision_artifact_quality_report_ref",
            current_inputs=(),
            current_artifact_refs=current_artifact_refs,
            artifact_store=store,
            current_report_verifier=lambda _ref_key, _expected_ref: True,
        )


def test_unregistered_policy_intent_owner_output_binds_normative_reentry_without_typed_edge(
    tmp_path: Path,
) -> None:
    from polisyos.runtime.http.services.control.nl_pipeline import (
        NaturalLanguagePipelineRefusalError,
        _runtime_quality_closure_reference_values,
        _runtime_quality_current_publisher_output_is_verified,
        _RuntimeQualityPublicationCandidate,
    )

    run_suffix = "policy-intent-current-owner"
    run_id = f"run-owner-{run_suffix}"
    job_id = f"job-owner-{run_suffix}"
    report_key = "policy_intent_envelope"
    ref_key = "policy_intent_envelope_ref"
    store = FileSystemCAS(tmp_path / f"cas-{run_suffix}").for_tenant(
        "tenant-1",
        cell_id="cell-a",
    )
    control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / f"control-{run_suffix}.sqlite3",
    )
    event_log = RuntimeDiagnosticEventLog(store=control_store, artifact_store=store)
    report_payload = {
        "schema_version": "polisyos.runtime.policy_intent_envelope.v1",
        "status": "pass",
        "intent_id": f"intent-{run_id}",
        "run_id": run_id,
        "job_id": job_id,
        "policy_problem": "Current normative publisher closure",
    }
    marker = {
        "schema_version": RUNTIME_QUALITY_OWNER_MARKER_SCHEMA,
        "report_key": report_key,
        "ref_key": ref_key,
        "projection": False,
    }
    authority_payload = {**report_payload, "runtime_authority_payload": marker}
    write_options = ArtifactWriteOptions(
        kind="runtime.policy_intent_envelope",
        media_type="application/json",
        schema=SchemaInfo(
            name="polisyos.runtime.PolicyIntentEnvelope",
            version="1.0",
        ),
        producer=ProducerInfo(
            component="polisyos.runtime.quality.policy_intent_envelope",
            version=RUNTIME_QUALITY_OWNER_PRODUCER_VERSION,
        ),
        governance=ArtifactGovernanceInfo(classification="runtime_quality_evidence"),
        inputs=[],
    )
    generated_at = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    closure = {
        "closure_id": f"{run_id}:runtime_quality",
        "status": "not_closed",
        "policy_intent_ref": None,
        "run_id": run_id,
        "job_id": job_id,
        "tenant_id": "tenant-1",
        "cell_id": "cell-a",
        "time_context_ref": None,
        "production_data_manifest_ref": None,
        "legal_snapshot_ref": None,
        "effective_mode_ref": "runtime-mode:production",
        "evidence_input_refs": [],
        "closure_sha256": None,
    }
    result = write_runtime_authority_artifact(
        store,
        event_log,
        authority_payload,
        write_options,
        evidence_id=f"runtime_quality_ref#{ref_key}",
        evidence_class="authority_bearing",
        authority_role="runtime_blocker",
        provenance_kind="runtime_blocker",
        owner="team-runtime",
        reader_contract=f"runtime_quality.{report_key}.v1",
        reader_contract_version="1.0",
        tenant_id="tenant-1",
        cell_id="cell-a",
        run_id=run_id,
        job_id=job_id,
        trace_id=f"trace-owner-{run_suffix}",
        span_id=f"{report_key}:cas_write",
        parent_span_id="span-parent",
        requested_execution_profile="production",
        effective_execution_profile="production",
        phase="policy_intent",
        generated_at=generated_at,
        as_of_time=generated_at,
        same_input_closure=closure,
        input_refs=[],
        effective_mode_ref="runtime-mode:production",
        validation_status="pass",
        blocking_status="blocking",
        governance=GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime",
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="runtime_owner_required",
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    selected_ref = result.cas_ref
    selected_id = str(selected_ref.artifact_id)
    assert store.verify(selected_ref).ok
    assert store.verify(result.diagnostic_event_ref).ok
    current_refs = {ref_key: selected_id}
    current_artifact_refs = {ref_key: selected_ref}
    event_summary = {
        "event_name": f"{report_key}.persisted",
        "event_type": "polisyos.runtime.diagnostic.cas_write.v1",
        "runtime_event_ref": str(result.diagnostic_event_ref.artifact_id),
        "runtime_event_manifest_profile_sha256": (
            result.diagnostic_event_ref.manifest_profile_sha256
        ),
        "artifact_ref": selected_id,
        "runtime_cas_ref": selected_id,
        "artifact_refs": [selected_id],
        "payload_ref": selected_id,
        "ref_key": ref_key,
        "report_key": report_key,
        "authority_envelope_ref": str(result.authority_envelope_ref.artifact_id),
        "manifest_ref": result.manifest_ref,
        "payload_sha256": result.payload_sha256,
    }
    candidate = _RuntimeQualityPublicationCandidate(
        result.identity_context.generated_at,
        result.identity_context.as_of_time,
        selected_id,
        None,
        None,
        None,
    )

    owner_verification_calls: list[tuple[str, str]] = []

    def verify_current_owner(
        current_ref_key: str,
        expected_ref: str,
        *,
        current_run_id: str = run_id,
        event_summaries: list[dict[str, Any]] | None = None,
    ) -> bool:
        owner_verification_calls.append((current_ref_key, expected_ref))
        return _runtime_quality_current_publisher_output_is_verified(
            artifact_store=store,
            runtime_ref=current_refs.get(current_ref_key),
            selected_ref=current_artifact_refs.get(current_ref_key),
            write_options=write_options,
            identity_context=result.identity_context,
            report_key=report_key,
            ref_key=current_ref_key,
            expected_role="policy_intent_envelope",
            expected_kind="runtime.policy_intent_envelope",
            expected_schema_name="polisyos.runtime.PolicyIntentEnvelope",
            expected_schema_version="1.0",
            phase="policy_intent",
            current_run_id=current_run_id,
            current_job_id=job_id,
            current_tenant_id="tenant-1",
            current_cell_id="cell-a",
            current_trace_id=f"trace-owner-{run_suffix}",
            current_parent_span_id="span-parent",
            current_requested_profile="production",
            current_effective_profile="production",
            requested_as_of_time=generated_at,
            event_summaries=(event_summaries if event_summaries is not None else [event_summary]),
        )

    # A present, equal local pointer is only a declaration until current owner CAS
    # identity and publication effects are independently read back.
    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        _runtime_quality_closure_reference_values(
            current_refs,
            candidate=candidate,
            output_artifact_id="sha256:" + "f" * 64,
            ref_key="normative_applicability_report_ref",
            current_inputs=(),
            current_artifact_refs=current_artifact_refs,
            artifact_store=store,
        )

    assert _runtime_quality_closure_reference_values(
        current_refs,
        candidate=candidate,
        output_artifact_id="sha256:" + "f" * 64,
        ref_key="normative_applicability_report_ref",
        current_inputs=(),
        current_artifact_refs=current_artifact_refs,
        artifact_store=store,
        current_report_verifier=verify_current_owner,
    ) == {
        "policy_intent_ref": selected_id,
        "production_data_manifest_ref": None,
        "legal_snapshot_ref": None,
    }
    typed_policy_intent = InputRef.model_validate(
        {
            "artifact_id": selected_id,
            "role": "policy_intent_envelope",
            "manifest_profile_sha256": selected_ref.manifest_profile_sha256,
        }
    )
    owner_verification_calls.clear()
    assert _runtime_quality_closure_reference_values(
        current_refs,
        candidate=candidate,
        output_artifact_id="sha256:" + "f" * 64,
        ref_key="normative_applicability_report_ref",
        current_inputs=[typed_policy_intent],
        current_artifact_refs=current_artifact_refs,
        artifact_store=store,
        current_report_verifier=verify_current_owner,
    ) == {
        "policy_intent_ref": selected_id,
        "production_data_manifest_ref": None,
        "legal_snapshot_ref": None,
    }
    assert owner_verification_calls == [(ref_key, selected_id)]

    owner_verification_calls.clear()
    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        _runtime_quality_closure_reference_values(
            current_refs,
            candidate=candidate,
            output_artifact_id="sha256:" + "f" * 64,
            ref_key="normative_applicability_report_ref",
            current_inputs=[typed_policy_intent],
            current_artifact_refs={},
            artifact_store=store,
        )
    assert owner_verification_calls == []

    assert not verify_current_owner(ref_key, selected_id, current_run_id="run-other")
    assert not verify_current_owner(ref_key, selected_id, event_summaries=[])


def test_publication_reuse_requires_exact_selected_closure() -> None:
    basis = _RuntimeQualityReportPublicationBasis(
        report_key="fabric_retrieval_trace",
        ref_key="fabric_retrieval_trace_ref",
        report_payload={"status": "pass"},
        artifact_ref={
            "artifact_id": "sha256:" + "a" * 64,
            "manifest_profile_sha256": "sha256:" + "b" * 64,
            "kind": "fabric.retrieval_trace",
            "media_type": "application/json",
        },
        runtime_event_ref="sha256:" + "c" * 64,
        runtime_event_manifest_profile_sha256="sha256:" + "d" * 64,
        authority_envelope_ref="sha256:" + "e" * 64,
        authority_envelope={
            "same_input_closure": {
                "closure_id": "run:runtime_quality",
                "status": "not_closed",
                "evidence_input_refs": ["sha256:" + "1" * 64, "sha256:" + "2" * 64],
            }
        },
        manifest_ref="cas-manifest://sha256:" + "a" * 64,
        payload_sha256="sha256:" + "a" * 64,
    )
    assert _runtime_quality_report_reuse_closure_matches(
        basis,
        {
            "closure_id": "run:runtime_quality",
            "status": "not_closed",
            "evidence_input_refs": ("sha256:" + "1" * 64, "sha256:" + "2" * 64),
        },
    )
    assert not _runtime_quality_report_reuse_closure_matches(
        basis,
        {
            "closure_id": "run:runtime_quality",
            "status": "not_closed",
            "evidence_input_refs": ("sha256:" + "1" * 64, "sha256:" + "3" * 64),
        },
    )
    assert not _runtime_quality_report_reuse_closure_matches(
        basis,
        {
            "closure_id": "run:runtime_quality",
            "status": "closed",
            "evidence_input_refs": ("sha256:" + "1" * 64, "sha256:" + "2" * 64),
        },
    )


def test_owner_registry_is_exact_for_source_backed_rows_only() -> None:
    assert len(RUNTIME_QUALITY_REPORT_OWNER_CONTRACTS) == 16
    assert set(RUNTIME_QUALITY_REPORT_OWNER_CONTRACTS).isdisjoint(_OWNERLESS_REGISTERED_ROLES)
    registered_gate_roles = set(QUALITY_REPORT_RUNTIME_REFS) - {"can_i_closeout"}
    assert len(registered_gate_roles) == 21
    assert len(_OWNERLESS_REGISTERED_ROLES) == 5
    assert (
        set(RUNTIME_QUALITY_REPORT_OWNER_CONTRACTS) | _OWNERLESS_REGISTERED_ROLES
    ) == registered_gate_roles
    for report_key, contract in RUNTIME_QUALITY_REPORT_OWNER_CONTRACTS.items():
        assert contract.report_key == report_key
        assert contract.ref_key == QUALITY_REPORT_RUNTIME_REFS[report_key]
        assert contract.schema_version == "1.0"
        assert contract.media_type == "application/json"
        assert contract.producer_component == f"polisyos.runtime.quality.{report_key}"
        assert contract.producer_version == "2026.05.15+hds-phase2.4"
        assert (
            runtime_quality_report_owner_identity_issues(
                report_key=report_key,
                ref_key=contract.ref_key,
                artifact_kind=contract.artifact_kind,
                schema_name=contract.schema_name,
                schema_version=contract.schema_version,
                phase=contract.phase,
                media_type=contract.media_type,
                producer_component=contract.producer_component,
                producer_version=contract.producer_version,
            )
            == ()
        )
    for report_key in _OWNERLESS_REGISTERED_ROLES:
        assert report_key in QUALITY_REPORT_RUNTIME_REFS
        assert (
            runtime_quality_report_owner_contract(
                report_key,
                QUALITY_REPORT_RUNTIME_REFS[report_key],
            )
            is None
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("artifact_kind", "runtime.other_report"),
        ("schema_name", "polisyos.runtime.OtherReport"),
        ("schema_version", "2.0"),
        ("phase", "other_phase"),
        ("media_type", "text/plain"),
        ("producer_component", "polisyos.runtime.quality.other_report"),
        ("producer_version", "candidate"),
    ],
)
def test_shared_owner_identity_validator_rejects_each_changed_dimension(
    field: str,
    replacement: str,
) -> None:
    contract = runtime_quality_report_owner_contract(
        "fabric_retrieval_trace",
        "fabric_retrieval_trace_ref",
    )
    assert contract is not None
    values: dict[str, object] = {
        "artifact_kind": contract.artifact_kind,
        "schema_name": contract.schema_name,
        "schema_version": contract.schema_version,
        "phase": contract.phase,
        "media_type": contract.media_type,
        "producer_component": contract.producer_component,
        "producer_version": contract.producer_version,
    }
    values[field] = replacement
    assert runtime_quality_report_owner_identity_issues(
        report_key=contract.report_key,
        ref_key=contract.ref_key,
        **values,
    ) == (field,)


def test_selected_report_cas_is_content_bound_before_scorecard_authority(
    tmp_path: Path,
) -> None:
    """CAS ownership/content may verify for blocked evidence; authority remains refused."""
    payload = {
        "schema_version": "1.0",
        "status": "pass",
        "claims": [{"claim_id": "claim-1"}],
    }
    store, result, report, envelope = _persist_report(
        tmp_path,
        report_key="fabric_retrieval_trace",
        run_suffix="fabric",
        payload=payload,
    )
    ref_key = "fabric_retrieval_trace_ref"
    runtime_ref = str(result.cas_ref.artifact_id)
    assert result.cas_ref.manifest_profile_sha256 is not None

    assert (
        runtime_quality_report_cas_admission_issues(
            artifact_store=store,
            selected_ref=result.cas_ref,
            runtime_ref=runtime_ref,
            report_key="fabric_retrieval_trace",
            ref_key=ref_key,
            report=report,
            envelope=envelope,
        )
        == []
    )

    job_payload = _runtime_payloads("fabric_retrieval_trace", result)
    evidence = {"fabric_retrieval_trace": report}
    gates = _authority_contract_gates(
        evidence,
        canary_kind="production",
        job_payload=job_payload,
        run_payload=None,
        quality_evidence_bundle_path=None,
        artifact_store=store,
    )
    assert not any(gate["code"].startswith("runtime_quality_") for gate in gates)
    assert "hds_borrowed_authority_envelope" not in {gate["code"] for gate in gates}
    assert envelope["authority_role"] == "runtime_blocker"
    assert any(gate["status"] == "fail" and gate["blocking"] for gate in gates)

    wrong_owner_evidence = deepcopy(evidence)
    wrong_owner_report = wrong_owner_evidence["fabric_retrieval_trace"]
    wrong_owner_report["authority_envelope"]["artifact_kind"] = "runtime.normative_evidence"
    assert wrong_owner_report[ref_key] == report[ref_key]
    assert (
        wrong_owner_report["runtime_quality_artifact_refs"]
        == report["runtime_quality_artifact_refs"]
    )
    assert (
        wrong_owner_report[_RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY]
        == report[_RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY]
    )
    wrong_owner_gates = _authority_contract_gates(
        wrong_owner_evidence,
        canary_kind="production",
        job_payload=job_payload,
        run_payload=None,
        quality_evidence_bundle_path=None,
        artifact_store=store,
    )
    assert any(
        gate["code"] == "hds_borrowed_authority_envelope"
        and gate["status"] == "fail"
        and gate["blocking"]
        for gate in wrong_owner_gates
    )

    # Keep all publisher markers and the real linked envelope. Inline evidence alone
    # must not admit authority when the selected CAS reader is unavailable.
    missing_store_gates = _authority_contract_gates(
        evidence,
        canary_kind="production",
        job_payload=job_payload,
        run_payload=None,
        quality_evidence_bundle_path=None,
        artifact_store=None,
    )
    assert any(
        gate["code"] == "runtime_quality_cas_store_not_available"
        and gate["status"] == "fail"
        and gate["blocking"]
        for gate in missing_store_gates
    )


def test_selected_report_cas_refuses_absence_and_divergent_inputs(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": "1.0",
        "status": "pass",
        "claims": [{"claim_id": "claim-1"}],
    }
    store, result, report, envelope = _persist_report(
        tmp_path,
        report_key="fabric_retrieval_trace",
        run_suffix="fabric",
        payload=payload,
    )
    contract = runtime_quality_report_owner_contract(
        "fabric_retrieval_trace",
        "fabric_retrieval_trace_ref",
    )
    assert contract is not None
    runtime_ref = str(result.cas_ref.artifact_id)

    def codes(**overrides: Any) -> set[str]:
        args = {
            "artifact_store": store,
            "selected_ref": result.cas_ref,
            "runtime_ref": runtime_ref,
            "report_key": "fabric_retrieval_trace",
            "ref_key": contract.ref_key,
            "report": report,
            "envelope": envelope,
            **overrides,
        }
        return {str(issue["code"]) for issue in runtime_quality_report_cas_admission_issues(**args)}

    assert "runtime_quality_cas_store_not_available" in codes(artifact_store=None)
    assert "runtime_quality_selected_ref_not_established" in codes(selected_ref=None)
    assert "runtime_quality_selected_profile_not_established" in codes(
        selected_ref=result.cas_ref.model_copy(update={"manifest_profile_sha256": None})
    )
    assert "runtime_quality_selected_media_type_mismatch" in codes(
        selected_ref=result.cas_ref.model_copy(update={"media_type": "text/plain"})
    )
    assert "runtime_quality_selected_kind_mismatch" in codes(
        selected_ref=result.cas_ref.model_copy(update={"kind": "fabric.unowned_trace"})
    )
    assert "runtime_quality_selected_cas_resolution_failed" in codes(
        selected_ref=result.cas_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "0" * 64}
        )
    )

    changed_basis = {**report, "claims": [{"claim_id": "forged-claim"}]}
    assert "runtime_quality_report_basis_mismatch" in codes(report=changed_basis)

    ownerless = runtime_quality_report_cas_admission_issues(
        artifact_store=store,
        selected_ref=result.cas_ref,
        runtime_ref=runtime_ref,
        report_key="hypothesis_ledger",
        ref_key="hypothesis_ledger_ref",
        report=report,
        envelope=envelope,
    )
    assert ownerless[0]["code"] == "runtime_quality_owner_contract_not_established"


def test_selected_report_cas_rejects_payload_hash_drift_with_markers_retained(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": "1.0",
        "status": "pass",
        "claims": [{"claim_id": "hash-claim"}],
    }
    store, result, report, envelope = _persist_report(
        tmp_path,
        report_key="fabric_retrieval_trace",
        run_suffix="hash-drift",
        payload=payload,
    )
    ref_key = "fabric_retrieval_trace_ref"
    runtime_ref = str(result.cas_ref.artifact_id)
    original_bytes = store.get_bytes(result.cas_ref)
    assert b'"runtime_authority_payload"' in original_bytes
    blob_path = store._paths(result.cas_ref.artifact_id)[0]
    blob_path.write_bytes(original_bytes + b" ")

    assert not store.verify(result.cas_ref).ok
    issues = runtime_quality_report_cas_admission_issues(
        artifact_store=store,
        selected_ref=result.cas_ref,
        runtime_ref=runtime_ref,
        report_key="fabric_retrieval_trace",
        ref_key=ref_key,
        report=report,
        envelope=envelope,
    )
    assert "runtime_quality_selected_cas_resolution_failed" in {
        str(issue["code"]) for issue in issues
    }


def test_selected_report_cas_rejects_a_borrowed_sibling_envelope(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": "1.0",
        "status": "pass",
        "claims": [{"claim_id": "fabric-claim"}],
    }
    store, result, report, _envelope = _persist_report(
        tmp_path,
        report_key="fabric_retrieval_trace",
        run_suffix="fabric",
        payload=payload,
    )
    _sibling_store, _sibling_result, _sibling_report, sibling_envelope = _persist_report(
        tmp_path,
        report_key="normative_evidence",
        run_suffix="normative",
        payload={"schema_version": "1.0", "status": "pass", "claims": []},
    )
    issues = runtime_quality_report_cas_admission_issues(
        artifact_store=store,
        selected_ref=result.cas_ref,
        runtime_ref=str(result.cas_ref.artifact_id),
        report_key="fabric_retrieval_trace",
        ref_key="fabric_retrieval_trace_ref",
        report=report,
        envelope=sibling_envelope,
    )
    assert "runtime_quality_inline_envelope_mismatch" in {str(issue["code"]) for issue in issues}


def test_selected_manifest_refuses_wrong_persisted_owner_identity(
    tmp_path: Path,
) -> None:
    variants = (
        (
            "wrong-kind",
            {"artifact_kind_override": "fabric.unowned_trace"},
            "runtime_quality_selected_kind_mismatch",
        ),
        (
            "wrong-schema-name",
            {"schema_name_override": "polisyos.fabric.OtherTrace"},
            "runtime_quality_manifest_owner_mismatch",
        ),
        (
            "wrong-schema-version",
            {"schema_version_override": "9.9"},
            "runtime_quality_manifest_owner_mismatch",
        ),
        (
            "wrong-producer",
            {"producer_component_override": "polisyos.runtime.quality.borrowed"},
            "runtime_quality_manifest_owner_mismatch",
        ),
    )
    for run_suffix, overrides, expected_code in variants:
        payload = {
            "schema_version": "1.0",
            "status": "pass",
            "claims": [{"claim_id": f"{run_suffix}-actual-owner"}],
        }
        store, result, report, envelope = _persist_report(
            tmp_path,
            report_key="fabric_retrieval_trace",
            run_suffix=run_suffix,
            payload=payload,
            **overrides,
        )
        issues = runtime_quality_report_cas_admission_issues(
            artifact_store=store,
            selected_ref=result.cas_ref,
            runtime_ref=str(result.cas_ref.artifact_id),
            report_key="fabric_retrieval_trace",
            ref_key="fabric_retrieval_trace_ref",
            report=report,
            envelope=envelope,
        )
        assert expected_code in {str(issue["code"]) for issue in issues}


def test_publication_basis_preserves_full_source_and_replays_exact_selected_view(
    tmp_path: Path,
) -> None:
    stale_ref = "sha256:" + "8" * 64
    payload = {
        "schema_version": "1.0",
        "status": "pass",
        "claims": [{"claim_id": "semantic-basis"}],
        "fabric_retrieval_trace_ref": stale_ref,
        "runtime_quality_artifact_refs": {"fabric_retrieval_trace_ref": {"artifact_id": stale_ref}},
        "runtime_event_ref": stale_ref,
        "runtime_event_manifest_profile_sha256": stale_ref,
        "authority_envelope_ref": stale_ref,
        "authority_envelope": {"stale": True},
        "manifest_ref": "cas-manifest://" + stale_ref,
        "payload_sha256": "8" * 64,
    }
    store, result, report, envelope = _persist_report(
        tmp_path,
        report_key="fabric_retrieval_trace",
        run_suffix="reserved-enrichment",
        payload=payload,
    )
    persisted = read_core_json_artifact(
        store,
        result.cas_ref,
        manifest_profile_sha256=result.cas_ref.manifest_profile_sha256,
    ).value
    assert persisted["runtime_event_ref"] == stale_ref
    assert persisted["manifest_ref"] == "cas-manifest://" + stale_ref
    assert report["runtime_event_ref"] != stale_ref
    assert report["manifest_ref"] == result.manifest_ref
    basis = report[_RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY]
    assert basis["report_payload"] == payload
    assert basis["report_payload"]["manifest_ref"] == "cas-manifest://" + stale_ref
    assert basis["report_payload"]["runtime_quality_artifact_refs"] == {
        "fabric_retrieval_trace_ref": {"artifact_id": stale_ref}
    }
    assert report["runtime_quality_artifact_refs"] == {
        "fabric_retrieval_trace_ref": result.cas_ref.model_dump(mode="json")
    }
    admission_args = {
        "artifact_store": store,
        "selected_ref": result.cas_ref,
        "runtime_ref": str(result.cas_ref.artifact_id),
        "report_key": "fabric_retrieval_trace",
        "ref_key": "fabric_retrieval_trace_ref",
        "report": report,
        "envelope": envelope,
    }
    assert runtime_quality_report_cas_admission_issues(**admission_args) == []

    fresh_store = FileSystemCAS(tmp_path / "cas-reserved-enrichment").for_tenant(
        "tenant-1",
        cell_id="cell-a",
    )
    selected_manifest = fresh_store.get_manifest(result.cas_ref.artifact_id)
    expected_write_options = ArtifactWriteOptions(
        kind=selected_manifest.kind,
        media_type=selected_manifest.media_type,
        schema=selected_manifest.artifact_schema,
        producer=selected_manifest.producer,
        governance=selected_manifest.governance,
        inputs=list(selected_manifest.inputs),
    )
    rebuilt_context = replace(result.identity_context)
    strict_admission_args = {
        **admission_args,
        "artifact_store": fresh_store,
        "expected_write_options": expected_write_options,
        "expected_identity_context": rebuilt_context,
    }
    assert runtime_quality_report_cas_admission_issues(**strict_admission_args) == []
    changed_current_input = replace(
        rebuilt_context,
        manifest_inputs=(
            rebuilt_context.manifest_inputs[0].model_copy(update={"role": "changed_role"}),
            *rebuilt_context.manifest_inputs[1:],
        ),
    )
    assert "runtime_quality_current_identity_mismatch" in {
        str(issue["code"])
        for issue in runtime_quality_report_cas_admission_issues(
            **{
                **strict_admission_args,
                "expected_identity_context": changed_current_input,
            }
        )
    }
    changed_write_input = expected_write_options.inputs[0].model_copy(
        update={"role": "changed_role"}
    )
    assert "runtime_quality_current_identity_mismatch" in {
        str(issue["code"])
        for issue in runtime_quality_report_cas_admission_issues(
            **{
                **strict_admission_args,
                "expected_write_options": replace(
                    expected_write_options,
                    inputs=[changed_write_input, *expected_write_options.inputs[1:]],
                ),
            }
        )
    }
    assert "runtime_quality_current_identity_not_established" in {
        str(issue["code"])
        for issue in runtime_quality_report_cas_admission_issues(
            **{
                **admission_args,
                "expected_write_options": expected_write_options,
            }
        )
    }

    changed_business_field = deepcopy(report)
    changed_business_field["claims"] = [{"claim_id": "forged-semantic-change"}]
    assert "runtime_quality_report_basis_mismatch" in {
        str(issue["code"])
        for issue in runtime_quality_report_cas_admission_issues(
            **{**admission_args, "report": changed_business_field}
        )
    }

    changed_original_reserved_field = deepcopy(report)
    changed_original_reserved_field[_RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY][
        "report_payload"
    ]["manifest_ref"] = "cas-manifest://spoofed-business-source"
    assert "runtime_quality_report_basis_mismatch" in {
        str(issue["code"])
        for issue in runtime_quality_report_cas_admission_issues(
            **{**admission_args, "report": changed_original_reserved_field}
        )
    }

    changed_selected_ref_map = deepcopy(report)
    changed_selected_ref_map["runtime_quality_artifact_refs"]["fabric_retrieval_trace_ref"][
        "artifact_id"
    ] = stale_ref
    assert "runtime_quality_report_basis_mismatch" in {
        str(issue["code"])
        for issue in runtime_quality_report_cas_admission_issues(
            **{**admission_args, "report": changed_selected_ref_map}
        )
    }

    forged_basis_ref = deepcopy(report)
    forged_basis_ref[_RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY]["publication"]["artifact_ref"][
        "artifact_id"
    ] = stale_ref
    forged_basis_ref["fabric_retrieval_trace_ref"] = stale_ref
    forged_basis_ref["runtime_quality_artifact_refs"]["fabric_retrieval_trace_ref"][
        "artifact_id"
    ] = stale_ref
    assert "runtime_quality_report_basis_mismatch" in {
        str(issue["code"])
        for issue in runtime_quality_report_cas_admission_issues(
            **{**admission_args, "report": forged_basis_ref}
        )
    }

    malformed_basis = deepcopy(report)
    malformed_basis[_RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY]["unexpected"] = True
    assert "runtime_quality_report_publication_basis_not_established" in {
        str(issue["code"])
        for issue in runtime_quality_report_cas_admission_issues(
            **{**admission_args, "report": malformed_basis}
        )
    }

    markers_without_basis = dict(report)
    del markers_without_basis[_RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY]
    assert "runtime_quality_report_publication_basis_not_established" in {
        str(issue["code"])
        for issue in runtime_quality_report_cas_admission_issues(
            **{**admission_args, "report": markers_without_basis}
        )
    }


def test_publisher_refuses_caller_supplied_publication_basis() -> None:
    contract = runtime_quality_report_owner_contract(
        "fabric_retrieval_trace",
        "fabric_retrieval_trace_ref",
    )
    assert contract is not None
    with pytest.raises(ValueError, match="publisher_owned"):
        _runtime_quality_report_writer_payload(
            {
                "schema_version": "1.0",
                _RUNTIME_QUALITY_REPORT_PUBLICATION_BASIS_KEY: {
                    "schema_version": "forged",
                },
            },
            report_key=contract.report_key,
            ref_key=contract.ref_key,
        )
    with pytest.raises(ValueError, match="marker_mismatch"):
        _runtime_quality_report_writer_payload(
            {
                "schema_version": "1.0",
                "runtime_authority_payload": {
                    "schema_version": "policyos.runtime.authority_payload_marker.v1",
                    "report_key": "normative_evidence",
                    "ref_key": "normative_applicability_report_ref",
                    "projection": False,
                },
            },
            report_key=contract.report_key,
            ref_key=contract.ref_key,
        )


def test_public_authority_refusal_and_actual_cas_corruption_are_separate_planes(
    tmp_path: Path,
) -> None:
    """A public missing-input-owner refusal is never reported as verified CAS data."""
    from polisyos.runtime.quality.authority import AuthorityEnvelopeError, assert_runtime_emitted

    cases = []
    roles: tuple[Literal["runtime_blocker", "producer_authority"], ...] = (
        "runtime_blocker",
        "producer_authority",
    )
    for role in roles:
        store, result, report, envelope = _persist_report(
            tmp_path,
            report_key="fabric_retrieval_trace",
            run_suffix=f"planes-{role}",
            payload={"schema_version": "1.0", "status": "pass", "claims": []},
            authority_role=role,
        )
        fresh = FileSystemCAS(tmp_path / f"cas-planes-{role}").for_tenant(
            "tenant-1", cell_id="cell-a"
        )
        args = {
            "artifact_store": fresh,
            "selected_ref": result.cas_ref,
            "runtime_ref": str(result.cas_ref.artifact_id),
            "report_key": "fabric_retrieval_trace",
            "ref_key": "fabric_retrieval_trace_ref",
            "report": report,
            "envelope": envelope,
        }
        assert fresh.verify(result.cas_ref).ok
        before = {
            str(issue["code"]) for issue in runtime_quality_report_cas_admission_issues(**args)
        }
        if role == "runtime_blocker":
            assert before == set()  # Ownership/read result, explicitly not authority.
        else:
            assert before == {"same_input_closure_owner_not_established"}
        with pytest.raises(AuthorityEnvelopeError):
            assert_runtime_emitted(envelope)
        cases.append((role, store, result, fresh, args))
    for role, store, result, fresh, args in cases:
        blob = store._paths(result.cas_ref.artifact_id)[0]
        blob.write_bytes(blob.read_bytes() + b" ")
        assert not fresh.verify(result.cas_ref).ok
        after = {
            str(issue["code"]) for issue in runtime_quality_report_cas_admission_issues(**args)
        }
        if role == "runtime_blocker":
            assert after == {"runtime_quality_selected_cas_resolution_failed"}
        else:
            # The public authority guard deliberately dominates. Independent
            # actual Core verification above proves this is corrupt, not empty
            # or owner-verified, even though the public refusal stays unchanged.
            assert after == {"same_input_closure_owner_not_established"}
