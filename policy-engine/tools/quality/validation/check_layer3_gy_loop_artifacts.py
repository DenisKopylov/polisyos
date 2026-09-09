#!/usr/bin/env python3
"""Validate committed Layer 3 GY loop artifacts and lifecycle registration."""

from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

import argparse
import ast
import contextlib
import difflib
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import uuid
from collections.abc import Iterator, Mapping
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Literal
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, Field

from tools.lib.timing import run_timed_entrypoint

if TYPE_CHECKING:
    from types import ModuleType

FAMILY_ID = "policy-design-case-layer3-gy-loop-artifacts"
HISTORY_FAMILY_ID = "policy-design-case-layer3-gy-loop-history-artifacts"
HISTORICAL_OUTCOME_RUN_SHA256 = (
    "sha256:5275653d5addcf48bc0b99948f49bcf44b7dc374322ecfbb6a98d5609004cf8a"
)
SOURCE_FAMILY_ID = "policy-design-case-layer3-gy-loop-source-artifacts"
MANIFEST_PATH = "architecture/policy_design_case/layer3_gy_slice0_fixture_manifest.json"
PROOFS_PATH = "architecture/policy_design_case/layer3_gy_production_loop_run_proofs.json"
GRADED_OUTCOME_PATH = (
    "architecture/policy_design_case/layer3_gy_graded_outcome_routing_report.json"
)
HISTORICAL_OUTCOME_RUN_PATH = "architecture/policy_design_case/layer3_gy_outcome_run.json"
OUTCOME_RUN_PATH = "architecture/policy_design_case/layer3_gy_outcome_run_v2.json"
OUTCOME_REPLAY_PATH = (
    "architecture/policy_design_case/layer3_gy_outcome_replay_proof.json"
)
BENCHMARK_PATH = "architecture/policy_design_case/layer3_gy_semantic_benchmark.json"


def declared_outputs() -> list[str]:
    """Return the generated artifacts this validator writes in --write mode."""

    return [
        PROOFS_PATH,
        GRADED_OUTCOME_PATH,
        OUTCOME_RUN_PATH,
        OUTCOME_REPLAY_PATH,
    ]


def validate(
    repo_root: Path,
    *,
    write: bool = False,
    corrupt_field_drift_check: bool = False,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    _ensure_src_path(repo_root)
    generated = tomllib.loads(
        (repo_root / "architecture/generated_artifacts.toml").read_text(encoding="utf-8")
    )
    _validate_loop_epoch_partition(repo_root, generated, issues)
    if issues:
        return {
            "status": "fail",
            "issues": issues,
            "checked_artifacts": [*declared_outputs(), HISTORICAL_OUTCOME_RUN_PATH],
            "family_id": FAMILY_ID,
            "source_family_id": SOURCE_FAMILY_ID,
            "history_family_id": HISTORY_FAMILY_ID,
            "write": write,
        }
    families = {family.get("id"): family for family in generated.get("family", [])}
    family = families.get(FAMILY_ID)
    if not family:
        issues.append({"code": "layer3_gy_generated_artifacts_family_missing"})
    else:
        outputs = set(family.get("outputs") or [])
        expected_outputs = set(declared_outputs())
        if outputs != expected_outputs:
            issues.append(
                {
                    "code": "layer3_gy_generated_output_scope_drift",
                    "expected": ",".join(sorted(expected_outputs)),
                    "actual": ",".join(sorted(outputs)),
                }
            )
        if family.get("stale_output_behavior") != "fail":
            issues.append({"code": "layer3_gy_stale_output_not_fail_closed"})
        if "--check" not in list(family.get("check_command") or []):
            issues.append({"code": "layer3_gy_check_command_missing_check_mode"})
        regenerate_commands = " ".join(family.get("regenerate_commands") or [])
        if "--write" not in regenerate_commands:
            issues.append({"code": "layer3_gy_regenerate_command_missing_write_mode"})
    source_family = families.get(SOURCE_FAMILY_ID)
    if not source_family:
        issues.append({"code": "layer3_gy_loop_source_family_missing"})
    else:
        source_outputs = set(source_family.get("outputs") or [])
        if source_outputs != {MANIFEST_PATH, BENCHMARK_PATH}:
            issues.append(
                {
                    "code": "layer3_gy_loop_source_output_scope_drift",
                    "expected": ",".join(sorted((MANIFEST_PATH, BENCHMARK_PATH))),
                    "actual": ",".join(sorted(source_outputs)),
                }
            )
        if source_family.get("lifecycle") != "source_committed":
            issues.append({"code": "layer3_gy_loop_source_family_lifecycle_drift"})
        _validate_source_artifact_integrity(repo_root, source_family, issues)

    manifest = _read_json(repo_root / MANIFEST_PATH, issues)
    if manifest:
        fixture_ids = {
            fixture.get("fixture_id")
            for fixture in manifest.get("fixtures", [])
            if isinstance(fixture, dict)
        }
        required = {
            "ua_msme_credit_worldbank_measurement",
            "tourism_local_development_ceiling_probe",
        }
        missing = sorted(required - fixture_ids)
        if missing:
            issues.append({"code": "layer3_gy_slice0_fixture_missing", "missing": ",".join(missing)})
        for fixture in manifest.get("fixtures", []):
            if not isinstance(fixture, dict):
                issues.append({"code": "layer3_gy_fixture_not_object"})
                continue
            for field in (
                "construct_scope_query",
                "expected_terminal",
                "forbidden_terminals",
                "expected_producer_root_kind",
            ):
                if not fixture.get(field):
                    issues.append(
                        {
                            "code": "layer3_gy_fixture_field_missing",
                            "fixture_id": str(fixture.get("fixture_id")),
                            "field": field,
                        }
                    )

    proofs = {} if write else _read_json(repo_root / PROOFS_PATH, issues)
    if proofs and not write:
        proof_items = proofs.get("proofs")
        if not isinstance(proof_items, list):
            issues.append({"code": "layer3_gy_proofs_not_list"})
        elif not proof_items:
            issues.append({"code": "layer3_gy_proofs_empty"})
        else:
            if len(proof_items) < 2:
                issues.append({"code": "layer3_gy_proofs_missing_two_slice0_paths"})
            for index, proof in enumerate(proof_items):
                if not isinstance(proof, dict):
                    issues.append(
                        {"code": "layer3_gy_proof_not_object", "index": str(index)}
                    )
                    continue
                _validate_production_loop_proof(index, proof, issues)
    graded_report = {} if write else _read_json(repo_root / GRADED_OUTCOME_PATH, issues)
    if graded_report and not write:
        _validate_graded_outcome_report(graded_report, issues)
    outcome_run = {} if write else _read_json(repo_root / OUTCOME_RUN_PATH, issues)
    outcome_replay = {} if write else _read_json(repo_root / OUTCOME_REPLAY_PATH, issues)
    if outcome_run and outcome_replay and not write:
        _validate_outcome_terminal_and_replay(outcome_run, outcome_replay, issues)
        _validate_gx_status_fields(outcome_run, issues)
    benchmark = _read_json(repo_root / BENCHMARK_PATH, issues)
    if benchmark:
        for field in ("label_owner", "expert_author", "reviewer", "provenance", "thresholds"):
            if not benchmark.get(field):
                issues.append({"code": "layer3_gy_benchmark_field_missing", "field": field})
        thresholds = benchmark.get("thresholds") or {}
        pre_decision = thresholds.get("pre_decision") if isinstance(thresholds, dict) else None
        for field in ("precision_at_5", "recall_at_known_seeds"):
            if not isinstance(pre_decision, dict) or field not in pre_decision:
                issues.append(
                    {"code": "layer3_gy_benchmark_threshold_missing", "field": field}
                )
        labels = benchmark.get("labels")
        if not isinstance(labels, list) or not labels:
            issues.append({"code": "layer3_gy_benchmark_labels_missing"})
        else:
            for label in labels:
                if not isinstance(label, dict):
                    issues.append({"code": "layer3_gy_benchmark_label_not_object"})
                    continue
                for field in (
                    "owner_expert",
                    "reviewer",
                    "known_admissible_dataset_ids",
                    "negative_control_dataset_ids",
                ):
                    if field not in label:
                        issues.append(
                            {
                                "code": "layer3_gy_benchmark_label_field_missing",
                                "fixture_id": str(label.get("fixture_id")),
                                "field": field,
                            }
                        )

    if any(
        issue.get("code")
        in {
            "layer3_gy_source_output_integrity_drift",
            "layer3_gy_source_output_missing",
            "layer3_gy_source_integrity_digest_missing",
            "layer3_gy_source_integrity_manifest_missing",
        }
        for issue in issues
    ):
        return {
            "status": "fail",
            "issues": issues,
            "checked_artifacts": [
                MANIFEST_PATH,
                PROOFS_PATH,
                GRADED_OUTCOME_PATH,
                OUTCOME_RUN_PATH,
                OUTCOME_REPLAY_PATH,
                BENCHMARK_PATH,
            ],
            "family_id": FAMILY_ID,
            "source_family_id": SOURCE_FAMILY_ID,
            "write": write,
        }

    try:
        live_payloads = build_live_loop_artifacts(repo_root)
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as error:
        issues.append(
            {
                "code": "layer3_gy_live_recomputation_failed",
                "reason": type(error).__name__ + ":" + str(error),
            }
        )
        return {
            "status": "fail",
            "issues": issues,
            "checked_artifacts": declared_outputs(),
            "family_id": FAMILY_ID,
            "source_family_id": SOURCE_FAMILY_ID,
            "write": write,
        }
    live_proofs = live_payloads[PROOFS_PATH]
    live_graded_report = live_payloads[GRADED_OUTCOME_PATH]
    live_outcome_run = live_payloads[OUTCOME_RUN_PATH]
    live_outcome_replay = live_payloads[OUTCOME_REPLAY_PATH]
    live_proof_items = live_proofs.get("proofs")
    if isinstance(live_proof_items, list):
        for index, proof in enumerate(live_proof_items):
            if isinstance(proof, dict):
                _validate_production_loop_proof(index, proof, issues)
            else:
                issues.append({"code": "layer3_gy_live_proof_not_object", "index": str(index)})
    else:
        issues.append({"code": "layer3_gy_live_proofs_not_list"})
    _validate_graded_outcome_report(live_graded_report, issues)
    validate_outcome_run(live_outcome_run, live_outcome_replay, issues)
    if corrupt_field_drift_check:
        corrupt_issues: list[dict[str, str]] = []
        corrupted = json.loads(json.dumps(live_outcome_run))
        corrupted["search_exit_contract"]["terminal_state"]["reason"] = (
            "corrupt-field-drift-check"
        )
        validate_outcome_run(corrupted, live_outcome_replay, corrupt_issues)
        if any(
            issue.get("code") == "layer3_gy_outcome_replay_output_drift"
            for issue in corrupt_issues
        ):
            issues.append({"code": "layer3_gy_graded_outcome_corrupt_field_drift_detected"})
        else:
            issues.append({"code": "layer3_gy_graded_outcome_corrupt_field_drift_not_detected"})
    final_payloads = _freeze_final_loop_family(live_payloads)
    if write:
        for relative_path, payload in final_payloads.items():
            output_path = repo_root / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(serialize_loop_artifact(payload))
    else:
        _compare_current_loop_outputs(
            {
                PROOFS_PATH: proofs,
                GRADED_OUTCOME_PATH: graded_report,
                OUTCOME_RUN_PATH: outcome_run,
                OUTCOME_REPLAY_PATH: outcome_replay,
            },
            final_payloads,
            issues,
        )

    from tools.quality.validation import check_layer3_gy_generated_public_lifecycle_audit

    lifecycle_report = (
        check_layer3_gy_generated_public_lifecycle_audit.validate_gy_lifecycle_registry(
            repo_root
        )
    )
    issues.extend(lifecycle_report["issues"])

    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "checked_artifacts": [
            MANIFEST_PATH,
            PROOFS_PATH,
            GRADED_OUTCOME_PATH,
            OUTCOME_RUN_PATH,
            OUTCOME_REPLAY_PATH,
            BENCHMARK_PATH,
        ],
        "family_id": FAMILY_ID,
        "source_family_id": SOURCE_FAMILY_ID,
        "write": write,
    }


class LoopFamilyCustodyError(ValueError):
    """Refuse an unbound, unreadable or changed canonical loop population."""


class CanonicalLoopRequest(BaseModel):
    """Declare one existing producer invocation, including its catalog scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fixture_id: str = Field(min_length=1)
    catalog_mode: Literal["slice0_fixture", "production"]

    def identity(self) -> str:
        """Return the identity of the complete invocation declaration."""
        return (
            "sha256:"
            + hashlib.sha256(serialize_loop_artifact(self.model_dump(mode="json"))).hexdigest()
        )

    def http_request_id(self) -> str:
        """Return the existing real route request id."""
        return f"gy-loop-{self.catalog_mode}-{_slug(self.fixture_id)}"

    def http_body(self, root_ref: str) -> dict[str, Any]:
        """Return the complete existing request body with its actual CAS input."""
        return {
            "data_source": {"data_snapshot_ref": root_ref},
            "params": {"slice0_fixture_id": self.fixture_id},
        }


def canonical_loop_requests() -> tuple[CanonicalLoopRequest, ...]:
    """Return the single source of the existing complete producer population."""
    return (
        CanonicalLoopRequest(
            fixture_id="ua_msme_credit_worldbank_measurement",
            catalog_mode="slice0_fixture",
        ),
        CanonicalLoopRequest(
            fixture_id="tourism_local_development_ceiling_probe",
            catalog_mode="slice0_fixture",
        ),
        CanonicalLoopRequest(
            fixture_id="ua_msme_credit_worldbank_measurement",
            catalog_mode="production",
        ),
    )


def serialize_loop_artifact(payload: object) -> bytes:
    """Serialize the exact bytes shared by canonical writing and GX overlays."""
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    ).encode("utf-8")


_LIVE_LOOP_ISSUER = object()


def _nonempty_ring2_models(value: object) -> list[BaseModel]:
    """Derive the protected quantity from actual model declarations recursively."""
    found: list[BaseModel] = []
    if isinstance(value, BaseModel):
        if any(
            getattr(value, name) not in (None, [], {})
            for name in getattr(type(value), "ring2_fields", frozenset())
        ):
            found.append(value)
        for name in type(value).model_fields:
            found.extend(_nonempty_ring2_models(getattr(value, name)))
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(_nonempty_ring2_models(item))
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            found.extend(_nonempty_ring2_models(item))
    return found


class _VerifiedWorkspaceExitReadback:
    """Keep the actual execution and reader reconstruction bound to identical bytes."""

    def __init__(
        self, actual: BaseModel, decoded: BaseModel, raw: dict[str, Any], *, issuer: object
    ) -> None:
        if issuer is not _LIVE_LOOP_ISSUER:
            raise LoopFamilyCustodyError("live_loop_exit_readback_not_verified")
        self.__actual = actual
        self.__decoded = decoded
        self.__payload = serialize_loop_artifact(raw)
        self._require_contract(raw)

    def _require_contract(self, raw: dict[str, Any]) -> None:
        if any(
            payload != self.__payload
            for payload in (
                serialize_loop_artifact(raw),
                serialize_loop_artifact(self.__actual.model_dump(mode="json")),
                serialize_loop_artifact(self.__decoded.model_dump(mode="json")),
            )
        ):
            raise LoopFamilyCustodyError("live_loop_verified_exit_changed")


class _LiveLoopExitCapture:
    """Observe real owner calls; caller-created models cannot mint readback custody."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self.__envelopes: list[tuple[BaseModel, bytes]] = []
        self.__contract: tuple[BaseModel, bytes, str] | None = None

    def observe_envelope(self, loop: Any, envelope: BaseModel) -> None:
        from polisyos.pdc import ArtifactEnvelope

        if loop._artifact_store is not self.store or type(envelope) is not ArtifactEnvelope:
            raise LoopFamilyCustodyError("live_loop_verifier_execution_owner_mismatch")
        self.__envelopes.append(
            (envelope, serialize_loop_artifact(envelope.model_dump(mode="json")))
        )

    def observe_contract(self, contract: BaseModel, job_id: str) -> None:
        from polisyos.runtime.quality.workspace.loop import WorkspaceSearchExitContract

        if self.__contract is not None or type(contract) is not WorkspaceSearchExitContract:
            raise LoopFamilyCustodyError("live_loop_contract_execution_not_unique")
        self.__contract = (
            contract,
            serialize_loop_artifact(contract.model_dump(mode="json")),
            job_id,
        )

    def verify(self, raw: dict[str, Any], job_id: str) -> _VerifiedWorkspaceExitReadback:
        from polisyos.runtime.quality.workspace.loop import WorkspaceSearchExitContract

        if self.__contract is None:
            raise LoopFamilyCustodyError("live_loop_actual_contract_execution_unobserved")
        actual, snapshot, observed_job = self.__contract
        if (
            observed_job != job_id
            or serialize_loop_artifact(raw) != snapshot
            or serialize_loop_artifact(actual.model_dump(mode="json")) != snapshot
        ):
            raise LoopFamilyCustodyError("live_loop_actual_contract_execution_drift")
        for envelope, before in self.__envelopes:
            if serialize_loop_artifact(envelope.model_dump(mode="json")) != before:
                raise LoopFamilyCustodyError("live_loop_observed_verifier_object_changed")
        # Substituting a protected parent must never conceal an unobserved
        # protected child, including a nested promotion-result field.
        for protected in _nonempty_ring2_models(actual):
            if not any(protected is envelope for envelope, _ in self.__envelopes):
                raise LoopFamilyCustodyError("live_loop_ring2_verifier_object_unobserved")

        def restore(value: object) -> object:
            if isinstance(value, dict):
                encoded = serialize_loop_artifact(value)
                for envelope, before in self.__envelopes:
                    if encoded == before:
                        return envelope
                return {key: restore(item) for key, item in value.items()}
            if isinstance(value, list):
                return [restore(item) for item in value]
            return value

        # This is a reader: it receives no writer role and cannot mint authority.
        decoded = WorkspaceSearchExitContract.model_validate(restore(json.loads(snapshot)))
        if serialize_loop_artifact(decoded.model_dump(mode="json")) != snapshot:
            raise LoopFamilyCustodyError("live_loop_exit_reader_roundtrip_drift")
        return _VerifiedWorkspaceExitReadback(actual, decoded, raw, issuer=_LIVE_LOOP_ISSUER)


class _VerifiedLoopObservation(dict):
    """Outward JSON view backed by a whole immutable, store-verified snapshot."""

    def __init__(
        self,
        observation: dict[str, Any],
        request: CanonicalLoopRequest,
        custody: dict[str, Any],
        *,
        exit_readback: _VerifiedWorkspaceExitReadback,
        issuer: object,
    ) -> None:
        if issuer is not _LIVE_LOOP_ISSUER:
            raise LoopFamilyCustodyError("live_loop_observation_verifier_not_consulted")
        self.__payload = serialize_loop_artifact(observation)
        self.__request = serialize_loop_artifact(request.model_dump(mode="json"))
        self.__custody = serialize_loop_artifact(custody)
        self.__exit_readback = exit_readback
        exit_readback._require_contract(observation["search_exit_contract"])
        super().__init__(json.loads(self.__payload))

    def _checked_snapshot(self) -> tuple[CanonicalLoopRequest, dict[str, Any]]:
        if serialize_loop_artifact(self) != self.__payload:
            raise LoopFamilyCustodyError("live_loop_observation_changed_after_verification")
        frozen = json.loads(self.__payload)
        self.__exit_readback._require_contract(frozen["search_exit_contract"])
        return CanonicalLoopRequest.model_validate_json(self.__request), frozen

    def _checked_exit_readback(self) -> _VerifiedWorkspaceExitReadback:
        self.__exit_readback._require_contract(json.loads(self.__payload)["search_exit_contract"])
        return self.__exit_readback


def _pre_gx_family_bytes(payloads: dict[str, dict[str, Any]]) -> bytes:
    # Deserialize once to a plain immutable-byte-derived snapshot. Independent
    # current GX admission owns exactly these two self-referential fields.
    frozen = json.loads(serialize_loop_artifact(payloads))
    outcome = frozen[OUTCOME_RUN_PATH]
    if not isinstance(outcome, dict):
        raise LoopFamilyCustodyError("live_loop_outcome_member_not_object")
    outcome.pop("gx_validator_status", None)
    outcome.pop("gx_validation", None)
    return serialize_loop_artifact(frozen)


class _VerifiedLoopFamily(dict):
    """Complete producer projection bound to admitted invocation observations."""

    def __init__(
        self,
        payloads: dict[str, dict[str, Any]],
        *,
        exit_readback: _VerifiedWorkspaceExitReadback,
        issuer: object,
    ) -> None:
        if issuer is not _LIVE_LOOP_ISSUER:
            raise LoopFamilyCustodyError("live_loop_family_producer_not_consulted")
        self.__payload = _pre_gx_family_bytes(payloads)
        self.__exit_readback = exit_readback
        exit_readback._require_contract(payloads[OUTCOME_RUN_PATH]["search_exit_contract"])
        super().__init__(json.loads(serialize_loop_artifact(payloads)))

    def _checked_snapshot(self) -> dict[str, dict[str, Any]]:
        if _pre_gx_family_bytes(self) != self.__payload:
            raise LoopFamilyCustodyError("live_loop_family_changed_after_verification")
        frozen = json.loads(self.__payload)
        self.__exit_readback._require_contract(frozen[OUTCOME_RUN_PATH]["search_exit_contract"])
        return frozen

    def _checked_exit_readback(self) -> _VerifiedWorkspaceExitReadback:
        self.__exit_readback._require_contract(
            json.loads(self.__payload)[OUTCOME_RUN_PATH]["search_exit_contract"]
        )
        return self.__exit_readback


def _read_actual_cas(store: Any, ref: str) -> tuple[bytes, Any, Any]:
    from polisyos.core.canon import from_canonical_bytes

    raw = store.get_bytes(ref)
    manifest = store.get_manifest(ref)
    manifest_raw = store.get_manifest_bytes(ref)
    digest = hashlib.sha256(raw).hexdigest()
    if (
        ref != f"sha256:{digest}"
        or str(manifest.artifact_id) != ref
        or manifest.byte_size != len(raw)
        or manifest.integrity.sha256 != digest
    ):
        raise LoopFamilyCustodyError("observation_cas_identity_or_bytes_drift")
    # The manifest is read back as an actual object and actual bytes. It is not
    # replaced by a ref description or the arguments originally passed to put.
    if not manifest_raw:
        raise LoopFamilyCustodyError("observation_cas_manifest_absent")
    return raw, manifest, from_canonical_bytes(raw)


def _compare_actual_cas_payload(
    store: Any, ref: str, payload: object, *, kind: str, schema: str
) -> tuple[Any, dict[str, Any]]:
    from polisyos.core.canon import CanonSpec, to_canonical_bytes

    raw, manifest, decoded = _read_actual_cas(store, ref)
    if (
        manifest.kind != kind
        or manifest.media_type != "application/json"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != schema
        or manifest.artifact_schema.version != "1.0"
        or manifest.canon is None
    ):
        raise LoopFamilyCustodyError("observation_cas_contract_identity_drift")
    spec = CanonSpec(**manifest.canon.model_dump())
    if raw != to_canonical_bytes(payload, spec):
        raise LoopFamilyCustodyError("observation_cas_payload_drift")
    return decoded, {
        "artifact_ref": ref,
        "payload_sha256": f"sha256:{hashlib.sha256(raw).hexdigest()}",
        "byte_size": len(raw),
        "kind": manifest.kind,
        "schema": manifest.artifact_schema.model_dump(mode="json"),
    }


def _verify_live_loop_observation(
    observation: dict[str, Any],
    *,
    request: CanonicalLoopRequest,
    http_request: Any,
    root_ref: str,
    root_payload: dict[str, Any],
    service: Any,
    catalog_graph: Any,
    catalog_before: tuple[Any, ...],
    exit_capture: _LiveLoopExitCapture,
) -> _VerifiedLoopObservation:
    """Reconcile the actual request/job/CAS/replay before the store is closed."""
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.contracts.control import WorkflowRunRequest
    from polisyos.runtime.http.services.control import run_lifecycle
    from polisyos.runtime.quality.authority import (
        OutcomeReplayProof,
        ProductionLoopRunProof,
        build_outcome_replay_proof,
    )

    frozen = json.loads(serialize_loop_artifact(observation))
    proof = ProductionLoopRunProof.model_validate(frozen["proof"])
    replay = OutcomeReplayProof.model_validate(frozen["outcome_replay_proof"])
    actual_request = WorkflowRunRequest.model_validate(http_request)
    if (
        serialize_loop_artifact(http_request)
        != serialize_loop_artifact(request.http_body(root_ref))
        or actual_request.params != {"slice0_fixture_id": request.fixture_id}
        or frozen["fixture_id"] != request.fixture_id
        or proof.http_request_id != request.http_request_id()
    ):
        raise LoopFamilyCustodyError("live_loop_request_identity_drift")
    job = service._control_store.get_job(proof.job_id)
    if job is None or job.state != "completed" or job.run_id != proof.run_id:
        raise LoopFamilyCustodyError("live_loop_durable_job_unavailable")
    transitions = service._control_store.list_job_state_transitions(proof.job_id)
    if (
        transitions != ["pending", "running", "completed"]
        or transitions != proof.control_store_state_transitions
    ):
        raise LoopFamilyCustodyError("live_loop_durable_transitions_drift")
    for projected, durable in (
        ("proof", "production_loop_run_proof"),
        ("search_exit_contract", "search_exit_contract"),
        ("outcome_replay_proof", "outcome_replay_proof"),
        ("artifacts_index", "artifacts_index"),
    ):
        if durable not in job.progress or serialize_loop_artifact(
            frozen[projected]
        ) != serialize_loop_artifact(job.progress[durable]):
            raise LoopFamilyCustodyError("live_loop_durable_payload_drift:" + durable)
    if catalog_graph._store._fetch_source_identities() != catalog_before:
        raise LoopFamilyCustodyError("live_loop_catalog_changed_during_run")
    store = service._artifact_store
    if not job.payload_ref:
        raise LoopFamilyCustodyError("live_loop_durable_request_missing")
    _, _, job_payload = _read_actual_cas(store, job.payload_ref)
    _compare_actual_cas_payload(
        store,
        job.payload_ref,
        job_payload,
        kind="runtime.control_job_payload.workflow_run",
        schema="polisyos.runtime.ControlJobPayload",
    )
    state = job_payload["state_payload"]
    ds_key, ds_value = run_lifecycle._resolve_data_source(actual_request.data_source)
    expected_inputs = {
        ds_key: run_lifecycle._make_artifact_ref(
            ds_value, kind=run_lifecycle._DATA_SOURCE_KEYS[ds_key]
        ).model_dump(mode="json")
    }
    for field, kind in run_lifecycle._OPTIONAL_INPUT_KEYS.items():
        value = getattr(actual_request, field)
        if value is not None:
            expected_inputs[field] = run_lifecycle._make_artifact_ref(value, kind=kind).model_dump(
                mode="json"
            )
    if (
        state["run_id"] != proof.run_id
        or state["params"] != actual_request.params
        or serialize_loop_artifact(state["inputs"]) != serialize_loop_artifact(expected_inputs)
        or job_payload["checkpoint_policy"] != actual_request.checkpoint_policy
        or job.requested_execution_profile != actual_request.execution_profile
    ):
        raise LoopFamilyCustodyError("live_loop_actual_request_payload_drift")
    expected_input_refs = [
        str(ArtifactRef.model_validate(value).artifact_id) for value in expected_inputs.values()
    ]
    if (
        proof.input_artifacts != expected_input_refs
        or root_ref not in expected_input_refs
        or ds_value != root_ref
    ):
        raise LoopFamilyCustodyError("live_loop_actual_request_input_closure_drift")
    _compare_actual_cas_payload(
        store,
        root_ref,
        root_payload,
        kind="gy.loop.proof.root",
        schema="polisyos.gy.loop.proof.root",
    )
    checks = []
    contract, check = _compare_actual_cas_payload(
        store,
        proof.output_search_exit_contract_ref,
        frozen["search_exit_contract"],
        kind="pdc.gy.search_exit_contract",
        schema="polisyos.pdc.gy.SearchExitContract",
    )
    checks.append(check)
    _, check = _compare_actual_cas_payload(
        store,
        frozen["proof_ref"],
        frozen["proof"],
        kind="pdc.gy.production_loop_run_proof",
        schema="polisyos.runtime.ProductionLoopRunProof",
    )
    checks.append(check)
    if proof.output_replay_proof_ref is None:
        raise LoopFamilyCustodyError("live_loop_replay_ref_missing")
    _, check = _compare_actual_cas_payload(
        store,
        proof.output_replay_proof_ref,
        frozen["outcome_replay_proof"],
        kind="pdc.gy.outcome_replay_proof",
        schema="polisyos.runtime.OutcomeReplayProof",
    )
    checks.append(check)
    if len(proof.input_artifacts) != len(set(proof.input_artifacts)):
        raise LoopFamilyCustodyError("live_loop_duplicate_input_identity")
    if len(proof.output_cas_refs) != len(set(proof.output_cas_refs)):
        raise LoopFamilyCustodyError("live_loop_duplicate_output_identity")
    inputs = {ref: _read_actual_cas(store, ref)[2] for ref in proof.input_artifacts}
    for ref in proof.output_cas_refs:
        _read_actual_cas(store, ref)
    expected_replay = build_outcome_replay_proof(
        case_id=replay.case_id,
        input_payloads=inputs,
        search_exit_contract=contract,
        output_cas_refs=[
            ref for ref in proof.output_cas_refs if ref != proof.output_replay_proof_ref
        ],
    )
    if expected_replay != replay:
        raise LoopFamilyCustodyError("live_loop_replay_recomputation_drift")
    issues: list[dict[str, str]] = []
    _validate_production_loop_proof(0, frozen["proof"], issues)
    if issues:
        raise LoopFamilyCustodyError("live_loop_packet_verification_failed:" + json.dumps(issues))
    if exit_capture.store is not store:
        raise LoopFamilyCustodyError("live_loop_exit_capture_store_mismatch")
    exit_readback = exit_capture.verify(frozen["search_exit_contract"], proof.job_id)
    custody = {
        "request": request.model_dump(mode="json"),
        "request_identity": request.identity(),
        "http_request": actual_request.model_dump(mode="json"),
        "job_payload_ref": job.payload_ref,
        "checked_cas": checks,
        "catalog_before_and_after": [
            value.model_dump(mode="json") if hasattr(value, "model_dump") else value
            for value in catalog_before
        ],
    }
    return _VerifiedLoopObservation(
        frozen, request, custody, exit_readback=exit_readback, issuer=_LIVE_LOOP_ISSUER
    )


def _assemble_live_loop_family(
    observations: list[_VerifiedLoopObservation],
) -> _VerifiedLoopFamily:
    """Project the complete actual canonical population without re-executing it."""
    requests = canonical_loop_requests()
    expected = [request.identity() for request in requests]
    if not expected or len(expected) != len(set(expected)):
        raise LoopFamilyCustodyError("live_loop_canonical_request_population_invalid")
    by_identity: dict[str, dict[str, Any]] = {}
    exit_readbacks: dict[str, _VerifiedWorkspaceExitReadback] = {}
    jobs: set[str] = set()
    for observation in observations:
        if type(observation) is not _VerifiedLoopObservation:
            raise LoopFamilyCustodyError("live_loop_observation_not_store_verified")
        request, frozen = observation._checked_snapshot()
        identity = request.identity()
        if identity in by_identity or frozen["proof"]["job_id"] in jobs:
            raise LoopFamilyCustodyError("live_loop_population_duplicate_identity")
        by_identity[identity] = frozen
        exit_readbacks[identity] = observation._checked_exit_readback()
        jobs.add(frozen["proof"]["job_id"])
    if set(by_identity) != set(expected):
        raise LoopFamilyCustodyError("live_loop_population_identity_set_drift")
    slice0_observations = [
        by_identity[request.identity()]
        for request in requests
        if request.catalog_mode == "slice0_fixture"
    ]
    production_observations = [
        by_identity[request.identity()]
        for request in requests
        if request.catalog_mode == "production"
    ]
    # The current artifact contract has one outcome/replay object. Refuse an
    # expanded population instead of silently choosing one member.
    if not slice0_observations or len(production_observations) != 1:
        raise LoopFamilyCustodyError("live_loop_current_family_cardinality_unsupported")
    outcome_observation = production_observations[0]
    proofs = [observation["proof"] for observation in slice0_observations]
    outcome_run = _build_outcome_run(outcome_observation)
    outcome_replay = {
        "schema_version": "policyos.policy_design_case.layer3_gy.outcome_replay_artifact.v1",
        "owner": "team-runtime-quality",
        "proof_source": "production_http_route_recomputed",
        "case_id": "ua-msme-affordable-loans-2022",
        "replay_proof": outcome_observation["outcome_replay_proof"],
    }
    payloads = {
        PROOFS_PATH: {
            "schema_version": "policyos.policy_design_case.layer3_gy.production_loop_run_proofs.v1",
            "owner": "team-runtime-quality",
            "proof_source": "durable_worker_recomputed",
            "proofs": proofs,
        },
        GRADED_OUTCOME_PATH: _build_graded_outcome_report(production_observations),
        OUTCOME_RUN_PATH: outcome_run,
        OUTCOME_REPLAY_PATH: outcome_replay,
    }
    production_request = next(
        request for request in requests if request.catalog_mode == "production"
    )
    exit_readback = exit_readbacks[production_request.identity()]
    _validate_pre_gx_family_members(payloads, exit_readback=exit_readback)
    return _VerifiedLoopFamily(payloads, exit_readback=exit_readback, issuer=_LIVE_LOOP_ISSUER)


def _validate_pre_gx_family_members(
    payloads: dict[str, dict[str, Any]], *, exit_readback: _VerifiedWorkspaceExitReadback
) -> None:
    from polisyos.runtime.quality.authority import OutcomeReplayProof, ProductionLoopRunProof

    declared = declared_outputs()
    if len(declared) != len(set(declared)) or set(payloads) != set(declared):
        raise LoopFamilyCustodyError("live_loop_family_output_identity_set_drift")
    if any(not isinstance(value, dict) or not value for value in payloads.values()):
        raise LoopFamilyCustodyError("live_loop_family_unreadable_member")
    proofs = payloads[PROOFS_PATH]["proofs"]
    if not isinstance(proofs, list) or not proofs:
        raise LoopFamilyCustodyError("live_loop_family_empty_or_invalid_proofs")
    for proof in proofs:
        ProductionLoopRunProof.model_validate(proof)
    outcome, replay_artifact = payloads[OUTCOME_RUN_PATH], payloads[OUTCOME_REPLAY_PATH]
    ProductionLoopRunProof.model_validate(outcome["production_loop_run_proof"])
    exit_readback._require_contract(outcome["search_exit_contract"])
    OutcomeReplayProof.model_validate(replay_artifact["replay_proof"])
    issues: list[dict[str, str]] = []
    _validate_graded_outcome_report(payloads[GRADED_OUTCOME_PATH], issues)
    _validate_outcome_terminal_and_replay(outcome, replay_artifact, issues)
    if issues:
        raise LoopFamilyCustodyError("live_loop_family_member_invalid:" + json.dumps(issues))


def freeze_pre_gx_output_family(
    payloads: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Return only the exact sealed basis; never reread the mutable caller after admission.

    Deserialized or caller-constructed packets have no live admission. Existing
    committed validation obtains the basis by rerunning the canonical producer.
    This validates the pre-GX basis only; current GX admission remains separate.
    """
    if type(payloads) not in {_VerifiedLoopFamily, _GXCheckedLoopFamily}:
        raise LoopFamilyCustodyError("live_loop_family_not_canonical_producer_verified")
    frozen = payloads._checked_snapshot()
    _validate_pre_gx_family_members(frozen, exit_readback=payloads._checked_exit_readback())
    return frozen


def validate_pre_gx_output_family(
    payloads: dict[str, dict[str, Any]],
    issues: list[dict[str, str]],
) -> None:
    """Report a refused live basis without minting admission for caller-authored JSON."""
    try:
        freeze_pre_gx_output_family(payloads)
    except (ValueError, TypeError, KeyError) as error:
        issues.append({"code": "layer3_gy_pre_gx_family_custody_failed", "reason": str(error)})


_GX_EXECUTION_ISSUER = object()


def _loop_gx_caller_basis(repo_root: Path) -> dict[str, Any]:
    """Reconcile every current Python path and relevant literal call/reference."""
    import io
    import tokenize

    roots = ("src", "tools", "tests")
    paths = {path for root in roots for path in (repo_root / root).rglob("*.py")}
    independent = {
        Path(directory) / name
        for root in roots
        for directory, _, names in os.walk(repo_root / root)
        for name in names
        if name.endswith(".py")
    }
    if not paths or paths != independent:
        raise ValueError("loop_gx_caller_denominator_unresolved")
    functions = {
        "_assemble_live_loop_family",
        "_attach_post_gx_result",
        "_gx_child",
        "_run_durable_workspace_loop_observation",
        "_run_full_gx_on_new_artifacts",
        "build_live_loop_artifacts",
        "validate_layer3_gx_hardening",
        "validate_outcome_run",
    }
    owner_types = set()
    references = []
    snapshots = {}
    ast_terminals, token_terminals = (set(), set())

    def scan(path: Path) -> None:
        relative = path.relative_to(repo_root).as_posix()
        raw = path.read_bytes()
        source = raw.decode("utf-8")
        source_lines = source.splitlines()
        snapshots[relative] = "sha256:" + hashlib.sha256(raw).hexdigest()
        tree = ast.parse(source, filename=relative)
        scopes: list[str] = []
        aliases: list[dict[str, str]] = [{}]

        def resolve(node: ast.AST | None) -> str:
            if isinstance(node, ast.Name):
                for table in reversed(aliases):
                    if node.id in table:
                        return table[node.id]
                return node.id
            if isinstance(node, ast.Attribute):
                return resolve(node.value) + "." + node.attr
            if isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "getattr"
                    and (len(node.args) >= 2)
                ):
                    member = node.args[1]
                    if isinstance(member, ast.Constant) and isinstance(member.value, str):
                        return resolve(node.args[0]) + "." + member.value
                target = resolve(node.func)
                return target if target.rsplit(".", 1)[-1] in owner_types else "<returned>"
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
                choices = [resolve(node.left), resolve(node.right)]
                return next(
                    (item for item in choices if item.rsplit(".", 1)[-1] in owner_types), "<union>"
                )
            return "<dynamic>"

        def relevant(target: str) -> bool:
            return target.rsplit(".", 1)[-1] in functions or any(
                part in owner_types for part in target.split(".")
            )

        def record(node: ast.AST, target: str, role: str) -> None:
            references.append(
                {
                    "path": relative,
                    "function": ".".join(scopes),
                    "line": node.lineno,
                    "column": node.col_offset,
                    "target": target,
                    "role": role,
                    "star_keyword": isinstance(node, ast.Call)
                    and any(item.arg is None for item in node.keywords),
                }
            )

        class Walk(ast.NodeVisitor):
            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
                for item in node.names:
                    aliases[-1][item.asname or item.name] = f"{node.module}.{item.name}"

            def visit_Import(self, node: ast.Import) -> None:
                for item in node.names:
                    aliases[-1][item.asname or item.name.split(".")[0]] = (
                        item.name if item.asname else item.name.split(".")[0]
                    )

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                scopes.append(node.name)
                aliases.append({"self": node.name})
                self.generic_visit(node)
                aliases.pop()
                scopes.pop()

            def visit_FunctionDef(self, node: Any) -> None:
                scopes.append(node.name)
                aliases.append({})
                for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                    target = resolve(arg.annotation)
                    if relevant(target):
                        aliases[-1][arg.arg] = target
                self.generic_visit(node)
                aliases.pop()
                scopes.pop()

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self.visit_FunctionDef(node)

            def visit_Assign(self, node: ast.Assign) -> None:
                self.generic_visit(node)
                target = resolve(node.value)
                if relevant(target):
                    for item in node.targets:
                        if isinstance(item, ast.Name):
                            aliases[-1][item.id] = target

            def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
                self.generic_visit(node)
                target = resolve(node.annotation) if node.annotation else resolve(node.value)
                if isinstance(node.target, ast.Name) and relevant(target):
                    aliases[-1][node.target.id] = target

            def visit_Call(self, node: ast.Call) -> None:
                target = resolve(node.func)
                if relevant(target):
                    record(node, target, "call")
                self.generic_visit(node)

            def visit_Name(self, node: ast.Name) -> None:
                if node.id in functions | owner_types:
                    ast_terminals.add((relative, node.lineno, node.col_offset, node.id))
                if isinstance(node.ctx, ast.Load) and relevant(resolve(node)):
                    record(node, resolve(node), "reference")

            def visit_Attribute(self, node: ast.Attribute) -> None:
                if node.attr in functions | owner_types:
                    ast_terminals.add(
                        (relative, node.end_lineno, node.end_col_offset - len(node.attr), node.attr)
                    )
                if isinstance(node.ctx, ast.Load) and relevant(resolve(node)):
                    record(node, resolve(node), "reference")
                self.generic_visit(node)

        Walk().visit(tree)
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.NAME and token.string in functions | owner_types:
                token_terminals.add((relative, *token.start, token.string))
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and node.name in functions | owner_types
            ):
                line = source_lines[node.lineno - 1]
                start = line.index(node.name, node.col_offset)
                ast_terminals.add((relative, node.lineno, start, node.name))
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    set((node.module or "").split("."))
                    if isinstance(node, ast.ImportFrom)
                    else set()
                )
                for item in node.names:
                    names.update(item.name.split("."))
                    if item.asname:
                        names.add(item.asname)
                if names.intersection(functions | owner_types):
                    lines = source_lines[node.lineno - 1 : node.end_lineno]
                    lines[0] = lines[0][node.col_offset :]
                    lines[-1] = lines[-1][
                        : node.end_col_offset - (node.col_offset if len(lines) == 1 else 0)
                    ]
                    for token in tokenize.generate_tokens(io.StringIO("\n".join(lines)).readline):
                        if token.type == tokenize.NAME and token.string in functions | owner_types:
                            ast_terminals.add(
                                (
                                    relative,
                                    node.lineno + token.start[0] - 1,
                                    token.start[1]
                                    + (node.col_offset if token.start[0] == 1 else 0),
                                    token.string,
                                )
                            )

    for path in sorted(paths):
        scan(path)
    if ast_terminals != token_terminals:
        raise ValueError(
            "loop_gx_literal_identity_reconciliation_failed:"
            + repr(
                {
                    "only_ast": sorted(ast_terminals - token_terminals),
                    "only_token": sorted(token_terminals - ast_terminals),
                }
            )
        )
    changed = [
        relative
        for relative, value in snapshots.items()
        if "sha256:" + hashlib.sha256((repo_root / relative).read_bytes()).hexdigest() != value
    ]
    reread = {path for root in roots for path in (repo_root / root).rglob("*.py")}
    if changed or reread != paths:
        raise ValueError("loop_gx_caller_source_changed")
    return {
        "source_denominator": {
            "roots": list(roots),
            "file_type": "all current .py",
            "rglob": len(paths),
            "os_walk": len(independent),
        },
        "literal_identity_reconciliation": {
            "ast": len(ast_terminals),
            "tokenize": len(token_terminals),
        },
        "source_basis_hash": "sha256:"
        + hashlib.sha256(json.dumps(snapshots, sort_keys=True).encode()).hexdigest(),
        "references": sorted(
            references, key=lambda row: (row["path"], row["line"], row["column"], row["role"])
        ),
        "source_changed": [],
        "source_hashes": snapshots,
    }


_LOOP_GX_PREDECESSOR_REVISION = "e2cf7f10f2853b7561034b8e0ba699e6bacd32ba"
_LOOP_GX_OWNER_PATH = "tools/quality/validation/check_layer3_gy_loop_artifacts.py"


def _loop_gx_fence_issues(basis: dict[str, Any]) -> list[dict[str, Any]]:
    """Fence this owner's former pre-output GX default; retain other GX owners."""
    issues = []
    local = [row for row in basis["references"] if row["path"] == _LOOP_GX_OWNER_PATH]
    for row in local:
        target = row["target"].rsplit(".", 1)[-1]
        if target == "validate_layer3_gx_hardening" and row["function"] != "_gx_child":
            issues.append({"code": "layer3_gy_pre_output_gx_reachable", **row})
    expected = (
        ("build_live_loop_artifacts", "_run_durable_workspace_loop_observation"),
        ("build_live_loop_artifacts", "_assemble_live_loop_family"),
        ("build_live_loop_artifacts", "_run_full_gx_on_new_artifacts"),
        ("build_live_loop_artifacts", "_attach_post_gx_result"),
        ("_gx_child", "validate_layer3_gx_hardening"),
    )
    for function, target in expected:
        if not any(
            row["role"] == "call"
            and row["function"] == function
            and row["target"].rsplit(".", 1)[-1] == target
            for row in local
        ):
            issues.append(
                {
                    "code": "layer3_gy_post_output_default_edge_missing",
                    "function": function,
                    "target": target,
                }
            )
    ordered = [
        row["target"].rsplit(".", 1)[-1]
        for row in local
        if row["role"] == "call"
        and row["function"] == "build_live_loop_artifacts"
        and row["target"].rsplit(".", 1)[-1] in {target for _, target in expected}
    ]
    if ordered != [
        target for function, target in expected if function == "build_live_loop_artifacts"
    ]:
        issues.append({"code": "layer3_gy_post_output_default_order_changed", "actual": ordered})
    return issues


class _LoopGXStrangleMeasurement:
    """Keep one complete caller snapshot private until the actual GX returns."""

    def __init__(self, root: Path) -> None:
        self.root = root
        basis = _loop_gx_caller_basis(root)
        self.hashes = basis.pop("source_hashes")
        issues = _loop_gx_fence_issues(basis)
        if issues:
            raise LoopFamilyCustodyError(
                "loop_gx_default_not_strangled:" + json.dumps(issues, sort_keys=True)
            )
        old = subprocess.check_output(
            [
                "git",
                "show",
                _LOOP_GX_PREDECESSOR_REVISION + ":policy-engine/" + _LOOP_GX_OWNER_PATH,
            ],
            cwd=root,
        )
        current = (root / _LOOP_GX_OWNER_PATH).read_bytes()

        def function_lines(raw: bytes) -> list[str]:
            source = raw.decode("utf-8")
            functions = [
                node
                for node in ast.parse(source).body
                if isinstance(node, ast.FunctionDef)
                and node.name == "_run_durable_workspace_loop_observation"
            ]
            if len(functions) != 1:
                raise LoopFamilyCustodyError("loop_gx_predecessor_function_identity_invalid")
            node = functions[0]
            return source.splitlines()[node.lineno - 1 : node.end_lineno]

        old_lines, new_lines = function_lines(old), function_lines(current)
        removed = sum(
            line.startswith("-") and not line.startswith("---")
            for line in difflib.unified_diff(old_lines, new_lines)
        )
        independent = sum(
            i2 - i1
            for tag, i1, i2, _, _ in difflib.SequenceMatcher(
                None, old_lines, new_lines
            ).get_opcodes()
            if tag in {"delete", "replace"}
        )
        if removed != independent or removed == 0:
            raise LoopFamilyCustodyError("loop_gx_predecessor_deletion_not_reconciled")
        self.receipt = {
            "schema_version": "policyos.layer3.gy.post_output_gx_strangle.v1",
            "pattern_id": "P28",
            "predecessor_ref": _LOOP_GX_OWNER_PATH
            + "@"
            + _LOOP_GX_PREDECESSOR_REVISION
            + ":_run_durable_workspace_loop_observation",
            "predecessor_source_sha256": "sha256:" + hashlib.sha256(old).hexdigest(),
            "replacement_ref": _LOOP_GX_OWNER_PATH + ":build_live_loop_artifacts",
            "disposition": "fenced_default_flipped",
            "default_before": "GX_on_prior_artifacts_before_durable_POST",
            "default_after": "complete_durable_request_family_then_actual_full_GX_then_checked_outcome",
            "guard_ref": _LOOP_GX_OWNER_PATH + ":_loop_gx_fence_issues",
            "removed_loc": {"unified_diff": removed, "sequence_opcodes": independent},
            "remaining_callers": basis.pop("references"),
            "caller_basis": basis,
            "remaining_callers_disposition": "All current references are enumerated. This owner's GX caller is the isolated post-output child; other GX owners and native controls retain their own semantics. The compatibility proof helper emits no checked current outcome.",
            "predicate_basis": "recomputed",
            "predicate_scope": "complete_current_source_default_fence; semantic_GX_execution_is_bound_separately",
            "verified_by": [
                "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_gy_l_full_gx_notices_unproven_positive_only_in_new_output",
                "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_gy_l_removed_post_output_execution_keeps_markers_but_turns_gate_red",
                "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_gy_l_asserted_pass_without_current_execution_is_refused",
            ],
            "guard_source_sha256": self.hashes[
                "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py"
            ],
        }

    def checked_snapshot(self) -> dict[str, Any]:
        roots = ("src", "tools", "tests")
        current = {
            path.relative_to(self.root).as_posix()
            for part in roots
            for path in (self.root / part).rglob("*.py")
        }
        independent = {
            str((Path(directory) / name).relative_to(self.root))
            for part in roots
            for directory, _, names in os.walk(self.root / part)
            for name in names
            if name.endswith(".py")
        }
        if current != independent or current != set(self.hashes):
            raise LoopFamilyCustodyError("loop_gx_strangle_source_population_changed")
        if any(
            "sha256:" + hashlib.sha256((self.root / path).read_bytes()).hexdigest() != digest
            for path, digest in self.hashes.items()
        ):
            raise LoopFamilyCustodyError("loop_gx_strangle_source_bytes_changed")
        return json.loads(serialize_loop_artifact(self.receipt))


class PostOutputGXVerification(BaseModel):
    """Record the actual complete GX run over the newly emitted family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.layer3.gy.post_output_gx_verification.v1"]
    proof_source: Literal["complete_gx_owner_on_fresh_output_family"]
    case_id: str = Field(min_length=1)
    verifier_ref: Literal[
        "tools.quality.validation.check_policy_design_case_layer3_gx_hardening:"
        "validate_layer3_gx_hardening"
    ]
    verifier_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    family_owner_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    input_projection_rule: Literal[
        "gy_outcome_v2_excludes_only_gx_validator_status_and_gx_validation_envelope"
    ]
    input_artifact_hashes: dict[str, str]
    complete_input_basis_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    materialized_source_namespace_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    complete_gx_artifact_denominator: int = Field(ge=1)
    complete_gx_python_denominator: int = Field(ge=1)
    status: Literal["pass", "fail", "expected_red"]
    finding_identities: list[str]
    report_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    strangle_receipt: dict[str, Any]


class _GXExecutionResult:
    """A result emitted by this invocation of the full verifier, not JSON admission."""

    def __init__(
        self,
        family: _VerifiedLoopFamily,
        basis: dict[str, dict[str, Any]],
        result: dict[str, Any],
        *,
        issuer: object,
    ) -> None:
        if issuer is not _GX_EXECUTION_ISSUER:
            raise LoopFamilyCustodyError("post_gx_execution_owner_not_consulted")
        self.__family = family
        self.__basis = serialize_loop_artifact(basis)
        self.__result = serialize_loop_artifact(result)

    def _checked_snapshot(self, family: _VerifiedLoopFamily) -> dict[str, Any]:
        if family is not self.__family:
            raise LoopFamilyCustodyError("post_gx_result_from_different_family_invocation")
        if serialize_loop_artifact(freeze_pre_gx_output_family(family)) != self.__basis:
            raise LoopFamilyCustodyError("post_gx_family_changed_during_verification")
        return json.loads(self.__result)


class _GXCheckedOutcome(dict):
    """Carry actual same-process verification with the complete immutable paired replay."""

    def __init__(self, outcome: dict[str, Any], replay: dict[str, Any], *, issuer: object) -> None:
        if issuer is not _GX_EXECUTION_ISSUER:
            raise LoopFamilyCustodyError("post_gx_outcome_verifier_not_consulted")
        self.__outcome = serialize_loop_artifact(outcome)
        self.__replay = serialize_loop_artifact(replay)
        super().__init__(json.loads(self.__outcome))

    def _checked_snapshot(self, replay: dict[str, Any]) -> dict[str, Any]:
        if (
            serialize_loop_artifact(self) != self.__outcome
            or serialize_loop_artifact(replay) != self.__replay
        ):
            raise LoopFamilyCustodyError("post_gx_outcome_or_replay_changed_after_verification")
        return json.loads(self.__outcome)


class _GXCheckedLoopFamily(_VerifiedLoopFamily):
    """Freeze all final output bytes once, after actual full GX result admission."""

    def __init__(
        self,
        payloads: dict[str, dict[str, Any]],
        *,
        exit_readback: _VerifiedWorkspaceExitReadback,
        issuer: object,
    ) -> None:
        if issuer is not _GX_EXECUTION_ISSUER:
            raise LoopFamilyCustodyError("post_gx_family_verifier_not_consulted")
        super().__init__(payloads, exit_readback=exit_readback, issuer=_LIVE_LOOP_ISSUER)
        self[OUTCOME_RUN_PATH] = _GXCheckedOutcome(
            self[OUTCOME_RUN_PATH],
            self[OUTCOME_REPLAY_PATH],
            issuer=issuer,
        )
        self.__final_payload = serialize_loop_artifact(self)

    def _frozen_final_output(self) -> dict[str, dict[str, Any]]:
        if serialize_loop_artifact(self) != self.__final_payload:
            raise LoopFamilyCustodyError("post_gx_final_family_changed_after_verification")
        return json.loads(self.__final_payload)


def _attach_post_gx_result(
    family: _VerifiedLoopFamily,
    result: _GXExecutionResult,
) -> _GXCheckedLoopFamily:
    if type(result) is not _GXExecutionResult:
        raise LoopFamilyCustodyError("post_gx_result_not_actual_owner_execution")
    packet = result._checked_snapshot(family)
    frozen = freeze_pre_gx_output_family(family)
    raw_verification = packet.get("verification")
    if raw_verification is None:
        status, verification = "fail", None
    else:
        typed = PostOutputGXVerification.model_validate(raw_verification)
        expected_hashes = {
            path: _gx_digest(serialize_loop_artifact(payload))
            for path, payload in sorted(frozen.items())
        }
        if typed.input_artifact_hashes != expected_hashes:
            raise LoopFamilyCustodyError("post_gx_verified_new_family_hashes_differ")
        report = packet["report"]
        identities = sorted(
            {
                json.dumps(issue, sort_keys=True, separators=(",", ":"), allow_nan=False)
                for issue in report["issues"]
            }
        )
        if (
            typed.status != report["status"]
            or typed.case_id != report["case_id"]
            or typed.finding_identities != identities
        ):
            raise LoopFamilyCustodyError("post_gx_report_projection_drift")
        if typed.status == "pass" and identities:
            raise LoopFamilyCustodyError("post_gx_pass_with_findings")
        status, verification = typed.status, typed.model_dump(mode="json")
    frozen[OUTCOME_RUN_PATH]["gx_validator_status"] = status
    frozen[OUTCOME_RUN_PATH]["gx_validation"] = verification
    # Deciding command output is retained once. It contains every real finding
    # and custody reference, never a duplicate of the generated artifact bodies.
    print("GY_POST_OUTPUT_GX " + json.dumps(packet, sort_keys=True, allow_nan=False))
    return _GXCheckedLoopFamily(
        frozen, exit_readback=family._checked_exit_readback(), issuer=_GX_EXECUTION_ISSUER
    )


def _validate_gx_status_fields(outcome: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if outcome.get("gx_validator_status") != "pass":
        issues.append(
            {
                "code": "layer3_gy_outcome_gx_not_passed",
                "path": OUTCOME_RUN_PATH,
                "actual": str(outcome.get("gx_validator_status")),
                "field_present": str("gx_validator_status" in outcome),
            }
        )
    raw = outcome.get("gx_validation")
    try:
        typed = PostOutputGXVerification.model_validate(raw)
    except (ValueError, TypeError) as error:
        issues.append(
            {
                "code": "layer3_gy_outcome_gx_verification_invalid",
                "path": OUTCOME_RUN_PATH,
                "reason": str(error),
            }
        )
        return
    if typed.status != "pass" or typed.finding_identities:
        issues.append({"code": "layer3_gy_outcome_gx_report_not_passed", "path": OUTCOME_RUN_PATH})


def _validate_current_gx_admission(
    outcome: dict[str, Any], replay: dict[str, Any], issues: list[dict[str, str]]
) -> None:
    _validate_gx_status_fields(outcome, issues)
    try:
        if type(outcome) is not _GXCheckedOutcome:
            raise LoopFamilyCustodyError("outcome_not_same_process_post_output_gx_verified")
        outcome._checked_snapshot(replay)
    except (ValueError, TypeError, KeyError) as error:
        issues.append(
            {
                "code": "layer3_gy_outcome_gx_execution_custody_failed",
                "path": OUTCOME_RUN_PATH,
                "reason": str(error),
            }
        )


def _freeze_final_loop_family(family: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if type(family) is not _GXCheckedLoopFamily:
        raise LoopFamilyCustodyError("final_loop_family_has_no_post_output_gx_execution")
    return family._frozen_final_output()


def _compare_current_loop_outputs(
    committed: dict[str, Any],
    fresh: dict[str, dict[str, Any]],
    issues: list[dict[str, str]],
) -> None:
    """Compare every declared output independently, preserving complete finding identities."""
    codes = {
        PROOFS_PATH: "layer3_gy_production_proof_drift",
        GRADED_OUTCOME_PATH: "layer3_gy_graded_outcome_report_drift",
        OUTCOME_RUN_PATH: "layer3_gy_outcome_run_drift",
        OUTCOME_REPLAY_PATH: "layer3_gy_outcome_replay_drift",
    }
    declared = declared_outputs()
    if set(codes) != set(declared) or len(declared) != len(set(declared)):
        raise LoopFamilyCustodyError("current_loop_output_comparison_population_invalid")
    for path in declared:
        if path not in committed or path not in fresh:
            issues.append({"code": codes[path], "path": path, "reason": "output_absent"})
            continue
        try:
            equal = serialize_loop_artifact(committed[path]) == serialize_loop_artifact(fresh[path])
        except (ValueError, TypeError) as error:
            issues.append(
                {"code": codes[path], "path": path, "reason": "output_unreadable:" + str(error)}
            )
            continue
        if not equal:
            issues.append({"code": codes[path], "path": path})


_GX_FORBIDDEN_DOCUMENTS = frozenset({"DEBT-REGISTER.md", "LEDGER.md"})
_GX_OWNER_MODULE = "tools.quality.validation.check_layer3_gy_loop_artifacts"


def _gx_current_owner() -> tuple[ModuleType, ModuleType]:
    from polisyos.runtime.quality.proving_ground import pinned_route_demand_home as data_owner
    from tools.quality.validation import check_policy_design_case_layer3_gx_hardening as gx

    return gx, data_owner


def _gx_digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _gx_file_digest(path: Path) -> str:
    if path.name in _GX_FORBIDDEN_DOCUMENTS:
        raise ValueError("gx_forbidden_document_read")
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f"gx_input_not_regular_file:{path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _gx_relative_path(value: str | Path) -> str:
    text = os.fspath(value)
    path = PurePosixPath(text)
    if path.is_absolute() or not text or any(part in {"", ".", ".."} for part in text.split("/")):
        raise ValueError(f"gx_owner_path_not_relative:{text}")
    return path.as_posix()


def _gx_raise_walk_error(error: OSError) -> None:
    raise error


def _gx_python_inputs(root: Path, gx: ModuleType) -> set[str]:
    actual = {
        path.relative_to(root).as_posix()
        for path in gx._iter_python_files(root, gx.DEFAULT_SCAN_ROOTS)
    }
    independent = set()
    for relative in gx.DEFAULT_SCAN_ROOTS:
        start = root / relative
        if start.is_file() and start.suffix == ".py":
            independent.add(start.relative_to(root).as_posix())
        elif start.is_dir():
            for directory, _, names in os.walk(
                start, onerror=_gx_raise_walk_error, followlinks=False
            ):
                for name in names:
                    if name.endswith(".py"):
                        independent.add((Path(directory) / name).relative_to(root).as_posix())
    if actual != independent:
        raise ValueError("gx_python_input_identity_sets_not_reconciled")
    return actual


def _gx_artifact_inputs(root: Path, gx: ModuleType) -> tuple[set[str], Any]:
    selection = gx.resolve_layer3_gx_data_home_selection(root, case="ua-msme")
    token = gx._CURRENT_GX_SELECTION.set(selection)
    try:
        actual = {path.as_posix() for path in gx._default_artifact_paths(root)}
    finally:
        gx._CURRENT_GX_SELECTION.reset(token)
    independent = {
        gx._gx_case_path(path, selection=selection).as_posix()
        for path in gx.GX_DATA_HOME_INPUT_PATHS
    }
    # The owner's actual patterns currently share POLICY_DESIGN_CASE_DIR.
    # A future pattern outside this root fails reconciliation, never shrinks it.
    for directory, _, names in os.walk(
        root / gx.POLICY_DESIGN_CASE_DIR, onerror=_gx_raise_walk_error, followlinks=False
    ):
        for name in names:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if (
                path.is_file()
                and not name.startswith("layer3_gx_")
                and any(
                    PurePosixPath(relative).match(pattern) for pattern in gx.DEFAULT_ARTIFACT_GLOBS
                )
            ):
                independent.add(relative)
    if actual != independent:
        raise ValueError("gx_artifact_input_identity_sets_not_reconciled")
    return actual, selection


def _gx_input_snapshot(root: Path, gx: ModuleType, data_owner: ModuleType) -> dict[str, Any]:
    artifacts, selection = _gx_artifact_inputs(root, gx)
    python = _gx_python_inputs(root, gx)
    hashes = {relative: _gx_file_digest(root / relative) for relative in sorted(artifacts | python)}
    for relative in sorted(artifacts):
        raw = (root / relative).read_bytes()
        if _gx_digest(raw) != hashes[relative]:
            raise ValueError("gx_input_changed_during_snapshot")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            # GX itself skips present-null in several scans; it must not be
            # conflated with an empty finding set by this admission instrument.
            raise ValueError(f"gx_input_json_not_object:{relative}")
    native = _gx_relative_path(data_owner.ACADEMIC_SKG_DB_PATH)
    native_path = root / native
    native_state = {"path": native, "state": "absent", "sha256": None}
    try:
        native_path.stat()
    except FileNotFoundError:
        for component in (native_path, *native_path.parents):
            if component.is_symlink():
                component.resolve(strict=True)
            if component == root:
                break
    else:
        native_state = {"path": native, "state": "present", "sha256": _gx_file_digest(native_path)}
    return {
        "case_id": selection.case_id,
        "case_selector": selection.selector_ref,
        "artifacts": sorted(artifacts),
        "python": sorted(python),
        "hashes": hashes,
        "native": native_state,
    }


def _gx_require_native_readable(path: Path) -> None:
    """Refuse a present copied database that the real native reader cannot open.

    The data-home owner deliberately maps an unavailable native database to an
    empty measurement map. This wrapper must distinguish unreadable present
    bytes from genuine absence before accepting GX's resulting input basis.
    Table membership remains the current owner's decision, not a new schema
    requirement or an invented measurement.
    """
    import duckdb

    connection = None
    try:
        connection = duckdb.connect(str(path), read_only=True)
        connection.execute("SELECT table_name FROM information_schema.tables").fetchall()
    except duckdb.Error as error:
        raise ValueError(f"gx_native_input_unreadable:{path}") from error
    finally:
        if connection is not None:
            connection.close()


def _gx_make_overlay(
    root: Path, view: Path, inputs: dict[str, dict[str, Any]], native: dict[str, Any]
) -> None:
    replace_paths = set(inputs)
    if native["state"] == "present":
        replace_paths.add(native["path"])
    ancestors = {
        parent.as_posix()
        for relative in replace_paths
        for parent in PurePosixPath(relative).parents
        if parent.as_posix() != "."
    }

    def materialize(relative: str = "") -> None:
        source_dir = root / relative
        target_dir = view / relative
        target_dir.mkdir(parents=True, exist_ok=True)
        entries = (
            {entry.name: entry for entry in os.scandir(source_dir)} if source_dir.is_dir() else {}
        )
        required = {
            PurePosixPath(path).relative_to(relative or ".").parts[0]
            for path in replace_paths | ancestors
            if not relative or path.startswith(relative + "/")
        }
        for name in sorted(set(entries) | required):
            if name in _GX_FORBIDDEN_DOCUMENTS:
                continue
            child = f"{relative}/{name}" if relative else name
            target = view / child
            source = root / child
            if child in inputs:
                target.write_bytes(serialize_loop_artifact(inputs[child]))
            elif native["state"] == "present" and child == native["path"]:
                shutil.copyfile(source, target)
                original_stat, copied_stat = source.stat(), target.stat()
                if (original_stat.st_dev, original_stat.st_ino) == (
                    copied_stat.st_dev,
                    copied_stat.st_ino,
                ):
                    raise ValueError("gx_native_input_copy_is_hardlink")
                if (
                    _gx_file_digest(target) != native["sha256"]
                    or _gx_file_digest(source) != native["sha256"]
                ):
                    raise ValueError("gx_native_input_copy_changed")
                _gx_require_native_readable(target)
                if (
                    _gx_file_digest(target) != native["sha256"]
                    or _gx_file_digest(source) != native["sha256"]
                ):
                    raise ValueError("gx_native_input_changed_during_readability_check")
            elif child in ancestors:
                materialize(child)
            else:
                # DirEntry includes ignored and broken-link entries. Creating
                # a pointer reads no file body and preserves their live shape.
                target.symlink_to(source, target_is_directory=source.is_dir())

    materialize()


def _gx_materialized_directory_snapshot(
    root: Path, inputs: dict[str, dict[str, Any]], native: dict[str, Any]
) -> dict[str, Any]:
    """Bind namespace entries where the view cannot reflect new siblings live."""
    replaced = set(inputs)
    if native["state"] == "present":
        replaced.add(native["path"])
    ancestors = {
        parent.as_posix() for relative in replaced for parent in PurePosixPath(relative).parents
    }
    result = {}
    for relative in sorted(ancestors):
        directory = root / relative
        try:
            entries = list(os.scandir(directory))
        except FileNotFoundError:
            result[relative] = {"state": "absent"}
            continue
        result[relative] = {
            entry.name: {
                "kind": stat.S_IFMT(entry.stat(follow_symlinks=False).st_mode),
                "link_target": os.readlink(entry.path) if entry.is_symlink() else None,
            }
            for entry in entries
            if entry.name not in _GX_FORBIDDEN_DOCUMENTS
        }
    return result


def _gx_assert_overlay(
    original: dict[str, Any], overlay: dict[str, Any], inputs: dict[str, dict[str, Any]]
) -> None:
    if (
        original["case_id"] != overlay["case_id"]
        or original["case_selector"] != overlay["case_selector"]
    ):
        raise ValueError("gx_overlay_case_changed")
    if set(overlay["artifacts"]) != set(original["artifacts"]) | set(inputs):
        raise ValueError("gx_overlay_artifact_denominator_changed")
    if original["python"] != overlay["python"] or original["native"] != overlay["native"]:
        raise ValueError("gx_overlay_source_denominator_changed")
    expected = {
        **original["hashes"],
        **{path: _gx_digest(serialize_loop_artifact(payload)) for path, payload in inputs.items()},
    }
    if expected != overlay["hashes"]:
        raise ValueError("gx_overlay_unrelated_bytes_changed")


class _GXReadOnlyPythonGuard:
    """Child-only Python audit boundary, not a general native-code sandbox."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.source_root: Path | None = None
        self.recording = False
        self.verifying = False
        self.nested_hash = False
        self.reads: dict[str, str] = {}
        self.json_reads: dict[str, dict[str, Any]] = {}
        self.mapping_reads: set[str] = set()
        self.read_issues: list[dict[str, str]] = []
        self.denied: list[str] = []

    def _read_failure(self, path: str, reason: str) -> None:
        self.read_issues.append({"path": path, "reason": reason})
        raise ValueError(f"gx_actual_json_read_refused:{reason}:{path}")

    def observe_json(self, path: Path, *, require_mapping: bool) -> dict[str, Any]:
        """Bind actual JSON read state without conflating absence with a parsed value."""
        key = str(path.absolute())
        nested = self.nested_hash
        self.nested_hash = True
        try:
            try:
                raw = path.read_bytes()
            except FileNotFoundError:
                # A broken link is a present unreadable source, never absence.
                for component in (path, *path.parents):
                    if component.is_symlink():
                        try:
                            component.resolve(strict=True)
                        except OSError:
                            self._read_failure(key, "unreadable_link")
                    if component in {self.root, self.source_root}:
                        break
                state = {"state": "absent", "sha256": None, "json_type": None}
            except OSError:
                self._read_failure(key, "unreadable_file")
            else:
                digest = _gx_digest(raw)
                try:
                    payload = json.loads(raw)
                except (UnicodeError, json.JSONDecodeError):
                    self.json_reads[key] = {
                        "state": "present_invalid_json",
                        "sha256": digest,
                        "json_type": None,
                    }
                    self._read_failure(key, "invalid_json")
                kind = (
                    "object"
                    if isinstance(payload, dict)
                    else "array"
                    if isinstance(payload, list)
                    else "null"
                    if payload is None
                    else "scalar"
                )
                state = {"state": "present", "sha256": digest, "json_type": kind}
            previous = self.json_reads.get(key)
            if previous is not None and previous != state:
                self._read_failure(key, "read_state_changed")
            self.json_reads[key] = state
            if require_mapping:
                self.mapping_reads.add(key)
                if state["state"] == "present" and state["json_type"] != "object":
                    self._read_failure(key, "mapping_reader_received_" + state["json_type"])
            return dict(state)
        finally:
            self.nested_hash = nested

    def recheck_json_reads(self) -> None:
        """Recheck every observed state, including absent mapping-reader inputs."""
        for path in tuple(self.json_reads):
            self.observe_json(Path(path), require_mapping=path in self.mapping_reads)
        if self.read_issues:
            raise ValueError("gx_actual_json_read_failure_caught_inside_owner")

    def __call__(self, event: str, args: tuple[Any, ...]) -> None:
        if event == "open":
            path, mode, flags = args
            flags = flags or 0
            write = (
                isinstance(mode, str) and any(character in mode for character in "wax+")
            ) or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if write:
                self._deny(f"{event}:{path}")
            if (
                self.recording
                and not self.nested_hash
                and isinstance(path, (str, bytes, os.PathLike))
            ):
                original = Path(os.fsdecode(path))
                if original.name in _GX_FORBIDDEN_DOCUMENTS:
                    self._deny(f"forbidden_document:{original.name}")
                self.nested_hash = True
                try:
                    key = str(original.absolute())
                    repository_read = original.absolute().is_relative_to(self.root) or (
                        self.source_root is not None
                        and original.absolute().is_relative_to(self.source_root)
                    )
                    state = None
                    if repository_read and original.suffix.lower() == ".json":
                        state = self.observe_json(original, require_mapping=False)
                        if state["state"] == "absent":
                            # The actual open still raises normally; its caller
                            # may handle absence, whose state remains bound.
                            return
                    resolved = original.resolve(strict=True)
                    digest = _gx_file_digest(resolved)
                    if key in self.reads and self.reads[key] != digest:
                        self._deny(f"source_changed_between_reads:{key}")
                    self.reads[key] = digest
                    if state is not None and state["sha256"] != digest:
                        self._read_failure(key, "changed_during_actual_open")
                finally:
                    self.nested_hash = False
        elif (
            (
                event.startswith("os.")
                and event
                not in {
                    "os.listdir",
                    "os.scandir",
                    "os.putenv",
                    "os.unsetenv",
                    "os.add_dll_directory",
                }
            )
            or event.startswith("subprocess.")
            or (self.verifying and event.startswith("ctypes."))
        ):
            self._deny(event)

    def _deny(self, reason: str) -> None:
        self.denied.append(reason)
        raise PermissionError(f"gx_read_only_python_boundary:{reason}")


@contextlib.contextmanager
def _gx_json_read_boundary(gx: ModuleType, guard: _GXReadOnlyPythonGuard) -> Iterator[None]:
    """Preserve the actual GX reader while binding every requested mapping input."""
    original = gx._read_json

    def checked(path: Path, *, default: Any) -> Any:
        expected_mapping = isinstance(default, Mapping)
        before = guard.observe_json(path, require_mapping=expected_mapping)
        result = original(path, default=default)
        after = guard.observe_json(path, require_mapping=expected_mapping)
        if before != after:
            guard._read_failure(str(path.absolute()), "mapping_read_state_changed")
        return result

    gx._read_json = checked
    try:
        yield
    finally:
        gx._read_json = original


def _gx_child(root: Path) -> int:
    # Resolve Python's station scratch before installing the input write fence:
    # its first call tests directory usability by creating and deleting a file.
    # No GX owner or data input is loaded outside the recorded boundary below.
    tempfile.gettempdir()
    guard = _GXReadOnlyPythonGuard(root)
    sys.addaudithook(guard)
    try:
        gx, data_owner = _gx_current_owner()
        guard.source_root = Path(gx.__file__).resolve().parents[3]
        guard.recording = True
        guard.verifying = True
        with _gx_json_read_boundary(gx, guard):
            report = gx.validate_layer3_gx_hardening(root, case="ua-msme", write=False)
        guard.recording = False
        guard.recheck_json_reads()
        if guard.denied:
            raise ValueError("gx_write_attempt_was_caught_inside_owner")
        if any(_gx_file_digest(Path(path)) != digest for path, digest in guard.reads.items()):
            raise ValueError("gx_actual_python_read_changed")
        if not isinstance(report, dict) or not isinstance(report.get("issues"), list):
            raise ValueError("gx_complete_report_not_returned")
        compact = {key: value for key, value in report.items() if key != "artifacts"}
        # The omitted member contains recomputable generated bodies; complete
        # issues, summary, case and rule/status fields stay in this one output.
        source_root = Path(gx.__file__).resolve().parents[3]

        def read_key(path: str) -> str:
            lexical = Path(path)
            if lexical.is_relative_to(root):
                return "overlay://" + lexical.relative_to(root).as_posix()
            if lexical.is_relative_to(source_root):
                return "source://" + lexical.relative_to(source_root).as_posix()
            return "station://" + lexical.as_posix()

        read_refs = {read_key(path): digest for path, digest in guard.reads.items()}
        json_read_states = {
            read_key(path): {**state, "mapping_required": path in guard.mapping_reads}
            for path, state in guard.json_reads.items()
        }
        result = {
            "report": compact,
            "full_report_sha256": _gx_digest(serialize_loop_artifact(report)),
            "report_projection": "all_members_except_recomputable_artifacts",
            "actual_python_read_refs": read_refs,
            "actual_json_read_states": json_read_states,
            "actual_json_states_rechecked": True,
            "write_guard": "child_python_audit_not_os_sandbox; native_owner_database_copied",
            "native_owner_ref": _gx_relative_path(data_owner.ACADEMIC_SKG_DB_PATH),
        }
        sys.stdout.write(
            "GY_POST_GX_RESULT "
            + json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False)
            + "\n"
        )
        sys.stdout.flush()
        return 0
    except Exception as error:
        guard.recording = False
        sys.stdout.write(
            "GY_POST_GX_RESULT "
            + json.dumps(
                {
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "denied_events": guard.denied,
                    "actual_json_read_issues": guard.read_issues,
                    "actual_json_read_states": guard.json_reads,
                },
                sort_keys=True,
            )
            + "\n"
        )
        sys.stdout.flush()
        return 2


def _run_full_gx_on_new_artifacts(
    root: Path, payloads: _VerifiedLoopFamily, *, timeout_seconds: float = 600
) -> _GXExecutionResult:
    """Check the exact current family through the unchanged full GX owner."""
    root = root.resolve()
    gx, data_owner = _gx_current_owner()
    inputs = freeze_pre_gx_output_family(payloads)
    strangle = _LoopGXStrangleMeasurement(root)
    before = _gx_input_snapshot(root, gx, data_owner)
    temporary_root = root / "_build/gy-gaps/tmp"
    temporary_root.mkdir(parents=True, exist_ok=True)
    namespace_before = _gx_materialized_directory_snapshot(root, inputs, before["native"])
    with tempfile.TemporaryDirectory(prefix="gy-post-output-gx-", dir=temporary_root) as directory:
        view = Path(directory) / "tree"
        _gx_make_overlay(root, view, inputs, before["native"])
        overlay_before = _gx_input_snapshot(view, gx, data_owner)
        _gx_assert_overlay(before, overlay_before, inputs)
        environment = os.environ.copy()
        environment.update(
            {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": f"{root / 'src'}:{root}",
                "PATH": f"{root / '.venv/bin'}:{environment.get('PATH', '')}",
                "TMPDIR": str(temporary_root),
                "POLISYOS_CACHE_HOME": str(root / "_build/gy-gaps/cache"),
            }
        )
        try:
            completed = subprocess.run(  # noqa: S603 - fixed module, current interpreter, owned paths.
                [sys.executable, "-m", _GX_OWNER_MODULE, "--child", str(view)],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            child_returncode, child_stdout, child_stderr = (
                completed.returncode,
                completed.stdout,
                completed.stderr,
            )
        except subprocess.TimeoutExpired as error:
            child_returncode = 124
            child_stdout = error.stdout or ""
            child_stderr = error.stderr or ""
            if isinstance(child_stdout, bytes):
                child_stdout = child_stdout.decode(errors="replace")
            if isinstance(child_stderr, bytes):
                child_stderr = child_stderr.decode(errors="replace")
        # Reread both complete identity sets and bytes even if GX refused.
        after = _gx_input_snapshot(root, gx, data_owner)
        overlay_after = _gx_input_snapshot(view, gx, data_owner)
        if before != after or overlay_before != overlay_after:
            raise ValueError("gx_input_identity_or_bytes_changed_during_verification")
        if namespace_before != _gx_materialized_directory_snapshot(root, inputs, after["native"]):
            raise ValueError("gx_materialized_source_namespace_changed_during_verification")
        _gx_assert_overlay(after, overlay_after, inputs)
        if child_returncode:
            return _GXExecutionResult(
                payloads,
                inputs,
                {
                    "verification": None,
                    "strangle_receipt": strangle.checked_snapshot(),
                    "child_returncode": child_returncode,
                    "child_stdout": child_stdout,
                    "child_stderr": child_stderr,
                },
                issuer=_GX_EXECUTION_ISSUER,
            )
        prefix = "GY_POST_GX_RESULT "
        packets = [
            line.removeprefix(prefix)
            for line in child_stdout.splitlines()
            if line.startswith(prefix)
        ]
        if len(packets) != 1:
            raise ValueError("gx_child_result_transport_incomplete")
        result = json.loads(packets[0])
        report = result["report"]
        if report.get("case_id") != before["case_id"] or report.get("write") is not False:
            raise ValueError("gx_child_case_or_write_disposition_changed")
        findings = sorted(
            {
                json.dumps(issue, sort_keys=True, separators=(",", ":"), allow_nan=False)
                for issue in report["issues"]
            }
        )
        verification = {
            "schema_version": "policyos.layer3.gy.post_output_gx_verification.v1",
            "proof_source": "complete_gx_owner_on_fresh_output_family",
            "case_id": before["case_id"],
            "verifier_ref": (
                "tools.quality.validation.check_policy_design_case_layer3_gx_hardening:"
                "validate_layer3_gx_hardening"
            ),
            "verifier_sha256": _gx_file_digest(Path(gx.__file__)),
            "family_owner_sha256": _gx_file_digest(Path(__file__)),
            "input_projection_rule": (
                "gy_outcome_v2_excludes_only_gx_validator_status_and_gx_validation_envelope"
            ),
            "input_artifact_hashes": {
                path: _gx_digest(serialize_loop_artifact(payload))
                for path, payload in sorted(inputs.items())
            },
            "complete_input_basis_sha256": _gx_digest(
                serialize_loop_artifact(
                    {
                        "declared_scan_snapshot": overlay_before,
                        "actual_python_read_refs": result["actual_python_read_refs"],
                        "actual_json_read_states": result["actual_json_read_states"],
                    }
                )
            ),
            "materialized_source_namespace_sha256": _gx_digest(
                serialize_loop_artifact(namespace_before)
            ),
            "complete_gx_artifact_denominator": len(overlay_before["artifacts"]),
            "complete_gx_python_denominator": len(overlay_before["python"]),
            "status": report["status"],
            "finding_identities": findings,
            "report_sha256": result["full_report_sha256"],
            "strangle_receipt": strangle.checked_snapshot(),
        }
        verification["strangle_receipt"]["actual_execution_ref"] = {
            "report_sha256": verification["report_sha256"],
            "input_basis_sha256": verification["complete_input_basis_sha256"],
            "status": verification["status"],
            "claim": "Actual complete GX execution; current outcome admission independently requires pass.",
        }
        # Read refs and the deciding report belong in the command receipt, not
        # duplicated inside the governed outcome verification envelope.
        return _GXExecutionResult(
            payloads,
            inputs,
            {
                "verification": verification,
                "report": report,
                "source_refs": overlay_before["hashes"],
                "native_source": before["native"],
                "actual_python_read_refs": result["actual_python_read_refs"],
                "actual_json_read_states": result["actual_json_read_states"],
                "actual_json_states_rechecked": result["actual_json_states_rechecked"],
                "write_guard": result["write_guard"],
                "child_stderr": child_stderr,
                "child_diagnostics": [
                    line for line in child_stdout.splitlines() if not line.startswith(prefix)
                ],
            },
            issuer=_GX_EXECUTION_ISSUER,
        )


def build_live_loop_artifacts(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Recompute the complete canonical family once through the durable owner."""
    _ensure_src_path(repo_root)
    observations = [
        _run_durable_workspace_loop_observation(
            fixture_id=request.fixture_id,
            repo_root=repo_root,
            catalog_mode=request.catalog_mode,
        )
        for request in canonical_loop_requests()
    ]
    family = _assemble_live_loop_family(observations)
    result = _run_full_gx_on_new_artifacts(repo_root, family)
    return _attach_post_gx_result(family, result)


def _build_outcome_run(observation: dict[str, Any]) -> dict[str, Any]:
    contract = dict(observation["search_exit_contract"])
    proof = dict(observation["proof"])
    replay = dict(observation["outcome_replay_proof"])
    terminal = dict(contract.get("terminal_state") or {})
    return {
        "schema_version": "policyos.policy_design_case.layer3_gy.outcome_run.v2",
        "rule_version": "policyos.layer3.gy.outcome_run.v2",
        "owner": "team-runtime-quality",
        "case_id": "ua-msme-affordable-loans-2022",
        "fixture_id": str(observation["fixture_id"]),
        "proof_source": "production_http_route_recomputed",
        "trigger_kind": str(observation["trigger_kind"]),
        "http_receipts": dict(observation["http_receipts"]),
        "gx_validator_status": str(observation["gx_validator_status"]),
        "gx_case_outcome": dict(observation["gx_case_outcome"]),
        "terminal_outcome": str(terminal.get("kind") or ""),
        "useful_design_credit": terminal.get("kind") == "grounded_partial_admissible",
        "evidence_kind": contract.get("evidence_kind"),
        "decision_grade": contract.get("decision_grade"),
        "evidence_ladder_rung": contract.get("evidence_ladder_rung"),
        "producer_roots": list(replay.get("producer_roots") or []),
        "incompleteness": dict(contract.get("incompleteness_record") or {}),
        "input_hashes": dict(replay.get("input_hashes") or {}),
        "output_hash": str(replay.get("output_hash") or ""),
        "search_exit_contract_ref": str(proof["output_search_exit_contract_ref"]),
        "production_loop_run_proof_ref": str(observation["proof_ref"]),
        "outcome_replay_proof_ref": str(proof["output_replay_proof_ref"]),
        "cas_resolution_checks": list(observation["cas_resolution_checks"]),
        "artifacts_index": dict(observation["artifacts_index"]),
        "production_loop_run_proof": proof,
        "search_exit_contract": contract,
    }


def _validate_loop_epoch_partition(
    repo_root: Path,
    generated: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    """Reconcile complete current/history ownership and immutable v1 bytes."""
    families = generated.get("family")
    if not isinstance(families, list) or any(not isinstance(row, dict) for row in families):
        issues.append({"code": "layer3_gy_loop_epoch_families_invalid"})
        families = []
    for family_id, expected, lifecycle in (
        (FAMILY_ID, declared_outputs(), "generated_committed"),
        (HISTORY_FAMILY_ID, [HISTORICAL_OUTCOME_RUN_PATH], "source_committed"),
    ):
        matches = [row for row in families if row.get("id") == family_id]
        if len(matches) != 1:
            issues.append(
                {"code": "layer3_gy_loop_epoch_family_identity_invalid", "family": family_id}
            )
        for family in matches:
            outputs = family.get("outputs")
            if (
                not isinstance(outputs, list)
                or any(not isinstance(path, str) for path in outputs)
                or len(outputs) != len(set(outputs))
                or set(outputs) != set(expected)
            ):
                issues.append(
                    {"code": "layer3_gy_loop_epoch_output_population_invalid", "family": family_id}
                )
            if (
                family.get("lifecycle") != lifecycle
                or family.get("stale_output_behavior") != "fail"
            ):
                issues.append({"code": "layer3_gy_loop_epoch_custody_invalid", "family": family_id})
            if family_id == HISTORY_FAMILY_ID:
                if family.get("source_integrity_sha256") != {
                    HISTORICAL_OUTCOME_RUN_PATH: HISTORICAL_OUTCOME_RUN_SHA256,
                }:
                    issues.append(
                        {
                            "code": "layer3_gy_loop_epoch_history_hash_declaration_invalid",
                            "family": family_id,
                        }
                    )
                if (
                    family.get("workflow")
                    != "tools/quality/validation/check_layer3_gy_loop_artifacts.py"
                ):
                    issues.append(
                        {"code": "layer3_gy_loop_epoch_history_owner_invalid", "family": family_id}
                    )
        for path in expected:
            claimants = [
                str(row.get("id"))
                for row in families
                if isinstance(row.get("outputs"), list) and path in row["outputs"]
            ]
            if claimants != [family_id]:
                issues.append({"code": "layer3_gy_loop_epoch_output_owner_conflict", "path": path})
    try:
        raw = (repo_root / HISTORICAL_OUTCOME_RUN_PATH).read_bytes()
    except (OSError, UnicodeError) as error:
        issues.append(
            {
                "code": "layer3_gy_loop_epoch_history_unreadable",
                "path": HISTORICAL_OUTCOME_RUN_PATH,
                "reason": str(error),
            }
        )
    else:
        if "sha256:" + hashlib.sha256(raw).hexdigest() != HISTORICAL_OUTCOME_RUN_SHA256:
            issues.append(
                {
                    "code": "layer3_gy_loop_epoch_history_changed",
                    "path": HISTORICAL_OUTCOME_RUN_PATH,
                }
            )


def _validate_source_artifact_integrity(
    repo_root: Path,
    family: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    integrity = family.get("source_integrity_sha256")
    if not isinstance(integrity, dict):
        issues.append({"code": "layer3_gy_source_integrity_manifest_missing"})
        return
    for output in (MANIFEST_PATH, BENCHMARK_PATH):
        expected = str(integrity.get(output) or "")
        if not expected:
            issues.append({"code": "layer3_gy_source_integrity_digest_missing", "path": output})
            continue
        path = repo_root / output
        if not path.is_file():
            issues.append({"code": "layer3_gy_source_output_missing", "path": output})
            continue
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            issues.append(
                {
                    "code": "layer3_gy_source_output_integrity_drift",
                    "path": output,
                    "expected": expected,
                    "actual": actual,
                }
            )


def _build_graded_outcome_report(
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    outcomes: list[dict[str, Any]] = []
    non_value_outcomes: list[dict[str, Any]] = []
    for observation in observations:
        proof = dict(observation["proof"])
        contract = dict(observation.get("search_exit_contract") or {})
        terminal = contract.get("terminal_state")
        authority = contract.get("authority_boundary")
        if not isinstance(terminal, dict):
            continue
        if terminal.get("kind") != "grounded_partial_admissible":
            non_value_outcomes.append(
                {
                    "fixture_id": str(observation["fixture_id"]),
                    "run_id": str(proof.get("run_id") or ""),
                    "job_id": str(proof.get("job_id") or ""),
                    "terminal_state": str(terminal.get("kind") or ""),
                    "decision_grade": str(contract.get("decision_grade") or "unsupported"),
                    "evidence_kind": contract.get("evidence_kind"),
                    "evidence_ladder_rung": str(
                        contract.get("evidence_ladder_rung") or "none"
                    ),
                    "incompleteness_recorded": bool(
                        contract.get("incompleteness_record")
                    ),
                    "useful_design_credit": False,
                }
            )
            continue
        if not isinstance(authority, dict):
            continue
        outcomes.append(
            {
                "fixture_id": str(observation["fixture_id"]),
                "run_id": str(proof.get("run_id") or ""),
                "job_id": str(proof.get("job_id") or ""),
                "output_search_exit_contract_ref": str(
                    proof.get("output_search_exit_contract_ref") or ""
                ),
                "terminal_state": str(terminal.get("kind") or ""),
                "conversion_outcome": "publish-with-limitation",
                "authority_boundary_ref": str(authority.get("boundary_id") or ""),
                "decision_grade": str(authority.get("decision_grade") or ""),
                "evidence_kind": str(authority.get("evidence_kind") or ""),
                "limitation_refs": list(authority.get("known_limits") or []),
                "may_not_use_for": list(authority.get("may_not_use_for") or []),
                "useful_design_credit_route": "genuine_graded_outcome_only",
                "floor_relaxation_used": False,
            }
        )
    capped_count = sum(
        1
        for outcome in outcomes
        if outcome.get("decision_grade") in {"descriptive_only", "advisory_admissible"}
    )
    return {
        "schema_version": (
            "policyos.policy_design_case.layer3_gy.graded_outcome_routing_report.v1"
        ),
        "rule_version": "policyos.layer3.gy.graded_outcome_routing.v1",
        "owner": "team-runtime-quality",
        "proof_source": "durable_worker_recomputed",
        "graded_outcomes": outcomes,
        "honest_non_value_outcomes": non_value_outcomes,
        "summary": {
            "grounded_partial_admissible_count": len(outcomes),
            "capped_decision_grade_count": capped_count,
            "floor_relaxation_used_count": sum(
                1 for outcome in outcomes if outcome.get("floor_relaxation_used") is True
            ),
            "useful_design_rate": (
                round(len(outcomes) / len(observations), 4) if observations else 0.0
            ),
        },
    }


def _validate_graded_outcome_report(
    report: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    if report.get("schema_version") != (
        "policyos.policy_design_case.layer3_gy.graded_outcome_routing_report.v1"
    ):
        issues.append({"code": "layer3_gy_graded_outcome_schema_version_invalid"})
    outcomes = report.get("graded_outcomes")
    if not isinstance(outcomes, list):
        issues.append({"code": "layer3_gy_graded_outcomes_missing"})
        return
    for index, outcome in enumerate(outcomes):
        if not isinstance(outcome, dict):
            issues.append(
                {"code": "layer3_gy_graded_outcome_not_object", "index": str(index)}
            )
            continue
        if outcome.get("terminal_state") != "grounded_partial_admissible":
            issues.append(
                {
                    "code": "layer3_gy_graded_outcome_terminal_invalid",
                    "index": str(index),
                }
            )
        if outcome.get("conversion_outcome") != "publish-with-limitation":
            issues.append(
                {
                    "code": "layer3_gy_graded_outcome_conversion_invalid",
                    "index": str(index),
                }
            )
        if outcome.get("decision_grade") not in {
            "descriptive_only",
            "advisory_admissible",
        }:
            issues.append(
                {
                    "code": "layer3_gy_graded_outcome_decision_grade_uncapped",
                    "index": str(index),
                }
            )
        if not outcome.get("limitation_refs"):
            issues.append(
                {
                    "code": "layer3_gy_graded_outcome_limitation_missing",
                    "index": str(index),
                }
            )
        may_not_use_for = set(outcome.get("may_not_use_for") or [])
        if not may_not_use_for or "production_decision" not in may_not_use_for:
            issues.append(
                {
                    "code": "layer3_gy_graded_outcome_deny_list_missing",
                    "index": str(index),
                }
            )
        if outcome.get("floor_relaxation_used") is not False:
            issues.append(
                {
                    "code": "layer3_gy_graded_outcome_floor_relaxation_used",
                    "index": str(index),
                }
            )
        ref = str(outcome.get("output_search_exit_contract_ref") or "")
        if not _looks_like_sha256_ref(ref):
            issues.append(
                {
                    "code": "layer3_gy_graded_outcome_contract_ref_invalid",
                    "index": str(index),
                }
            )
    non_value = report.get("honest_non_value_outcomes")
    if not isinstance(non_value, list):
        issues.append({"code": "layer3_gy_honest_non_value_outcomes_missing"})
        return
    for index, outcome in enumerate(non_value):
        if not isinstance(outcome, dict):
            issues.append(
                {"code": "layer3_gy_honest_non_value_outcome_not_object", "index": str(index)}
            )
            continue
        if outcome.get("terminal_state") not in {
            "grounded_abstention",
            "search_ceiling_repair_required",
            "acquisition_required",
            "a_spec_gap",
            "tool_failure",
            "composition_invalid",
            "recursive_blocked",
            "budget_exhausted",
            "human_decision_required",
        }:
            issues.append(
                {"code": "layer3_gy_honest_non_value_terminal_invalid", "index": str(index)}
            )
        if outcome.get("useful_design_credit") is not False:
            issues.append(
                {"code": "layer3_gy_honest_non_value_forced_useful", "index": str(index)}
            )
        if outcome.get("incompleteness_recorded") is not True:
            issues.append(
                {"code": "layer3_gy_honest_non_value_incompleteness_missing", "index": str(index)}
            )
    summary = report.get("summary")
    if isinstance(summary, dict):
        expected_rate = (
            round(len(outcomes) / (len(outcomes) + len(non_value)), 4)
            if outcomes or non_value
            else 0.0
        )
        if summary.get("useful_design_rate") != expected_rate:
            issues.append({"code": "layer3_gy_useful_design_rate_drift"})


def validate_outcome_run(
    outcome: dict[str, Any],
    replay_artifact: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    """Require the terminal/replay contract and actual fresh complete GX admission."""
    _validate_outcome_terminal_and_replay(outcome, replay_artifact, issues)
    _validate_current_gx_admission(outcome, replay_artifact, issues)


def _validate_outcome_terminal_and_replay(
    outcome: dict[str, Any],
    replay_artifact: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    """Recompute the GY-L outcome claims from the production run payloads."""

    from pydantic import ValidationError

    from polisyos.core.canon import CanonSpec, to_canonical_bytes
    from polisyos.runtime.quality.authority import (
        OutcomeReplayProof,
        ProductionLoopRunProof,
    )
    from tools.quality.validation.gy_evidence_canon import canonical_evidence_hash

    if outcome.get("trigger_kind") != "http_control_route":
        issues.append({"code": "layer3_gy_outcome_direct_helper_rejected"})
    if outcome.get("proof_source") != "production_http_route_recomputed":
        issues.append({"code": "layer3_gy_outcome_hand_authored_proof_rejected"})
    proof_payload = outcome.get("production_loop_run_proof")
    contract = outcome.get("search_exit_contract")
    replay_payload = replay_artifact.get("replay_proof")
    if not isinstance(proof_payload, dict):
        issues.append({"code": "layer3_gy_outcome_production_proof_missing"})
        return
    if not isinstance(contract, dict):
        issues.append({"code": "layer3_gy_outcome_search_exit_contract_missing"})
        return
    if not isinstance(replay_payload, dict):
        issues.append({"code": "layer3_gy_outcome_replay_proof_missing"})
        return
    try:
        proof = ProductionLoopRunProof.model_validate(proof_payload)
        replay = OutcomeReplayProof.model_validate(replay_payload)
    except ValidationError:
        issues.append({"code": "layer3_gy_outcome_typed_proof_invalid"})
        return

    receipts = outcome.get("http_receipts")
    launch = receipts.get("launch") if isinstance(receipts, dict) else None
    readback = receipts.get("readback") if isinstance(receipts, dict) else None
    if not isinstance(launch, dict) or (
        launch.get("method") != "POST"
        or launch.get("surface") != "/api/v1/control/runs"
        or launch.get("status_code") != 200
        or launch.get("job_id") != proof.job_id
        or launch.get("run_id") != proof.run_id
    ):
        issues.append({"code": "layer3_gy_outcome_http_launch_receipt_invalid"})
    if not isinstance(readback, dict) or (
        readback.get("method") != "GET"
        or readback.get("status_code") != 200
        or readback.get("observed_state") != "completed"
        or proof.job_id not in str(readback.get("surface") or "")
    ):
        issues.append({"code": "layer3_gy_outcome_http_readback_receipt_invalid"})

    terminal = contract.get("terminal_state")
    terminal_kind = terminal.get("kind") if isinstance(terminal, dict) else None
    accepted_terminals = {
        "grounded_partial_admissible",
        "grounded_abstention",
        "search_ceiling_repair_required",
        "acquisition_required",
        "a_spec_gap",
        "tool_failure",
        "composition_invalid",
        "recursive_blocked",
        "budget_exhausted",
        "human_decision_required",
    }
    if terminal_kind not in accepted_terminals:
        issues.append({"code": "layer3_gy_outcome_terminal_invalid"})
    if terminal_kind != outcome.get("terminal_outcome"):
        issues.append({"code": "layer3_gy_outcome_terminal_projection_drift"})
    if outcome.get("case_id") == "ua-msme-affordable-loans-2022" and (
        terminal_kind == "grounded_partial_admissible"
        or outcome.get("useful_design_credit") is not False
    ):
        issues.append({"code": "layer3_gy_outcome_ua_msme_forced_value_rejected"})
    gx_case_outcome = outcome.get("gx_case_outcome")
    if not isinstance(gx_case_outcome, dict) or (
        gx_case_outcome.get("case_id") != outcome.get("case_id")
        or gx_case_outcome.get("outcome_kind") != terminal_kind
        or gx_case_outcome.get("useful_design_credit") is not outcome.get("useful_design_credit")
        or not _looks_like_sha256_ref(str(gx_case_outcome.get("final_run_hash") or ""))
        or gx_case_outcome.get("input_artifact_ref") not in replay.input_hashes
    ):
        issues.append({"code": "layer3_gy_outcome_gx_terminal_drift"})
    if not contract.get("incompleteness_record") or not outcome.get("incompleteness"):
        issues.append({"code": "layer3_gy_outcome_incompleteness_missing"})
    boundary = contract.get("authority_boundary")
    expected_evidence_kind = boundary.get("evidence_kind") if isinstance(boundary, dict) else None
    expected_decision_grade = (
        boundary.get("decision_grade") if isinstance(boundary, dict) else "unsupported"
    ) or "unsupported"
    if contract.get("evidence_kind") != expected_evidence_kind:
        issues.append({"code": "layer3_gy_outcome_evidence_kind_drift"})
    if contract.get("decision_grade") != expected_decision_grade:
        issues.append({"code": "layer3_gy_outcome_decision_grade_drift"})
    if contract.get("evidence_ladder_rung") != (expected_evidence_kind or "none"):
        issues.append({"code": "layer3_gy_outcome_ladder_rung_drift"})

    recomputed_output_hash = canonical_evidence_hash(contract)
    if (
        replay.output_hash != recomputed_output_hash
        or outcome.get("output_hash") != recomputed_output_hash
    ):
        issues.append({"code": "layer3_gy_outcome_replay_output_drift"})
    if replay.replay_levels != ["A", "B", "C"] or any(
        level.status != "verified" for level in replay.level_proofs
    ):
        issues.append({"code": "layer3_gy_outcome_replay_levels_invalid"})
    if not replay.input_hashes or replay.input_hashes != outcome.get("input_hashes"):
        issues.append({"code": "layer3_gy_outcome_input_hash_drift"})
    if not replay.producer_roots or replay.producer_roots != outcome.get("producer_roots"):
        issues.append({"code": "layer3_gy_outcome_producer_roots_missing"})

    cas_checks = outcome.get("cas_resolution_checks")
    resolved_refs = {
        str(item.get("artifact_ref"))
        for item in cas_checks or []
        if isinstance(item, dict) and item.get("resolved") is True
    }
    if any(
        item.get("payload_sha256") != item.get("artifact_ref")
        for item in cas_checks or []
        if isinstance(item, dict) and item.get("resolved") is True
    ):
        issues.append({"code": "layer3_gy_outcome_cas_content_hash_drift"})
    if not set(proof.output_cas_refs) <= resolved_refs:
        issues.append({"code": "layer3_gy_outcome_cas_resolution_missing"})
    proof_ref = str(outcome.get("production_loop_run_proof_ref") or "")
    recomputed_proof_ref = (
        "sha256:"
        + hashlib.sha256(
            to_canonical_bytes(proof_payload, CanonSpec(forbid_floats=False))
        ).hexdigest()
    )
    if proof_ref not in resolved_refs or proof_ref != recomputed_proof_ref:
        issues.append({"code": "layer3_gy_outcome_production_proof_content_drift"})
    artifacts_index = outcome.get("artifacts_index")
    if not isinstance(artifacts_index, dict) or any(
        key not in artifacts_index for key in proof.artifacts_index_refs
    ):
        issues.append({"code": "layer3_gy_outcome_artifacts_index_resolution_missing"})
    if proof.output_replay_proof_ref != outcome.get("outcome_replay_proof_ref"):
        issues.append({"code": "layer3_gy_outcome_replay_ref_drift"})
    if proof.control_store_state_transitions != ["pending", "running", "completed"]:
        issues.append({"code": "layer3_gy_outcome_store_transitions_invalid"})
    if "runs_readback" not in proof.surface_reads_checked or not proof.surface_readbacks:
        issues.append({"code": "layer3_gy_outcome_runs_readback_missing"})


def _run_durable_workspace_loop_proof(
    *,
    fixture_id: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Return only the proof payload for compatibility with older tests."""

    return _run_durable_workspace_loop_observation(
        fixture_id=fixture_id,
        repo_root=(repo_root or Path.cwd()).resolve(),
        catalog_mode="slice0_fixture",
    )["proof"]


def _run_durable_workspace_loop_observation(
    *,
    fixture_id: str,
    repo_root: Path,
    catalog_mode: str,
) -> dict[str, Any]:
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_registry_providers import (
        resolve_control_registry_providers,
    )
    from polisyos.runtime.http.services.control_worker import ControlWorker
    from polisyos.runtime.quality.authority import (
        OutcomeReplayProof,
        ProductionLoopRunProof,
    )

    try:
        from fastapi.testclient import TestClient
    except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency gate
        raise RuntimeError("FastAPI TestClient is required for production-route proof") from exc

    request = CanonicalLoopRequest(fixture_id=fixture_id, catalog_mode=catalog_mode)
    fixed_now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
    uuid_iter = _deterministic_uuid_sequence(
        f"gy-loop-proof:{catalog_mode}:{fixture_id}"
    )
    if catalog_mode == "production":
        catalog_root = (
            repo_root
            / "production_data/datasets_full_phase3full_20260327_183054"
        )
        catalog_path = catalog_root / "dataset_catalog.duckdb"
        if not catalog_path.is_file():
            raise RuntimeError(
                "GY-L production catalog prerequisite missing: " + str(catalog_path)
            )
        from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph

        catalog_graph = DatasetCatalogGraph(catalog_path, catalog_root)
        gx_input_path = (
            repo_root
            / "architecture/policy_design_case/layer3_gx_reports/"
            "ua-msme-affordable-loans-2022/"
            "layer3_gx_final_pinned_route_outcome_report.json"
        )
        root_payload = json.loads(gx_input_path.read_text(encoding="utf-8"))
        gx_validator_status = "not_measured"
    elif catalog_mode == "slice0_fixture":
        catalog_graph = None
        root_payload = {"fixture_id": fixture_id, "root": True}
        gx_validator_status = "not_applicable_slice0_fixture"
    else:
        raise ValueError(f"unsupported catalog_mode: {catalog_mode}")

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.security import build_fixture_identity_claims

    identity = build_fixture_identity_claims()
    with (
        tempfile.TemporaryDirectory(prefix=f"polisyos-gy-loop-proof-{fixture_id}-") as tmp,
        tenant_scope(None, tenant_id=identity.tenant_id, cell_id=identity.cell_id),
    ):
        root = Path(tmp)
        cas_root = root / ".polisyos"
        from polisyos.runtime.http.dependencies import build_runtime_api_context

        runtime_context = build_runtime_api_context(
            cas_root=cas_root, core_runs_root=cas_root / "runs"
        )
        store = runtime_context.store
        root_ref = store.put_json(
            root_payload,
            PutOptions(
                kind="gy.loop.proof.root",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.gy.loop.proof.root", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        if catalog_graph is None:
            catalog_graph = build_slice0_fixture_catalog_graph(root / "catalog")
        catalog_before = catalog_graph._store._fetch_source_identities()
        http_request = request.http_body(str(root_ref.artifact_id))
        providers = resolve_control_registry_providers(
            gy_catalog_graph=catalog_graph
        )
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "polisyos.core.run.context.new_run_id",
                    return_value=f"run-gy-loop-proof-{fixture_id}",
                )
            )
            for target in (
                "polisyos.runtime.http.services.control.run_lifecycle.uuid.uuid4",
                "polisyos.runtime.http.services.control.workspace_loop_transition.uuid.uuid4",
                "polisyos.runtime.http.services.control_worker.uuid.uuid4",
            ):
                stack.enter_context(patch(target, side_effect=lambda: next(uuid_iter)))
            stack.enter_context(
                patch(
                    "polisyos.runtime.http.services.control_plane_store._utc_now",
                    return_value=fixed_now,
                )
            )
            stack.enter_context(
                patch(
                    "polisyos.runtime.quality.acquisition_planner._utc",
                    return_value=fixed_now,
                )
            )
            stack.enter_context(
                patch(
                    "polisyos.runtime.quality.workspace.loop._utc_now",
                    return_value=fixed_now,
                )
            )
            service = ControlPlaneService(
                cas_root=cas_root,
                core_runs_root=cas_root / "runs",
                artifact_store=store,
                registry_providers=providers,
                policy_resolver=RuntimeExecutionPolicyResolver(
                    default_profile="dev",
                    worker_backend="external",
                    state_store_backend="sqlite",
                    sqlite_path=str(root / "control_plane.sqlite3"),
                    postgres_dsn=None,
                ),
            )
            from polisyos.runtime.quality.workspace.loop import WorkspaceLoop

            exit_capture = _LiveLoopExitCapture(store)
            original_verifier = WorkspaceLoop._verifier_certified_envelope
            original_run = service._run_workspace_loop_fixture

            def observe_verifier(loop: Any, *args: Any, **kwargs: Any) -> BaseModel:
                envelope = original_verifier(loop, *args, **kwargs)
                exit_capture.observe_envelope(loop, envelope)
                return envelope

            def observe_run(*, job: Any, fixture_id: str) -> BaseModel:
                contract = original_run(job=job, fixture_id=fixture_id)
                exit_capture.observe_contract(contract, job.job_id)
                return contract

            stack.enter_context(
                patch.object(WorkspaceLoop, "_verifier_certified_envelope", new=observe_verifier)
            )
            stack.enter_context(
                patch.object(service, "_run_workspace_loop_fixture", new=observe_run)
            )
            service._worker = ControlWorker(
                store=service._control_store,
                handler=service._process_control_job,
                worker_id=(
                    f"control-worker-gy-loop-proof-{catalog_mode}-{_slug(fixture_id)}"
                ),
            )
            app = create_runtime_api_app(
                cas_root=cas_root,
                core_runs_root=cas_root / "runs",
                enable_security_middlewares=False,
                allow_fixture_identity=True,
                container_overrides=RuntimeContainerOverrides(
                    runtime_api_context=runtime_context,
                    decision_validity_service=service._decision_validity_service,
                    control_service=service,
                ),
            )
            try:
                with TestClient(app) as client:
                    launch_response = client.post(
                        "/api/v1/control/runs",
                        json=http_request,
                        headers={"X-Request-ID": request.http_request_id()},
                    )
                    if launch_response.status_code != 200:
                        raise RuntimeError(
                            "Production control route rejected GY loop run: "
                            f"{launch_response.status_code} {launch_response.text}"
                        )
                    launch = launch_response.json()
                    if service._worker is None:
                        raise RuntimeError("ControlWorker was not initialized")
                    service._worker.dispatch_once()
                    readback_response = client.get(
                        f"/api/v1/control/jobs/{launch['job_id']}",
                        headers={
                            "X-Request-ID": (
                                f"gy-loop-readback-{catalog_mode}-{_slug(fixture_id)}"
                            )
                        },
                    )
                    response_payload = readback_response.json()
                    if response_payload.get("state") != "completed":
                        raise RuntimeError(
                            f"Durable proof job for {fixture_id} did not complete: "
                            f"{response_payload.get('state')}"
                        )
                    progress = dict(response_payload["progress"])
                    proof_payload = progress.get("production_loop_run_proof")
                    proof = ProductionLoopRunProof.model_validate(proof_payload)
                    contract_payload = progress.get("search_exit_contract")
                    replay_payload = progress.get("outcome_replay_proof")
                    replay = OutcomeReplayProof.model_validate(replay_payload)
                    cas_checks = []
                    proof_ref = str(progress["production_loop_run_proof_ref"])
                    for artifact_ref in [*proof.output_cas_refs, proof_ref]:
                        payload_bytes = store.get_bytes(artifact_ref)
                        cas_checks.append(
                            {
                                "artifact_ref": artifact_ref,
                                "resolved": True,
                                "payload_sha256": "sha256:"
                                + hashlib.sha256(payload_bytes).hexdigest(),
                            }
                        )
                    observation = {
                        "fixture_id": fixture_id,
                        "proof": proof.model_dump(mode="json", by_alias=True),
                        "proof_ref": proof_ref,
                        "outcome_replay_proof": replay.model_dump(mode="json"),
                        "search_exit_contract": (
                            contract_payload if isinstance(contract_payload, dict) else {}
                        ),
                        "artifacts_index": dict(progress.get("artifacts_index") or {}),
                        "cas_resolution_checks": cas_checks,
                        "trigger_kind": "http_control_route",
                        "gx_validator_status": gx_validator_status,
                        "gx_case_outcome": {
                            "case_id": str(root_payload.get("case_id") or ""),
                            "status": str(root_payload.get("status") or ""),
                            "outcome_kind": str(root_payload.get("outcome_kind") or ""),
                            "useful_design_credit": root_payload.get("useful_design_credit"),
                            "final_run_hash": str(root_payload.get("final_run_hash") or ""),
                            "input_artifact_ref": str(root_ref.artifact_id),
                        },
                        "http_receipts": {
                            "launch": {
                                "method": "POST",
                                "surface": "/api/v1/control/runs",
                                "status_code": launch_response.status_code,
                                "run_id": launch["run_id"],
                                "job_id": launch["job_id"],
                            },
                            "readback": {
                                "method": "GET",
                                "surface": f"/api/v1/control/jobs/{launch['job_id']}",
                                "status_code": readback_response.status_code,
                                "observed_state": response_payload["state"],
                            },
                        },
                    }
                    return _verify_live_loop_observation(
                        observation,
                        request=request,
                        http_request=http_request,
                        root_ref=str(root_ref.artifact_id),
                        root_payload=root_payload,
                        service=service,
                        catalog_graph=catalog_graph,
                        catalog_before=catalog_before,
                        exit_capture=exit_capture,
                    )
            finally:
                service.close()


def _deterministic_uuid_sequence(seed: str) -> Iterator[uuid.UUID]:
    index = 0
    while True:
        yield uuid.uuid5(uuid.NAMESPACE_URL, f"{seed}:{index}")
        index += 1


def _slug(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
    compact = "-".join(part for part in normalized.split("-") if part)
    return compact or "item"


def _ensure_src_path(repo_root: Path) -> None:
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def _read_json(path: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues.append({"code": "layer3_gy_artifact_missing", "path": str(path)})
        return {}
    except json.JSONDecodeError as exc:
        issues.append({"code": "layer3_gy_artifact_invalid_json", "path": str(path), "error": str(exc)})
        return {}
    if not isinstance(payload, dict):
        issues.append({"code": "layer3_gy_artifact_not_object", "path": str(path)})
        return {}
    return payload


def _validate_production_loop_proof(
    index: int,
    proof: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    required_fields = (
        "run_id",
        "job_id",
        "endpoint",
        "http_request_id",
        "job_kind",
        "worker_lease_id",
        "worker_id",
        "_execute_workflow_invocation_id",
        "workspace_loop_invocation_id",
        "control_store_state_transitions",
        "input_artifacts",
        "output_search_exit_contract_ref",
        "output_replay_proof_ref",
        "output_cas_refs",
        "artifacts_index_refs",
        "surface_reads_checked",
        "legacy_path_disposition",
    )
    for field in required_fields:
        if not proof.get(field):
            issues.append(
                {
                    "code": "layer3_gy_proof_field_missing",
                    "index": str(index),
                    "field": field,
                }
            )
    if proof.get("endpoint") != "/api/v1/control/runs":
        issues.append({"code": "layer3_gy_proof_endpoint_not_runs", "index": str(index)})
    if proof.get("job_kind") != "workflow_run":
        issues.append({"code": "layer3_gy_proof_job_kind_not_workflow", "index": str(index)})
    if proof.get("legacy_path_disposition") != "routed_to_workspace_loop":
        issues.append(
            {"code": "layer3_gy_proof_not_workspace_loop_authority_path", "index": str(index)}
        )
    if proof.get("control_store_state_transitions") != ["pending", "running", "completed"]:
        issues.append({"code": "layer3_gy_proof_state_sequence_invalid", "index": str(index)})
    if "runs_readback" not in set(proof.get("surface_reads_checked") or []):
        issues.append({"code": "layer3_gy_proof_runs_readback_missing", "index": str(index)})
    readbacks = proof.get("surface_readbacks")
    if not isinstance(readbacks, list) or not readbacks:
        issues.append(
            {"code": "layer3_gy_proof_runs_readback_observation_missing", "index": str(index)}
        )
    else:
        observed_results = set()
        for readback_index, readback in enumerate(readbacks):
            if not isinstance(readback, dict):
                issues.append(
                    {
                        "code": "layer3_gy_proof_readback_not_object",
                        "index": str(index),
                        "readback_index": str(readback_index),
                    }
                )
                continue
            observed_results.add(str(readback.get("observed_authority_result") or ""))
            if readback.get("surface") != "/api/v1/control/runs":
                issues.append(
                    {
                        "code": "layer3_gy_proof_readback_surface_invalid",
                        "index": str(index),
                        "readback_index": str(readback_index),
                    }
                )
            if readback.get("observed_job_state") != "completed":
                issues.append(
                    {
                        "code": "layer3_gy_proof_readback_not_completed",
                        "index": str(index),
                        "readback_index": str(readback_index),
                    }
                )
            if readback.get("observed_search_exit_contract_ref") != proof.get(
                "output_search_exit_contract_ref"
            ):
                issues.append(
                    {
                        "code": "layer3_gy_proof_readback_contract_ref_mismatch",
                        "index": str(index),
                        "readback_index": str(readback_index),
                    }
                )
            if readback.get("matched_search_exit_contract_ref") is not True:
                issues.append(
                    {
                        "code": "layer3_gy_proof_readback_match_not_true",
                        "index": str(index),
                        "readback_index": str(readback_index),
                    }
                )
        if "verifier_stamped" in observed_results and (
            "authority_derivation_trace_refs"
            not in set(proof.get("artifacts_index_refs") or [])
        ):
            issues.append(
                {"code": "layer3_gy_proof_authority_trace_ref_missing", "index": str(index)}
            )
        if "acquisition_required" in observed_results and (
            "authority_derivation_trace_refs"
            in set(proof.get("artifacts_index_refs") or [])
        ):
            issues.append(
                {
                    "code": "layer3_gy_proof_acquisition_must_not_claim_authority_trace",
                    "index": str(index),
                }
            )
    if not str(proof.get("worker_lease_id") or "").startswith("control-worker"):
        issues.append({"code": "layer3_gy_proof_worker_lease_missing", "index": str(index)})
    if proof.get("worker_lease_id") != proof.get("worker_id"):
        issues.append({"code": "layer3_gy_proof_worker_lease_mismatch", "index": str(index)})
    refs = [
        str(proof.get("output_search_exit_contract_ref") or ""),
        str(proof.get("output_replay_proof_ref") or ""),
        *[str(ref) for ref in proof.get("output_cas_refs") or []],
    ]
    for ref in refs:
        if not _looks_like_sha256_ref(ref):
            issues.append(
                {
                    "code": "layer3_gy_proof_ref_not_content_addressed",
                    "index": str(index),
                    "ref": ref,
                }
            )
        elif len(set(ref.removeprefix("sha256:"))) == 1:
            issues.append(
                {
                    "code": "layer3_gy_proof_placeholder_ref",
                    "index": str(index),
                    "ref": ref,
                }
            )


def _looks_like_sha256_ref(value: str) -> bool:
    prefix = "sha256:"
    return (
        value.startswith(prefix)
        and len(value) == len(prefix) + 64
        and all(char in "0123456789abcdef" for char in value[len(prefix) :])
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-format", choices=("json", "text"), default="text")
    parser.add_argument("--check", action="store_true", help="Validate committed artifacts.")
    parser.add_argument("--write", action="store_true", help="Regenerate committed proof artifacts.")
    parser.add_argument(
        "--corrupt-field-drift-check",
        action="store_true",
        help="Mutate a recomputed graded-outcome field and require validation to fail.",
    )
    parser.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child is not None:
        return _gx_child(args.child.resolve())
    if args.check and args.write:
        parser.error("--check and --write are mutually exclusive")

    with contextlib.redirect_stdout(sys.stderr):
        report = validate(
            Path(args.repo_root).resolve(),
            write=args.write,
            corrupt_field_drift_check=args.corrupt_field_drift_check,
        )
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Layer 3 GY loop artifacts: {report['status']}")
        for issue in report["issues"]:
            print(f"- {issue['code']}: {issue}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(
        run_timed_entrypoint(
            main,
            script_path=__file__,
            argv=sys.argv[1:],
            started_perf_counter=_TIMING_STARTED_AT,
        )
    )
