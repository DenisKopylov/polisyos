"""Actual MC persistence through a fresh selected Science reader."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts._profiled_ref import profile_bound_ref
from polisyos.core.artifacts.canonical_profile import validate_core_model_json_artifact
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import InputRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import MetricsRef, SimulationResult
from polisyos.core.contracts.foundry import ExecPlanRef
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    CertificateKind,
    ComposedFlavour,
    CompositionProvenance,
    CompositionStep,
    DistributionFamily,
    ExactnessKind,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import _persist_report
from polisyos.scientist.nodes.builtins.simulate.uncertainty_source_projection import (
    PropagationReportV11,
    _load_validated_uncertainty_source_read,
    load_science_simulation_result_uncertainty_admission,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext


@pytest.mark.parametrize("context", ["provenance", "metadata"])
def test_actual_mc_persisted_ledger_and_envelope_are_freshly_read_without_authority(
    execution_context: ExecutionContext, tmp_path: Path, context: str
) -> None:
    class MutableEnum(Enum):
        VALUE = {"entries": ["before"]}

    class BehavioralDependency(Enum):
        VALUE = "unknown"

        def __str__(self) -> str:
            return "known"

    prior = CompositionProvenance(
        native_flavour=ComposedFlavour.ANALYTICAL,
        composed_flavour=ComposedFlavour.DELTA,
        exactness=ExactnessKind.APPROXIMATION,
        certificate_kind=CertificateKind.TAYLOR_REMAINDER,
        operator_history=(
            CompositionStep(
                op="push_forward",
                stage_name="prior.stage",
                input_flavours=(ComposedFlavour.ANALYTICAL,),
                output_flavour=ComposedFlavour.DELTA,
                notes={"nested": [MutableEnum.VALUE]} if context == "provenance" else {},
            ),
        ),
    )
    envelope = UncertaintyEnvelope(
        point_estimate=0.0,
        confidence_interval=(-1.959963984540054, 1.959963984540054),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        composition_provenance=prior,
        metadata={"dependency": BehavioralDependency.VALUE} if context == "metadata" else {},
    )
    limitation = f"{context}_context_status"

    def response(x: float) -> dict[str, float]:
        MutableEnum.VALUE.value["entries"].append("after")
        return {"y": x, "z": 2 * x}

    results = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=100, mc_batch_size=100, compute_sensitivity=False)
    ).propagate(response, {"x": 0.0}, {"x": envelope}, ["y", "z"])
    assert all(not result.envelope.gate_eligible for result in results)
    assert (
        results[0].diagnostics["draw_outcome_provenance"]
        is results[1].diagnostics["draw_outcome_provenance"]
    )
    report_ref = _persist_report(
        execution_context,
        results=results,
        input_envelopes={"x": envelope},
        output_metrics=["y", "z"],
        mapped_params={"x"},
        unmapped_metric_ids=[],
        missing_output_metric_ids=[],
        incomplete_output_metric_ids=[],
        mapping_source="caller_parameters",
    )
    envelope_ref = persist_uncertainty_envelope(
        ensure_ir_artifact_store(execution_context.store),
        results[0].envelope,
        return_selected_profile=True,
    )

    fresh_store = FileSystemCAS(tmp_path)
    original_report = profile_bound_ref(fresh_store, report_ref)
    report_payload = json.loads(fresh_store.get_bytes(original_report))
    # The same producer bytes receive a second selected manifest profile.
    selected_report = fresh_store.put_json(
        report_payload,
        PutOptions(
            kind="foundry.propagation_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.PropagationReport", version="1.1"),
            producer=ProducerInfo(component="test.c90.selected-profile", version="1.0.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert selected_report.artifact_id == original_report.artifact_id
    assert selected_report.manifest_profile_sha256 != original_report.manifest_profile_sha256
    plan_ref = fresh_store.put_json(
        {"schema_version": "0.2.0"},
        PutOptions(
            kind="foundry.exec_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ExecPlan", version="0.2.0"),
        ),
        return_selected_profile=True,
    )
    metrics_ref = fresh_store.put_json(
        {"schema_version": "0.1.0", "values": {}},
        PutOptions(
            kind="foundry.metrics",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.Metrics", version="0.1.0"),
        ),
        return_selected_profile=True,
    )
    simulation = SimulationResult(
        schema_version="1.4",
        exec_plan_ref=ExecPlanRef.model_validate(plan_ref.model_dump(mode="python")),
        metrics_ref=MetricsRef.model_validate(metrics_ref.model_dump(mode="python")),
        uncertainty_envelopes={"y": envelope_ref},
        propagation_report_ref=selected_report,
    )
    simulation_ref = fresh_store.put_json(
        simulation.to_artifact_payload(),
        PutOptions(
            kind=SimulationResult.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                version=SimulationResult.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[
                InputRef(
                    artifact_id=selected_report.artifact_id,
                    role="propagation_report",
                    manifest_profile_sha256=selected_report.manifest_profile_sha256,
                ),
                InputRef(
                    artifact_id=envelope_ref.artifact_id,
                    role="metric_envelope.y",
                    manifest_profile_sha256=envelope_ref.manifest_profile_sha256,
                ),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    producer_simulation = simulation.model_copy(update={"propagation_report_ref": original_report})
    producer_simulation_ref = fresh_store.put_json(
        producer_simulation.to_artifact_payload(),
        PutOptions(
            kind=SimulationResult.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                version=SimulationResult.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[
                InputRef(
                    artifact_id=original_report.artifact_id,
                    role="propagation_report",
                    manifest_profile_sha256=original_report.manifest_profile_sha256,
                ),
                InputRef(
                    artifact_id=envelope_ref.artifact_id,
                    role="metric_envelope.y",
                    manifest_profile_sha256=envelope_ref.manifest_profile_sha256,
                ),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    reopened = FileSystemCAS(tmp_path)
    producer_read = _load_validated_uncertainty_source_read(reopened, producer_simulation_ref)
    assert (
        producer_read.propagation_report_ref.manifest_profile_sha256
        == original_report.manifest_profile_sha256
    )
    assert producer_read.propagation_report.draw_outcome_provenance is not None
    assert (
        producer_read.propagation_report.draw_outcome_provenance.input_identity_status
        == "not_established"
    )
    read = _load_validated_uncertainty_source_read(reopened, simulation_ref)
    assert (
        read.propagation_report_ref.manifest_profile_sha256
        == selected_report.manifest_profile_sha256
    )
    report = read.propagation_report
    ledger = report.draw_outcome_provenance
    assert ledger is not None
    assert ledger.input_identity_status == "not_established"
    assert set(ledger.model_dump(mode="json")) == set(type(ledger).model_fields)
    assert report.mapping_status == "consumer_asserted"
    assert all(row.diagnostics[limitation] == "not_established" for row in report.diagnostics)
    restored = load_uncertainty_envelope(ensure_ir_artifact_store(reopened), envelope_ref)
    assert restored.gate_eligible is False
    assert restored.metadata[limitation] == "not_established"
    admission = load_science_simulation_result_uncertainty_admission(reopened, simulation_ref, "y")
    assert not admission.admitted
    assert "draw_success_ledger_missing" in admission.limitation_codes
    assert "draw_basis_verifier_missing" in admission.limitation_codes

    for kind in ("unknown_field", "malformed_count"):
        tampered = json.loads(fresh_store.get_bytes(selected_report))
        if kind == "unknown_field":
            tampered["draw_outcome_provenance"]["unknown_authority"] = True
        else:
            tampered["draw_outcome_provenance"]["requested_draw_count"] = "100"
        bad_ref = fresh_store.put_json(
            tampered,
            PutOptions(
                kind="foundry.propagation_report",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.foundry.PropagationReport", version="1.1"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        with pytest.raises(ValidationError):
            validate_core_model_json_artifact(
                PropagationReportV11,
                FileSystemCAS(tmp_path),
                bad_ref,
                manifest_profile_sha256=bad_ref.manifest_profile_sha256,
            )
