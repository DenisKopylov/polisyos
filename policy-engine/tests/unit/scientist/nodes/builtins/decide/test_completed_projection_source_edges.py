"""Exercise the issued AD01 basis through the real evaluation writer."""

from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import artifact_ref_identity_key, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import PutOptions
from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
    attach_completed_method_metric_observation_projection,
    read_completed_admitted_method_metric_projection,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    persist_policy_evaluation_vector,
    persist_policy_evaluation_vector_to_store,
)
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from tests.unit.scientist.nodes.builtins.decide.test_policy_runtime_method_metrics import (
    _exercise_public_execute_method_metric_source,
)


def _evaluated(source, monkeypatch, *, fidelity="selection"):
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.scientist.nodes.builtins.decide import policy_runtime_support
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

    basis, ref, store = source["projection"].basis, source["candidate_ref"], source["store"]
    assert basis is not None
    candidate = PolicyCandidateSchema.model_validate(load_core_json_artifact(store, ref))
    # This synthetic association witness does not claim safety or grounding.
    monkeypatch.setattr(
        policy_runtime_support, "_production_policy_evaluation_safety_blockers", lambda **kwargs: []
    )
    backend = policy_runtime_support.ProductionPolicyEvaluationBackend().with_method_metric_projection_basis(
        basis=basis, candidate_ref=ref
    )
    artifact = backend.evaluate(
        candidate,
        fidelity=fidelity,
        simulation_metrics={},
        uncertainty=None,
        distributional_report=None,
        causal_effect_report=None,
        cross_graph_profile=None,
        governance_report=None,
        evaluation_attempt_id="attempt:medium",
    )
    assert artifact.completed_projection_binding is not None
    return candidate, artifact, backend


def test_issued_basis_binds_real_projection_edges_and_requires_fresh_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _exercise_public_execute_method_metric_source(
        tmp_path, monkeypatch, canonical_compile=True
    )
    basis = source["projection"].basis
    assert basis is not None
    candidate = source["candidate_ref"]
    store = source["store"]
    actual_candidate, artifact, backend = _evaluated(source, monkeypatch)
    vector = artifact.evaluation_vector
    binding = artifact.completed_projection_binding
    assert (
        backend.select_completed_evaluation_binding(
            evaluation=vector,
            candidate_ref=candidate,
            packet_ref=None,
            ticket_id=None,
            candidate_hash=None,
        )
        is None
    )
    different_candidate = actual_candidate.model_copy(
        update={"implementation_notes": ["same id, different policy content"]}
    )
    assert different_candidate.candidate_id == actual_candidate.candidate_id
    with pytest.raises(ValueError, match="completed_projection_evaluated_candidate_mismatch"):
        attach_completed_method_metric_observation_projection(
            PolicyEvaluationVector(candidate_id=actual_candidate.candidate_id),
            candidate_ref=candidate,
            evaluated_candidate=different_candidate,
            basis=basis,
        )
    forged_vector = vector.model_copy(update={"feasible": not vector.feasible})
    assert forged_vector.candidate_id == vector.candidate_id
    assert (
        backend.select_completed_evaluation_binding(
            evaluation=forged_vector,
            candidate_ref=candidate,
            packet_ref=None,
            ticket_id=None,
            candidate_hash=None,
        )
        is None
    )
    with pytest.raises(ValueError, match="completed_projection_evaluation_binding"):
        persist_policy_evaluation_vector_to_store(
            store,
            candidate_ref=candidate,
            evaluation_vector=forged_vector,
            completed_projection_basis=basis,
            completed_projection_binding=binding,
        )
    forged_hash = vector.model_copy(
        update={"metadata": {**vector.metadata, "candidate_hash": "wrong-candidate-hash"}}
    )
    with pytest.raises(ValueError, match="completed_projection_evaluation_binding_mismatch"):
        persist_policy_evaluation_vector_to_store(
            store,
            candidate_ref=candidate,
            evaluation_vector=forged_hash,
            completed_projection_basis=basis,
            completed_projection_binding=binding,
        )
    result = persist_policy_evaluation_vector_to_store(
        store,
        candidate_ref=candidate,
        evaluation_vector=vector,
        completed_projection_basis=basis,
        completed_projection_binding=binding,
    )
    inputs = {edge.role: edge for edge in store.get_manifest(result).inputs}
    for role, ref in (
        ("completed_projection_source_candidate", basis.candidate_ref),
        ("completed_projection_source_state", basis.source_state_ref),
        ("completed_projection_vector", basis.vector_ref),
    ):
        assert str(inputs[role].artifact_id) == str(ref.artifact_id)
        assert inputs[role].manifest_profile_sha256 == ref.manifest_profile_sha256
    assert (
        vector.metadata["completed_method_metric_projection"]["authority_status"]
        == "candidate_only"
    )
    with pytest.raises(ValueError, match="completed_projection_owner_basis_required"):
        persist_policy_evaluation_vector_to_store(
            store, candidate_ref=candidate, evaluation_vector=vector
        )

    manifest = store.get_manifest(candidate)
    alternate = store.put_bytes(
        store.get_bytes(candidate),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
            env=manifest.env,
            inputs=[
                *manifest.inputs,
                input_ref_from_artifact_ref(candidate, role="profile_variant_source"),
            ],
            canon=manifest.canon,
            governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            same_input_closure=manifest.same_input_closure,
            authority=manifest.authority,
            warnings=manifest.warnings,
        ),
        return_selected_profile=True,
    )
    assert alternate.artifact_id == candidate.artifact_id
    assert alternate.manifest_profile_sha256 != candidate.manifest_profile_sha256
    with pytest.raises(ValueError, match="completed_projection_candidate_selection_mismatch"):
        persist_policy_evaluation_vector_to_store(
            store,
            candidate_ref=alternate,
            evaluation_vector=vector,
            completed_projection_basis=basis,
            completed_projection_binding=binding,
        )

    raw = dict(vector.metadata["completed_method_metric_projection"])
    source_ref = dict(raw["source_candidate_ref"])
    source_ref["manifest_profile_sha256"] = "sha256:" + "f" * 64
    raw["source_candidate_ref"] = source_ref
    forged = vector.model_copy(
        update={"metadata": {**vector.metadata, "completed_method_metric_projection": raw}}
    )
    with pytest.raises(ValueError, match="completed_projection_owner_basis_mismatch"):
        persist_policy_evaluation_vector_to_store(
            store,
            candidate_ref=candidate,
            evaluation_vector=forged,
            completed_projection_basis=basis,
            completed_projection_binding=binding,
        )

    from types import SimpleNamespace

    class CurrentOwner:
        calls = 0

        def resolve_completed_method_metric_selection(self, **kwargs):
            self.calls += 1
            return source["completed_source"]

    owner = CurrentOwner()
    current_context = SimpleNamespace(
        store=store,
        method_metric_selection_owner=owner,
        run=SimpleNamespace(tenant_id="tenant-public-execute", cell_id="cell-public-execute"),
    )
    repersisted = persist_policy_evaluation_vector(
        current_context,
        candidate_ref=candidate,
        evaluation_vector=vector,
        completed_projection_binding=binding,
    )
    assert repersisted.manifest_profile_sha256 is not None
    assert owner.calls == 4

    class RevokedOwner:
        def resolve_completed_method_metric_selection(self, **kwargs):
            return None

    revoked_context = SimpleNamespace(
        store=store,
        method_metric_selection_owner=RevokedOwner(),
        run=SimpleNamespace(tenant_id="tenant-public-execute", cell_id="cell-public-execute"),
    )
    with pytest.raises(ValueError, match="completed_projection_current_owner_not_selected"):
        persist_policy_evaluation_vector(
            revoked_context,
            candidate_ref=candidate,
            evaluation_vector=vector,
            completed_projection_binding=binding,
        )

    refreshed = read_completed_admitted_method_metric_projection(
        store,
        owner=RevokedOwner(),
        source_run_id=source["work"].run_id,
        candidate_ref=candidate,
        tenant_id="tenant-public-execute",
        cell_id="cell-public-execute",
    )
    assert refreshed.status != "selected"
    assert refreshed.basis is None
    assert artifact_ref_identity_key(candidate) == artifact_ref_identity_key(basis.candidate_ref)


def test_projection_closure_refuses_omitted_selected_vector_edge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.core.artifacts.canonical_profile import (
        CoreJsonReadLimits,
        read_core_input_manifest_profile_bounded,
    )
    from polisyos.scientist.orchestration.engine.child_output_closure import (
        ChildOutputClosureRefusalError,
        TypedChildOutputClosureResolver,
    )

    source = _exercise_public_execute_method_metric_source(
        tmp_path, monkeypatch, canonical_compile=True
    )
    basis, candidate, store = source["projection"].basis, source["candidate_ref"], source["store"]
    assert basis is not None
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

    actual_candidate = PolicyCandidateSchema.model_validate(
        load_core_json_artifact(store, candidate)
    )
    vector = attach_completed_method_metric_observation_projection(
        PolicyEvaluationVector(candidate_id=actual_candidate.candidate_id),
        candidate_ref=candidate,
        evaluated_candidate=actual_candidate,
        basis=basis,
    )
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.scientist.methods.search.objective import method_metric_observation_input_refs

    # Deliberately write a synthetic payload directly: this tests only the closure
    # parser and does not assert owner-produced invocation provenance.
    edges = [input_ref_from_artifact_ref(candidate, role="candidate")]
    edges.extend(
        input_ref_from_artifact_ref(ref, role=role)
        for role, ref in (
            ("completed_projection_source_candidate", basis.candidate_ref),
            ("completed_projection_source_state", basis.source_state_ref),
            ("completed_projection_vector", basis.vector_ref),
        )
    )
    edges.extend(
        input_ref_from_artifact_ref(ref, role=role)
        for role, ref in method_metric_observation_input_refs(basis.observations)
    )
    actual = store.put_json(
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
    manifest = store.get_manifest(actual)
    priors = tuple(
        read_core_input_manifest_profile_bounded(
            store, edge, max_manifest_bytes=16 * 1024 * 1024
        ).effective_ref
        for edge in manifest.inputs
    )

    class OwnerFixture:
        def __getattr__(self, name):
            return getattr(store, name)

        def selected_source_ref(self, role):
            return candidate if role == "candidate" else None

        def is_previously_authorized(self, ref):
            return any(
                artifact_ref_identity_key(ref) == artifact_ref_identity_key(value)
                for value in priors
            )

    owner = OwnerFixture()
    resolver = TypedChildOutputClosureResolver(
        limits=CoreJsonReadLimits(
            max_bytes=8 * 1024 * 1024,
            max_depth=128,
            max_elements=100000,
            max_manifest_bytes=16 * 1024 * 1024,
        )
    )
    closure = resolver.resolve(owner, actual)
    assert artifact_ref_identity_key(basis.vector_ref) in {
        artifact_ref_identity_key(ref) for ref in closure
    }
    forged = store.put_json(
        vector,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=[edge for edge in manifest.inputs if edge.role != "completed_projection_vector"],
        ),
        return_selected_profile=True,
    )
    with pytest.raises(ChildOutputClosureRefusalError, match="child_output_payload_input_mismatch"):
        resolver.resolve(owner, forged)


def test_backend_evaluate_refuses_actual_different_candidate_same_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.scientist.nodes.builtins.decide import policy_runtime_support
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

    source = _exercise_public_execute_method_metric_source(
        tmp_path, monkeypatch, canonical_compile=True
    )
    basis, ref, store = source["projection"].basis, source["candidate_ref"], source["store"]
    assert basis is not None
    actual = PolicyCandidateSchema.model_validate(load_core_json_artifact(store, ref))
    other = actual.model_copy(
        update={"implementation_notes": ["same id; changed candidate content"]}
    )
    assert other.candidate_id == actual.candidate_id
    # Synthetic association test only: this does not establish safety or grounding.
    monkeypatch.setattr(
        policy_runtime_support, "_production_policy_evaluation_safety_blockers", lambda **kwargs: []
    )
    backend = policy_runtime_support.ProductionPolicyEvaluationBackend().with_method_metric_projection_basis(
        basis=basis, candidate_ref=ref
    )
    args = {
        "fidelity": "selection",
        "simulation_metrics": {},
        "uncertainty": None,
        "distributional_report": None,
        "causal_effect_report": None,
        "cross_graph_profile": None,
        "governance_report": None,
    }
    selected = backend.evaluate(actual, **args)
    assert (
        selected.evaluation_vector.metadata["completed_method_metric_projection"][
            "authority_status"
        ]
        == "candidate_only"
    )
    with pytest.raises(ValueError, match="completed_projection_evaluated_candidate_mismatch"):
        backend.evaluate(other, **args)


def test_store_only_work_packet_reselects_issuer_after_double_withdrawal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine import (
        _persist_policy_runtime_work_packet,
    )
    from tests.unit.scientist.nodes.builtins.decide.test_policy_blueprint_runtime_engine import (
        _initial_state,
    )

    source = _exercise_public_execute_method_metric_source(
        tmp_path, monkeypatch, canonical_compile=True
    )
    basis, ref, store = source["projection"].basis, source["candidate_ref"], source["store"]
    assert basis is not None
    candidate, artifact, _backend = _evaluated(source, monkeypatch, fidelity="medium")
    vector, binding = artifact.evaluation_vector, artifact.completed_projection_binding
    historical_ref = persist_policy_evaluation_vector_to_store(
        store,
        candidate_ref=ref,
        evaluation_vector=vector,
        completed_projection_basis=basis,
        completed_projection_binding=binding,
    )
    historical_bytes = store.get_bytes(historical_ref)
    # The fixture's issuer is a test double. A real owner lifecycle transition is separately required.
    monkeypatch.setattr(
        basis._selection_owner, "resolve_completed_method_metric_selection", lambda **kwargs: None
    )
    with pytest.raises(ValueError, match="completed_projection_current_owner_not_selected"):
        _persist_policy_runtime_work_packet(
            initial_state=_initial_state(store, ref, run_id="run_owner_withdrawal"),
            fidelity="medium",
            evaluation_attempt_id="attempt:medium",
            runtime_artifact=artifact,
            completed_projection_basis=basis,
        )
    assert store.get_bytes(historical_ref) == historical_bytes


def test_live_level4_repersistence_uses_actual_per_result_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine import (
        _persist_policy_runtime_work_packet,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
        ProductionPolicyEvaluationBackend,
    )
    from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
        _resolve_runtime_policy_evaluation,
    )
    from tests.unit.scientist.nodes.builtins.decide.test_policy_blueprint_runtime_engine import (
        _initial_state,
    )

    source = _exercise_public_execute_method_metric_source(
        tmp_path, monkeypatch, canonical_compile=True
    )
    basis, ref, store = source["projection"].basis, source["candidate_ref"], source["store"]
    assert basis is not None
    _candidate, artifact, backend = _evaluated(source, monkeypatch, fidelity="full")
    run_id = "run_live_owner"
    ticket_id = f"ticket:{run_id}"
    packet_ref, reason = _persist_policy_runtime_work_packet(
        initial_state=_initial_state(store, ref, run_id=run_id),
        fidelity="full",
        evaluation_attempt_id="attempt:medium",
        runtime_artifact=artifact,
        completed_projection_basis=basis,
    )
    assert reason is None and packet_ref is not None
    backend.bind_completed_work_packet(
        store=store,
        packet_ref=packet_ref,
        evaluation=artifact.evaluation_vector,
        candidate_ref=ref,
        run_id=run_id,
        ticket_id=ticket_id,
        candidate_hash=f"candidate-hash:{run_id}",
        attempt_id="attempt:medium",
        fidelity="full",
    )
    stage = SimpleNamespace(
        feedback={
            "policy_evaluation": artifact.evaluation_vector.model_dump(mode="json"),
            "policy_runtime_fidelity": "full",
        },
        executed_work_packet_ref=packet_ref,
    )
    outcome = SimpleNamespace(
        stage_results={4: stage}, ticket_id=ticket_id, candidate_hash=f"candidate-hash:{run_id}"
    )
    ctx = SimpleNamespace(
        store=store,
        method_metric_selection_owner=basis._selection_owner,
        run=SimpleNamespace(tenant_id="tenant-public-execute", cell_id="cell-public-execute"),
    )
    vector, result_ref = _resolve_runtime_policy_evaluation(
        ctx,
        candidate_ref=ref,
        outcome=outcome,
        fallback=artifact.evaluation_vector,
        runtime_backend=backend,
    )
    assert result_ref is not None
    assert vector.model_dump(mode="json") == artifact.evaluation_vector.model_dump(mode="json")
    wrong_ticket = SimpleNamespace(
        stage_results={4: stage},
        ticket_id="other-ticket",
        candidate_hash=f"candidate-hash:{run_id}",
    )
    with pytest.raises(ValueError, match="completed_projection_evaluation_binding_mismatch"):
        _resolve_runtime_policy_evaluation(
            ctx,
            candidate_ref=ref,
            outcome=wrong_ticket,
            fallback=artifact.evaluation_vector,
            runtime_backend=backend,
        )
    # A newly resumed backend has no proof that this serialized vector was its live result.
    resumed = ProductionPolicyEvaluationBackend().with_method_metric_projection_basis(
        basis=basis, candidate_ref=ref
    )
    with pytest.raises(ValueError, match="completed_projection_evaluation_binding_mismatch"):
        _resolve_runtime_policy_evaluation(
            ctx,
            candidate_ref=ref,
            outcome=outcome,
            fallback=artifact.evaluation_vector,
            runtime_backend=resumed,
        )


def test_forged_observed_measurement_is_not_persisted_as_recomputed(tmp_path: Path) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.scientist.methods.search.objective import SourceMetricObservation

    store = FileSystemCAS(tmp_path / "cas")
    source = store.put_json(
        {"not": "a simulation"},
        PutOptions(kind="test.fake", media_type="application/json"),
        return_selected_profile=True,
    )
    observation = SourceMetricObservation(
        source_status="observed",
        predicate_status="recomputed",
        metric_id="government_balance",
        slot_id="government.balance",
        value=1.0,
        unit_id="usd",
        scope="global",
        quantity_kind="stock",
        simulation_step=0,
        time_basis="simulation_step",
        source_result_ref=source,
        source_metrics_ref=source,
        source_snapshot_ref=source,
    )
    vector = PolicyEvaluationVector(
        metadata={"policy_runtime_source_measurement": observation.model_dump(mode="json")}
    )
    with pytest.raises(ValueError, match="policy_runtime_source_measurement_not_recomputed"):
        persist_policy_evaluation_vector_to_store(
            store, candidate_ref=source, evaluation_vector=vector
        )
