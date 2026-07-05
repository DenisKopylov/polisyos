"""Workspace loop transition helpers for durable workflow jobs."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from polisyos.pdc import AuthorityBoundary, EvidenceBasis

if TYPE_CHECKING:
    from polisyos.runtime.quality.workspace.loop import WorkspaceSearchExitContract

    from ..control_plane_store import ControlJobRecord


class _WorkflowExecutionNonAuthorityError(RuntimeError):
    """Workflow execution failed after preparing a non-authority progress packet."""

    def __init__(self, message: str, *, progress: dict[str, Any]) -> None:
        super().__init__(message)
        self.progress = progress


class ControlPlaneWorkspaceLoopTransitionMixin:
    """Route workflow jobs through the GY WorkspaceLoop authority waist."""

    def _execute_workflow_control_transition(
        self,
        state_payload: dict[str, Any],
        checkpoint_policy: str,
        *,
        job: ControlJobRecord,
        endpoint: str,
        http_request_id: str,
    ) -> dict[str, Any]:
        if self._execute_workflow_is_overridden():
            result = self._execute_workflow(state_payload, checkpoint_policy)
            if isinstance(result, dict):
                if self._workflow_result_failed(result):
                    progress = self._workflow_failure_progress(
                        job=job,
                        phase="workflow_failed",
                        reason=(
                            "Workflow execution returned a failed result and cannot "
                            "produce authority."
                        ),
                        failure_code="workflow_failed_non_authority",
                        failure_message=self._workflow_failure_message(result),
                    )
                    raise _WorkflowExecutionNonAuthorityError(
                        progress["failure"]["message"],
                        progress=progress,
                    )
                if result.get("authority_path") == "workspace_loop":
                    return result
                return self._legacy_shadow_progress(
                    job=job,
                    phase="workflow_test_override",
                    reason=(
                        "Workflow execution hook override is treated as legacy-shadow "
                        "unless it returns explicit WorkspaceLoop progress."
                    ),
                )
            return self._legacy_shadow_progress(
                job=job,
                phase="workflow_test_override",
                reason=(
                    "Workflow execution hook override is treated as legacy-shadow "
                    "unless it returns explicit WorkspaceLoop progress."
                ),
            )
        params = dict(state_payload.get("params") or {})
        transition = str(params.get("control_plane_transition") or "workspace_loop")
        if transition == "legacy_shadow":
            return self._execute_legacy_shadow_workflow(
                state_payload,
                checkpoint_policy,
                job=job,
            )
        return self._execute_workspace_loop_workflow(
            state_payload,
            job=job,
            endpoint=endpoint,
            http_request_id=http_request_id,
        )

    def _execute_workflow(
        self,
        state_payload: dict[str, Any],
        checkpoint_policy: str,
    ) -> dict[str, Any] | None:
        self._run_legacy_scientist_workflow(state_payload)
        return None

    def _execute_workflow_is_overridden(self) -> bool:
        current = type(self).__dict__.get("_execute_workflow")
        if current is None:
            current = ControlPlaneWorkspaceLoopTransitionMixin.__dict__["_execute_workflow"]
        if isinstance(current, staticmethod):
            current = current.__func__
        return not (
            getattr(current, "__name__", None) == "_execute_workflow"
            and getattr(current, "__module__", None) == __name__
        )

    def _execute_workspace_loop_workflow(
        self,
        state_payload: dict[str, Any],
        *,
        job: ControlJobRecord,
        endpoint: str,
        http_request_id: str,
    ) -> dict[str, Any]:
        from polisyos.runtime.quality.authority import (
            ProductionLoopRunProof,
            build_outcome_replay_proof,
        )

        execute_invocation_id = f"execute-workflow-{uuid.uuid4().hex[:16]}"
        loop_invocation_id = f"workspace-loop-{uuid.uuid4().hex[:16]}"
        params = dict(state_payload.get("params") or {})
        fixture_id = str(params.get("slice0_fixture_id") or "ua_msme_credit_worldbank_measurement")
        input_artifacts = self._input_artifact_refs(state_payload)
        try:
            contract = self._run_workspace_loop_fixture(job=job, fixture_id=fixture_id)
        except _WorkflowExecutionNonAuthorityError as exc:
            progress = self._attach_failed_workspace_loop_proof(
                dict(exc.progress),
                job=job,
                endpoint=endpoint,
                execute_invocation_id=execute_invocation_id,
                loop_invocation_id=loop_invocation_id,
                input_artifacts=input_artifacts,
                http_request_id=http_request_id,
            )
            raise _WorkflowExecutionNonAuthorityError(str(exc), progress=progress) from exc
        contract_payload = contract.model_dump(mode="json")
        search_exit_ref = self._put_json_artifact(
            contract_payload,
            kind="pdc.gy.search_exit_contract",
            schema_name="polisyos.pdc.gy.SearchExitContract",
        )
        ledger_ref = self._put_json_artifact(
            contract.search_ledger.model_dump(mode="json"),
            kind="pdc.gy.search_ledger",
            schema_name="polisyos.pdc.gy.SearchLedger",
        )
        authority_trace_refs = [
            self._put_json_artifact(
                trace.model_dump(mode="json"),
                kind="pdc.gy.authority_derivation_trace",
                schema_name="polisyos.pdc.gy.AuthorityDerivationTrace",
            )
            for trace in contract.authority_derivation_traces
        ]
        artifact_payload_refs = [
            envelope.payload_ref
            for envelope in contract.artifact_envelopes
            if str(envelope.payload_ref).startswith("sha256:")
        ]
        output_cas_refs = [
            search_exit_ref,
            ledger_ref,
            *authority_trace_refs,
            *artifact_payload_refs,
        ]
        replay_proof = build_outcome_replay_proof(
            case_id=(
                "ua-msme-affordable-loans-2022"
                if fixture_id == "ua_msme_credit_worldbank_measurement"
                else fixture_id
            ),
            input_payloads=self._resolved_input_artifact_payloads(input_artifacts),
            search_exit_contract=contract_payload,
            output_cas_refs=output_cas_refs,
        )
        replay_payload = replay_proof.model_dump(mode="json")
        replay_ref = self._put_json_artifact(
            replay_payload,
            kind="pdc.gy.outcome_replay_proof",
            schema_name="polisyos.runtime.OutcomeReplayProof",
        )
        output_cas_refs.append(replay_ref)
        authority_result, quality_scorecard, approval_projection = (
            self._workspace_loop_authority_projection(
                terminal_kind=str(contract.terminal_state["kind"]),
                has_authority_boundary=contract.authority_boundary is not None,
                search_exit_ref=search_exit_ref,
            )
        )
        proof = ProductionLoopRunProof(
            run_id=str(job.run_id or state_payload.get("run_id") or ""),
            job_id=job.job_id,
            endpoint=endpoint,
            http_request_id=http_request_id,
            job_kind=job.kind,
            enqueued_at=job.created_at.isoformat() if job.created_at else None,
            worker_lease_id=job.lease_owner,
            worker_id=job.lease_owner,
            execute_workflow_invocation_id=execute_invocation_id,
            workspace_loop_invocation_id=loop_invocation_id,
            control_store_state_transitions=self._control_store.list_job_state_transitions(
                job.job_id
            ),
            input_artifacts=input_artifacts,
            output_search_exit_contract_ref=search_exit_ref,
            output_replay_proof_ref=replay_ref,
            output_cas_refs=output_cas_refs,
            artifacts_index_refs=[
                "search_exit_contract_ref",
                "search_ledger_ref",
                "outcome_replay_proof_ref",
                *(["authority_derivation_trace_refs"] if authority_trace_refs else []),
                "output_artifact_payload_refs",
            ],
            surface_reads_checked=["control_worker_precompletion"],
            legacy_path_disposition="routed_to_workspace_loop",
        )
        proof_payload = proof.model_dump(mode="json", by_alias=True)
        proof_ref = self._put_json_artifact(
            proof_payload,
            kind="pdc.gy.production_loop_run_proof",
            schema_name="polisyos.runtime.ProductionLoopRunProof",
        )
        quality_scorecard["evidence_refs"] = {
            **dict(quality_scorecard.get("evidence_refs") or {}),
            "search_exit_contract_ref": search_exit_ref,
            "search_ledger_ref": ledger_ref,
            "outcome_replay_proof_ref": replay_ref,
            "production_loop_run_proof_ref": proof_ref,
            "authority_derivation_trace_refs": authority_trace_refs,
        }
        return {
            "state": "completed",
            "phase": "workspace_loop",
            "runtime_state": "completed",
            "authority_path": "workspace_loop",
            "authority_result": authority_result,
            "fixture_id": fixture_id,
            "search_exit_contract_ref": search_exit_ref,
            "search_ledger_ref": ledger_ref,
            "production_loop_run_proof_ref": proof_ref,
            "authority_derivation_trace_refs": authority_trace_refs,
            "production_loop_run_proof": proof_payload,
            "outcome_replay_proof": replay_payload,
            "search_exit_contract": contract_payload,
            "artifacts_index": {
                "search_exit_contract_ref": search_exit_ref,
                "search_ledger_ref": ledger_ref,
                "outcome_replay_proof_ref": replay_ref,
                "production_loop_run_proof_ref": proof_ref,
                "authority_derivation_trace_refs": authority_trace_refs,
                "output_artifact_payload_refs": artifact_payload_refs,
            },
            "quality_scorecard": quality_scorecard,
            "approval_projection": approval_projection,
        }

    def _attach_failed_workspace_loop_proof(
        self,
        progress: dict[str, Any],
        *,
        job: ControlJobRecord,
        endpoint: str,
        execute_invocation_id: str,
        loop_invocation_id: str,
        input_artifacts: list[str],
        http_request_id: str,
    ) -> dict[str, Any]:
        """Attach a non-authority proof packet to a failed workspace-loop attempt."""

        from polisyos.runtime.quality.authority import ProductionLoopRunProof

        failure_ref = self._put_json_artifact(
            {
                "state": progress.get("state"),
                "phase": progress.get("phase"),
                "authority_path": progress.get("authority_path"),
                "authority_result": progress.get("authority_result"),
                "legacy_path_disposition": progress.get("legacy_path_disposition"),
                "failure": progress.get("failure"),
            },
            kind="pdc.gy.workflow_failure_non_authority",
            schema_name="polisyos.pdc.gy.WorkflowFailureNonAuthority",
        )
        output_cas_refs = [failure_ref]
        boundary = progress.get("authority_boundary")
        if isinstance(boundary, Mapping):
            boundary_ref = self._put_json_artifact(
                dict(boundary),
                kind="pdc.gy.workflow_failure_authority_boundary",
                schema_name="polisyos.pdc.gy.WorkflowFailureAuthorityBoundary",
            )
            output_cas_refs.append(boundary_ref)
        packet = progress.get("authority_surface_packet")
        if isinstance(packet, Mapping):
            packet_ref = self._put_json_artifact(
                dict(packet),
                kind="pdc.gy.workflow_failure_authority_surface_packet",
                schema_name="polisyos.pdc.gy.WorkflowFailureAuthoritySurfacePacket",
            )
            output_cas_refs.append(packet_ref)
        proof = ProductionLoopRunProof(
            run_id=str(job.run_id or progress.get("run_id") or ""),
            job_id=job.job_id,
            endpoint=endpoint,
            http_request_id=http_request_id,
            job_kind=job.kind,
            enqueued_at=job.created_at.isoformat() if job.created_at else None,
            worker_lease_id=job.lease_owner,
            worker_id=job.lease_owner,
            execute_workflow_invocation_id=execute_invocation_id,
            workspace_loop_invocation_id=loop_invocation_id,
            control_store_state_transitions=self._control_store.list_job_state_transitions(
                job.job_id
            ),
            input_artifacts=input_artifacts,
            output_search_exit_contract_ref=failure_ref,
            output_cas_refs=output_cas_refs,
            artifacts_index_refs=[
                "workflow_failure_ref",
                "authority_boundary",
                "authority_surface_packet",
            ],
            surface_reads_checked=["control_worker_precompletion"],
            legacy_path_disposition=str(
                progress.get("legacy_path_disposition")
                or "blocked_workflow_failure_ring2_withheld"
            ),
        )
        proof_payload = proof.model_dump(mode="json", by_alias=True)
        proof_ref = self._put_json_artifact(
            proof_payload,
            kind="pdc.gy.production_loop_run_proof",
            schema_name="polisyos.runtime.ProductionLoopRunProof",
        )
        progress["production_loop_run_proof"] = proof_payload
        progress["production_loop_run_proof_ref"] = proof_ref
        artifacts_index = progress.get("artifacts_index")
        base_index = dict(artifacts_index) if isinstance(artifacts_index, Mapping) else {}
        progress["artifacts_index"] = {
            **base_index,
            "workflow_failure_ref": failure_ref,
            "production_loop_run_proof_ref": proof_ref,
        }
        quality_scorecard = progress.get("quality_scorecard")
        if isinstance(quality_scorecard, Mapping):
            scorecard = dict(quality_scorecard)
            evidence_refs = scorecard.get("evidence_refs")
            evidence_refs = dict(evidence_refs) if isinstance(evidence_refs, Mapping) else {}
            evidence_refs["workflow_failure_ref"] = failure_ref
            evidence_refs["production_loop_run_proof_ref"] = proof_ref
            scorecard["evidence_refs"] = evidence_refs
            progress["quality_scorecard"] = scorecard
        return progress

    def _run_workspace_loop_fixture(
        self,
        *,
        job: ControlJobRecord,
        fixture_id: str,
    ) -> WorkspaceSearchExitContract:
        from polisyos.runtime.quality.workspace.loop import WorkspaceLoop

        try:
            return WorkspaceLoop(
                catalog_graph=getattr(self._registry_providers, "gy_catalog_graph", None),
                artifact_store=self._artifact_store,
            ).run_control_plane_fixture(fixture_id)
        except Exception as exc:
            progress = self._workflow_failure_progress(
                job=job,
                phase="workspace_loop_failed",
                reason="WorkspaceLoop failed before it could produce authority.",
                failure_code="workspace_loop_failed_non_authority",
                failure_message=str(exc),
            )
            raise _WorkflowExecutionNonAuthorityError(str(exc), progress=progress) from exc

    @staticmethod
    def _workspace_loop_authority_projection(
        *,
        terminal_kind: str,
        has_authority_boundary: bool,
        search_exit_ref: str,
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        if has_authority_boundary:
            gate = {
                "name": "slice0_estimate_scope_only",
                "code": "slice0_estimate_scope_only",
                "status": "warn",
                "layer": "pdc.gy",
                "phase": "workspace_loop",
                "message": (
                    "Slice 0 may carry verifier-stamped estimate-port authority, "
                    "but not design or production authority."
                ),
                "blocking": False,
                "evidence_ref": search_exit_ref,
            }
            return (
                "verifier_stamped",
                {
                    "quality_status": "warn",
                    "approval_state": "candidate_only",
                    "approval_ready": False,
                    "quality_gates": [gate],
                    "blocking_quality_failures": [],
                    "evidence_refs": {},
                },
                {
                    "state": "candidate_only",
                    "eligible": False,
                    "reasons": ["slice0_estimate_scope_only"],
                },
            )

        code = (
            "acquisition_required"
            if terminal_kind == "acquisition_required"
            else "search_ceiling_repair_required"
        )
        message = (
            "The loop reached an acquisition_required terminal; Ring-2 authority is withheld "
            "until the named missing distribution is acquired by an approved producer."
            if code == "acquisition_required"
            else "The loop reached a search repair terminal; Ring-2 authority is withheld."
        )
        gate = {
            "name": code,
            "code": code,
            "status": "fail",
            "layer": "pdc.gy",
            "phase": "workspace_loop",
            "message": message,
            "blocking": True,
            "evidence_ref": search_exit_ref,
            "next_action": (
                "Run an approved acquisition producer for the named missing distribution."
                if code == "acquisition_required"
                else "Repair search recall/freshness before authority use."
            ),
        }
        return (
            code if code == "acquisition_required" else "repair_required",
            {
                "quality_status": "fail",
                "approval_state": "candidate_only",
                "approval_ready": False,
                "quality_gates": [gate],
                "blocking_quality_failures": [
                    {
                        "gate": code,
                        "code": code,
                        "layer": "pdc.gy",
                        "phase": "workspace_loop",
                        "message": message,
                        "evidence_ref": search_exit_ref,
                    }
                ],
                "evidence_refs": {},
            },
            {
                "state": "candidate_only",
                "eligible": False,
                "reasons": [code],
            },
        )

    def _finalize_workspace_loop_run_proof(self, *, job_id: str, endpoint: str) -> None:
        """Persist a post-completion proof that includes observed /runs readback."""

        from polisyos.runtime.quality.authority import ProductionLoopRunProof

        record = self._control_store.get_job(job_id)
        if record is None:
            return
        progress = dict(record.progress)
        if progress.get("authority_path") != "workspace_loop":
            return
        proof_payload = progress.get("production_loop_run_proof")
        if not isinstance(proof_payload, Mapping):
            return
        proof = ProductionLoopRunProof.model_validate(proof_payload)
        readbacks = list(proof.surface_readbacks)
        if any(
            item.get("surface") == endpoint and item.get("observed_job_state") == record.state
            for item in readbacks
        ):
            return
        observed_search_exit_ref = str(progress.get("search_exit_contract_ref") or "")
        contract_payload = progress.get("search_exit_contract")
        terminal_kind = None
        if isinstance(contract_payload, Mapping):
            terminal_state = contract_payload.get("terminal_state")
            if isinstance(terminal_state, Mapping):
                terminal_kind = terminal_state.get("kind")
        readbacks.append(
            {
                "surface": endpoint,
                "read_method": "ControlPlaneStore.get_job",
                "job_id": record.job_id,
                "run_id": record.run_id,
                "observed_job_state": record.state,
                "observed_authority_path": progress.get("authority_path"),
                "observed_authority_result": progress.get("authority_result"),
                "observed_terminal_kind": terminal_kind,
                "observed_search_exit_contract_ref": observed_search_exit_ref,
                "matched_search_exit_contract_ref": (
                    observed_search_exit_ref == proof.output_search_exit_contract_ref
                ),
            }
        )
        surface_reads_checked = list(proof.surface_reads_checked)
        for surface in ("control_job_status", "runs_readback"):
            if surface not in surface_reads_checked:
                surface_reads_checked.append(surface)
        final_proof = proof.model_copy(
            update={
                "control_store_state_transitions": (
                    self._control_store.list_job_state_transitions(job_id)
                ),
                "surface_reads_checked": surface_reads_checked,
                "surface_readbacks": readbacks,
            }
        )
        final_payload = final_proof.model_dump(mode="json", by_alias=True)
        final_ref = self._put_json_artifact(
            final_payload,
            kind="pdc.gy.production_loop_run_proof",
            schema_name="polisyos.runtime.ProductionLoopRunProof",
        )
        progress["production_loop_run_proof"] = final_payload
        progress["production_loop_run_proof_ref"] = final_ref
        artifacts_index = progress.get("artifacts_index")
        if isinstance(artifacts_index, Mapping):
            progress["artifacts_index"] = {
                **dict(artifacts_index),
                "production_loop_run_proof_ref": final_ref,
            }
        quality_scorecard = progress.get("quality_scorecard")
        if isinstance(quality_scorecard, Mapping):
            quality_scorecard = dict(quality_scorecard)
            evidence_refs = quality_scorecard.get("evidence_refs")
            evidence_refs = dict(evidence_refs) if isinstance(evidence_refs, Mapping) else {}
            evidence_refs["production_loop_run_proof_ref"] = final_ref
            quality_scorecard["evidence_refs"] = evidence_refs
            progress["quality_scorecard"] = quality_scorecard
        self._control_store.upsert_progress(job_id=record.job_id, progress=progress)

    def _execute_legacy_shadow_workflow(
        self,
        state_payload: dict[str, Any],
        checkpoint_policy: str,
        *,
        job: ControlJobRecord,
    ) -> dict[str, Any]:
        try:
            self._run_legacy_scientist_workflow(state_payload)
        except Exception as exc:
            progress = self._workflow_failure_progress(
                job=job,
                phase="legacy_workflow_failed",
                reason="Legacy workflow failed and cannot produce authority.",
                failure_code="legacy_workflow_failed_non_authority",
                failure_message=str(exc),
            )
            raise _WorkflowExecutionNonAuthorityError(str(exc), progress=progress) from exc
        return self._legacy_shadow_progress(
            job=job,
            phase="legacy_workflow_shadow",
            reason="Legacy workflow path is candidate-only until migrated behind WorkspaceLoop.",
        )

    def _legacy_shadow_progress(
        self,
        *,
        job: ControlJobRecord,
        phase: str,
        reason: str,
    ) -> dict[str, Any]:
        quality_scorecard = {
            "quality_status": "fail",
            "approval_state": "candidate_only",
            "approval_ready": False,
            "quality_gates": [
                {
                    "name": "legacy_shadow_candidate_only",
                    "code": "legacy_shadow_candidate_only",
                    "status": "fail",
                    "layer": "pdc.gy",
                    "phase": phase,
                    "message": reason,
                    "blocking": True,
                    "evidence_ref": None,
                    "next_action": (
                        "Route this entrypoint through WorkspaceLoop before authority use."
                    ),
                    "next_diagnostic_command": (
                        "uv run pytest tests/unit/runtime/http/"
                        "test_workspace_loop_transition.py -q"
                    ),
                }
            ],
            "blocking_quality_failures": [
                {
                    "gate": "legacy_shadow_candidate_only",
                    "code": "legacy_shadow_candidate_only",
                    "layer": "pdc.gy",
                    "phase": phase,
                    "message": reason,
                    "next_action": (
                        "Route this entrypoint through WorkspaceLoop before authority use."
                    ),
                }
            ],
            "evidence_refs": {},
        }
        progress = {
            "state": "completed",
            "phase": phase,
            "runtime_state": "candidate_only",
            "authority_path": "legacy_shadow",
            "authority_result": "candidate_only",
            "legacy_path_disposition": "candidate_only_ring2_withheld",
            "run_id": job.run_id,
            "quality_scorecard": quality_scorecard,
            "approval_projection": {
                "state": "candidate_only",
                "eligible": False,
                "reasons": ["legacy_shadow_candidate_only"],
            },
        }
        return self._with_authority_surface_packet(
            progress,
            job=job,
            phase=phase,
            reason=reason,
            gate_code="legacy_shadow_candidate_only",
            authority_result="candidate_only",
            surface_result="candidate_only",
        )

    @staticmethod
    def _workflow_result_failed(result: Mapping[str, Any]) -> bool:
        failure_values = {
            str(result.get(key) or "").strip().casefold()
            for key in (
                "status",
                "state",
                "runtime_state",
                "execution_status",
                "workflow_status",
                "verdict",
            )
        }
        if failure_values & {"fail", "failed", "error", "errored"}:
            return True
        if result.get("ok") is False or result.get("success") is False:
            return True
        failure_payload = result.get("failure") or result.get("error")
        return isinstance(failure_payload, Mapping) or bool(str(failure_payload or "").strip())

    @staticmethod
    def _workflow_failure_message(result: Mapping[str, Any]) -> str:
        failure = result.get("failure")
        if isinstance(failure, Mapping):
            message = failure.get("message") or failure.get("error") or failure.get("code")
            if message:
                return str(message)
        for key in ("message", "error", "status", "state"):
            value = result.get(key)
            if value:
                return f"Workflow failed: {value}"
        return "Workflow failed."

    def _workflow_failure_progress(
        self,
        *,
        job: ControlJobRecord,
        phase: str,
        reason: str,
        failure_code: str,
        failure_message: str,
    ) -> dict[str, Any]:
        next_action = "Repair the workflow failure before any authority surface can consume it."
        quality_scorecard = {
            "quality_status": "fail",
            "approval_state": "candidate_only",
            "approval_ready": False,
            "quality_gates": [
                {
                    "name": failure_code,
                    "code": failure_code,
                    "status": "fail",
                    "layer": "pdc.gy",
                    "phase": phase,
                    "message": reason,
                    "blocking": True,
                    "evidence_ref": None,
                    "next_action": next_action,
                    "next_diagnostic_command": (
                        "uv run pytest tests/unit/runtime/http/"
                        "test_workspace_loop_transition.py -q"
                    ),
                }
            ],
            "blocking_quality_failures": [
                {
                    "gate": failure_code,
                    "code": failure_code,
                    "layer": "pdc.gy",
                    "phase": phase,
                    "message": reason,
                    "next_action": next_action,
                }
            ],
            "evidence_refs": {},
        }
        progress = {
            "state": "failed",
            "phase": phase,
            "runtime_state": "blocked",
            "authority_path": "workflow_failure",
            "authority_result": "repair_required",
            "legacy_path_disposition": "blocked_workflow_failure_ring2_withheld",
            "run_id": job.run_id,
            "failure": {
                "code": failure_code,
                "layer": "scientist_workflow",
                "phase": phase,
                "message": failure_message,
                "retryable": False,
                "artifact_refs": {},
                "next_action": next_action,
            },
            "quality_scorecard": quality_scorecard,
            "approval_projection": {
                "state": "candidate_only",
                "eligible": False,
                "reasons": [failure_code],
            },
        }
        return self._with_authority_surface_packet(
            progress,
            job=job,
            phase=phase,
            reason=reason,
            gate_code=failure_code,
            authority_result="repair_required",
            surface_result="blocked",
        )

    @staticmethod
    def _non_authority_boundary(
        *,
        job: ControlJobRecord,
        gate_code: str,
        phase: str,
        reason: str,
    ) -> dict[str, Any]:
        boundary = AuthorityBoundary(
            boundary_id=f"runtime.{gate_code}.{job.job_id}",
            authoritative_for=["runtime_surface_downgrade"],
            may_not_use_for=[
                "approval_authority",
                "decision_authority",
                "design_recommendation_authority",
                "publication_authority",
                "runtime_closeout_authority",
                "scorecard_authority",
                "workflow_success_authority",
            ],
            source_authority="deterministic_producer",
            posture="shadow",
            rule_version_refs=["policyos.runtime.surface_authority_boundary.v1"],
            evidence_kind="elicitation",
            decision_grade="unsupported",
            evidence_basis=EvidenceBasis(
                method_refs=["runtime.control.workflow_transition", phase],
            ),
            known_limits=[reason],
        )
        return boundary.model_dump(mode="json")

    @staticmethod
    def _surface_packet(
        *,
        boundary: Mapping[str, Any],
        gate_code: str,
        phase: str,
        reason: str,
        authority_result: str,
        surface_result: str,
    ) -> dict[str, Any]:
        boundary_id = str(boundary.get("boundary_id") or "")
        may_not_use_for = list(boundary.get("may_not_use_for") or [])
        decision_grade = str(boundary.get("decision_grade") or "unsupported")
        evidence_kind = str(boundary.get("evidence_kind") or "elicitation")
        surface_names = (
            "run",
            "artifact",
            "lineage",
            "export",
            "dashboard",
            "public_packet",
        )
        surfaces = {
            surface: {
                "surface": surface,
                "status": surface_result,
                "authority_result": surface_result,
                "consumed_boundary_id": boundary_id,
                "boundary_source": "AuthorityBoundary",
                "decision_grade": decision_grade,
                "evidence_kind": evidence_kind,
                "may_not_use_for": may_not_use_for,
                "reason": reason,
            }
            for surface in surface_names
        }
        return {
            "schema_version": "policyos.runtime.authority_surface_packet.v1",
            "phase": phase,
            "gate_code": gate_code,
            "authority_result": authority_result,
            "boundary": dict(boundary),
            "surfaces": surfaces,
        }

    def _with_authority_surface_packet(
        self,
        progress: dict[str, Any],
        *,
        job: ControlJobRecord,
        phase: str,
        reason: str,
        gate_code: str,
        authority_result: str,
        surface_result: str,
    ) -> dict[str, Any]:
        boundary = self._non_authority_boundary(
            job=job,
            gate_code=gate_code,
            phase=phase,
            reason=reason,
        )
        packet = self._surface_packet(
            boundary=boundary,
            gate_code=gate_code,
            phase=phase,
            reason=reason,
            authority_result=authority_result,
            surface_result=surface_result,
        )
        progress["authority_boundary"] = boundary
        progress["authority_surface_packet"] = packet
        progress["surface_authority"] = packet["surfaces"]
        progress["public_packet"] = {
            "authority_boundary": boundary,
            "projection": packet["surfaces"]["public_packet"],
        }
        progress["export_projection"] = packet["surfaces"]["export"]
        progress["lineage_projection"] = packet["surfaces"]["lineage"]
        progress["artifact_projection"] = packet["surfaces"]["artifact"]
        artifacts_index = progress.get("artifacts_index")
        if isinstance(artifacts_index, Mapping):
            progress["artifacts_index"] = {
                **dict(artifacts_index),
                "authority_boundary": str(boundary["boundary_id"]),
                "authority_surface_packet": "progress.authority_surface_packet",
            }
        else:
            progress["artifacts_index"] = {
                "authority_boundary": str(boundary["boundary_id"]),
                "authority_surface_packet": "progress.authority_surface_packet",
            }

        quality_scorecard = progress.get("quality_scorecard")
        if isinstance(quality_scorecard, Mapping):
            scorecard = dict(quality_scorecard)
            scorecard["authority_boundary"] = boundary
            scorecard["authority_surface_packet"] = packet
            scorecard["approval_ready"] = False
            scorecard["approval_state"] = "candidate_only"
            for field in ("quality_gates", "blocking_quality_failures"):
                rows = scorecard.get(field)
                if isinstance(rows, list):
                    scorecard[field] = [
                        {
                            **dict(row),
                            "authority_refs": {
                                **dict(row.get("authority_refs") or {}),
                                "authority_boundary": str(boundary["boundary_id"]),
                            },
                        }
                        if isinstance(row, Mapping)
                        else row
                        for row in rows
                    ]
            progress["quality_scorecard"] = scorecard
        failure = progress.get("failure")
        if isinstance(failure, Mapping):
            progress["failure"] = {
                **dict(failure),
                "authority_refs": {
                    **dict(failure.get("authority_refs") or {}),
                    "authority_boundary": str(boundary["boundary_id"]),
                },
            }
        return progress

    @staticmethod
    def _input_artifact_refs(state_payload: dict[str, Any]) -> list[str]:
        refs: list[str] = []
        inputs = state_payload.get("inputs")
        if not isinstance(inputs, Mapping):
            return refs
        for value in inputs.values():
            if isinstance(value, Mapping):
                artifact_id = value.get("artifact_id")
                if isinstance(artifact_id, str):
                    refs.append(artifact_id)
            elif isinstance(value, str):
                refs.append(value)
        return refs

    def _resolved_input_artifact_payloads(
        self,
        artifact_refs: list[str],
    ) -> dict[str, Any]:
        """Resolve and content-bind every production workflow input from CAS."""

        payloads: dict[str, Any] = {}
        for artifact_ref in artifact_refs:
            payloads[artifact_ref] = self._load_payload_ref(artifact_ref)
        return payloads
