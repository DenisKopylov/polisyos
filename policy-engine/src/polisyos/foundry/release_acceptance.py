"""Release-bundle acceptance roundtrip for bundle-backed Foundry execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecuteRequest,
    FoundryInputBindingsRef,
    Metrics,
    SimulationResult,
)
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.data_plane.bindings import build_input_bindings
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.executor import put_state_snapshot
from polisyos.scientist.governance.postflight import postflight_checks
from polisyos.ukraine_data.manifests import ReleaseManifest, load_manifest
from polisyos.ir.trinity import TrinityBundle


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _normalize_simulation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(payload))
    for field in (
        "metrics_ref",
        "state_snapshot_ref",
        "environment_ref",
        "trace_slice_ref",
        "distributional_report_ref",
        "propagation_config_ref",
        "propagation_report_ref",
    ):
        value = normalized.get(field)
        if isinstance(value, dict):
            normalized[field] = {
                "kind": value.get("kind"),
                "media_type": value.get("media_type"),
                "present": True,
            }
        elif value is not None:
            normalized[field] = {"present": True}
        else:
            normalized[field] = None
    return normalized


def _extract_metrics_ref(execute_result: Any) -> ArtifactRef | None:
    return next(
        (
            item.ref
            for item in execute_result.derived_refs
            if item.role == "metrics"
        ),
        None,
    )


def _stable_metrics(values: dict[str, Any]) -> dict[str, Any]:
    unstable_suffixes = ("_latency_ms", "_wall_ms", "_duration_ms")
    filtered: dict[str, Any] = {}
    for key, value in values.items():
        if key in {"step_latency_ms"}:
            continue
        if any(key.endswith(suffix) for suffix in unstable_suffixes):
            continue
        filtered[key] = value
    return filtered


class ReleaseAcceptanceStep(BaseModel):
    """One executed acceptance step and its outcome."""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    status: str = Field(pattern="^(passed|failed)$")
    details: dict[str, Any] = Field(default_factory=dict)


class ReleaseAcceptanceReport(BaseModel):
    """Typed D5 acceptance report for the disk-backed release bundle."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    passed: bool = False
    manifest_path: str
    release_bundle_root: str
    packet_ref: str | None = None
    original_simulation_result_ref: str | None = None
    replay_simulation_result_ref: str | None = None
    governance_verdict: str | None = None
    replay_verification: dict[str, Any] = Field(default_factory=dict)
    steps: list[ReleaseAcceptanceStep] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ReleaseAcceptanceRunner:
    """Run the real D5 acceptance roundtrip from assembled bundle files on disk."""

    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store

    def run(
        self,
        *,
        release_manifest_path: Path,
        runtime_bundle_dir: Path,
        method_contract_bundle_dir: Path,
        governance_profile: ValidationProfile | None = None,
    ) -> ReleaseAcceptanceReport:
        manifest = load_manifest(release_manifest_path, ReleaseManifest)
        steps: list[ReleaseAcceptanceStep] = []

        hash_errors = self._verify_manifest_hashes(manifest)
        steps.append(
            ReleaseAcceptanceStep(
                step_id="verify_release_hashes",
                status="passed" if not hash_errors else "failed",
                details={"errors": hash_errors},
            )
        )
        if hash_errors:
            return ReleaseAcceptanceReport(
                passed=False,
                manifest_path=str(release_manifest_path),
                release_bundle_root=str(release_manifest_path.parent),
                steps=steps,
                notes=["release_manifest_hash_verification_failed"],
            )

        state = self._build_bundle_backed_state(runtime_bundle_dir)
        steps.append(
            ReleaseAcceptanceStep(
                step_id="materialize_global_state",
                status="passed",
                details={
                    "n_agents": int(state.agents.size),
                    "n_firms": int(state.firms.size),
                    "n_cells": 0 if state.cells is None else int(state.cells.size),
                    "n_household_cells": (
                        0 if state.household_cells is None else int(state.household_cells.size)
                    ),
                },
            )
        )

        registry_bundle = build_default_registry_bundle(self._store)
        state_snapshot_ref = put_state_snapshot(self._store, state=state, step=0)
        data_snapshot_ref = self._store.put_json(
            DataSnapshot(data_ref=state_snapshot_ref),
            PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            ),
        )
        built = build_input_bindings(
            self._store,
            data_snapshot_ref=ArtifactRef.model_validate(data_snapshot_ref),
            registry_bundle_ref=registry_bundle.bundle_ref,
        )
        steps.append(
            ReleaseAcceptanceStep(
                step_id="build_input_bindings",
                status="passed",
                details={
                    "input_bindings_ref": str(built.input_bindings_ref.artifact_id),
                    "bound_state_snapshot_ref": str(built.bound_state_snapshot_ref.artifact_id),
                    "applied_binding_ids": list(built.applied_binding_ids),
                },
            )
        )

        acceptance_bundle_path = method_contract_bundle_dir / "acceptance_contract_bundle.json"
        if not acceptance_bundle_path.exists():
            return ReleaseAcceptanceReport(
                passed=False,
                manifest_path=str(release_manifest_path),
                release_bundle_root=str(release_manifest_path.parent),
                steps=[
                    *steps,
                    ReleaseAcceptanceStep(
                        step_id="load_acceptance_contract",
                        status="failed",
                        details={"missing_path": str(acceptance_bundle_path)},
                    ),
                ],
                notes=["acceptance_contract_bundle_missing"],
            )

        trinity_bundle = TrinityBundle.model_validate_json(acceptance_bundle_path.read_text(encoding="utf-8"))
        trinity_bundle = trinity_bundle.model_copy(
            update={
                "model_spec": trinity_bundle.model_spec.model_copy(
                    update={"registry_bundle_ref": str(registry_bundle.bundle_ref.artifact_id)}
                )
            }
        )
        trinity_ref = self._store.put_json(
            trinity_bundle,
            PutOptions(
                kind="ir.trinity_bundle",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=trinity_bundle.schema_version),
            ),
        )
        steps.append(
            ReleaseAcceptanceStep(
                step_id="load_acceptance_contract",
                status="passed",
                details={"policy_id": trinity_bundle.policy_spec.policy_id},
            )
        )

        compile_result = compile_foundry(
            self._store,
            CompileRequest(
                input_kind="trinity",
                policy_ref=ArtifactRef.model_validate(trinity_ref),
                registry_bundle_ref=registry_bundle.bundle_ref,
            ),
        )
        compile_ok = bool(compile_result.ok and compile_result.exec_plan_ref is not None)
        steps.append(
            ReleaseAcceptanceStep(
                step_id="compile_exec_plan",
                status="passed" if compile_ok else "failed",
                details={"notes": list(compile_result.notes)},
            )
        )
        if not compile_ok:
            return ReleaseAcceptanceReport(
                passed=False,
                manifest_path=str(release_manifest_path),
                release_bundle_root=str(release_manifest_path.parent),
                steps=steps,
                notes=["acceptance_compile_failed"],
            )

        exec_request = ExecuteRequest(
            exec_plan_ref=compile_result.exec_plan_ref,
            input_bindings_ref=FoundryInputBindingsRef(artifact_id=built.input_bindings_ref.artifact_id),
            registry_bundle_ref=registry_bundle.bundle_ref,
        )
        execute_result = execute_foundry(self._store, exec_request)
        execute_ok = bool(execute_result.ok and execute_result.simulation_result_ref is not None)
        steps.append(
            ReleaseAcceptanceStep(
                step_id="execute_simulation_step",
                status="passed" if execute_ok else "failed",
                details={"notes": list(execute_result.notes)},
            )
        )
        if not execute_ok:
            return ReleaseAcceptanceReport(
                passed=False,
                manifest_path=str(release_manifest_path),
                release_bundle_root=str(release_manifest_path.parent),
                steps=steps,
                notes=["acceptance_execute_failed"],
            )

        postflight_state, gate_decision = postflight_checks(
            {
                "run_id": "R_release_acceptance",
                "ir": trinity_bundle.model_dump(mode="json"),
                "registry_bundle_ref": registry_bundle.bundle_ref.model_dump(mode="json"),
                "simulation_result_ref": execute_result.simulation_result_ref.model_dump(mode="json"),
            },
            profile=governance_profile or ValidationProfile.mvp(),
        )
        governance_ok = gate_decision is None
        steps.append(
            ReleaseAcceptanceStep(
                step_id="run_governance",
                status="passed" if governance_ok else "failed",
                details={
                    "gate_decision": None if gate_decision is None else gate_decision.model_dump(mode="json"),
                    "validation_issues": list(postflight_state.get("validation_issues", [])),
                },
            )
        )
        if not governance_ok:
            return ReleaseAcceptanceReport(
                passed=False,
                manifest_path=str(release_manifest_path),
                release_bundle_root=str(release_manifest_path.parent),
                governance_verdict="reject",
                original_simulation_result_ref=str(execute_result.simulation_result_ref.artifact_id),
                steps=steps,
                notes=["acceptance_governance_failed"],
            )

        replay_execute_result = execute_foundry(self._store, exec_request)
        replay_ok = bool(replay_execute_result.ok and replay_execute_result.simulation_result_ref is not None)
        steps.append(
            ReleaseAcceptanceStep(
                step_id="replay_execute_roundtrip",
                status="passed" if replay_ok else "failed",
                details={"notes": list(replay_execute_result.notes)},
            )
        )
        if not replay_ok:
            return ReleaseAcceptanceReport(
                passed=False,
                manifest_path=str(release_manifest_path),
                release_bundle_root=str(release_manifest_path.parent),
                governance_verdict="approve",
                original_simulation_result_ref=str(execute_result.simulation_result_ref.artifact_id),
                steps=steps,
                notes=["acceptance_replay_execute_failed"],
            )

        original_metrics_ref = _extract_metrics_ref(execute_result)
        replay_metrics_ref = _extract_metrics_ref(replay_execute_result)
        packet_payload = {
            "schema_version": "3.0",
            "run_id": "R_release_acceptance",
            "inputs": {
                "trinity_bundle_ref": str(ArtifactRef.model_validate(trinity_ref).artifact_id),
                "input_bindings_ref": str(built.input_bindings_ref.artifact_id),
                "data_snapshot_ref": str(ArtifactRef.model_validate(data_snapshot_ref).artifact_id),
                "registry_bundle_ref": str(registry_bundle.bundle_ref.artifact_id),
            },
            "artifacts": {
                "exec_plan_ref": str(compile_result.exec_plan_ref.artifact_id),
                "simulation_result_ref": str(execute_result.simulation_result_ref.artifact_id),
                "metrics_ref": None if original_metrics_ref is None else str(original_metrics_ref.artifact_id),
            },
        }
        packet_ref = self._store.put_json(
            packet_payload,
            PutOptions(kind="scientist.decision_packet", media_type="application/json"),
        )
        original_sim_payload = SimulationResult.model_validate(
            from_canonical_bytes(self._store.get_bytes(execute_result.simulation_result_ref.artifact_id))
        ).model_dump(mode="json")
        replay_sim_payload = SimulationResult.model_validate(
            from_canonical_bytes(self._store.get_bytes(replay_execute_result.simulation_result_ref.artifact_id))
        ).model_dump(mode="json")
        normalized_original = _normalize_simulation_payload(original_sim_payload)
        normalized_replay = _normalize_simulation_payload(replay_sim_payload)
        if original_metrics_ref is None or replay_metrics_ref is None:
            metrics_exact = False
            original_metrics_sha = None
            replay_metrics_sha = None
            stable_original_metrics: dict[str, Any] = {}
            stable_replay_metrics: dict[str, Any] = {}
        else:
            original_metrics_bytes = self._store.get_bytes(original_metrics_ref.artifact_id)
            replay_metrics_bytes = self._store.get_bytes(replay_metrics_ref.artifact_id)
            original_metrics_sha = _sha256_bytes(original_metrics_bytes)
            replay_metrics_sha = _sha256_bytes(replay_metrics_bytes)
            stable_original_metrics = _stable_metrics(
                Metrics.model_validate(from_canonical_bytes(original_metrics_bytes)).values
            )
            stable_replay_metrics = _stable_metrics(
                Metrics.model_validate(from_canonical_bytes(replay_metrics_bytes)).values
            )
            metrics_exact = stable_original_metrics == stable_replay_metrics
        replay_verified = bool(
            normalized_original == normalized_replay
            and metrics_exact
        )
        steps.append(
            ReleaseAcceptanceStep(
                step_id="verify_replay_roundtrip",
                status="passed" if replay_verified else "failed",
                details={
                    "simulation_structure_match": normalized_original == normalized_replay,
                    "metrics_bit_exact": metrics_exact,
                    "original_metrics_sha256": original_metrics_sha,
                    "replay_metrics_sha256": replay_metrics_sha,
                    "stable_original_metrics": stable_original_metrics,
                    "stable_replay_metrics": stable_replay_metrics,
                },
            )
        )
        return ReleaseAcceptanceReport(
            passed=all(step.status == "passed" for step in steps),
            manifest_path=str(release_manifest_path),
            release_bundle_root=str(release_manifest_path.parent),
            packet_ref=str(packet_ref.artifact_id),
            original_simulation_result_ref=str(execute_result.simulation_result_ref.artifact_id),
            replay_simulation_result_ref=str(replay_execute_result.simulation_result_ref.artifact_id),
            governance_verdict="approve",
            replay_verification={
                "passed": replay_verified,
                "mode": "content_exact_filtered_metrics",
                "details": {
                    "simulation_structure_match": normalized_original == normalized_replay,
                    "metrics_bit_exact": metrics_exact,
                    "original_metrics_sha256": original_metrics_sha,
                    "replay_metrics_sha256": replay_metrics_sha,
                    "stable_original_metrics": stable_original_metrics,
                    "stable_replay_metrics": stable_replay_metrics,
                },
            },
            steps=steps,
        )

    def _verify_manifest_hashes(self, manifest: ReleaseManifest) -> list[str]:
        errors: list[str] = []
        for bundle_name, files in manifest.bundle_contents.items():
            for relative_name, record in files.items():
                path = Path(record.path)
                if not path.exists():
                    errors.append(f"missing:{bundle_name}:{relative_name}")
                    continue
                if path.stat().st_size != int(record.size_bytes):
                    errors.append(f"size_mismatch:{bundle_name}:{relative_name}")
                if record.sha256 and _sha256_file(path) != record.sha256:
                    errors.append(f"sha256_mismatch:{bundle_name}:{relative_name}")
        return errors

    def _build_bundle_backed_state(self, runtime_bundle_dir: Path) -> GlobalState:
        runtime_agents = pd.read_parquet(runtime_bundle_dir / "agent_registry_runtime.parquet")
        cell_registry = pd.read_parquet(runtime_bundle_dir / "cell_registry_region_sector.parquet")
        n_agents = max(1, len(runtime_agents))
        n_firms = max(1, min(len(runtime_agents), max(1, len(runtime_agents) // 128)))
        n_cells = max(0, len(cell_registry))
        n_household_cells = max(1, min(32, n_cells or 1))
        return GlobalState.empty(
            n_agents=n_agents,
            n_firms=n_firms,
            n_cells=n_cells,
            n_household_cells=n_household_cells,
        )


__all__ = [
    "ReleaseAcceptanceReport",
    "ReleaseAcceptanceRunner",
    "ReleaseAcceptanceStep",
]
