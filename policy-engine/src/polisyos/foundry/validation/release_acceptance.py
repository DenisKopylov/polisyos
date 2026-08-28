"""CAS-backed Foundry compilation, execution, and replay acceptance receipt."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
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
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.data_plane.bindings import build_input_bindings
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.ir.trinity import TrinityBundle


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
        (item.ref for item in execute_result.derived_refs if item.role == "metrics"),
        None,
    )


def _stable_metrics(values: dict[str, Any]) -> dict[str, Any]:
    unstable_suffixes = ("_latency_ms", "_wall_ms", "_duration_ms")
    return {
        key: value
        for key, value in values.items()
        if key != "step_latency_ms"
        and not any(key.endswith(suffix) for suffix in unstable_suffixes)
    }


class ReleaseAcceptanceStep(BaseModel):
    """One executed Foundry acceptance step and its outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str
    status: str = Field(pattern="^(passed|failed)$")
    details: dict[str, Any] = Field(default_factory=dict)


class ReleaseAcceptanceReport(BaseModel):
    """Legacy-shaped Scientist release projection returned at the CLI boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["2.0"] = "2.0"
    passed: bool = False
    manifest_path: str
    release_bundle_root: str
    packet_ref: str | None = None
    admission_receipt_ref: str | None = None
    predicate_receipt_ref: str | None = None
    foundry_receipt_ref: str | None = None
    postflight_receipt_ref: str | None = None
    original_simulation_result_ref: str | None = None
    replay_simulation_result_ref: str | None = None
    governance_verdict: Literal["approve", "reject"] | None = None
    release_admissibility_status: Literal["admissible", "blocked"] | None = None
    execution_artifacts: dict[str, str] = Field(default_factory=dict)
    replay_verification: dict[str, Any] = Field(default_factory=dict)
    steps: list[ReleaseAcceptanceStep] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _preserve_legacy_status_projection(self) -> ReleaseAcceptanceReport:
        if self.governance_verdict is None and self.release_admissibility_status is None:
            return self
        expected_governance = "approve" if self.passed else "reject"
        expected_admissibility = "admissible" if self.passed else "blocked"
        if (
            self.governance_verdict != expected_governance
            or self.release_admissibility_status != expected_admissibility
        ):
            raise ValueError("legacy and scoped release statuses must project the final outcome")
        return self


class FoundryReleaseAcceptanceReceipt(BaseModel):
    """Purpose-limited receipt for Foundry technical execution and replay only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.foundry.release_acceptance_receipt.v1"] = (
        "policyos.foundry.release_acceptance_receipt.v1"
    )
    rule_version: Literal["foundry-technical-release-acceptance.v1"] = (
        "foundry-technical-release-acceptance.v1"
    )
    authority_purpose: Literal["foundry_technical_acceptance_receipt"] = (
        "foundry_technical_acceptance_receipt"
    )
    authoritative_for: tuple[str, ...] = ()
    verified_for: tuple[str, ...] = (
        "technical_compilation",
        "technical_execution",
        "technical_replay",
    )
    may_not_use_for: tuple[str, ...] = (
        "release_admissibility",
        "governance_admissibility",
        "publication_authorization",
    )
    technical_passed: bool = False
    manifest_path: str
    release_bundle_root: str
    original_simulation_result_ref: str | None = None
    replay_simulation_result_ref: str | None = None
    execution_artifacts: dict[str, str] = Field(default_factory=dict)
    replay_verification: dict[str, Any] = Field(default_factory=dict)
    steps: list[ReleaseAcceptanceStep] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enforce_technical_scope(self) -> FoundryReleaseAcceptanceReceipt:
        if self.authoritative_for:
            raise ValueError("Foundry technical receipt cannot declare release authority")
        if self.verified_for != (
            "technical_compilation",
            "technical_execution",
            "technical_replay",
        ):
            raise ValueError("Foundry technical receipt must retain its exact verified scope")
        if self.may_not_use_for != (
            "release_admissibility",
            "governance_admissibility",
            "publication_authorization",
        ):
            raise ValueError("Foundry technical receipt must retain every authority denial")
        replay_passed = self.replay_verification.get("passed") is True
        executed_steps_passed = bool(self.steps) and all(
            step.status == "passed" for step in self.steps
        )
        if self.technical_passed != (executed_steps_passed and replay_passed):
            raise ValueError("technical_passed must compose executed steps and replay proof")
        return self


class ReleaseAcceptanceRunner:
    """Compile, execute, and replay from artifacts already admitted into CAS.

    Foundry deliberately does not inspect producer paths, admit DataForge
    declarations, invoke governance, or emit Scientist decision artifacts.
    """

    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store

    def run(
        self,
        *,
        release_manifest_ref: ArtifactRef,
        runtime_agent_registry_ref: ArtifactRef,
        cell_registry_ref: ArtifactRef,
        trinity_bundle_ref: ArtifactRef,
        manifest_path: str,
        release_bundle_root: str,
    ) -> FoundryReleaseAcceptanceReceipt:
        """Run deterministic Foundry acceptance over immutable CAS inputs."""

        steps: list[ReleaseAcceptanceStep] = []
        try:
            manifest_bytes = self._store.get_bytes(release_manifest_ref.artifact_id)
            runtime_agents_bytes = self._store.get_bytes(
                runtime_agent_registry_ref.artifact_id
            )
            cell_registry_bytes = self._store.get_bytes(cell_registry_ref.artifact_id)
            trinity_bytes = self._store.get_bytes(trinity_bundle_ref.artifact_id)
            trinity_bundle = TrinityBundle.model_validate_json(trinity_bytes)
            runtime_agents = pd.read_parquet(BytesIO(runtime_agents_bytes))
            cell_registry = pd.read_parquet(BytesIO(cell_registry_bytes))
        except Exception as exc:
            return self._failed(
                manifest_path=manifest_path,
                release_bundle_root=release_bundle_root,
                steps=[
                    ReleaseAcceptanceStep(
                        step_id="load_admitted_release_artifacts",
                        status="failed",
                        details={"error": str(exc)},
                    )
                ],
                note="admitted_release_artifact_load_failed",
            )
        steps.append(
            ReleaseAcceptanceStep(
                step_id="load_admitted_release_artifacts",
                status="passed",
                details={
                    "manifest_sha256": _sha256_bytes(manifest_bytes),
                    "runtime_agent_registry_sha256": _sha256_bytes(runtime_agents_bytes),
                    "cell_registry_sha256": _sha256_bytes(cell_registry_bytes),
                    "trinity_bundle_sha256": _sha256_bytes(trinity_bytes),
                },
            )
        )

        state = self._build_bundle_backed_state(runtime_agents, cell_registry)
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

        effective_trinity = trinity_bundle.model_copy(
            update={
                "model_spec": trinity_bundle.model_spec.model_copy(
                    update={
                        "data_snapshot_ref": str(data_snapshot_ref.artifact_id),
                        "registry_bundle_ref": str(registry_bundle.bundle_ref.artifact_id),
                    }
                )
            }
        )
        effective_trinity_ref = self._store.put_json(
            effective_trinity,
            PutOptions(
                kind="ir.trinity_bundle",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.ir.TrinityBundle",
                    version=effective_trinity.schema_version,
                ),
            ),
        )
        compile_result = compile_foundry(
            self._store,
            CompileRequest(
                input_kind="trinity",
                policy_ref=ArtifactRef.model_validate(effective_trinity_ref),
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
            return self._failed(
                manifest_path=manifest_path,
                release_bundle_root=release_bundle_root,
                steps=steps,
                note="acceptance_compile_failed",
            )

        exec_request = ExecuteRequest(
            exec_plan_ref=compile_result.exec_plan_ref,
            input_bindings_ref=FoundryInputBindingsRef(
                artifact_id=built.input_bindings_ref.artifact_id
            ),
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
            return self._failed(
                manifest_path=manifest_path,
                release_bundle_root=release_bundle_root,
                steps=steps,
                note="acceptance_execute_failed",
            )

        replay_execute_result = execute_foundry(self._store, exec_request)
        replay_ok = bool(
            replay_execute_result.ok and replay_execute_result.simulation_result_ref is not None
        )
        steps.append(
            ReleaseAcceptanceStep(
                step_id="replay_execute_roundtrip",
                status="passed" if replay_ok else "failed",
                details={"notes": list(replay_execute_result.notes)},
            )
        )
        if not replay_ok:
            return self._failed(
                manifest_path=manifest_path,
                release_bundle_root=release_bundle_root,
                steps=steps,
                note="acceptance_replay_execute_failed",
                original_simulation_result_ref=str(
                    execute_result.simulation_result_ref.artifact_id
                ),
            )

        original_metrics_ref = _extract_metrics_ref(execute_result)
        replay_metrics_ref = _extract_metrics_ref(replay_execute_result)
        original_sim_payload = SimulationResult.model_validate(
            from_canonical_bytes(
                self._store.get_bytes(execute_result.simulation_result_ref.artifact_id)
            )
        ).model_dump(mode="json")
        replay_sim_payload = SimulationResult.model_validate(
            from_canonical_bytes(
                self._store.get_bytes(replay_execute_result.simulation_result_ref.artifact_id)
            )
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
        replay_verified = normalized_original == normalized_replay and metrics_exact
        replay_details = {
            "simulation_structure_match": normalized_original == normalized_replay,
            "metrics_bit_exact": metrics_exact,
            "original_metrics_sha256": original_metrics_sha,
            "replay_metrics_sha256": replay_metrics_sha,
            "stable_original_metrics": stable_original_metrics,
            "stable_replay_metrics": stable_replay_metrics,
        }
        steps.append(
            ReleaseAcceptanceStep(
                step_id="verify_replay_roundtrip",
                status="passed" if replay_verified else "failed",
                details=replay_details,
            )
        )
        execution_artifacts = {
            "release_manifest_ref": str(release_manifest_ref.artifact_id),
            "runtime_agent_registry_ref": str(runtime_agent_registry_ref.artifact_id),
            "cell_registry_ref": str(cell_registry_ref.artifact_id),
            "trinity_bundle_ref": str(trinity_bundle_ref.artifact_id),
            "compiled_trinity_bundle_ref": str(effective_trinity_ref.artifact_id),
            "registry_bundle_ref": str(registry_bundle.bundle_ref.artifact_id),
            "input_bindings_ref": str(built.input_bindings_ref.artifact_id),
            "exec_plan_ref": str(compile_result.exec_plan_ref.artifact_id),
            "simulation_result_ref": str(execute_result.simulation_result_ref.artifact_id),
        }
        if original_metrics_ref is not None:
            execution_artifacts["metrics_ref"] = str(original_metrics_ref.artifact_id)
        return FoundryReleaseAcceptanceReceipt(
            technical_passed=all(step.status == "passed" for step in steps),
            manifest_path=manifest_path,
            release_bundle_root=release_bundle_root,
            original_simulation_result_ref=str(
                execute_result.simulation_result_ref.artifact_id
            ),
            replay_simulation_result_ref=str(
                replay_execute_result.simulation_result_ref.artifact_id
            ),
            execution_artifacts=execution_artifacts,
            replay_verification={
                "passed": replay_verified,
                "mode": "content_exact_filtered_metrics",
                "details": replay_details,
            },
            steps=steps,
        )

    @staticmethod
    def _build_bundle_backed_state(
        runtime_agents: pd.DataFrame,
        cell_registry: pd.DataFrame,
    ) -> GlobalState:
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

    @staticmethod
    def _failed(
        *,
        manifest_path: str,
        release_bundle_root: str,
        steps: list[ReleaseAcceptanceStep],
        note: str,
        original_simulation_result_ref: str | None = None,
    ) -> FoundryReleaseAcceptanceReceipt:
        return FoundryReleaseAcceptanceReceipt(
            technical_passed=False,
            manifest_path=manifest_path,
            release_bundle_root=release_bundle_root,
            original_simulation_result_ref=original_simulation_result_ref,
            steps=steps,
            notes=[note],
        )


__all__ = [
    "FoundryReleaseAcceptanceReceipt",
    "ReleaseAcceptanceReport",
    "ReleaseAcceptanceRunner",
    "ReleaseAcceptanceStep",
]
