"""Installed consumer checks for the E02 source-to-wheel packaging wave.

These tests deliberately read only the public-surface source contract from the
frozen checkout. Product behavior is exercised through the imported package,
which the installed-wave origin plugin verifies came from site-packages.
"""

from __future__ import annotations

import importlib
import json
import os
import tomllib
from pathlib import Path

import pytest


def _source_root() -> Path:
    configured = os.environ.get("E02_SOURCE_ROOT")
    if configured:
        return Path(configured).resolve(strict=True)
    return Path(__file__).resolve().parents[4]


def test_public_surface_entrypoints_resolve_declared_exports(record_testsuite_property) -> None:
    """Resolve every supported entry point and its runtime-declared exports."""
    root = _source_root()
    contract = tomllib.loads(
        (root / "architecture/public_surface/contract.toml").read_text(encoding="utf-8")
    )["package"]
    inventory = json.loads(
        (root / "architecture/public_surface/inventory.json").read_text(encoding="utf-8")
    )["packages"]

    entrypoints = [name for row in contract for name in row["supported_entrypoints"]]
    unresolved_inventory_rows = sum(
        row.get("facade_mode_observed") == "unresolved_exports" for row in inventory
    )
    assert len(contract) == len(inventory) == 20
    assert len(entrypoints) == len(set(entrypoints)) == 38
    assert [row["module"] for row in contract] == [row["module"] for row in inventory]
    assert unresolved_inventory_rows == 20

    resolved_export_count = 0
    for module_name in entrypoints:
        module = importlib.import_module(module_name)
        exports = getattr(module, "__all__", None)
        assert isinstance(exports, (list, tuple)), f"{module_name} has no explicit __all__"
        assert all(isinstance(name, str) for name in exports), module_name
        assert len(exports) == len(set(exports)), f"{module_name} repeats an export"
        for export_name in exports:
            getattr(module, export_name)
        resolved_export_count += len(exports)

    record_testsuite_property("source_contract_package_definitions", len(contract))
    record_testsuite_property("source_contract_supported_entrypoints", len(entrypoints))
    record_testsuite_property("ast_inventory_unresolved_package_rows", unresolved_inventory_rows)
    record_testsuite_property("runtime_declared_exports_resolved", resolved_export_count)


def test_workflow_request_rejects_wrong_typed_intake_ref_kind_or_media_type() -> None:
    """The typed production intake arm rejects refs that name a different artifact."""
    from pydantic import ValidationError

    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.contracts import WorkflowRunRequest

    artifact_id = ArtifactID.from_sha256_hex("a" * 64)
    base = {"data_source": {"data_snapshot_ref": "sha256:" + "b" * 64}}
    wrong_kind = ArtifactRef(
        artifact_id=artifact_id,
        kind="unrelated.artifact",
        media_type="application/json",
    )
    wrong_media_type = ArtifactRef(
        artifact_id=artifact_id,
        kind="gy.loop.proof.root",
        media_type="text/plain",
    )
    valid_ref = ArtifactRef(
        artifact_id=artifact_id,
        kind="gy.loop.proof.root",
        media_type="application/json",
    )

    for invalid_ref in (wrong_kind, wrong_media_type):
        with pytest.raises(
            ValidationError, match="production_case_intake_ref_kind_or_media_type_invalid"
        ):
            WorkflowRunRequest(**base, production_case_intake_ref=invalid_ref)

    accepted = WorkflowRunRequest(**base, production_case_intake_ref=valid_ref)
    assert accepted.production_case_intake_ref == valid_ref


def test_gate_request_selected_replay_requirement_is_versioned() -> None:
    """Current requests require a selected replay view while the legacy schema remains readable."""
    from pydantic import ValidationError

    from polisyos.ir.governance import GateRequest

    base = {
        "request_id": "gate.e02.installed",
        "run_id": "run.e02.installed",
        "reason": "review selected replay evidence",
        "context": {"workflow_id": "workflow.e02", "node_alias": "review", "phase": "gate"},
    }
    with pytest.raises(ValidationError, match="requires selected_replay_refs"):
        GateRequest(**base, schema_version="1.2")

    current = GateRequest(
        **{
            **base,
            "context": {**base["context"], "selected_replay_refs": {}},
        },
        schema_version="1.2",
    )
    legacy = GateRequest(**base, schema_version="1.1")
    assert current.context.selected_replay_refs == {}
    assert legacy.context.selected_replay_refs is None


def test_cas_nondefault_manifest_profile_round_trips_through_fresh_reader(tmp_path: Path) -> None:
    """A selected nondefault manifest profile keeps its content and typed metadata on read."""
    from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import content_hash

    cas_root = tmp_path / "cas"
    writer = FileSystemCAS(cas_root)
    payload = b"installed nondefault profile payload\n"
    default_ref = writer.put_bytes(
        payload,
        ArtifactWriteOptions(kind="e02.default", media_type="text/plain"),
    )
    selected_ref = writer.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="e02.selected",
            media_type="application/octet-stream",
            schema=SchemaInfo(name="e02.selected-payload", version="2.0"),
            producer=ProducerInfo(component="e02.installed-consumer", version="1.0.0"),
        ),
    )
    assert selected_ref.artifact_id == default_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None

    reader = FileSystemCAS(cas_root)
    assert reader.get_bytes(selected_ref) == payload
    assert content_hash(payload) == selected_ref.artifact_id.hex
    manifest = reader.get_manifest(selected_ref)
    assert manifest.kind == "e02.selected"
    assert manifest.media_type == "application/octet-stream"
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == "e02.selected-payload"
    assert manifest.artifact_schema.version == "2.0"
    assert manifest.producer is not None
    assert manifest.producer.component == "e02.installed-consumer"
    assert reader.get_manifest(default_ref).kind == "e02.default"


def test_small_monte_carlo_report_is_consumed_from_fresh_cas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real propagation node report reaches and is bounded by a fresh IR consumer."""
    import logging

    import numpy as np

    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec, from_canonical_bytes
    from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
    from polisyos.core.contracts.foundry import ExecPlanRef, MetricsRef, SimulationResult
    from polisyos.core.errors import ErrorCategory, PolicyOSError
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
    from polisyos.ir.analytics.normative_arbitration import (
        ArbitrationOption,
        NormativeAuditStatus,
        NormativeModelCompleteness,
        load_normative_arbitration_result,
    )
    from polisyos.ir.analytics.uncertainty import (
        DistributionFamily,
        IntervalSemantics,
        UncertaintyEnvelope,
        UncertaintySource,
        load_simulation_result_uncertainty_admission,
        load_uncertainty_envelope,
        persist_uncertainty_envelope,
    )
    from polisyos.ir.governance.policy_spec import PolicySpec
    from polisyos.ir.governance.problem_frame import (
        NormativeArbitrationPolicy,
        NormativeFrame,
        NormativeOutcomeChannel,
        ObjectiveSpec,
        ProblemDomain,
        ProblemFrame,
        StakeholderOutcomeBinding,
        StakeholderRightSpec,
        StakeholderSpec,
        StakeholderUtilityTerm,
    )
    from polisyos.ir.model_layer.model_spec import FidelityLevel, ModelSpec
    from polisyos.ir.model_layer.types import EntityType, OptimizationDirection
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.scientist.nodes.builtins.governance.run_normative_arbitration import (
        RunNormativeArbitrationNode,
    )
    from polisyos.scientist.nodes.builtins.simulate import propagate_uncertainty as node_module
    from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
        PropagateUncertaintyNode,
    )
    from polisyos.scientist.nodes.builtins.state_keys import (
        ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
        ARTIFACT_SIMULATION_RESULT_REF,
        INPUT_DATA_SNAPSHOT_REF,
        INPUT_TRINITY_BUNDLE_REF,
    )
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    cas_root = tmp_path / "monte-carlo-cas"
    store = FileSystemCAS(cas_root)
    registry_bundle_ref = build_default_registry_bundle(store).bundle_ref
    run_id = "R_q2_installed_monte_carlo"
    run = RunContext.start(store=store, registry_bundle=registry_bundle_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.q2.installed"))

    input_envelope = UncertaintyEnvelope(
        point_estimate=0.0,
        confidence_interval=(-1.96, 1.96),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
        metadata={"param_name": "x"},
    )
    input_envelope_ref = persist_uncertainty_envelope(
        ensure_ir_artifact_store(store), input_envelope
    )
    state_snapshot_ref = store.put_json(
        {"state": {}},
        ArtifactWriteOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=state_snapshot_ref, uncertainty_envelope_ref=input_envelope_ref),
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
        ),
    )
    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        ArtifactWriteOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        {"values": {"y": 0}},
        ArtifactWriteOptions(kind="foundry.metrics", media_type="application/json"),
    )
    initial_simulation_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        ),
        ArtifactWriteOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    state = ExperimentState(
        run_id=run_id,
        inputs={
            INPUT_DATA_SNAPSHOT_REF: DataSnapshotRef(artifact_id=data_snapshot_ref.artifact_id)
        },
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: initial_simulation_ref},
        params={
            "propagation_config": {
                "preferred_method": "monte_carlo",
                "mc_n_samples": 100,
                "mc_batch_size": 100,
                "mc_min_valid_samples": 10,
                "mc_seed": 194,
                "compute_sensitivity": False,
            },
            "propagation_sensitivity": {"y": {"x": 1.0}},
        },
    )

    draws = np.linspace(-1.0, 1.0, 100, dtype=np.float64)
    draw_offset = [0]

    def sample_fixed_values(_rng, _envelope, count: int) -> np.ndarray:
        start = draw_offset[0]
        selected = draws[start : start + count]
        assert selected.shape == (count,)
        draw_offset[0] += count
        return selected

    monkeypatch.setattr(
        MonteCarloPropagator,
        "_sample_from_envelope",
        staticmethod(sample_fixed_values),
    )
    sampled_inputs: list[float] = []
    transient_raised = False

    def build_intermittent_fn(params, *, base_metric_values, nominal_params):
        del params, base_metric_values, nominal_params

        def evaluate(**current_params):
            nonlocal transient_raised
            x = float(current_params["x"])
            sampled_inputs.append(x)
            if x < 0 and not transient_raised:
                transient_raised = True
                raise PolicyOSError("temporary evaluator outage", category=ErrorCategory.TRANSIENT)
            return {"y": x}

        evaluate._sensitivity_map = {"y": {"x": 1.0}}
        return evaluate, {"x"}

    monkeypatch.setattr(node_module, "_build_propagation_fn", build_intermittent_fn)
    produced = PropagateUncertaintyNode().execute(ctx, state)
    assert produced.status == "ok"
    produced_sim_ref = produced.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    produced_simulation = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(produced_sim_ref.artifact_id))
    )
    report = from_canonical_bytes(
        store.get_bytes(produced_simulation.propagation_report_ref.artifact_id)
    )
    envelope = load_uncertainty_envelope(
        ensure_ir_artifact_store(store), produced_simulation.uncertainty_envelopes["y"]
    )
    assert envelope.gate_eligible is True
    assert report["schema_version"] == "1.1"
    assert isinstance(report["diagnostics"], list)
    metric_diagnostic = next(row for row in report["diagnostics"] if row["metric_id"] == "y")
    assert metric_diagnostic["diagnostics"]["output_coverage_complete"] is True
    ledger = report["draw_outcome_provenance"]
    assert ledger["outcome_denominator_complete"] is True
    assert ledger["requested_draw_count"] == 100
    assert ledger["attempted_draw_count"] == 100
    assert ledger["successful_draw_count"] == 100
    assert ledger["unattempted_draw_count"] == 0
    assert ledger["failure_records"] == []
    assert ledger["simulation_attempt_count"] == 102
    assert ledger["retry_attempt_count"] == 1
    assert ledger["simulation_attempt_count"] == (
        1 + ledger["attempted_draw_count"] + ledger["retry_attempt_count"]
    )
    assert draw_offset == [100]
    assert transient_raised is True
    assert len(sampled_inputs) == ledger["simulation_attempt_count"]
    assert len([value for value in sampled_inputs if value == -1.0]) == 2

    trinity_ref = store.put_json(
        TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="q2_installed_uncertainty_consumer",
                domain=ProblemDomain.SOCIAL,
                objectives=[
                    ObjectiveSpec(
                        objective_id="uncertainty_objective",
                        metric_id="y",
                        direction=OptimizationDirection.MINIMIZE,
                    )
                ],
                stakeholders=[
                    StakeholderSpec(
                        stakeholder_id="workers",
                        entity_type=EntityType.AGENT,
                        priority=1,
                    )
                ],
                normative_frame=NormativeFrame(
                    default_policy=NormativeArbitrationPolicy.WEIGHTED_WELFARE,
                    enabled_policies=[NormativeArbitrationPolicy.WEIGHTED_WELFARE],
                    stakeholder_bindings=[
                        StakeholderOutcomeBinding(
                            binding_id="workers_uncertainty",
                            stakeholder_id="workers",
                            channel=NormativeOutcomeChannel.UNCERTAINTY_CI_WIDTH_RATIO,
                            outcome_key="y",
                        )
                    ],
                    utility_terms=[
                        StakeholderUtilityTerm(
                            term_id="workers_uncertainty_utility",
                            stakeholder_id="workers",
                            binding_refs=["workers_uncertainty"],
                            welfare_weight=1,
                        )
                    ],
                    rights_catalog=[
                        StakeholderRightSpec(
                            right_id="workers_uncertainty_is_known",
                            stakeholder_id="workers",
                            binding_ref="workers_uncertainty",
                            operator=">=",
                            threshold=0,
                        )
                    ],
                ),
            ),
            policy_spec=PolicySpec(policy_id="q2_installed_policy", interventions=[]),
            model_spec=ModelSpec(
                model_id="q2_installed_model",
                data_snapshot_ref="sha256:" + "0" * 64,
                fidelity_level=FidelityLevel.HYBRID,
            ),
        ),
        ArtifactWriteOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )

    # Reopen the CAS so both admission and orchestration consume persisted bytes.
    reader = FileSystemCAS(cas_root)
    fresh_store = ensure_ir_artifact_store(reader)
    admission = load_simulation_result_uncertainty_admission(fresh_store, produced_sim_ref, "y")
    assert admission.envelope is None
    assert "draw_success_ledger_missing" in admission.limitation_codes
    assert "draw_basis_verifier_missing" in admission.limitation_codes
    assert "propagation_report_diagnostics_missing" not in admission.limitation_codes
    assert "propagation_draw_denominator_mismatch" not in admission.limitation_codes

    reader_run = RunContext.start(
        store=reader,
        registry_bundle=registry_bundle_ref,
        run_id=f"{run_id}_reader",
    )
    reader_ctx = ExecutionContext(
        store=reader,
        run=reader_run,
        logger=logging.getLogger("test.q2.installed.reader"),
    )
    normative_state = ExperimentState(
        run_id=run_id,
        inputs={INPUT_TRINITY_BUNDLE_REF: trinity_ref},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: produced_sim_ref},
    )
    outcome = RunNormativeArbitrationNode().execute(reader_ctx, normative_state)
    assert outcome.status == "ok"
    result_ref = outcome.state.artifacts_index[ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF]
    result = load_normative_arbitration_result(fresh_store, result_ref)
    assert result.model_completeness is NormativeModelCompleteness.PARTIAL
    assert any("draw_basis_verifier_missing" in warning for warning in result.warnings)
    assert not any(
        "propagation_draw_denominator_mismatch" in warning for warning in result.warnings
    )
    proposal = next(
        item for item in result.option_matrix if item.option is ArbitrationOption.PROPOSAL
    )
    assert "workers_uncertainty" not in proposal.binding_values
    assert result.rights_audit[0].status is NormativeAuditStatus.UNEVALUATED

    # Remove diagnostics from actual producer output but retain its remaining ledger markers.
    missing_diagnostics = dict(report)
    missing_diagnostics.pop("diagnostics")
    assert missing_diagnostics["draw_outcome_provenance"]["outcome_denominator_complete"] is True
    forged_report_ref = store.put_json(
        missing_diagnostics,
        ArtifactWriteOptions(
            kind="foundry.propagation_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.PropagationReport", version="1.1"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    forged_sim_ref = store.put_json(
        produced_simulation.model_copy(update={"propagation_report_ref": forged_report_ref}),
        ArtifactWriteOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.1"),
        ),
    )
    corrupted_admission = load_simulation_result_uncertainty_admission(
        fresh_store, forged_sim_ref, "y"
    )
    assert corrupted_admission.envelope is None
    assert "propagation_report_diagnostics_missing" in corrupted_admission.limitation_codes
    assert "propagation_draw_denominator_mismatch" not in corrupted_admission.limitation_codes
    assert "draw_basis_verifier_missing" in corrupted_admission.limitation_codes

    forged_normative_state = normative_state.model_copy(
        update={
            "artifacts_index": {
                **normative_state.artifacts_index,
                ARTIFACT_SIMULATION_RESULT_REF: forged_sim_ref,
            }
        }
    )
    forged_outcome = RunNormativeArbitrationNode().execute(reader_ctx, forged_normative_state)
    assert forged_outcome.status == "ok"
    forged_result_ref = forged_outcome.state.artifacts_index[
        ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF
    ]
    forged_result = load_normative_arbitration_result(fresh_store, forged_result_ref)
    assert forged_result.model_completeness is NormativeModelCompleteness.PARTIAL
    assert any(
        "propagation_report_diagnostics_missing" in warning for warning in forged_result.warnings
    )
    forged_proposal = next(
        item for item in forged_result.option_matrix if item.option is ArbitrationOption.PROPOSAL
    )
    assert "workers_uncertainty" not in forged_proposal.binding_values


def test_scholar_raw_source_binding_survives_fresh_cas_read_and_rejects_invented_quote(
    tmp_path: Path,
) -> None:
    """Persisted citations bind to raw bytes and a fresh reader refuses a fabricated span."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.canon import content_hash, from_canonical_bytes
    from polisyos.scholar.search.cache import UrlFetchCache
    from polisyos.scholar.search.fetcher import _extract_title_and_text, source_id_from_url
    from polisyos.scholar.search.models import (
        FetchResult,
        QueryGraph,
        ResearchBrief,
        WebEvidenceBundle,
        WebSearchHit,
    )
    from polisyos.scholar.search.scoring import build_source_metadata, compress_page_to_snippets
    from polisyos.scholar.search.security import sanitize_untrusted_text
    from polisyos.scholar.search.service import ScholarDeepSearchService
    from polisyos.scholar.search.source_binding import validate_web_evidence_source_binding
    from polisyos.scientist.evidence.verifier import verify_web_evidence_bundle

    cas_root = tmp_path / "scholar-cas"
    writer = FileSystemCAS(cas_root)
    url = "https://agency.gov/minimum-wage"
    raw_bytes = (
        b"<html><body><p>Minimum wage increased earnings for low-wage workers.</p></body></html>"
    )
    title, extracted_text = _extract_title_and_text(
        raw_bytes,
        mime="text/html",
        final_url=url,
    )
    extracted_text = sanitize_untrusted_text(extracted_text)
    raw_digest = content_hash(raw_bytes)
    fetched = FetchResult(
        url=url,
        final_url=url,
        title=title,
        text=extracted_text,
        content_type="text/html",
        content_sha256=raw_digest,
        byte_size=len(raw_bytes),
        status="ok",
        source_type="government",
    )
    fetched = UrlFetchCache(cas=writer).put(fetched, raw_bytes=raw_bytes).to_fetch_result()
    source_id = source_id_from_url(url, raw_digest)
    hit = WebSearchHit(
        url=url,
        provider="fixture",
        query="minimum wage earnings",
        rank=1,
        source_type="government",
    )
    source = build_source_metadata(source_id=source_id, hit=hit, fetch=fetched)
    snippets = compress_page_to_snippets(
        source_id=source_id,
        url=url,
        text=extracted_text,
        query_node_id="q1",
        perspective="overview",
        query_terms=["earnings"],
        max_snippets=1,
        window_chars=len(extracted_text),
    )
    assert len(snippets) == 1
    brief = ResearchBrief(question="minimum wage earnings")
    produced_bundle = WebEvidenceBundle(
        bundle_id="bundle.e02.installed-source-binding",
        brief=brief,
        query_graph=QueryGraph(brief=brief),
        sources=[source],
        snippets=snippets,
    )
    bundle_ref = ScholarDeepSearchService(cas=writer).persist_bundle(produced_bundle)
    assert source.raw_artifact_ref is not None
    assert writer.get_bytes(source.raw_artifact_ref) == raw_bytes
    assert source.raw_artifact_ref.artifact_id.hex == raw_digest

    reader = FileSystemCAS(cas_root)
    persisted_bytes = reader.get_bytes(bundle_ref)
    consumed_bundle = WebEvidenceBundle.model_validate(from_canonical_bytes(persisted_bytes))
    bound = validate_web_evidence_source_binding(consumed_bundle, cas=reader)
    assert bound.passed is True
    assert bound.source_text_by_id[source_id] == extracted_text
    assert verify_web_evidence_bundle(consumed_bundle, cas=reader).passed is True

    invented_snippet = consumed_bundle.snippets[0].model_copy(update={"text": "invented quote"})
    invented_bundle = consumed_bundle.model_copy(update={"snippets": [invented_snippet]})
    refusal = validate_web_evidence_source_binding(invented_bundle, cas=reader)
    assert refusal.passed is False
    assert any(item.startswith("span_text_mismatch:") for item in refusal.violations)
    assert verify_web_evidence_bundle(invented_bundle, cas=reader).passed is False
