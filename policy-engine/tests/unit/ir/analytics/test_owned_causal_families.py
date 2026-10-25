from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicConstraintFamily,
    AlgebraicConstraintReport,
    CausalDiscoveryReport,
    ImpliedConstraintSpec,
    persist_causal_discovery_report,
)
from polisyos.ir.analytics.causal_ensemble import (
    CausalModelEnsemble,
    EnsembleMember,
    persist_causal_model_ensemble,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphProjectionStatus,
    GraphType,
    graph_projection_disposition,
    load_causal_graph_model,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.causal_queries import (
    CausalQuery,
    CausalQueryResult,
    InterventionSpec,
    QueryType,
    persist_causal_query_result,
)
from polisyos.ir.analytics.structural_causal_model import (
    StructuralCausalModelSpec,
    persist_structural_causal_model_spec,
)
from polisyos.ir.analytics.twin_network import (
    TwinNetworkResult,
    load_twin_network_result,
    persist_twin_network_result,
)
from polisyos.ir.artifacts import get_json_artifact, put_json_artifact
from polisyos.ir.artifacts.io import _put_owned_json_artifact
from polisyos.ir.migrations import base as migration_base
from polisyos.ir.migrations.base import (
    CompatibilityMode,
    get_ir_owner_registry_snapshot,
    register_ir_representation,
    register_schema_version,
)
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation


class CountingStore:
    """Count payload reads while forwarding actual FileSystemCAS operations."""

    def __init__(self, wrapped: object) -> None:
        self.wrapped = wrapped
        self.payload_reads = 0
        self.put_calls = 0

    def get_manifest_bytes(self, ref: object) -> bytes:
        return self.wrapped.get_manifest_bytes(ref)

    def get_manifest(self, ref: object) -> object:
        return self.wrapped.get_manifest(ref)

    def get_bytes(self, ref: object) -> bytes:
        self.payload_reads += 1
        return self.wrapped.get_bytes(ref)

    def put_json(
        self,
        payload: object,
        *,
        opts: object,
        canon_spec: object,
        return_selected_profile: bool = False,
    ) -> object:
        self.put_calls += 1
        return self.wrapped.put_json(
            payload,
            opts=opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )


def _graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["new_policy_action", "unseen_population_outcome"],
        edges=[
            CausalEdge(
                src="new_policy_action",
                dst="unseen_population_outcome",
                mark_src=EdgeMark.TAIL,
                mark_dst=EdgeMark.ARROW,
            )
        ],
        discovery_method="owner_contract_fixture",
    )


@pytest.fixture
def isolated_graph_registry() -> Iterator[None]:
    """Restore only the graph schema rows changed by the nondefault-writer test."""
    registry_key = "causal_graph_model"
    with migration_base._REGISTRY_LOCK:
        before = dict(migration_base._SCHEMA_REGISTRY.get(registry_key, {}))
    try:
        yield
    finally:
        with migration_base._REGISTRY_LOCK:
            if before:
                migration_base._SCHEMA_REGISTRY[registry_key] = before
            else:
                migration_base._SCHEMA_REGISTRY.pop(registry_key, None)


def _one_node_graph() -> CausalGraphModel:
    return CausalGraphModel(graph_type=GraphType.DAG, nodes=["x"], edges=[])


def _query_result() -> CausalQueryResult:
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="x",
        treatment_value=1.0,
        outcome_variable="y",
    )
    return CausalQueryResult(query=query, result_mean=1.0, result_std=0.2, result_ci=(0.6, 1.4))


def _scm_spec() -> StructuralCausalModelSpec:
    return StructuralCausalModelSpec(graph=_one_node_graph(), fit_method="manual")


def _ensemble() -> CausalModelEnsemble:
    return CausalModelEnsemble(
        members=[
            EnsembleMember(
                graph_ref="sha256:" + "a" * 64,
                discovery_method="fixture",
                weight=1.0,
                bootstrap_stability=0.5,
            )
        ]
    )


def _discovery_report() -> CausalDiscoveryReport:
    graph = _one_node_graph()
    return CausalDiscoveryReport(
        method="fixture",
        graph=graph,
        projection_disposition=graph_projection_disposition(
            graph, None, status=GraphProjectionStatus.IDENTITY
        ),
    )


def _twin_result() -> TwinNetworkResult:
    return TwinNetworkResult(
        outcome_variable="y",
        factual_intervention=InterventionSpec(value=0.0),
        counterfactual_intervention=InterventionSpec(value=1.0),
        po_factual_mean=2.0,
        po_factual_std=1.0,
        po_counter_mean=3.0,
        po_counter_std=1.0,
        ite_mean=1.0,
        ite_std=0.5,
        ite_ci=(0.0, 2.0),
        po_correlation=0.5,
    )


def _write_cases() -> tuple[
    tuple[str, Callable[..., object], Callable[[], object], dict[str, object]], ...
]:
    return (
        ("graph", persist_causal_graph_model, _graph, {"nodes": []}),
        ("query", persist_causal_query_result, _query_result, {"result_std": -1.0}),
        ("scm", persist_structural_causal_model_spec, _scm_spec, {"fit_method": "gcm"}),
        ("twin", persist_twin_network_result, _twin_result, {"po_factual_std": -1.0}),
        ("ensemble", persist_causal_model_ensemble, _ensemble, {"members": []}),
        ("discovery", persist_causal_discovery_report, _discovery_report, {"n_bootstrap": -1}),
    )


def _model_construct_with(model: Any, **updates: object) -> Any:
    payload = {name: getattr(model, name) for name in type(model).model_fields}
    payload.update(updates)
    return type(model).model_construct(**payload)


@pytest.mark.parametrize("bad_override", ["", False, 0])
@pytest.mark.parametrize("field", ["schema_name", "schema_version"])
def test_all_public_family_writers_refuse_malformed_overrides_before_cas(
    tmp_path: Path, bad_override: object, field: str
) -> None:
    for index, (_name, persist, build, _invalid_fields) in enumerate(_write_cases()):
        store = CountingStore(
            ensure_ir_artifact_store(FileSystemCAS(tmp_path / f"{field}-{bad_override!r}-{index}"))
        )
        with pytest.raises(ValueError):
            persist(store, build(), **{field: bad_override})
        assert store.put_calls == 0


@pytest.mark.parametrize("bad_inputs", [False, 0, "", b"", {"not-a-sequence": True}])
def test_all_public_family_writers_refuse_falsey_lineage_before_any_cas(
    tmp_path: Path, bad_inputs: object
) -> None:
    for index, (_name, persist, build, _invalid_fields) in enumerate(_write_cases()):
        store = CountingStore(
            ensure_ir_artifact_store(FileSystemCAS(tmp_path / f"inputs-{bad_inputs!r}-{index}"))
        )
        with pytest.raises(CanonViolation, match="ir_artifact_inputs_invalid"):
            persist(store, build(), inputs=bad_inputs)
        assert store.put_calls == 0


@pytest.mark.parametrize(("name", "persist", "build", "invalid_fields"), _write_cases())
def test_owner_writers_revalidate_constructed_dtos_before_cas(
    tmp_path: Path,
    name: str,
    persist: Callable[..., object],
    build: Callable[[], object],
    invalid_fields: dict[str, object],
) -> None:
    store = CountingStore(ensure_ir_artifact_store(FileSystemCAS(tmp_path / name)))
    invalid = _model_construct_with(build(), **invalid_fields)
    with pytest.raises(ValueError):
        persist(store, invalid)
    assert store.put_calls == 0


@pytest.mark.parametrize("malformation", ["extra", "missing"])
def test_graph_owner_refuses_extra_or_missing_source_fields_before_cas(
    tmp_path: Path, malformation: str
) -> None:
    import polisyos.ir.analytics.causal_graph as graph_module

    payload = _graph().model_dump(mode="json")
    if malformation == "extra":
        payload["unowned_field"] = "must not be dropped"
    else:
        payload.pop("edges")
    store = CountingStore(
        ensure_ir_artifact_store(FileSystemCAS(tmp_path / f"mapping-{malformation}"))
    )
    with pytest.raises(ValueError):
        _put_owned_json_artifact(
            store,
            payload,
            owner=graph_module._CAUSAL_GRAPH_OWNER,
            schema_name="ir.causal_graph_model",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
        )
    assert store.put_calls == 0


def test_discovery_bad_parent_is_rejected_before_sidecar_cas(tmp_path: Path) -> None:
    report = _discovery_report().model_copy(
        update={
            "algebraic_constraints": AlgebraicConstraintReport(
                families_run=[AlgebraicConstraintFamily.CI],
                n_implied_constraints=1,
                implied_constraints_preview=[
                    ImpliedConstraintSpec(
                        constraint_id="ci:x|y|_",
                        family=AlgebraicConstraintFamily.CI,
                        statement="x independent of y",
                        variables=("x", "y"),
                    )
                ],
            )
        }
    )
    invalid = _model_construct_with(report, n_bootstrap=-1)
    store = CountingStore(ensure_ir_artifact_store(FileSystemCAS(tmp_path / "discovery-sidecar")))
    with pytest.raises(ValueError):
        persist_causal_discovery_report(store, invalid)
    assert store.put_calls == 0


@pytest.mark.parametrize("bad_inputs", [False, {"not-a-sequence": True}])
def test_discovery_bad_lineage_is_rejected_before_sidecar_cas(
    tmp_path: Path, bad_inputs: object
) -> None:
    report = _discovery_report().model_copy(
        update={
            "algebraic_constraints": AlgebraicConstraintReport(
                families_run=[AlgebraicConstraintFamily.CI],
                n_implied_constraints=1,
                implied_constraints_preview=[
                    ImpliedConstraintSpec(
                        constraint_id="ci:x|y|_",
                        family=AlgebraicConstraintFamily.CI,
                        statement="x independent of y",
                        variables=("x", "y"),
                    )
                ],
            )
        }
    )
    store = CountingStore(ensure_ir_artifact_store(FileSystemCAS(tmp_path / "bad-sidecar-inputs")))
    with pytest.raises(CanonViolation, match="ir_artifact_inputs_invalid"):
        persist_causal_discovery_report(store, report, inputs=bad_inputs)
    assert store.put_calls == 0


def test_pre_cas_projection_is_required_even_when_owner_markers_remain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    import polisyos.ir.analytics.causal_graph as graph_module

    invalid = _model_construct_with(_graph(), nodes=[])
    store = CountingStore(ensure_ir_artifact_store(FileSystemCAS(tmp_path / "projection-control")))
    with pytest.raises(ValueError):
        persist_causal_graph_model(store, invalid)
    assert store.put_calls == 0

    original_owner = graph_module._CAUSAL_GRAPH_OWNER
    monkeypatch.setattr(
        graph_module,
        "_CAUSAL_GRAPH_OWNER",
        replace(original_owner, project_for_consumer=lambda source, _admission: source),
    )
    # Removal control: identity, registry, kind and profile stay intact, but disabling
    # typed source projection permits malformed producer bytes to be stored.
    mutant_ref = persist_causal_graph_model(store, invalid)
    assert store.put_calls == 1
    monkeypatch.undo()
    fresh = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "projection-control"))
    with pytest.raises(ValueError):
        load_causal_graph_model(fresh, mutant_ref)


def test_actual_cas_nondefault_same_law_unseen_graph_and_generic_rollback(
    tmp_path: Path, isolated_graph_registry: None
) -> None:
    key, owner = "causal_graph_model", "polisyos.ir.analytics.causal_graph.CausalGraphModel"
    version = "1.2"
    register_schema_version(
        key,
        version,
        compatibility=CompatibilityMode.NONE,
        notes=("Test-only extension reuses the admitted graph JSON law.",),
    )
    register_ir_representation(
        registry_key=key,
        owner_ref=owner,
        dto_abi=owner,
        wire_policy_ref="causal-graph-model-json",
        wire_policy_revision="1",
        schema_name="ir.causal_graph_model",
        schema_version=version,
        payload_version="1.0",
        writable=True,
    )
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    graph = _graph()
    ref = persist_causal_graph_model(
        store, graph, schema_version=version, return_selected_profile=True
    )
    assert ref.manifest_profile_sha256
    fresh = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    assert load_causal_graph_model(fresh, ref) == graph
    assert fresh.get_manifest(ref).artifact_schema.version == version
    # An old opaque reader can still inspect and validate the same admitted grammar.
    assert CausalGraphModel.model_validate(get_json_artifact(fresh, ref)) == graph

    # Rollback to the admitted default writer keeps the prior reader route usable.
    rollback_ref = persist_causal_graph_model(store, graph, return_selected_profile=True)
    rollback_reader = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    assert rollback_reader.get_manifest(rollback_ref).artifact_schema.version == "1.0"
    assert load_causal_graph_model(rollback_reader, rollback_ref) == graph

    # A producer cannot self-select an unregistered payload discriminator.
    unknown_graph = graph.model_copy(update={"schema_version": "9.9"})
    with pytest.raises(ValueError, match="ir_owned_artifact_write_override_unregistered"):
        persist_causal_graph_model(store, unknown_graph, schema_version=version)


def test_owner_reader_rejects_wrong_kind_before_bytes_and_removal_control(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    store = ensure_ir_artifact_store(cas)
    graph = _graph()
    wrong_ref = put_json_artifact(
        store,
        graph.model_dump(mode="json"),
        kind="ir.not_causal_graph",
        schema_name="ir.causal_graph_model",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
    )
    counted = CountingStore(ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas")))
    with pytest.raises(ValueError, match="ir_owned_artifact_manifest_identity_mismatch"):
        load_causal_graph_model(counted, wrong_ref)  # type: ignore[arg-type]
    assert counted.payload_reads == 0
    # Removing owner admission while retaining DTO markers would admit this artifact.
    assert CausalGraphModel.model_validate(get_json_artifact(counted, wrong_ref)) == graph
    assert counted.payload_reads == 1


def test_graph_registry_has_one_current_default_and_exact_source_rows() -> None:
    snapshot = get_ir_owner_registry_snapshot()
    rows = [
        r
        for r in snapshot.representation_records
        if r.registry_key == "causal_graph_model"
        and r.owner_ref == "polisyos.ir.analytics.causal_graph.CausalGraphModel"
    ]
    assert len(rows) == 2
    current = [r for r in rows if r.current]
    assert len(current) == 1
    assert (current[0].schema_version, current[0].payload_version, current[0].default_write) == (
        "1.0",
        "1.0",
        True,
    )
    assert all(r.profile_ref is None for r in rows)


def test_twin_owner_current_writer_and_fresh_consumer(tmp_path: Path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "twin-cas"))
    result = TwinNetworkResult(
        outcome_variable="policy_outcome",
        factual_intervention=InterventionSpec(value=0.0),
        counterfactual_intervention=InterventionSpec(value=1.0),
        po_factual_mean=2.0,
        po_factual_std=1.0,
        po_counter_mean=3.0,
        po_counter_std=1.0,
        ite_mean=1.0,
        ite_std=0.0,
        ite_ci=(1.0, 1.0),
        po_correlation=0.5,
    )
    ref = persist_twin_network_result(store, result)
    fresh = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "twin-cas"))
    assert load_twin_network_result(fresh, ref) == result
