from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_discovery import (
    _DISCOVERY_OWNER,
    _IMPLIED_OWNER,
    AlgebraicConstraintFamily,
    AlgebraicConstraintReport,
    CausalDiscoveryReport,
    ConstraintEvaluationResult,
    ImpliedConstraintSpec,
    load_causal_discovery_report,
    persist_causal_discovery_report,
)
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel,
    GraphProjectionStatus,
    GraphType,
    graph_projection_disposition,
)
from polisyos.ir.artifacts.io import _put_owned_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation


class CountingStore:
    """Count real CAS writes while forwarding the owned JSON boundary."""

    def __init__(self, wrapped: object) -> None:
        self.wrapped = wrapped
        self.put_calls = 0

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


def _report_with_both_sidecars() -> CausalDiscoveryReport:
    graph = CausalGraphModel(graph_type=GraphType.DAG, nodes=["x"], edges=[])
    implied = ImpliedConstraintSpec(
        constraint_id="ci:x|y|_",
        family=AlgebraicConstraintFamily.CI,
        statement="x independent of y",
        variables=("x", "y"),
    )
    violated = ConstraintEvaluationResult(
        constraint_id="ci:x|y|_",
        family=AlgebraicConstraintFamily.CI,
        status="violated",
    )
    return CausalDiscoveryReport(
        method="fixture",
        graph=graph,
        projection_disposition=graph_projection_disposition(
            graph, None, status=GraphProjectionStatus.IDENTITY
        ),
        algebraic_constraints=AlgebraicConstraintReport(
            families_run=[AlgebraicConstraintFamily.CI],
            n_implied_constraints=1,
            n_violated_constraints=1,
            implied_constraints_preview=[implied],
            violated_constraints_preview=[violated],
        ),
    )


def test_discovery_array_sidecars_roundtrip_through_fresh_cas(tmp_path: Path) -> None:
    root = tmp_path / "cas"
    writer = ensure_ir_artifact_store(FileSystemCAS(root))
    source = _report_with_both_sidecars()

    ref = persist_causal_discovery_report(writer, source)
    fresh_reader = ensure_ir_artifact_store(FileSystemCAS(root))
    loaded = load_causal_discovery_report(fresh_reader, ref)

    assert fresh_reader is not writer
    assert loaded.algebraic_constraints is not None
    assert loaded.algebraic_constraints.implied_constraints_ref is not None
    assert loaded.algebraic_constraints.violated_constraints_ref is not None
    assert loaded.algebraic_constraints.implied_constraints_preview == (
        source.algebraic_constraints.implied_constraints_preview
    )
    assert loaded.algebraic_constraints.violated_constraints_preview == (
        source.algebraic_constraints.violated_constraints_preview
    )


def test_object_owner_refuses_array_root_before_cas_write(tmp_path: Path) -> None:
    store = CountingStore(ensure_ir_artifact_store(FileSystemCAS(tmp_path / "object-owner-array")))

    with pytest.raises(CanonViolation, match="ir_owned_artifact_payload_version_invalid"):
        _put_owned_json_artifact(
            store,
            [{"schema_version": "1.1"}],
            owner=_DISCOVERY_OWNER,
            canon_spec=CanonSpec(forbid_floats=False),
        )

    assert store.put_calls == 0


def test_opaque_root_is_not_admitted_as_canonical_json(tmp_path: Path) -> None:
    store = CountingStore(ensure_ir_artifact_store(FileSystemCAS(tmp_path / "opaque-root")))

    with pytest.raises(CanonViolation):
        _put_owned_json_artifact(
            store,
            object(),
            owner=_IMPLIED_OWNER,
            canon_spec=CanonSpec(forbid_floats=False),
        )

    assert store.put_calls == 0


def test_array_owner_callback_mutation_is_refused_before_cas_write(tmp_path: Path) -> None:
    def mutate_array(payload: object) -> None:
        assert type(payload) is list
        payload.append({"extra": "mutation"})

    owner = replace(_IMPLIED_OWNER, payload_version_of=mutate_array)
    store = CountingStore(
        ensure_ir_artifact_store(FileSystemCAS(tmp_path / "array-owner-mutation"))
    )

    with pytest.raises(
        CanonViolation,
        match="ir_owned_artifact_payload_version_input_mutated",
    ):
        _put_owned_json_artifact(
            store,
            [{"constraint_id": "ci:x|y|_"}],
            owner=owner,
            canon_spec=CanonSpec(forbid_floats=False),
        )

    assert store.put_calls == 0
