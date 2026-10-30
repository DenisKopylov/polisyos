"""Owner-semantic selected-profile closure witnesses for a real candidate model."""

from pathlib import Path

import pytest

from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
from polisyos.core.artifacts.manifest import artifact_ref_identity_key, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ObjectiveSpec, ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import OptimizationDirection
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.nodes.builtins.planning.stage_b_projection import persist_stage_b_candidate
from polisyos.scientist.orchestration.engine.child_output_closure import (
    ChildOutputClosureRefusalError,
    TypedChildOutputClosureResolver,
)
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    TargetPopulationSpec,
    persist_policy_candidate_schema,
)


class _OwnerReadFixture:
    """Test stand-in: composed Core must independently supply these owner methods."""

    def __init__(self, store, sources, prior=None):
        self.store = store
        self.sources = sources
        self.prior = tuple(sources.values()) if prior is None else prior

    def __getattr__(self, name):
        return getattr(self.store, name)

    def selected_source_ref(self, role):
        return self.sources.get(role)

    def is_previously_authorized(self, ref):
        return any(
            artifact_ref_identity_key(ref) == artifact_ref_identity_key(value)
            for value in self.prior
        )


def _candidate(data, registry, *, sibling=None):
    return PolicyCandidateSchema(
        candidate_id="candidate_one",
        trinity_bundle=TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="candidate_problem",
                domain=ProblemDomain.SOCIAL,
                objectives=[
                    ObjectiveSpec(
                        objective_id="objective_ex_ante_mean_change",
                        metric_id="metric_ex_ante_mean_change",
                        direction=OptimizationDirection.MAXIMIZE,
                    )
                ],
            ),
            policy_spec=PolicySpec(
                policy_id="candidate_policy",
                interventions=[],
                problem_frame_ref=str(sibling.artifact_id) if sibling else None,
            ),
            model_spec=ModelSpec(
                model_id="candidate_model",
                data_snapshot_ref=str(data.artifact_id),
                registry_bundle_ref=str(registry.artifact_id),
            ),
        ),
        target_population=TargetPopulationSpec(population_id="all", description="Software fixture"),
    )


def _resolver():
    return TypedChildOutputClosureResolver(
        limits=CoreJsonReadLimits(
            max_bytes=1000000, max_depth=100, max_elements=10000, max_manifest_bytes=1000000
        )
    )


def _put(store, value, inputs=None):
    return store.put_json(
        value,
        PutOptions(kind="test.input", media_type="application/json", inputs=inputs),
        return_selected_profile=True,
    )


def test_real_candidate_owner_reconciles_selected_state_and_manifest(tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    data, registry = _put(store, {"data": 1}), _put(store, {"registry": 1})
    candidate = _candidate(data, registry)
    projection = persist_stage_b_candidate(
        store, candidate, {"data_snapshot_ref": data, "registry_bundle_ref": registry}
    )
    owner = _OwnerReadFixture(
        store,
        {
            "candidate": projection,
            "model_primary_data_snapshot": data,
            "model_primary_registry": registry,
        },
        prior=(data, registry),
    )
    result = _resolver().resolve(owner, projection)
    assert {artifact_ref_identity_key(x) for x in result} == {
        artifact_ref_identity_key(data),
        artifact_ref_identity_key(registry),
    }


def test_valid_candidate_payload_with_unreleased_sibling_and_missing_edge_refuses(tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    data, registry, sibling = (
        _put(store, {"data": 1}),
        _put(store, {"registry": 1}),
        _put(store, {"sibling": 1}),
    )
    candidate = _candidate(data, registry, sibling=sibling)
    forged = persist_policy_candidate_schema(
        store,
        candidate,
        inputs=[
            input_ref_from_artifact_ref(data, role="model_primary_data_snapshot"),
            input_ref_from_artifact_ref(registry, role="model_primary_registry"),
        ],
        return_selected_profile=True,
    )
    owner = _OwnerReadFixture(
        store,
        {
            "model_primary_data_snapshot": data,
            "model_primary_registry": registry,
            "model_primary_problem_frame": sibling,
            "candidate": forged,
        },
        prior=(data, registry),
    )
    with pytest.raises(ChildOutputClosureRefusalError, match="child_output_payload_input_mismatch"):
        _resolver().resolve(owner, forged)


def test_same_content_wrong_selected_profile_cannot_satisfy_owner_state(tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    seed = _put(store, {"seed": 1})
    actual = _put(store, {"data": 1})
    other = _put(store, {"data": 1}, [input_ref_from_artifact_ref(seed, role="seed")])
    registry = _put(store, {"registry": 1})
    assert actual.artifact_id == other.artifact_id
    assert actual.manifest_profile_sha256 != other.manifest_profile_sha256
    forged = persist_policy_candidate_schema(
        store,
        _candidate(actual, registry),
        inputs=[
            input_ref_from_artifact_ref(other, role="model_primary_data_snapshot"),
            input_ref_from_artifact_ref(registry, role="model_primary_registry"),
        ],
        return_selected_profile=True,
    )
    owner = _OwnerReadFixture(
        store,
        {
            "candidate": forged,
            "model_primary_data_snapshot": actual,
            "model_primary_registry": registry,
        },
        prior=(actual, registry),
    )
    with pytest.raises(ChildOutputClosureRefusalError, match="child_output_payload_input_mismatch"):
        _resolver().resolve(owner, forged)


def test_no_owner_state_binding_refuses(tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    data, registry = _put(store, {"data": 1}), _put(store, {"registry": 1})
    ref = persist_stage_b_candidate(
        store, _candidate(data, registry), {"data": data, "registry": registry}
    )
    with pytest.raises(
        ChildOutputClosureRefusalError, match="child_output_owner_state_binding_unavailable"
    ):
        _resolver().resolve(store, ref)


def test_unknown_nonempty_candidate_metadata_refuses(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    data, registry = _put(store, {"data": 1}), _put(store, {"registry": 1})
    candidate = _candidate(data, registry).model_copy(update={"metadata": {"opaque": "unknown"}})
    ref = persist_stage_b_candidate(store, candidate, {"data": data, "registry": registry})
    owner = _OwnerReadFixture(
        store,
        {"candidate": ref, "model_primary_data_snapshot": data, "model_primary_registry": registry},
        prior=(data, registry),
    )
    with pytest.raises(
        ChildOutputClosureRefusalError, match="child_output_candidate_field_unsupported"
    ):
        _resolver().resolve(owner, ref)


def test_real_evaluation_producer_reconciles_typed_source_observation(tmp_path: Path) -> None:
    from polisyos.scientist.methods.search.objective import SourceMetricObservation
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
        persist_policy_evaluation_vector_to_store,
    )
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

    store = FileSystemCAS(tmp_path / "cas")
    data, registry, source = (
        _put(store, {"data": 1}),
        _put(store, {"registry": 1}),
        _put(store, {"source": 1}),
    )
    candidate = persist_stage_b_candidate(
        store, _candidate(data, registry), {"data": data, "registry": registry}
    )
    observation = SourceMetricObservation(
        source_status="unavailable",
        predicate_status="not_established",
        time_basis="not_established",
        source_result_ref=source,
    )
    vector = PolicyEvaluationVector(
        metadata={"policy_runtime_source_measurement": observation.model_dump(mode="json")}
    )
    evaluation = persist_policy_evaluation_vector_to_store(
        store, candidate_ref=candidate, evaluation_vector=vector
    )
    owner = _OwnerReadFixture(
        store,
        {
            "candidate": candidate,
            "model_primary_data_snapshot": data,
            "model_primary_registry": registry,
        },
        prior=(data, registry, source),
    )
    result = _resolver().resolve(owner, evaluation)
    assert {artifact_ref_identity_key(x) for x in result} == {
        artifact_ref_identity_key(candidate),
        artifact_ref_identity_key(data),
        artifact_ref_identity_key(registry),
        artifact_ref_identity_key(source),
    }


def test_evaluation_typed_source_sibling_missing_edge_refuses(tmp_path: Path) -> None:
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.scientist.methods.search.objective import SourceMetricObservation
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

    store = FileSystemCAS(tmp_path / "cas")
    data, registry, sibling = (
        _put(store, {"data": 1}),
        _put(store, {"registry": 1}),
        _put(store, {"sibling": 1}),
    )
    candidate = persist_stage_b_candidate(
        store, _candidate(data, registry), {"data": data, "registry": registry}
    )
    observation = SourceMetricObservation(
        source_status="unavailable",
        predicate_status="not_established",
        time_basis="not_established",
        source_result_ref=sibling,
    )
    vector = PolicyEvaluationVector(
        metadata={"policy_runtime_source_measurement": observation.model_dump(mode="json")}
    )
    forged = store.put_json(
        vector,
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.policy_design.PolicyEvaluationVector", version="1.2"
            ),
            inputs=[input_ref_from_artifact_ref(candidate, role="candidate")],
        ),
        return_selected_profile=True,
    )
    owner = _OwnerReadFixture(
        store,
        {
            "candidate": candidate,
            "model_primary_data_snapshot": data,
            "model_primary_registry": registry,
        },
        prior=(data, registry),
    )
    with pytest.raises(ChildOutputClosureRefusalError, match="child_output_payload_input_mismatch"):
        _resolver().resolve(owner, forged)


def test_evaluation_observation_same_blob_wrong_profile_refuses(tmp_path: Path) -> None:
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.scientist.methods.search.objective import SourceMetricObservation
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

    store = FileSystemCAS(tmp_path / "cas")
    seed = _put(store, {"seed": 1})
    source = _put(store, {"source": 1})
    other = _put(store, {"source": 1}, [input_ref_from_artifact_ref(seed, role="seed")])
    data, registry = _put(store, {"data": 1}), _put(store, {"registry": 1})
    candidate = persist_stage_b_candidate(
        store, _candidate(data, registry), {"data": data, "registry": registry}
    )
    observation = SourceMetricObservation(
        source_status="unavailable",
        predicate_status="not_established",
        time_basis="not_established",
        source_result_ref=source,
    )
    vector = PolicyEvaluationVector(
        metadata={"policy_runtime_source_measurement": observation.model_dump(mode="json")}
    )
    forged = store.put_json(
        vector,
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.policy_design.PolicyEvaluationVector", version="1.2"
            ),
            inputs=[
                input_ref_from_artifact_ref(candidate, role="candidate"),
                input_ref_from_artifact_ref(other, role="source_simulation_result"),
            ],
        ),
        return_selected_profile=True,
    )
    owner = _OwnerReadFixture(
        store,
        {
            "candidate": candidate,
            "model_primary_data_snapshot": data,
            "model_primary_registry": registry,
        },
        prior=(data, registry, source),
    )
    with pytest.raises(ChildOutputClosureRefusalError, match="child_output_payload_input_mismatch"):
        _resolver().resolve(owner, forged)


def _method_observation_fixture(store):
    from polisyos.scientist.methods.search.objective import MethodMetricObservation

    def put(kind):
        return store.put_json(
            {"fixture": kind},
            PutOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )

    binding = put("foundry.method_metric_binding_set")
    execution = put("foundry.method_execution_bundle")
    simulation = put("foundry.simulation_result")
    evidence = put("test.predicate_evidence")
    observation = MethodMetricObservation.model_validate(
        {
            "source_status": "unavailable",
            "binding_set_ref": binding.model_dump(mode="json"),
            "execution_bundle_ref": execution.model_dump(mode="json"),
            "simulation_result_ref": simulation.model_dump(mode="json"),
            "binding_id": "fixture_binding",
            "objective_id": "fixture_objective",
            "metric_id": "fixture_metric",
            "node_id": "fixture_node",
            "method_fqn": "fixture.method",
            "method_version": "1.0",
            "method_abi_digest": "a" * 64,
            "method_abi_digest_algorithm": "blake2b",
            "slot_id": "fixture_slot",
            "source_unit": {"dimension": "count", "symbol": "count", "scale": 1.0},
            "target_unit": {"kind": "count"},
            "law_id": "fixture_law",
            "law_version": "1.0",
            "law_code_digest": "b" * 64,
            "adapter_id": "fixture_adapter",
            "adapter_version": "1.0",
            "adapter_code_digest": "c" * 64,
            "verifier_id": "fixture_verifier",
            "verifier_revision": "1.0",
            "verifier_code_digest": "d" * 64,
            "checked_context_sha256": "e" * 64,
            "limitations": ["synthetic unavailable fixture"],
            "predicate_evidence": [
                {
                    "predicate_id": "fixture_predicate",
                    "classification": "not_established",
                    "evidence_ref": evidence.model_dump(mode="json"),
                    "limitation": "fixture only",
                }
            ],
        }
    )
    return observation, (binding, execution, simulation, evidence)


def test_real_evaluation_v13_producer_includes_typed_predicate_ref(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from polisyos.scientist.nodes.builtins.causal.counterfactual_identification_gate import (
        evaluate_counterfactual_gate,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
        persist_policy_evaluation_vector_to_store,
    )
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

    store = FileSystemCAS(tmp_path / "cas")
    data, registry = _put(store, {"data": 1}), _put(store, {"registry": 1})
    candidate = persist_stage_b_candidate(
        store, _candidate(data, registry), {"data": data, "registry": registry}
    )
    observation, sources = _method_observation_fixture(store)
    gate = evaluate_counterfactual_gate(None, SimpleNamespace(artifacts_index={}, params={}))
    vector = PolicyEvaluationVector(
        metadata={"candidate_hash": "fixture-hash", "counterfactual_gate_summary": gate.summary},
        method_metric_observations=(observation,),
    )
    evaluation = persist_policy_evaluation_vector_to_store(
        store, candidate_ref=candidate, evaluation_vector=vector
    )
    owner = _OwnerReadFixture(
        store,
        {
            "candidate": candidate,
            "model_primary_data_snapshot": data,
            "model_primary_registry": registry,
        },
        prior=(data, registry, *sources),
    )
    result = _resolver().resolve(owner, evaluation)
    assert {artifact_ref_identity_key(x) for x in result} == {
        artifact_ref_identity_key(x) for x in (candidate, data, registry, *sources)
    }


def test_v13_typed_predicate_sibling_omitted_from_manifest_refuses(tmp_path: Path) -> None:
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.scientist.methods.search.objective import method_metric_observation_input_refs
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

    store = FileSystemCAS(tmp_path / "cas")
    data, registry = _put(store, {"data": 1}), _put(store, {"registry": 1})
    candidate = persist_stage_b_candidate(
        store, _candidate(data, registry), {"data": data, "registry": registry}
    )
    observation, sources = _method_observation_fixture(store)
    vector = PolicyEvaluationVector(method_metric_observations=(observation,))
    edges = [input_ref_from_artifact_ref(candidate, role="candidate")]
    edges.extend(
        input_ref_from_artifact_ref(ref, role=role)
        for role, ref in method_metric_observation_input_refs((observation,))
        if not role.startswith("method_metric_evidence:")
    )
    forged = store.put_json(
        vector,
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.policy_design.PolicyEvaluationVector", version="1.3"
            ),
            inputs=edges,
        ),
        return_selected_profile=True,
    )
    owner = _OwnerReadFixture(
        store,
        {
            "candidate": candidate,
            "model_primary_data_snapshot": data,
            "model_primary_registry": registry,
        },
        prior=(data, registry, *sources[:-1]),
    )
    with pytest.raises(ChildOutputClosureRefusalError, match="child_output_payload_input_mismatch"):
        _resolver().resolve(owner, forged)


def test_v13_typed_predicate_same_blob_wrong_profile_refuses(tmp_path: Path) -> None:
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.scientist.methods.search.objective import method_metric_observation_input_refs
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

    store = FileSystemCAS(tmp_path / "cas")
    data, registry = _put(store, {"data": 1}), _put(store, {"registry": 1})
    candidate = persist_stage_b_candidate(
        store, _candidate(data, registry), {"data": data, "registry": registry}
    )
    observation, sources = _method_observation_fixture(store)
    seed = _put(store, {"seed": 1})
    other = store.put_json(
        {"fixture": "test.predicate_evidence"},
        PutOptions(
            kind="test.predicate_evidence",
            media_type="application/json",
            inputs=[input_ref_from_artifact_ref(seed, role="seed")],
        ),
        return_selected_profile=True,
    )
    assert other.artifact_id == sources[-1].artifact_id
    assert other.manifest_profile_sha256 != sources[-1].manifest_profile_sha256
    edges = [input_ref_from_artifact_ref(candidate, role="candidate")]
    edges.extend(
        input_ref_from_artifact_ref(
            other if role.startswith("method_metric_evidence:") else ref, role=role
        )
        for role, ref in method_metric_observation_input_refs((observation,))
    )
    forged = store.put_json(
        PolicyEvaluationVector(method_metric_observations=(observation,)),
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.policy_design.PolicyEvaluationVector", version="1.3"
            ),
            inputs=edges,
        ),
        return_selected_profile=True,
    )
    owner = _OwnerReadFixture(
        store,
        {
            "candidate": candidate,
            "model_primary_data_snapshot": data,
            "model_primary_registry": registry,
        },
        prior=(data, registry, *sources),
    )
    with pytest.raises(ChildOutputClosureRefusalError, match="child_output_payload_input_mismatch"):
        _resolver().resolve(owner, forged)


def test_untyped_gate_summary_extension_refuses_without_shape_guess(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from polisyos.scientist.nodes.builtins.causal.counterfactual_identification_gate import (
        evaluate_counterfactual_gate,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
        persist_policy_evaluation_vector_to_store,
    )
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

    store = FileSystemCAS(tmp_path / "cas")
    data, registry, sibling = (
        _put(store, {"data": 1}),
        _put(store, {"registry": 1}),
        _put(store, {"sibling": 1}),
    )
    candidate = persist_stage_b_candidate(
        store, _candidate(data, registry), {"data": data, "registry": registry}
    )
    gate = evaluate_counterfactual_gate(None, SimpleNamespace(artifacts_index={}, params={}))
    altered = {**gate.summary, "unknown_extension": sibling.model_dump(mode="json")}
    evaluation = persist_policy_evaluation_vector_to_store(
        store,
        candidate_ref=candidate,
        evaluation_vector=PolicyEvaluationVector(metadata={"counterfactual_gate_summary": altered}),
    )
    owner = _OwnerReadFixture(
        store,
        {
            "candidate": candidate,
            "model_primary_data_snapshot": data,
            "model_primary_registry": registry,
        },
        prior=(data, registry),
    )
    with pytest.raises(
        ChildOutputClosureRefusalError, match="child_output_gate_summary_unsupported"
    ):
        _resolver().resolve(owner, evaluation)


def test_malformed_gate_reason_is_a_typed_refusal(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from polisyos.scientist.nodes.builtins.causal.counterfactual_identification_gate import (
        evaluate_counterfactual_gate,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
        persist_policy_evaluation_vector_to_store,
    )
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

    store = FileSystemCAS(tmp_path / "cas")
    data, registry = _put(store, {"data": 1}), _put(store, {"registry": 1})
    candidate = persist_stage_b_candidate(
        store, _candidate(data, registry), {"data": data, "registry": registry}
    )
    gate = evaluate_counterfactual_gate(None, SimpleNamespace(artifacts_index={}, params={}))
    malformed = {**gate.summary, "reason": {"unknown": "content"}}
    evaluation = persist_policy_evaluation_vector_to_store(
        store,
        candidate_ref=candidate,
        evaluation_vector=PolicyEvaluationVector(
            metadata={"counterfactual_gate_summary": malformed}
        ),
    )
    owner = _OwnerReadFixture(
        store,
        {
            "candidate": candidate,
            "model_primary_data_snapshot": data,
            "model_primary_registry": registry,
        },
        prior=(data, registry),
    )
    with pytest.raises(
        ChildOutputClosureRefusalError, match="child_output_gate_summary_unsupported"
    ):
        _resolver().resolve(owner, evaluation)


def test_forged_extra_staged_sibling_is_not_admitted_as_lineage(tmp_path: Path) -> None:
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

    store = FileSystemCAS(tmp_path / "cas")
    data, registry = _put(store, {"data": 1}), _put(store, {"registry": 1})
    main = persist_stage_b_candidate(
        store, _candidate(data, registry), {"data": data, "registry": registry}
    )
    sibling_value = _candidate(data, registry).model_copy(
        update={"candidate_id": "candidate_sibling"}
    )
    sibling = persist_stage_b_candidate(store, sibling_value, {"data": data, "registry": registry})
    vector = PolicyEvaluationVector(candidate_id="candidate_one")
    forged = store.put_json(
        vector,
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.policy_design.PolicyEvaluationVector", version="1.2"
            ),
            inputs=[
                input_ref_from_artifact_ref(main, role="candidate"),
                input_ref_from_artifact_ref(sibling, role="unselected_sibling"),
            ],
        ),
        return_selected_profile=True,
    )
    owner = _OwnerReadFixture(
        store,
        {
            "candidate": main,
            "model_primary_data_snapshot": data,
            "model_primary_registry": registry,
        },
        prior=(data, registry),
    )
    with pytest.raises(
        ChildOutputClosureRefusalError, match="child_output_unselected_staged_input"
    ):
        _resolver().resolve(owner, forged)
    # An independently prior-authorized same edge does not become a released child member.
    prior_owner = _OwnerReadFixture(
        store,
        {
            "candidate": main,
            "model_primary_data_snapshot": data,
            "model_primary_registry": registry,
        },
        prior=(data, registry, sibling),
    )
    resolved = _resolver().resolve(prior_owner, forged)
    assert artifact_ref_identity_key(sibling) not in {
        artifact_ref_identity_key(item) for item in resolved
    }
