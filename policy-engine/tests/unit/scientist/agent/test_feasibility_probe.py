from __future__ import annotations

import asyncio

import pytest

jax = pytest.importorskip("jax")
import jax.numpy as jnp
from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.scientist.agent.feasibility import StateSnapshotFeasibilityProbe


def run(coro):
    return asyncio.run(coro)


def _build_data_snapshot_ref(cas: FileSystemCAS) -> str:
    state = GlobalState.empty(n_agents=5, seed=42)
    state = state.replace(
        agents=state.agents.replace(
            income=jnp.array([100.0, 500.0, 1200.0, 1800.0, 2500.0], dtype=jnp.float32),
            active=jnp.array([True, True, True, True, True], dtype=jnp.bool_),
        )
    )

    state_snapshot_ref = put_state_snapshot(cas, state=state, step=0)
    data_snapshot = DataSnapshot(data_ref=state_snapshot_ref)
    data_snapshot_ref = cas.put_json(
        data_snapshot.model_dump(mode="json"),
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    return str(data_snapshot_ref.artifact_id)


def _tamper_snapshot_lineage(cas: FileSystemCAS, data_snapshot_ref: str) -> None:
    data_snapshot = DataSnapshot.model_validate(
        from_canonical_bytes(cas.get_bytes(ArtifactID.model_validate(data_snapshot_ref)))
    )
    snapshot_ref = data_snapshot.data_ref
    manifest = cas.get_manifest(snapshot_ref.artifact_id)
    _blob_path, manifest_path = cas._paths(snapshot_ref.artifact_id)
    manifest_path.write_bytes(
        ManifestLifecycle.to_bytes(
            manifest.model_copy(
                update={
                    "inputs": [
                        InputRef(
                            artifact_id=ArtifactID.from_sha256_hex("a" * 64),
                            role="tampered_context",
                        ),
                        *manifest.inputs[1:],
                    ]
                }
            )
        )
    )


def test_state_snapshot_probe_counts_matching_agents(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    data_snapshot_ref = _build_data_snapshot_ref(cas)

    probe = StateSnapshotFeasibilityProbe(cas)
    selector = SelectorPredicate(
        field="income",
        operator=SelectorOperator.LESS_THAN,
        value="1000",
    )

    result = run(
        probe.count_matching_agents(
            selector_expr=selector,
            data_snapshot_ref=data_snapshot_ref,
        )
    )

    assert result.matching_count == 2
    assert result.total_count == 5
    assert 0.39 <= result.match_ratio <= 0.41


def test_state_snapshot_probe_attribute_and_budget_checks(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    data_snapshot_ref = _build_data_snapshot_ref(cas)

    probe = StateSnapshotFeasibilityProbe(cas)
    selector = SelectorPredicate(
        field="income",
        operator=SelectorOperator.GREATER_EQUAL,
        value="1200",
    )

    has_income = run(
        probe.check_attribute_exists(
            attribute_name="income",
            data_snapshot_ref=data_snapshot_ref,
        )
    )
    has_unknown = run(
        probe.check_attribute_exists(
            attribute_name="unknown_field",
            data_snapshot_ref=data_snapshot_ref,
        )
    )
    budget = run(
        probe.estimate_budget_impact(
            selector_expr=selector,
            amount_per_agent=100.0,
            data_snapshot_ref=data_snapshot_ref,
            budget_limit=250.0,
        )
    )

    assert has_income is True
    assert has_unknown is False
    assert budget.matching_count == 3
    assert budget.estimated_total_cost == 300.0
    assert budget.feasible is False


def test_state_snapshot_probe_does_not_raw_fallback_on_2_1_lineage_failure(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    data_snapshot_ref = _build_data_snapshot_ref(cas)
    _tamper_snapshot_lineage(cas, data_snapshot_ref)

    probe = StateSnapshotFeasibilityProbe(cas)
    selector = SelectorPredicate(
        field="income",
        operator=SelectorOperator.LESS_THAN,
        value="1000",
    )

    result = run(
        probe.count_matching_agents(
            selector_expr=selector,
            data_snapshot_ref=data_snapshot_ref,
        )
    )

    assert result.matching_count == -1
    assert result.total_count == -1
    assert "lineage" in result.query_description
