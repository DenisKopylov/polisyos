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
