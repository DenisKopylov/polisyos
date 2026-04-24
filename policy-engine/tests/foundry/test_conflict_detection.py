"""Tests for compile-time conflict detection."""

from __future__ import annotations

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import (
    ProgramGraph,
    ProgramNode,
    ProgramOp,
)
from polisyos.foundry.conflict_checker import (
    CompileTimeConflictChecker,
    ConflictReport,
    SlotConflict,
)
from polisyos.foundry.merge_engine import MergeConflictKind
from polisyos.ir.kernel import (
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    MergeRuleRef,
    SlotKind,
    SlotRegistry,
    SlotScope,
    SlotSpec,
    SlotValueType,
)


def _make_ir_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("0" * 64),
        kind="ir.trinity_bundle",
        media_type="application/json",
    )


def _make_mechanism_node(
    node_id: str,
    mechanism_type: str,
    outputs: list[str],
) -> ProgramNode:
    return ProgramNode(
        node_id=node_id,
        node_kind="op",
        mechanism_type=mechanism_type,
        op=ProgramOp(op_kind="apply_mechanism"),
        outputs=outputs,
    )


class TestConflictDetectionBasics:
    def test_single_writer_no_conflict(self) -> None:
        graph = ProgramGraph(
            ir_ref=_make_ir_ref(),
            nodes=[
                _make_mechanism_node("mech_a", "income_tax", ["agents.tax_paid"]),
                _make_mechanism_node("mech_b", "ubi", ["agents.transfer"]),
            ],
            edges=[],
            entrypoints=["mech_a"],
        )

        checker = CompileTimeConflictChecker(
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        )

        report = checker.check(graph)

        assert report.ok is True
        assert len(report.conflicts) == 0
        assert report.statistics["conflicts_found"] == 0

    def test_multi_writer_error_rule_conflict(self) -> None:
        slot_registry = SlotRegistry(
            slots={
                "test.gdp": SlotSpec(
                    slot_id="test.gdp",
                    scope=SlotScope.GLOBAL,
                    value_type=SlotValueType.DECIMAL,
                    kind=SlotKind.STOCK,
                    merge_rule=MergeRuleRef(rule_id="error"),
                )
            }
        )

        graph = ProgramGraph(
            ir_ref=_make_ir_ref(),
            nodes=[
                _make_mechanism_node("mech_a", "gdp_calc_v1", ["test.gdp"]),
                _make_mechanism_node("mech_b", "gdp_calc_v2", ["test.gdp"]),
            ],
            edges=[],
            entrypoints=["mech_a"],
        )

        checker = CompileTimeConflictChecker(
            slot_registry=slot_registry,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        )

        report = checker.check(graph)

        assert report.ok is False
        assert len(report.conflicts) == 1

        conflict = report.conflicts[0]
        assert conflict.slot_id == "test.gdp"
        assert conflict.conflict_kind == MergeConflictKind.MULTIPLE_WRITERS
        assert "mech_a" in conflict.writers
        assert "mech_b" in conflict.writers
        assert conflict.severity == "blocker"

    def test_multi_writer_sum_rule_allowed(self) -> None:
        graph = ProgramGraph(
            ir_ref=_make_ir_ref(),
            nodes=[
                _make_mechanism_node("mech_a", "wage_income", ["agents.income"]),
                _make_mechanism_node("mech_b", "capital_income", ["agents.income"]),
            ],
            edges=[],
            entrypoints=["mech_a"],
        )

        checker = CompileTimeConflictChecker(
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        )

        report = checker.check(graph)

        assert report.ok is True
        assert len(report.conflicts) == 0
        assert len(report.warnings) > 0 or report.statistics["multi_writer_slots"] > 0


class TestConflictDetectionEdgeCases:
    def test_empty_graph(self) -> None:
        graph = ProgramGraph(ir_ref=_make_ir_ref(), nodes=[], edges=[], entrypoints=[])

        checker = CompileTimeConflictChecker(
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        )

        report = checker.check(graph)

        assert report.ok is True
        assert report.statistics["mechanism_nodes"] == 0

    def test_non_mechanism_nodes_ignored(self) -> None:
        graph = ProgramGraph(
            ir_ref=_make_ir_ref(),
            nodes=[
                ProgramNode(
                    node_id="merge_state",
                    node_kind="op",
                    op=ProgramOp(op_kind="merge_state"),
                )
            ],
            edges=[],
            entrypoints=[],
        )

        checker = CompileTimeConflictChecker(
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        )

        report = checker.check(graph)

        assert report.ok is True
        assert report.statistics["mechanism_nodes"] == 0

    def test_unknown_slot_strict_mode(self) -> None:
        graph = ProgramGraph(
            ir_ref=_make_ir_ref(),
            nodes=[
                _make_mechanism_node("mech_a", "test", ["nonexistent.slot"]),
                _make_mechanism_node("mech_b", "test", ["nonexistent.slot"]),
            ],
            edges=[],
            entrypoints=["mech_a"],
        )

        checker = CompileTimeConflictChecker(
            slot_registry=SlotRegistry(slots={}),
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            strict_mode=True,
        )

        report = checker.check(graph)

        assert report.ok is False
        assert any(
            conflict.conflict_kind == MergeConflictKind.MISSING_VALUE
            for conflict in report.conflicts
        )


class TestConflictReportConversion:
    def test_to_issues_format(self) -> None:
        conflict = SlotConflict(
            slot_id="test.slot",
            writers=frozenset({"a", "b"}),
            conflict_kind=MergeConflictKind.MULTIPLE_WRITERS,
            location="slots.test.slot",
            suggestion="Fix it",
            severity="blocker",
        )

        report = ConflictReport(ok=False, conflicts=[conflict])

        issues = report.to_issues()

        assert len(issues) == 1
        assert issues[0]["severity"] == "blocker"
        assert "test.slot" in issues[0]["message"]
        assert issues[0]["path"] == ["program_graph", "slots.test.slot"]
