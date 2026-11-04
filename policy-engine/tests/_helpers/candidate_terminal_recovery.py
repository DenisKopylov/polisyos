"""Test-only exact writer inputs for candidate terminal recovery controls."""

from __future__ import annotations

import hashlib

from polisyos.core.artifacts.manifest import ArtifactGovernanceInfo, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.runtime.http.services.control.run_lifecycle import _acquisition_route_receipt_inputs
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionCandidateRouteLoopReceipt
from polisyos.runtime.quality.authority import GovernanceMetadata


def candidate_terminal_writer_inputs(
    terminal: AcquisitionCandidateRouteLoopReceipt,
) -> tuple[ArtifactWriteOptions, dict[str, object]]:
    """Construct sink-equivalent test inputs; this does not establish a live owner."""
    inputs = _acquisition_route_receipt_inputs(terminal)
    spec = CanonSpec(forbid_floats=False)
    suffix = hashlib.sha256(to_canonical_bytes(terminal.model_dump(mode="json"), spec)).hexdigest()
    opts = ArtifactWriteOptions(
        kind="runtime_quality.acquisition_route_loop_receipt",
        media_type="application/json",
        schema=SchemaInfo(name="polisyos.runtime.AcquisitionRouteLoopReceipt", version="3.0"),
        producer=ProducerInfo(
            component="polisyos.runtime.acquisition_route_loop", version="2026.08.28+ds15-c02"
        ),
        governance=ArtifactGovernanceInfo(classification="internal"),
        inputs=[],
    )
    fields: dict[str, object] = {
        "evidence_id": terminal.receipt_id,
        "evidence_class": "authority_bearing",
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "owner": "team-runtime-quality",
        "reader_contract": "runtime.acquisition_route_loop.reader",
        "reader_contract_version": "1.0",
        "tenant_id": terminal.tenant_id,
        "cell_id": terminal.cell_id,
        "run_id": terminal.run_id,
        "job_id": terminal.job_id,
        "trace_id": f"trace-{terminal.job_id}",
        "span_id": "span-terminal",
        "parent_span_id": None,
        "requested_execution_profile": "governed",
        "effective_execution_profile": "governed",
        "phase": "acquisition_route_loop",
        "generated_at": terminal.generated_at.isoformat(),
        "as_of_time": terminal.generated_at.isoformat(),
        "same_input_closure": {
            "closure_id": f"acquisition-route:{terminal.receipt_id}",
            "status": "closed",
            "run_id": terminal.run_id,
            "job_id": terminal.job_id,
            "tenant_id": terminal.tenant_id,
            "cell_id": terminal.cell_id,
            "evidence_input_refs": inputs,
            "closure_sha256": terminal.route_id,
        },
        "input_refs": inputs,
        "effective_mode_ref": terminal.route_id,
        "degradation_ledger_ref": None,
        "semantic_binding_ref": terminal.cost_basis_hash,
        "validation_status": "pass",
        "blocking_status": "non_blocking",
        "governance": GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime.acquisition_route_loop",
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="pa2_ds9_decision_required",
        ),
        "event_id": f"evt_acquisition_{terminal.action_generation}_loop_terminal_{suffix}",
        "event_source": "polisyos.runtime.quality.acquisition_route_loop",
        "event_type": "polisyos.runtime.acquisition.route_loop.v3",
        "event_subject": f"run/{terminal.run_id}/job/{terminal.job_id}/acquisition/terminal",
        "state_before": "candidate_input_reentry_pending",
        "state_after": "terminal",
        "canon_spec": spec,
    }
    return opts, fields
