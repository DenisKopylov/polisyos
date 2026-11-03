"""Actual ensemble jobs use the canonical selected-SCM CAS consumer."""

import copy
import os
import subprocess
import sys

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    PutOptions,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
)
from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.analytics.causal_queries import CausalQuery, CausalQueryResult
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
    persist_structural_causal_model_spec,
)
from polisyos.scientist.nodes.builtins.causal import run_causal_ensemble as ensemble
from polisyos.scientist.nodes.builtins.causal.run_causal_queries import RunCausalQueriesNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENSEMBLE_ENVELOPE_REF,
    ARTIFACT_CAUSAL_QUERY_RESULT_REF,
    ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF,
)


def _model_and_query():
    scm = StructuralCausalModelSpec(
        graph=CausalGraphModel(
            graph_type="dag", nodes=["X", "Y"], edges=[{"src": "X", "dst": "Y"}]
        ),
        mechanisms=[
            NodeMechanism(
                variable="X",
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.0, "std": 1.0},
                source=MechanismSource.DEFAULT,
            ),
            NodeMechanism(
                variable="Y",
                parents=["X"],
                family=MechanismFamily.LINEAR,
                family_params={"intercept": 1.0, "coefficients": {"X": 2.0}, "noise_std": 0.0},
                source=MechanismSource.DEFAULT,
            ),
        ],
        fit_method="manual",
    )
    query = CausalQuery(
        query_type="interventional",
        treatment_variable="X",
        treatment_value=2.0,
        outcome_variable="Y",
        n_samples=32,
    )
    MethodRegistry.get_instance().register(GCMQuery, override=True)
    return scm, query


def test_actual_ensemble_member_job_records_its_selected_scm_input(execution_context, monkeypatch):
    scm, query = _model_and_query()
    source = persist_structural_causal_model_spec(
        ensure_ir_artifact_store(execution_context.store), scm
    )
    original = ensemble.run_job
    observed = {}

    def actual_job(spec, **kwargs):
        observed["spec"] = spec
        result = original(spec, **kwargs)
        observed["result"] = result
        return result

    monkeypatch.setattr(ensemble, "run_job", actual_job)
    result = ensemble._run_member_query(ctx=execution_context, query=query, scm_spec=scm, seed=13)
    assert result.result_mean == pytest.approx(5.0, abs=1e-12)
    selected_input = observed["spec"].input_refs.get("scm_spec")
    assert selected_input is not None
    source_core = ArtifactRef.model_validate(source.model_dump(mode="json"))
    assert selected_input == source_core
    manifest = execution_context.store.get_manifest(observed["result"].method_result_ref)
    assert any(
        i.artifact_id == source_core.artifact_id
        and i.manifest_profile_sha256 == source_core.manifest_profile_sha256
        and i.role == "input:scm_spec"
        for i in manifest.inputs
    )


def test_actual_ensemble_member_refuses_peer_alias_different_from_persisted_result(
    execution_context, monkeypatch
):
    scm, query = _model_and_query()
    original = ensemble.run_job

    def altered_job(spec, **kwargs):
        result = original(spec, **kwargs)
        assert not result.issues
        changed = copy.deepcopy(result.final_state)
        original_result = CausalQueryResult.model_validate(changed["query_result"])
        changed["query_result"] = original_result.model_copy(
            update={
                "result_mean": original_result.result_mean + 10.0,
                "result_ci": tuple(x + 10.0 for x in original_result.result_ci),
                "result_distribution": [x + 10.0 for x in original_result.result_distribution],
            }
        )
        return result.model_copy(update={"final_state": changed})

    monkeypatch.setattr(ensemble, "run_job", altered_job)
    with pytest.raises(ValueError, match="peer output differs"):
        ensemble._run_member_query(ctx=execution_context, query=query, scm_spec=scm, seed=13)


@pytest.mark.parametrize("variant", ["matching", "foreign-model", "same-bytes-other-profile"])
def test_precomputed_ensemble_result_requires_exact_selected_scm_lineage(
    execution_context, minimal_state, variant
):
    scm, query = _model_and_query()
    ir_store = ensure_ir_artifact_store(execution_context.store)
    scm_ref = persist_structural_causal_model_spec(ir_store, scm)
    request_state = minimal_state.model_copy(
        update={
            "params": {"causal_query": query.model_dump(mode="json"), "random_seed": 13},
            "artifacts_index": {ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF: scm_ref},
        }
    )
    produced = RunCausalQueriesNode().execute(execution_context, request_state)
    assert produced.status == "ok", produced.error
    result_ref = produced.state.artifacts_index[ARTIFACT_CAUSAL_QUERY_RESULT_REF]
    selected_scm_ref = scm_ref
    if variant == "foreign-model":
        changed_y = scm.mechanisms[1].model_copy(
            update={
                "family_params": {**scm.mechanisms[1].family_params, "intercept": 2.0},
            }
        )
        changed = StructuralCausalModelSpec.model_validate(
            scm.model_copy(update={"mechanisms": [scm.mechanisms[0], changed_y]}).model_dump(
                mode="json"
            )
        )
        selected_scm_ref = persist_structural_causal_model_spec(ir_store, changed)
    elif variant == "same-bytes-other-profile":
        note = execution_context.store.put_json(
            {"scope": "distinct declared lineage"},
            PutOptions(kind="tests.scm_lineage_note", media_type="application/json"),
        )
        selected_scm_ref = persist_structural_causal_model_spec(
            ir_store,
            scm,
            inputs=[
                input_ref_from_artifact_ref(note, role="declared_source_note"),
            ],
        )
        assert selected_scm_ref.artifact_id == scm_ref.artifact_id
        assert selected_scm_ref.manifest_profile_sha256 != scm_ref.manifest_profile_sha256
    request = minimal_state.model_copy(
        update={
            "params": {
                "causal_ensemble_enabled": True,
                "causal_ensemble_members": [
                    {
                        "structural_causal_model_spec_ref": selected_scm_ref.model_dump(
                            mode="json"
                        ),
                        "causal_query_result_ref": result_ref.model_dump(mode="json"),
                    }
                ],
            }
        }
    )
    outcome = ensemble.RunCausalEnsembleNode().execute(execution_context, request)
    if variant == "matching":
        assert outcome.status == "ok", outcome.error
        envelope_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_ENSEMBLE_ENVELOPE_REF]
        reader = """
import sys
from polisyos.core.artifacts import ArtifactRef,FileSystemCAS,ensure_ir_artifact_store
from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
from polisyos.ir.registry.refs import UncertaintyEnvelopeRef
store=FileSystemCAS(sys.argv[1])
envelope=load_uncertainty_envelope(ensure_ir_artifact_store(store),UncertaintyEnvelopeRef.model_validate_json(sys.argv[2]))
assert envelope.point_estimate == 5.0
assert envelope.confidence_interval == (5.0,5.0)
assert envelope.gate_eligible is False, envelope.model_dump_json()
assert envelope.confidence_level is None
assert envelope.interval_semantics.value == 'heuristic_range'
assert envelope.is_heuristic_ci is True
assert envelope.distribution_family.value == 'unknown'
assert envelope.metadata['member_semantics'][0]['gate_eligible'] is False
assert envelope.metadata['member_semantics'][0]['metadata']['authority_limitation']
assert envelope.metadata['member_weights'] == [1.0]
manifest=store.get_manifest(ArtifactRef.model_validate_json(sys.argv[2]))
source=ArtifactRef.model_validate_json(sys.argv[3])
assert any(i.role=='member_0.query_result' and i.artifact_id==source.artifact_id and i.manifest_profile_sha256==source.manifest_profile_sha256 for i in manifest.inputs)
print('PASS actual fixed-model member draws remain a useful non-gating empirical range')
"""
        child = subprocess.run(
            [
                sys.executable,
                "-c",
                reader,
                str(execution_context.store.root),
                envelope_ref.model_dump_json(),
                result_ref.model_dump_json(),
            ],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            check=False,
        )
        assert child.returncode == 0, child.stdout + child.stderr
    else:
        assert outcome.status == "fail"
        assert "selected SCM binding" in outcome.error.message


def test_actual_ensemble_query_retains_checked_method_result_and_evidence_lineage(
    execution_context, minimal_state
):
    scm, query = _model_and_query()
    scm_ref = persist_structural_causal_model_spec(
        ensure_ir_artifact_store(execution_context.store), scm
    )
    state = minimal_state.model_copy(
        update={
            "params": {
                "causal_ensemble_enabled": True,
                "causal_query": query.model_dump(mode="json"),
                "random_seed": 13,
                "causal_ensemble_members": [
                    {"structural_causal_model_spec_ref": scm_ref.model_dump(mode="json")}
                ],
            }
        }
    )
    outcome = ensemble.RunCausalEnsembleNode().execute(execution_context, state)
    assert outcome.status == "ok", outcome.error
    envelope_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_ENSEMBLE_ENVELOPE_REF]
    manifest = execution_context.store.get_manifest(
        ArtifactRef.model_validate(envelope_ref.model_dump(mode="json"))
    )
    result_inputs = [i for i in manifest.inputs if i.role == "member_0.method_result"]
    evidence_inputs = [i for i in manifest.inputs if i.role == "member_0.method_evidence"]
    assert len(result_inputs) == len(evidence_inputs) == 1
    assert result_inputs[0].manifest_profile_sha256 is not None
    assert evidence_inputs[0].manifest_profile_sha256 is not None
    result_ref = ArtifactRef(
        artifact_id=result_inputs[0].artifact_id,
        kind="scientist.method_result.causal.structural",
        media_type="application/json",
        manifest_profile_sha256=result_inputs[0].manifest_profile_sha256,
    )
    source_manifest = execution_context.store.get_manifest(result_ref)
    source_core = ArtifactRef.model_validate(scm_ref.model_dump(mode="json"))
    assert any(
        i.role == "input:scm_spec"
        and i.artifact_id == source_core.artifact_id
        and i.manifest_profile_sha256 == source_core.manifest_profile_sha256
        for i in source_manifest.inputs
    )
