from __future__ import annotations

import importlib

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.contracts.foundry import ProgramGraph, ProgramNode


def _program_graph() -> ProgramGraph:
    ir_ref = ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("0" * 64),
        kind="ir.trinity_bundle",
        media_type="application/json",
    )
    return ProgramGraph(
        ir_ref=ir_ref,
        nodes=[
            ProgramNode(
                node_id="tax",
                node_kind="mechanism",
                mechanism_type="income_tax",
            ),
            ProgramNode(
                node_id="labor",
                node_kind="mechanism",
                mechanism_type="labor_market",
            ),
        ],
        edges=[],
        entrypoints=["tax"],
    )


def _canonical_randomization_module():
    try:
        return importlib.import_module("polisyos.foundry.compile.randomization")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "canonical randomization owner is missing: " + str(exc),
            pytrace=False,
        )


def test_randomization_owner_preserves_treasury_plan_bytes_and_seed_laws() -> None:
    """The relocated builder must preserve historical plan bytes and seed behavior."""
    randomization = _canonical_randomization_module()
    legacy = importlib.import_module("polisyos.foundry.mechanisms.treasury")
    graph = _program_graph()

    for seed in (0, 17):
        canonical_plan = randomization.build_treasury_plan(graph, root_seed=seed)
        legacy_plan = legacy.build_treasury_plan(graph, root_seed=seed)
        assert to_canonical_bytes(canonical_plan) == to_canonical_bytes(legacy_plan)

    zero_plan = randomization.build_treasury_plan(graph, root_seed=0)
    seeded_plan = randomization.build_treasury_plan(graph, root_seed=17)
    repeated_plan = randomization.build_treasury_plan(graph, root_seed=17)
    reordered_graph = graph.model_copy(update={"nodes": list(reversed(graph.nodes))})
    reordered_plan = randomization.build_treasury_plan(reordered_graph, root_seed=17)

    assert zero_plan.node_salts["tax"] == randomization.stable_hash("node:tax")
    assert zero_plan.stream_salts["default"] == randomization.stable_hash("stream:default")
    assert seeded_plan.node_salts["tax"] != zero_plan.node_salts["tax"]
    assert seeded_plan.stream_salts["default"] != zero_plan.stream_salts["default"]
    assert to_canonical_bytes(seeded_plan) == to_canonical_bytes(repeated_plan)
    assert to_canonical_bytes(seeded_plan) == to_canonical_bytes(reordered_plan)
