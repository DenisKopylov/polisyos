from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import ProgramGraph, ProgramNode
from polisyos.foundry.mechanisms.treasury import build_treasury_plan, stable_hash


def _dummy_ir_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("0" * 64),
        kind="ir.trinity_bundle",
        media_type="application/json",
    )


def test_stable_hash_is_deterministic_and_distinguishes_values() -> None:
    assert stable_hash("income_tax") == stable_hash("income_tax")
    assert stable_hash("income_tax") != stable_hash("labor_market")


def test_build_treasury_plan_populates_node_and_stream_salts() -> None:
    graph = ProgramGraph(
        ir_ref=_dummy_ir_ref(),
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

    plan = build_treasury_plan(graph, root_seed=17)

    assert plan.root_seed == 17
    assert plan.schema_version == "1.0"
    assert plan.node_salts["tax"] != stable_hash("tax")
    assert plan.node_salts["labor"] != stable_hash("labor")
    assert plan.stream_salts["default"] != stable_hash("default")
    assert any("reproducible execution streams" in note for note in plan.notes)


def test_build_treasury_plan_zero_seed_preserves_historical_salts() -> None:
    graph = ProgramGraph(
        ir_ref=_dummy_ir_ref(),
        nodes=[
            ProgramNode(
                node_id="tax",
                node_kind="mechanism",
                mechanism_type="income_tax",
            ),
        ],
        edges=[],
        entrypoints=["tax"],
    )

    plan = build_treasury_plan(graph, root_seed=0)

    assert plan.node_salts == {"tax": stable_hash("node:tax")}
    assert plan.stream_salts["default"] == stable_hash("stream:default")


def test_build_treasury_plan_root_seed_changes_salts() -> None:
    graph = ProgramGraph(
        ir_ref=_dummy_ir_ref(),
        nodes=[
            ProgramNode(
                node_id="tax",
                node_kind="mechanism",
                mechanism_type="income_tax",
            ),
        ],
        edges=[],
        entrypoints=["tax"],
    )

    low_seed = build_treasury_plan(graph, root_seed=1)
    high_seed = build_treasury_plan(graph, root_seed=2)

    assert low_seed.node_salts["tax"] != high_seed.node_salts["tax"]
    assert low_seed.stream_salts["default"] != high_seed.stream_salts["default"]
