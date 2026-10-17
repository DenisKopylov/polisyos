"""Deployment composition reaches the real persisted acquisition authority owner."""

from __future__ import annotations

import hashlib
import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.runtime.http import deployment_security as security
from polisyos.runtime.http.services.acquisition_action_service import AcquisitionActionService
from polisyos.runtime.quality import agent_action_authority as authority
from tests.integration.core_runtime import test_acquisition_admission_bundle as fixtures
from tests.unit.runtime.http.test_runtime_deployment_security import _config_mapping


def _closure():
    return SimpleNamespace(
        tenant_id=fixtures.TENANT_ID,
        cell_id=fixtures.CELL_ID,
        run_id=fixtures.RUN_ID,
        route_id="sha256:" + "5" * 64,
        cost_basis_hash="sha256:" + "4" * 64,
        compiled_ref="sha256:" + "1" * 64,
        source_cycle=SimpleNamespace(cycle_index=1),
    )


def test_empty_deployment_provider_persists_real_refusal(tmp_path, monkeypatch):
    from polisyos.runtime.http.services.acquisition_authority_provider import (
        ProductionAcquisitionAuthorityProvider,
    )

    monkeypatch.setattr(authority, "_utcnow", lambda: fixtures.NOW)
    store, event_log, idempotency = fixtures._harness(tmp_path)
    deployment = security.build_deployment_security(
        security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    )
    provider = ProductionAcquisitionAuthorityProvider(
        deployment_security=deployment,
        artifact_store=store,
        event_log=event_log,
        idempotency_store=idempotency,
        execution_profile="governed",
    )
    effects = []
    closure = _closure()
    request = fixtures.ACQUISITION_REQUEST
    proof = fixtures._proof()
    gateway = provider.for_request(
        closure=closure,
        request=request,
        job_id=fixtures.JOB_ID,
        bound_permission=proof,
        effect_handler=lambda call: effects.append(call),
    )
    operation, invocation, intent = AcquisitionActionService._action_tuple(closure, request)
    with authority.agent_action_authority_scope(gateway):
        decision = authority.produce_agent_action_authority_decision(
            bound_permission=proof,
            operation=operation,
            invocation=invocation,
            intent=intent,
        )
        receipt = gateway.persist_decision(decision)
    loaded = gateway.load_persisted_decision(str(receipt.write_result.cas_ref.artifact_id))
    assert loaded.decision.outcome == "refused"
    assert "delegation_contract_not_persisted" in loaded.decision.refusal_reasons
    assert "governed_admission_bundle_missing" in loaded.decision.refusal_reasons
    assert not provider.authority_available
    assert effects == []


def test_real_worker_replay_refuses_absent_decision_verification_appointment(tmp_path, monkeypatch):
    """An actual approved job cannot switch to unsigned legacy replay at restart."""
    from polisyos.runtime.http.services.acquisition_authority_provider import (
        ProductionAcquisitionAuthorityProvider,
    )
    from tests.integration.core_runtime.test_acquisition_authority_served import (
        test_served_acquisition_selects_committed_human_authority_and_reopens_worker,
    )

    original = ProductionAcquisitionAuthorityProvider.for_job
    observed: list[str] = []
    witness_records: list[dict[str, object]] = []
    output_path = tmp_path / "provider-verifier-removal.json"

    def check_replay(provider, **kwargs):
        # First establish that these exact persisted bytes authorize the actual
        # worker with its appointed verifier. Do not execute its live effect.
        verified_gateway = original(provider, **kwargs)
        config = provider._deployment.config
        missing = security.build_deployment_security(
            config.model_copy(
                update={
                    "acquisition_authority": config.acquisition_authority.model_copy(
                        update={"decision_signer": None}
                    )
                }
            )
        )
        restarted = ProductionAcquisitionAuthorityProvider(
            deployment_security=missing,
            artifact_store=provider._store,
            event_log=provider._event_log,
            idempotency_store=provider._idempotency,
            execution_profile=provider._execution_profile,
            human_decision_service=provider._human_decisions,
            production_approval_resolver=provider._approval_resolver,
        )
        effects: list[object] = []
        loaded_decisions: list[str] = []
        replay_args = {**kwargs, "effect_handler": effects.append}
        instant = datetime.now(UTC)
        source_path = Path(inspect.getsourcefile(ProductionAcquisitionAuthorityProvider))
        decision_ref = kwargs["decision_ref"]
        decision_artifact_id = str(getattr(decision_ref, "artifact_id", decision_ref))
        decision_profile = getattr(decision_ref, "manifest_profile_sha256", None)

        def file_receipt(path: Path, *, optional_signature: bool) -> dict[str, object]:
            try:
                return {
                    "status": "read",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            except FileNotFoundError as exc:
                if optional_signature:
                    return {"status": "unsigned_sidecar_absent"}
                return {"status": "UNRUN", "error": repr(exc)}
            except OSError as exc:
                return {"status": "UNRUN", "error": repr(exc)}

        def appointment_summary(deployment_config) -> dict[str, object]:
            authority_config = deployment_config.acquisition_authority
            appointment = (
                authority_config.decision_signer if authority_config is not None else None
            )
            return {
                "decision_signer_appointed": appointment is not None,
                "decision_signer_identity": (
                    appointment.signer_identity if appointment is not None else None
                ),
                "decision_signer_purpose": (
                    appointment.purpose if appointment is not None else None
                ),
                "verifier_provenance_ref": (
                    appointment.verifier_provenance_ref if appointment is not None else None
                ),
            }

        def model_sha256(value) -> str:
            payload = json.dumps(
                value.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            return hashlib.sha256(payload).hexdigest()

        witness = {
            "decision_ref": decision_artifact_id,
            "decision_manifest_profile_sha256": decision_profile,
            "cas_scope": "exact refs and selected views observed through owner methods",
            "configured_decision_appointment": appointment_summary(config),
            "empty_decision_appointment": appointment_summary(missing.config),
            "closure_sha256": model_sha256(kwargs["closure"]),
            "request_sha256": model_sha256(kwargs["request"]),
            "job_id": kwargs["job_id"],
            "evaluation_time": instant.isoformat(),
        }
        witness_sha = hashlib.sha256(
            json.dumps(witness, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        record = {
            "witness": witness,
            "witness_sha256": witness_sha,
            "original_provider_source": {
                "path": str(source_path),
                "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            },
            "mutation": "ProductionAcquisitionAuthorityProvider._require_worker_decision_verification",
            "same_provider_object": id(restarted),
            "read_boundary": [
                "has",
                "get_bytes",
                "get_manifest",
                "get_manifest_bytes",
                "get_signature",
                "get_signature_bytes",
                "verify",
                "verify_signature",
            ],
            "write_boundary": [
                "record_artifact_owner",
                "import_exact_view",
                "put_signature",
                "sign_artifact",
                "sign_all_artifacts",
                "put_bytes",
                "put_json",
                "import_subgraph",
            ],
            "forbidden_global_inventory": [
                "iter_artifact_ids",
                "inventory_snapshot",
                "_bulk_inventory_artifact_ids",
                "_iter_artifact_ids_lazy",
                "verify_all_signatures",
            ],
            "outside_read_boundary": [
                "Existing diagnostic event store and DS9 exposure audit remain the same objects; their backing files are not claimed as CAS bytes.",
                "Deployment keys are factory-captured; configured/empty attestation states remain fixed.",
                "No connector or original worker callback is called in the measurement phases.",
                "Direct filesystem actors outside FileSystemCAS are unresolved by construction.",
            ],
            "phases": [],
        }
        witness_records.append(record)

        def load_replay() -> None:
            replay = original(restarted, **replay_args)
            loaded = replay.load_persisted_decision(kwargs["decision_ref"])
            assert loaded.decision.outcome == "allowed"
            loaded_decisions.append(str(loaded.write_result.cas_ref.artifact_id))

        def require_refusal() -> None:
            with pytest.raises(
                authority.AgentActionAuthorityRecordingError,
                match="acquisition_worker_decision_verification_unallocated",
            ):
                load_replay()
            assert effects == []

        with monkeypatch.context() as phase_patch:
            phase_patch.setattr(authority, "_utcnow", lambda: instant)
            phase_patch.setattr(provider._human_decisions, "_clock", lambda: instant)
            store_type = authority.artifacts.FileSystemCAS
            actual_reads: list[dict[str, object]] = []
            actual_writes: list[dict[str, object]] = []
            phase_input_paths: dict[Path, bool] = {}

            def selected_identity(reference):
                identity = authority.artifacts.ArtifactID.model_validate(
                    getattr(reference, "artifact_id", reference)
                )
                profile_sha256 = getattr(reference, "manifest_profile_sha256", None)
                return identity, profile_sha256

            def selected_member_paths(store, reference, method_name):
                identity, profile_sha256 = selected_identity(reference)
                if method_name == "get_bytes":
                    paths = (store._paths(identity)[0],)
                elif method_name in {"get_manifest", "get_manifest_bytes"}:
                    paths = (store._manifest_path_for_ref(identity, profile_sha256),)
                elif method_name in {"get_signature", "get_signature_bytes"}:
                    paths = (store._sig_path(identity, profile_sha256),)
                elif method_name == "has" or method_name == "verify":
                    paths = (
                        store._paths(identity)[0],
                        store._manifest_path_for_ref(identity, profile_sha256),
                    )
                elif method_name == "verify_signature":
                    paths = (
                        store._paths(identity)[0],
                        store._manifest_path_for_ref(identity, profile_sha256),
                        store._sig_path(identity, profile_sha256),
                    )
                else:
                    paths = ()
                return paths, identity, profile_sha256

            def traced_read(method_name, method):
                def read(store, artifact_ref, *args, **kwargs):
                    attempt: dict[str, object] = {
                        "operation": method_name,
                        "artifact_id": str(
                            getattr(artifact_ref, "artifact_id", artifact_ref)
                        ),
                        "manifest_profile_sha256": getattr(
                            artifact_ref, "manifest_profile_sha256", None
                        ),
                        "status": "attempted",
                    }
                    actual_reads.append(attempt)
                    paths = ()
                    try:
                        paths, identity, profile_sha256 = selected_member_paths(
                            store, artifact_ref, method_name
                        )
                        attempt["artifact_id"] = str(identity)
                        attempt["manifest_profile_sha256"] = profile_sha256
                        if paths:
                            attempt["paths"] = [str(path) for path in paths]
                            optional_signature = method_name in {
                                "get_signature",
                                "verify_signature",
                            }
                            before_files = {}
                            for path in paths:
                                path_is_optional_signature = (
                                    optional_signature and path == paths[-1]
                                )
                                phase_input_paths.setdefault(
                                    path,
                                    path_is_optional_signature,
                                )
                                before_files[str(path)] = file_receipt(
                                    path,
                                    optional_signature=path_is_optional_signature,
                                )
                            attempt["files_before"] = before_files
                    except Exception as exc:
                        attempt["path_binding"] = {"status": "UNRUN", "error": repr(exc)}
                    try:
                        value = method(store, artifact_ref, *args, **kwargs)
                    except Exception as exc:
                        attempt.update(status="failed_read", error=repr(exc))
                        if paths:
                            after_files = {
                                str(path): file_receipt(
                                    path,
                                    optional_signature=method_name
                                    in {"get_signature", "verify_signature"}
                                    and path == paths[-1],
                                )
                                for path in paths
                            }
                            attempt["files_after"] = after_files
                            attempt["files_unchanged"] = (
                                attempt["files_before"] == after_files
                            )
                        raise
                    attempt["status"] = "read"
                    if paths:
                        after_files = {
                            str(path): file_receipt(
                                path,
                                optional_signature=(method_name == "get_signature"
                                and value is None)
                                or (method_name == "verify_signature"
                                and path == paths[-1]),
                            )
                            for path in paths
                        }
                        attempt["files_after"] = after_files
                        attempt["files_unchanged"] = attempt["files_before"] == after_files
                        if any(item["status"] == "UNRUN" for item in after_files.values()):
                            attempt["status"] = "UNRUN"
                        if method_name == "get_bytes" and isinstance(value, bytes):
                            returned_sha256 = hashlib.sha256(value).hexdigest()
                            attempt["returned_sha256"] = "sha256:" + returned_sha256
                            attempt["returned_content_matches_artifact_id"] = (
                                returned_sha256 == identity.hex
                            )
                        if method_name == "verify":
                            attempt["verified"] = bool(getattr(value, "ok", False))
                        elif method_name == "verify_signature":
                            status = getattr(value, "status", "unknown")
                            attempt["signature_status"] = getattr(status, "value", str(status))
                    if method_name == "has":
                        attempt["exists"] = bool(value)
                    return value

                return read

            def traced_write(method_name, method):
                def write(store, *args, **kwargs):
                    entry: dict[str, object] = {
                        "operation": method_name,
                        "status": "attempted",
                    }
                    ref_arguments = []
                    for value in (*args, *kwargs.values()):
                        candidate = getattr(value, "artifact_id", value)
                        if isinstance(candidate, str) and candidate.startswith("sha256:"):
                            ref_arguments.append(candidate)
                    if ref_arguments:
                        entry["artifact_refs"] = sorted(set(ref_arguments))
                    actual_writes.append(entry)
                    result = method(store, *args, **kwargs)
                    entry["status"] = "completed"
                    return result

                return write

            def forbid_global_inventory(method_name):
                def forbidden(_store, *args, **kwargs):
                    actual_reads.append(
                        {
                            "operation": method_name,
                            "status": "forbidden_global_inventory_attempt",
                        }
                    )
                    raise AssertionError("provider replay attempted a global CAS inventory")

                return forbidden

            read_methods = (
                "has",
                "get_bytes",
                "get_manifest",
                "get_manifest_bytes",
                "get_signature",
                "get_signature_bytes",
                "verify",
                "verify_signature",
            )
            write_methods = (
                "record_artifact_owner",
                "import_exact_view",
                "put_signature",
                "sign_artifact",
                "sign_all_artifacts",
                "put_bytes",
                "put_json",
                "import_subgraph",
            )
            forbidden_inventory_methods = (
                "iter_artifact_ids",
                "inventory_snapshot",
                "_bulk_inventory_artifact_ids",
                "_iter_artifact_ids_lazy",
                "verify_all_signatures",
            )
            assert all(callable(getattr(store_type, name, None)) for name in read_methods)
            assert all(callable(getattr(store_type, name, None)) for name in write_methods)
            assert all(
                callable(getattr(store_type, name, None))
                for name in forbidden_inventory_methods
            )
            for method_name in read_methods:
                phase_patch.setattr(
                    store_type,
                    method_name,
                    traced_read(method_name, getattr(store_type, method_name)),
                )
            for method_name in write_methods:
                phase_patch.setattr(
                    store_type,
                    method_name,
                    traced_write(method_name, getattr(store_type, method_name)),
                )
            for method_name in forbidden_inventory_methods:
                phase_patch.setattr(
                    store_type,
                    method_name,
                    forbid_global_inventory(method_name),
                )
            enforcement = (
                ProductionAcquisitionAuthorityProvider._require_worker_decision_verification
            )
            try:
                for phase in ("baseline", "removed", "restored"):
                    effects.clear()
                    loaded_decisions.clear()
                    actual_reads.clear()
                    actual_writes.clear()
                    phase_input_paths.clear()
                    phase_patch.setattr(
                        ProductionAcquisitionAuthorityProvider,
                        "_require_worker_decision_verification",
                        (lambda self: None) if phase == "removed" else enforcement,
                    )
                    code = 0
                    failure = None
                    unexpected = None
                    try:
                        require_refusal()
                    except pytest.fail.Exception as exc:
                        code = 1
                        failure = str(exc)
                    except Exception as exc:
                        code = 2
                        failure = repr(exc)
                        unexpected = exc
                    final_files = {
                        str(path): file_receipt(
                            path,
                            optional_signature=optional_signature,
                        )
                        for path, optional_signature in sorted(
                            phase_input_paths.items(), key=lambda item: str(item[0])
                        )
                    }
                    changed_or_failed_files = {}
                    for attempt in actual_reads:
                        if "paths" not in attempt:
                            continue
                        before_files = attempt.get("files_before", {})
                        for path in attempt["paths"]:
                            before = before_files.get(path)
                            after = final_files[path]
                            if before != after or after["status"] == "UNRUN":
                                changed_or_failed_files[path] = {
                                    "before": before,
                                    "after": after,
                                }
                    decision_read_operations = {
                        attempt.get("operation")
                        for attempt in actual_reads
                        if attempt.get("artifact_id") == decision_artifact_id
                    }
                    complete = (
                        all(attempt["status"] == "read" for attempt in actual_reads)
                        and all("path_binding" not in attempt for attempt in actual_reads)
                        and all(
                            attempt.get("files_unchanged", True) for attempt in actual_reads
                        )
                        and all(
                            attempt.get("returned_content_matches_artifact_id", True)
                            for attempt in actual_reads
                        )
                        and all(
                            attempt.get("verified", True) for attempt in actual_reads
                        )
                        and all(
                            attempt.get("signature_status", "valid") == "valid"
                            for attempt in actual_reads
                        )
                        and not changed_or_failed_files
                        and not actual_writes
                        and unexpected is None
                    )
                    if phase == "removed":
                        assert {"get_bytes", "get_manifest"}.issubset(
                            decision_read_operations
                        )
                        assert any(
                            attempt["operation"] == "has"
                            and attempt["artifact_id"] == decision_artifact_id
                            and attempt.get("exists") is True
                            for attempt in actual_reads
                        )
                    else:
                        assert actual_reads == []
                    record["phases"].append(
                        {
                            "phase": phase,
                            "gate_code": code,
                            "failure": failure,
                            "effect_callbacks": len(effects),
                            "allowed_decision_refs": list(loaded_decisions),
                            "same_witness_sha256": witness_sha,
                            "actual_reads": list(actual_reads),
                            "actual_writes": list(actual_writes),
                            "selected_cas_refs": sorted(
                                {
                                    attempt["artifact_id"]
                                    for attempt in actual_reads
                                    if isinstance(attempt.get("artifact_id"), str)
                                }
                            ),
                            "cas_read_denominator": len(actual_reads),
                            "cas_write_denominator": len(actual_writes),
                            "retained_input_readback_sha256": hashlib.sha256(
                                json.dumps(final_files, sort_keys=True).encode()
                            ).hexdigest(),
                            "observed_cas_files": final_files,
                            "changed_or_failed_input_reads": changed_or_failed_files,
                            "coverage": (
                                "COMPLETE_FOR_OBSERVED_OWNER_READS"
                                if complete
                                else "UNRUN; partial owner-boundary coverage"
                            ),
                        }
                    )
                    output_path.write_text(
                        json.dumps({"cases": witness_records}, indent=2) + "\n", encoding="utf-8"
                    )
                    if unexpected is not None:
                        raise unexpected
                    assert complete
                    assert code == (1 if phase == "removed" else 0)
                    assert effects == []
                    assert loaded_decisions == (
                        [decision_artifact_id] if phase == "removed" else []
                    )
            finally:
                phase_patch.setattr(
                    ProductionAcquisitionAuthorityProvider,
                    "_require_worker_decision_verification",
                    enforcement,
                )
        observed.append(kwargs["decision_ref"])
        return verified_gateway

    monkeypatch.setattr(ProductionAcquisitionAuthorityProvider, "for_job", check_replay)
    test_served_acquisition_selects_committed_human_authority_and_reopens_worker(
        tmp_path, monkeypatch
    )
    assert observed


_OWNER_IDENTITY = fixtures.MANDATE_OWNER_REF
_CURRENTNESS_IDENTITY = fixtures.MANDATE_AUTHORITY_IDENTITY
_ADMISSION_IDENTITY = fixtures.ADMISSION_IDENTITY
_DECISION_IDENTITY = "service://runtime/acquisition-decision/provider-refusal-test"
_ROUTE_ID = "sha256:" + "5" * 64


def _write_keypair(tmp_path: Path, name: str):
    from polisyos.core.artifacts.signing import KeyPair

    pair = KeyPair.generate()
    private_path = tmp_path / f"{name}.private.pem"
    public_path = tmp_path / f"{name}.public.pem"
    private_path.write_bytes(pair.private_pem())
    public_path.write_bytes(pair.public_pem())
    return pair, private_path, public_path


class _ReadUnavailableCAS:
    def __init__(self, delegate):
        self._delegate = delegate

    def __getattr__(self, name):
        return getattr(self._delegate, name)

    def get_bytes(self, _ref):
        raise OSError("synthetic CAS read dependency failure")


def _provider_with_selected_slot(
    tmp_path: Path,
    *,
    current: bool = True,
    wrong_currentness_role: bool = False,
    information: str = "none",
):
    from datetime import timedelta

    from polisyos.core.artifacts import ArtifactID, ArtifactRef
    from polisyos.core.artifacts.signing import Ed25519Signer
    from polisyos.runtime.http.services.acquisition_authority_configuration import (
        AcquisitionAdmissionSignerConfig,
        AcquisitionAuthorityConfig,
        AcquisitionDecisionSignerConfig,
        AcquisitionMandateSlot,
    )
    from polisyos.runtime.quality.agent_action_authority import (
        CURRENT_MANDATE_OWNER_ARTIFACT_KIND,
        CURRENT_MANDATE_OWNER_SCHEMA_VERSION,
        DELEGATION_CONTRACT_ARTIFACT_KIND,
        LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
        CurrentMandateOwnerEvidence,
    )

    store, event_log, idempotency = fixtures._harness(tmp_path)
    owner = _write_keypair(tmp_path, "owner")
    current_signer = _write_keypair(tmp_path, "current")
    admission = _write_keypair(tmp_path, "admission")
    decision = _write_keypair(tmp_path, "decision")
    contract_ref = fixtures._persist_signed(
        store=store,
        event_log=event_log,
        payload=fixtures._contract(),
        kind=DELEGATION_CONTRACT_ARTIFACT_KIND,
        schema_name="polisyos.runtime.DelegationContract",
        schema_version=LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
        signer=Ed25519Signer(owner[0].private_key),
        signer_identity=_OWNER_IDENTITY,
    )
    evidence_signer = owner if wrong_currentness_role else current_signer
    evidence_identity = (
        _OWNER_IDENTITY if wrong_currentness_role else _CURRENTNESS_IDENTITY
    )
    evidence = CurrentMandateOwnerEvidence(
        evidence_id="mandate-authority.provider-refusal-test",
        evidence_ref="institution://test-only/provider-refusal-head",
        mandate_owner_ref=_OWNER_IDENTITY,
        authority_purpose="agent_action_delegation",
        current=current,
        effective_from=fixtures.NOW - timedelta(hours=1),
        effective_until=fixtures.NOW + timedelta(hours=1),
        delegation_rule_version_ref=authority.AGENT_ACTION_AUTHORITY_RULE_VERSION,
        evidence_signer_identity=evidence_identity,
        verifier_provenance="independently_reconciled",
        provenance_refs=("institution://test-only/synthetic-source",),
    )
    current_ref = fixtures._persist_signed(
        store=store,
        event_log=event_log,
        payload=evidence,
        kind=CURRENT_MANDATE_OWNER_ARTIFACT_KIND,
        schema_name="polisyos.runtime.CurrentMandateOwnerEvidence",
        schema_version=CURRENT_MANDATE_OWNER_SCHEMA_VERSION,
        signer=Ed25519Signer(evidence_signer[0].private_key),
        signer_identity=evidence_identity,
    )

    information_refs = ()
    missing_information_ref = None
    if information == "missing":
        missing_information_ref = "sha256:" + "9" * 64
        information_refs = (
            ArtifactRef(
                artifact_id=ArtifactID.model_validate(missing_information_ref),
                kind="polisyos.test.acquisition-information",
                media_type="application/json",
            ),
        )
    elif information == "contract":
        manifest = store.get_manifest(contract_ref)
        information_refs = (
            ArtifactRef(
                artifact_id=ArtifactID.model_validate(contract_ref),
                kind=manifest.kind,
                media_type=manifest.media_type,
            ),
        )
    elif information != "none":
        raise ValueError(f"unsupported test information mode: {information}")

    base = security.DeploymentSecurityConfig.from_mapping(_config_mapping(tmp_path))
    acquisition_config = AcquisitionAuthorityConfig(
        mandates=(
            AcquisitionMandateSlot(
                tenant_id=fixtures.TENANT_ID,
                cell_id=fixtures.CELL_ID,
                run_id=fixtures.RUN_ID,
                route_id=_ROUTE_ID,
                resource_digest=fixtures.RESOURCE_DIGEST,
                delegation_contract_ref=contract_ref,
                mandate_owner_ref=_OWNER_IDENTITY,
                delegation_public_key_path=owner[2],
                current_mandate_evidence_ref=current_ref,
                current_mandate_signer_identity=_CURRENTNESS_IDENTITY,
                current_mandate_public_key_path=current_signer[2],
                verifier_provenance_ref="synthetic-test-only",
                decision_information_refs=information_refs,
            ),
        ),
        admission_signer=AcquisitionAdmissionSignerConfig(
            signer_identity=_ADMISSION_IDENTITY,
            private_key_path=admission[1],
            public_key_path=admission[2],
            verifier_provenance_ref="synthetic-test-only",
        ),
        decision_signer=AcquisitionDecisionSignerConfig(
            signer_identity=_DECISION_IDENTITY,
            private_key_path=decision[1],
            public_key_path=decision[2],
            verifier_provenance_ref="synthetic-test-only",
        ),
    )
    deployment = security.build_deployment_security(
        base.model_copy(update={"acquisition_authority": acquisition_config})
    )
    authority_store = _ReadUnavailableCAS(store) if information == "contract" else store
    from polisyos.runtime.http.services.acquisition_authority_provider import (
        ProductionAcquisitionAuthorityProvider,
    )

    provider = ProductionAcquisitionAuthorityProvider(
        deployment_security=deployment,
        artifact_store=authority_store,
        event_log=event_log,
        idempotency_store=idempotency,
        execution_profile="governed",
    )
    return (
        store,
        event_log,
        idempotency,
        deployment,
        provider,
        contract_ref,
        current_ref,
        missing_information_ref,
    )


def _persist_provider_refusal(provider, store, monkeypatch):
    monkeypatch.setattr(authority, "_utcnow", lambda: fixtures.NOW)
    closure = _closure()
    request = fixtures.ACQUISITION_REQUEST
    proof = fixtures._proof()
    effects: list[object] = []
    gateway = provider.for_request(
        closure=closure,
        request=request,
        job_id=fixtures.JOB_ID,
        bound_permission=proof,
        effect_handler=effects.append,
    )
    operation, invocation, intent = AcquisitionActionService._action_tuple(
        closure, request
    )
    with authority.agent_action_authority_scope(gateway):
        decision = authority.produce_agent_action_authority_decision(
            bound_permission=proof,
            operation=operation,
            invocation=invocation,
            intent=intent,
        )
        persisted = gateway.persist_decision(decision)
    loaded = gateway.load_persisted_decision(
        str(persisted.write_result.cas_ref.artifact_id)
    )
    assert effects == []
    return (
        decision,
        loaded.decision,
        store.get_manifest(persisted.write_result.cas_ref.artifact_id),
    )


def test_provider_persists_exact_currentness_refusal_for_configured_noncurrent_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, _, _, provider, contract_ref, current_ref, _ = (
        _provider_with_selected_slot(tmp_path, current=False)
    )
    decision, loaded, manifest = _persist_provider_refusal(provider, store, monkeypatch)
    assert decision.outcome == "refused"
    assert "current_mandate_authority_not_established" in loaded.refusal_reasons
    assert "delegation_contract_not_persisted" not in loaded.refusal_reasons
    assert contract_ref in loaded.replay_input_refs
    assert current_ref in loaded.replay_input_refs
    manifest_inputs = {str(row.artifact_id): row for row in manifest.inputs}
    assert contract_ref in manifest_inputs
    assert current_ref in manifest_inputs
    assert all(row.manifest_profile_sha256 is None for row in manifest.inputs)
    assert "governed_admission_bundle_missing" in loaded.refusal_reasons


def test_provider_persists_exact_refusal_for_valid_but_wrong_role_currentness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, _, deployment, provider, contract_ref, current_ref, _ = (
        _provider_with_selected_slot(tmp_path, wrong_currentness_role=True)
    )
    signature = store.verify_signature(
        current_ref,
        deployment.acquisition_authority.verifier,
        strict_identity=True,
    )
    assert signature.status.value == "valid"
    assert signature.signer_identity == _OWNER_IDENTITY
    decision, loaded, manifest = _persist_provider_refusal(provider, store, monkeypatch)
    assert decision.outcome == "refused"
    assert "acquisition_mandate_trust_role_mismatch" in loaded.refusal_reasons
    assert "delegation_contract_not_persisted" not in loaded.refusal_reasons
    assert contract_ref in loaded.replay_input_refs
    assert current_ref in loaded.replay_input_refs
    manifest_refs = {str(row.artifact_id) for row in manifest.inputs}
    assert {contract_ref, current_ref} <= manifest_refs
    assert loaded.admission_bundle_ref is None


def test_missing_selected_information_ref_persists_item_local_refusal_without_fake_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, _, _, provider, contract_ref, current_ref, missing_ref = (
        _provider_with_selected_slot(tmp_path, information="missing")
    )
    assert missing_ref is not None
    before = {str(value) for value in store.iter_artifact_ids()}
    decision, loaded, manifest = _persist_provider_refusal(provider, store, monkeypatch)
    assert decision.outcome == "refused"
    assert "acquisition_decision_information_unverified" in loaded.refusal_reasons
    assert "delegation_contract_not_persisted" not in loaded.refusal_reasons
    assert contract_ref in loaded.replay_input_refs
    assert current_ref in loaded.replay_input_refs
    assert missing_ref in loaded.replay_input_refs
    assert missing_ref not in {str(row.artifact_id) for row in manifest.inputs}
    assert all(row.manifest_profile_sha256 is None for row in manifest.inputs)
    assert loaded.admission_bundle_ref is None
    new_ids = {str(value) for value in store.iter_artifact_ids()} - before
    new_kinds = {store.get_manifest(value).kind for value in new_ids}
    assert authority.AGENT_ACTION_ADMISSION_ARTIFACT_KIND not in new_kinds


def test_general_cas_read_error_is_not_converted_to_item_local_refusal(
    tmp_path: Path,
) -> None:
    store, _, _, _, provider, _, _, _ = _provider_with_selected_slot(
        tmp_path, information="contract"
    )
    with pytest.raises(OSError, match="synthetic CAS read dependency failure"):
        provider.for_request(
            closure=_closure(),
            request=fixtures.ACQUISITION_REQUEST,
            job_id=fixtures.JOB_ID,
            bound_permission=fixtures._proof(),
            effect_handler=lambda _call: pytest.fail("no gateway should be returned"),
        )
    assert store.iter_artifact_ids()
