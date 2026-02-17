from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from polisyos.foundry.merge_engine import MergeConflictKind
from polisyos.ir.kernel import ConflictResolution, MergeRuleKind

if TYPE_CHECKING:
    from polisyos.core.contracts.foundry import ProgramGraph, ProgramNode
    from polisyos.ir.kernel import MergeRuleRegistry, SlotRegistry


class SlotConflict(BaseModel):
    """Compile-time detected slot conflict with actionable context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slot_id: str = Field(..., description="The conflicting slot identifier")
    writers: frozenset[str] = Field(
        ..., description="Set of mechanism node IDs writing to this slot"
    )
    conflict_kind: MergeConflictKind = Field(
        ..., description="Classification from MergeEngine"
    )
    location: str = Field(..., description="Path in ProgramGraph for diagnostics")
    suggestion: str = Field(..., description="Actionable fix recommendation")
    severity: str = Field(default="blocker", pattern=r"^(blocker|warning|info)$")

    def to_compliance_issue(self) -> dict:
        """Convert to Phase 9 ComplianceIssue-compatible format."""
        return {
            "path": ["program_graph", self.location],
            "message": (
                f"Slot '{self.slot_id}' has {len(self.writers)} concurrent writers: "
                f"{sorted(self.writers)}"
            ),
            "severity": self.severity,
            "suggestion": self.suggestion,
            "code": f"CONFLICT_{self.conflict_kind.value.upper()}",
        }


class ConflictReport(BaseModel):
    """Comprehensive report of compile-time conflict analysis."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    ok: bool = Field(..., description="True if no blockers found")
    conflicts: list[SlotConflict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    statistics: dict[str, int] = Field(default_factory=dict)

    def to_issues(self) -> list[dict]:
        """Convert all conflicts to ComplianceIssue format."""
        return [conflict.to_compliance_issue() for conflict in self.conflicts]

    def has_blockers(self) -> bool:
        """Check if any blocking conflicts exist."""
        return any(conflict.severity == "blocker" for conflict in self.conflicts)


@dataclass
class _WriterInfo:
    """Internal tracking of writers per slot."""

    node_ids: set[str] = field(default_factory=set)
    mechanism_types: set[str] = field(default_factory=set)


class CompileTimeConflictChecker:
    """
    Static analyzer detecting slot conflicts before JAX compilation.

    Runs on ProgramGraph in pure Python. Integrates with existing
    MergeEngine semantics by reusing MergeConflictKind classification.

    Performance: O(n*m) where n=nodes, m=avg slots per node.
    Expected <10ms for typical graphs.
    """

    def __init__(
        self,
        slot_registry: "SlotRegistry",
        merge_registry: "MergeRuleRegistry",
        *,
        strict_mode: bool = True,
    ):
        self._slot_registry = slot_registry
        self._merge_registry = merge_registry
        self._strict_mode = strict_mode

    def check(self, program_graph: "ProgramGraph") -> ConflictReport:
        """
        Analyze ProgramGraph for slot conflicts.

        Args:
            program_graph: Compiled graph from _build_program_graph

        Returns:
            ConflictReport with conflicts and statistics
        """
        slot_writers: dict[str, _WriterInfo] = {}
        mechanism_node_count = 0

        for node in program_graph.nodes:
            if not self._is_mechanism_node(node):
                continue

            mechanism_node_count += 1
            writes = list(getattr(node, "outputs", None) or [])
            mechanism_type = node.mechanism_type or "unknown"

            for slot_id in writes:
                info = slot_writers.setdefault(slot_id, _WriterInfo())
                info.node_ids.add(node.node_id)
                info.mechanism_types.add(mechanism_type)

        conflicts: list[SlotConflict] = []
        warnings: list[str] = []

        for slot_id, info in sorted(slot_writers.items()):
            if len(info.node_ids) <= 1:
                continue

            conflict, warning = self._analyze_multi_writer(slot_id, info)
            if conflict is not None:
                if conflict.severity == "blocker":
                    conflicts.append(conflict)
            if warning:
                warnings.append(warning)

        return ConflictReport(
            ok=len(conflicts) == 0,
            conflicts=conflicts,
            warnings=warnings,
            statistics={
                "total_nodes": len(program_graph.nodes),
                "mechanism_nodes": mechanism_node_count,
                "unique_slots_written": len(slot_writers),
                "multi_writer_slots": sum(
                    1 for info in slot_writers.values() if len(info.node_ids) > 1
                ),
                "conflicts_found": len(conflicts),
            },
        )

    def _is_mechanism_node(self, node: "ProgramNode") -> bool:
        if node.node_kind in {"mechanism", "method"}:
            return True
        if node.node_kind == "op" and node.op and node.op.op_kind in {
            "apply_mechanism",
            "apply_method",
        }:
            return True
        return False

    def _analyze_multi_writer(
        self,
        slot_id: str,
        info: _WriterInfo,
    ) -> tuple[SlotConflict | None, str | None]:
        """Determine if multi-writer scenario is a conflict."""
        slot_spec = self._slot_registry.slots.get(slot_id)
        if slot_spec is None:
            if self._strict_mode:
                return (
                    SlotConflict(
                        slot_id=slot_id,
                        writers=frozenset(info.node_ids),
                        conflict_kind=MergeConflictKind.MISSING_VALUE,
                        location=f"slots.{slot_id}",
                        suggestion=f"Register slot '{slot_id}' in SlotRegistry",
                        severity="blocker",
                    ),
                    None,
                )
            return (
                None,
                f"Slot '{slot_id}' not registered; skipping conflict evaluation",
            )

        rule_ref = slot_spec.merge_rule
        rule_spec = self._merge_registry.rules.get(rule_ref.rule_id)

        if rule_spec is None:
            return (
                SlotConflict(
                    slot_id=slot_id,
                    writers=frozenset(info.node_ids),
                    conflict_kind=MergeConflictKind.UNSUPPORTED_RULE,
                    location=f"slots.{slot_id}.merge_rule",
                    suggestion=(
                        f"Register merge rule '{rule_ref.rule_id}' in MergeRuleRegistry"
                    ),
                    severity="blocker",
                ),
                None,
            )

        if rule_spec.kind == MergeRuleKind.ERROR:
            resolution = rule_spec.conflict_resolution
            override = slot_spec.merge_override
            if override and override.conflict_resolution:
                resolution = override.conflict_resolution

            if resolution == ConflictResolution.ERROR:
                return (
                    SlotConflict(
                        slot_id=slot_id,
                        writers=frozenset(info.node_ids),
                        conflict_kind=MergeConflictKind.MULTIPLE_WRITERS,
                        location=f"slots.{slot_id}",
                        suggestion=self._generate_suggestion(slot_id, info),
                        severity="blocker",
                    ),
                    None,
                )
            return (
                None,
                f"Slot '{slot_id}' has multiple writers with ERROR rule "
                "but conflict_resolution allows it (verify intent)",
            )

        if rule_spec.kind in {MergeRuleKind.SUM, MergeRuleKind.OVERRIDE, MergeRuleKind.PRIORITY}:
            return (
                None,
                f"Slot '{slot_id}' has {len(info.node_ids)} writers with "
                "merge rule allowing this (verify intent)",
            )

        return (
            SlotConflict(
                slot_id=slot_id,
                writers=frozenset(info.node_ids),
                conflict_kind=MergeConflictKind.UNSUPPORTED_RULE,
                location=f"slots.{slot_id}.merge_rule",
                suggestion=(
                    f"Unsupported merge rule '{rule_spec.kind}' for slot '{slot_id}'"
                ),
                severity="blocker",
            ),
            None,
        )

    def _generate_suggestion(self, slot_id: str, info: _WriterInfo) -> str:
        writers_list = ", ".join(sorted(info.node_ids))
        suggestions = [
            f"Slot '{slot_id}' has multiple writers: [{writers_list}].",
            "Options to resolve:",
            "1. Change merge_rule to 'sum' if values should be aggregated",
            "2. Change merge_rule to 'priority' and assign priorities to mechanisms",
            "3. Ensure only one mechanism writes to this slot per time step",
            "4. Add slot-level merge_override with conflict_resolution='first' or 'last'",
        ]
        return " ".join(suggestions)


def create_conflict_checker(
    slot_registry: "SlotRegistry",
    merge_registry: "MergeRuleRegistry",
    *,
    strict_mode: bool = True,
) -> CompileTimeConflictChecker:
    """Factory function for ConflictChecker creation."""
    return CompileTimeConflictChecker(
        slot_registry=slot_registry,
        merge_registry=merge_registry,
        strict_mode=strict_mode,
    )
