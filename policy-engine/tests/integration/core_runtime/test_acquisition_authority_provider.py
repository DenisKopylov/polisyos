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
        retained_paths: dict[Path, bool] = {}
        artifact_ids = tuple(provider._store.iter_artifact_ids())
        for artifact_id in artifact_ids:
            for path in provider._store.get_paths(artifact_id):
                retained_paths[path] = False
            retained_paths[provider._store._sig_path(artifact_id)] = True

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

        def retained_bytes() -> dict[str, dict[str, object]]:
            return {
                str(path): file_receipt(path, optional_signature=retained_paths[path])
                for path in sorted(retained_paths)
            }

        initial_bytes = retained_bytes()
        witness = {
            "cas_blob_manifest_signature_files": initial_bytes,
            "selected_artifact_denominator": len(artifact_ids),
            "selected_file_denominator": len(retained_paths),
            "configured_deployment": config.model_dump(mode="json"),
            "empty_decision_slot_deployment": missing.config.model_dump(mode="json"),
            "closure": kwargs["closure"].model_dump(mode="json"),
            "request": kwargs["request"].model_dump(mode="json"),
            "job_id": kwargs["job_id"],
            "decision_ref": kwargs["decision_ref"],
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
            "read_boundary": "Actual FileSystemCAS get_bytes/get_manifest/get_signature beneath unchanged guarded proxies, across instances",
            "outside_read_boundary": [
                "Existing diagnostic event store and DS9 exposure audit remain the same objects; their backing files are not claimed as CAS bytes.",
                "Deployment keys are factory-captured; configured/empty attestation states remain fixed.",
                "No connector or original worker callback is called in the measurement phases.",
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

            def traced(method_name, method):
                def read(store, artifact_id, *args, **kwargs):
                    attempt: dict[str, object] = {
                        "operation": method_name,
                        "artifact_id": str(artifact_id),
                        "status": "attempted",
                    }
                    actual_reads.append(attempt)
                    path = None
                    try:
                        identity = authority.artifacts.ArtifactID.model_validate(artifact_id)
                        blob, manifest = store.get_paths(identity)
                        path = {
                            "get_bytes": blob,
                            "get_manifest": manifest,
                            "get_signature": store._sig_path(identity),
                        }[method_name]
                        attempt["path"] = str(path)
                    except Exception as exc:
                        attempt["path_binding"] = {"status": "UNRUN", "error": repr(exc)}
                    try:
                        value = method(store, artifact_id, *args, **kwargs)
                    except Exception as exc:
                        attempt.update(status="failed_read", error=repr(exc))
                        raise
                    attempt["status"] = "read" if path is not None else "UNRUN"
                    if path is not None:
                        receipt = file_receipt(
                            path,
                            optional_signature=method_name == "get_signature" and value is None,
                        )
                        attempt["file_read"] = receipt
                        if receipt["status"] == "UNRUN":
                            attempt["status"] = "UNRUN"
                    return value

                return read

            for method_name in ("get_bytes", "get_manifest", "get_signature"):
                phase_patch.setattr(
                    store_type, method_name, traced(method_name, getattr(store_type, method_name))
                )
            enforcement = (
                ProductionAcquisitionAuthorityProvider._require_worker_decision_verification
            )
            try:
                for phase in ("baseline", "removed", "restored"):
                    before_bytes = retained_bytes()
                    effects.clear()
                    loaded_decisions.clear()
                    actual_reads.clear()
                    phase_patch.setattr(
                        ProductionAcquisitionAuthorityProvider,
                        "_require_worker_decision_verification",
                        (lambda self: None) if phase == "removed" else enforcement,
                    )
                    code = 0
                    failure = None
                    unexpected = None
                    try:
                        if before_bytes != initial_bytes or any(
                            row["status"] == "UNRUN" for row in before_bytes.values()
                        ):
                            raise RuntimeError(
                                "provider replay witness input changed or unreadable"
                            )
                        require_refusal()
                    except pytest.fail.Exception as exc:
                        code = 1
                        failure = str(exc)
                    except Exception as exc:
                        code = 2
                        failure = repr(exc)
                        unexpected = exc
                    final_bytes = retained_bytes()
                    complete = (
                        all(row["status"] != "UNRUN" for row in initial_bytes.values())
                        and before_bytes == initial_bytes
                        and final_bytes == initial_bytes
                        and all(row["status"] == "read" for row in actual_reads)
                        and unexpected is None
                    )
                    record["phases"].append(
                        {
                            "phase": phase,
                            "gate_code": code,
                            "failure": failure,
                            "effect_callbacks": len(effects),
                            "allowed_decision_refs": list(loaded_decisions),
                            "same_witness_sha256": witness_sha,
                            "actual_reads": list(actual_reads),
                            "retained_input_readback_sha256": hashlib.sha256(
                                json.dumps(final_bytes, sort_keys=True).encode()
                            ).hexdigest(),
                            "changed_or_failed_input_reads": {
                                path: {"before": before_bytes[path], "after": final_bytes[path]}
                                for path in initial_bytes
                                if before_bytes[path] != initial_bytes[path]
                                or final_bytes[path] != initial_bytes[path]
                                or initial_bytes[path]["status"] == "UNRUN"
                            },
                            "coverage": "COMPLETE" if complete else "UNRUN; partial coverage",
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
                        [kwargs["decision_ref"]] if phase == "removed" else []
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
