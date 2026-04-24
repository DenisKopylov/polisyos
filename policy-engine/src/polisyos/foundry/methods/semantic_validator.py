"""
Cross-method semantic validator for compiled method chains.

``CrossMethodValidator.validate_chain()`` inspects a ``CompiledMethodChain``
and reports issues that individual slot-level checks cannot catch:

1. **Semantic slot compatibility** — uses ``slot_schema.is_semantically_compatible``
   to flag data-flow edges where source and target slot semantics are
   mismatched (e.g., connecting a ``"treatment_effect"`` slot to an
   ``"outcome"`` input).

2. **Tag-based ordering rules** — domain conventions encoded as
   ``_ORDERING_RULES``.  Example: a ``sensitivity`` method should appear
   *after* at least one ``causal`` or ``estimation`` method in the chain.

3. **Conflict detection** — methods that declare ``conflicts_with`` should
   not appear in the same chain (already partially checked by composer, but
   repeated here for the full FQN list).

4. **Isolation rules** — certain method pairs are flagged when they share a
   data-flow edge but belong to domains that should not be directly connected
   (e.g., ``spatial`` → ``causal`` without an intermediate normalisation step).

Usage::

    from polisyos.foundry.methods.semantic_validator import CrossMethodValidator

    validator = CrossMethodValidator()
    report = validator.validate_chain(compiled_chain)
    if report.errors:
        raise ValueError(report.summary())
    for w in report.warnings:
        print("Warning:", w)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from polisyos.foundry.methods.slot_schema import is_semantically_compatible

if TYPE_CHECKING:
    from polisyos.foundry.methods.composer import CompiledMethodChain

__all__ = [
    "CrossMethodValidator",
    "ValidationIssue",
    "ValidationReport",
]


# ---------------------------------------------------------------------------
# Issue data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation finding."""

    severity: str  # "error" | "warning"
    category: str  # "semantic_slot" | "ordering" | "conflict" | "isolation"
    message: str
    source_fqn: str = ""
    target_fqn: str = ""


@dataclass
class ValidationReport:
    """Aggregated result of ``CrossMethodValidator.validate_chain()``."""

    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = [f"ValidationReport: {len(self.errors)} error(s), {len(self.warnings)} warning(s)"]
        for issue in self.issues:
            prefix = "ERROR" if issue.severity == "error" else "WARNING"
            lines.append(f"  [{prefix}][{issue.category}] {issue.message}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"<ValidationReport errors={len(self.errors)} warnings={len(self.warnings)}>"


# ---------------------------------------------------------------------------
# Tag-based ordering rules
# ---------------------------------------------------------------------------
# Each rule is a tuple (prerequisite_tags, dependent_tags, message).
# If any method with a dependent_tag is in the chain, at least one method
# with a prerequisite_tag must appear *before* it in execution order.

_ORDERING_RULES: list[tuple[frozenset[str], frozenset[str], str]] = [
    (
        frozenset({"causal", "estimation", "iv", "did", "rdd"}),
        frozenset({"sensitivity", "refutation"}),
        "Sensitivity/refutation methods should follow a causal estimation step.",
    ),
    (
        frozenset({"estimation", "regression", "causal"}),
        frozenset({"welfare", "welfare_analysis"}),
        "Welfare analysis methods should follow an estimation step.",
    ),
    (
        frozenset({"first_stage", "iv"}),
        frozenset({"ivqreg", "local_iv"}),
        "IV quantile regression requires a first-stage IV estimation.",
    ),
    (
        frozenset({"normalisation", "preprocessing"}),
        frozenset({"spatial", "gwr", "moran"}),
        "Spatial methods should be preceded by a normalisation/preprocessing step "
        "when receiving tabular inputs.",
    ),
]

# ---------------------------------------------------------------------------
# Isolation rules — tag pairs that should NOT share a direct data-flow edge.
# ---------------------------------------------------------------------------
# Each entry is (source_tags, target_tags, message).

_ISOLATION_RULES: list[tuple[frozenset[str], frozenset[str], str]] = [
    (
        frozenset({"spatial", "gwr"}),
        frozenset({"causal", "did", "iv"}),
        "Spatial method output should not feed directly into a causal estimator "
        "without an intermediate normalisation or aggregation step.",
    ),
    (
        frozenset({"simulation", "abm", "microsim"}),
        frozenset({"causal", "identification"}),
        "Simulation outputs should not feed directly into causal identification "
        "methods — simulated data violates SUTVA.",
    ),
]


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class CrossMethodValidator:
    """
    Validates a compiled method chain for cross-method semantic issues.

    Parameters
    ----------
    strict:
        If True, ordering-rule violations are upgraded to errors.
        Default False (ordering issues are warnings).
    """

    def __init__(self, strict: bool = False) -> None:
        self._strict = strict

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_chain(self, chain: CompiledMethodChain) -> ValidationReport:
        """
        Run all validation passes on *chain*.

        Parameters
        ----------
        chain:
            A compiled chain produced by ``MethodComposer.build()``.

        Returns
        -------
        ValidationReport
            Contains all errors and warnings found.  Never raises.
        """
        report = ValidationReport()
        self._check_semantic_slots(chain, report)
        self._check_ordering_rules(chain, report)
        self._check_conflicts(chain, report)
        self._check_isolation_rules(chain, report)
        return report

    # ------------------------------------------------------------------
    # Pass 1: Semantic slot compatibility along data-flow edges
    # ------------------------------------------------------------------

    def _check_semantic_slots(self, chain: CompiledMethodChain, report: ValidationReport) -> None:
        """Flag edges where slot semantics are mismatched."""
        for binding in chain.bindings:
            source_slot = binding.source_slot
            target_slot = binding.target_slot
            source_fqn = binding.source_method
            target_fqn = binding.target_method

            if source_slot == target_slot:
                # Same name → always semantically compatible.
                continue

            if not is_semantically_compatible(source_slot, target_slot):
                report.issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="semantic_slot",
                        message=(
                            f"Slot '{source_slot}' (from {source_fqn}) connected to "
                            f"'{target_slot}' (in {target_fqn}): "
                            "semantic schemas are incompatible — check that you are "
                            "not mixing unrelated slot types."
                        ),
                        source_fqn=source_fqn,
                        target_fqn=target_fqn,
                    )
                )

    # ------------------------------------------------------------------
    # Pass 2: Tag-based ordering rules
    # ------------------------------------------------------------------

    def _check_ordering_rules(self, chain: CompiledMethodChain, report: ValidationReport) -> None:
        """Verify that ordering prerequisites are satisfied."""
        # Build tag → set[node_id] and ordered list of (node_id, fqn, tags).
        ordered_nodes: list[tuple[str, frozenset[str]]] = []  # (fqn, tags)
        fqn_to_tags: dict[str, frozenset[str]] = {}

        for node_id in chain.execution_order:
            sig = chain.signatures[node_id]
            # Tags can be stored in metadata; we only have the signature here.
            # Use family and name as proxy for tags.
            tags: frozenset[str] = frozenset()
            # Check if metadata is available through the chain (not always stored).
            # We rely on the sig.family and sig.variant as rough tag proxies.
            tag_sources = set()
            if sig.family:
                tag_sources.add(sig.family.lower())
            if sig.variant:
                tag_sources.add(sig.variant.lower())
            # Also check data_modalities
            for dm in sig.data_modalities:
                tag_sources.add(dm.lower())
            tags = frozenset(tag_sources)
            fqn_to_tags[sig.fqn] = tags
            ordered_nodes.append((sig.fqn, tags))

        severity = "error" if self._strict else "warning"

        for prereq_tags, dep_tags, message in _ORDERING_RULES:
            # Find all dependent methods in the chain.
            dependent_fqns = [fqn for fqn, tags in ordered_nodes if tags & dep_tags]
            if not dependent_fqns:
                continue  # Rule not triggered.

            # Find all prerequisite methods.
            prereq_fqns = [fqn for fqn, tags in ordered_nodes if tags & prereq_tags]
            if not prereq_fqns:
                # No prerequisite exists at all.
                for dep_fqn in dependent_fqns:
                    report.issues.append(
                        ValidationIssue(
                            severity=severity,
                            category="ordering",
                            message=f"{dep_fqn}: {message}",
                            target_fqn=dep_fqn,
                        )
                    )
                continue

            # Check ordering: for each dependent, at least one prereq must precede it.
            fqn_order_index = {fqn: i for i, (fqn, _) in enumerate(ordered_nodes)}
            for dep_fqn in dependent_fqns:
                dep_idx = fqn_order_index.get(dep_fqn, 0)
                any_prereq_before = any(
                    fqn_order_index.get(p_fqn, dep_idx + 1) < dep_idx for p_fqn in prereq_fqns
                )
                if not any_prereq_before:
                    report.issues.append(
                        ValidationIssue(
                            severity=severity,
                            category="ordering",
                            message=(
                                f"{dep_fqn}: {message} "
                                f"(prerequisite methods found: "
                                f"{', '.join(prereq_fqns[:3])}{'...' if len(prereq_fqns) > 3 else ''}, "
                                f"but none precede it in execution order)"
                            ),
                            target_fqn=dep_fqn,
                        )
                    )

    # ------------------------------------------------------------------
    # Pass 3: conflicts_with declarations
    # ------------------------------------------------------------------

    def _check_conflicts(self, chain: CompiledMethodChain, report: ValidationReport) -> None:
        """Flag methods in the chain that conflict with each other."""
        all_fqns = {chain.signatures[nid].fqn for nid in chain.execution_order}
        seen_conflicts: set[tuple[str, str]] = set()

        for node_id in chain.execution_order:
            sig = chain.signatures[node_id]
            for conflict_fqn in sig.conflicts_with:
                if conflict_fqn in all_fqns:
                    pair = tuple(sorted([sig.fqn, conflict_fqn]))
                    if pair not in seen_conflicts:
                        seen_conflicts.add(pair)  # type: ignore[arg-type]
                        report.issues.append(
                            ValidationIssue(
                                severity="error",
                                category="conflict",
                                message=(
                                    f"'{sig.fqn}' declares a conflict with '{conflict_fqn}', "
                                    "but both are present in the same chain."
                                ),
                                source_fqn=sig.fqn,
                                target_fqn=conflict_fqn,
                            )
                        )

    # ------------------------------------------------------------------
    # Pass 4: Isolation rules (certain cross-domain edges are flagged)
    # ------------------------------------------------------------------

    def _check_isolation_rules(self, chain: CompiledMethodChain, report: ValidationReport) -> None:
        """Flag data-flow edges that violate domain isolation rules."""
        fqn_to_tags: dict[str, frozenset[str]] = {}
        for node_id in chain.execution_order:
            sig = chain.signatures[node_id]
            tags: set[str] = set()
            if sig.family:
                tags.add(sig.family.lower())
            if sig.variant:
                tags.add(sig.variant.lower())
            for dm in sig.data_modalities:
                tags.add(dm.lower())
            fqn_to_tags[sig.fqn] = frozenset(tags)

        for source_tags, target_tags, message in _ISOLATION_RULES:
            # Check each data-flow edge in the chain.
            for binding in chain.bindings:
                src_tags = fqn_to_tags.get(binding.source_method, frozenset())
                tgt_tags = fqn_to_tags.get(binding.target_method, frozenset())
                if src_tags & source_tags and tgt_tags & target_tags:
                    report.issues.append(
                        ValidationIssue(
                            severity="warning",
                            category="isolation",
                            message=(
                                f"Direct edge from '{binding.source_method}' → "
                                f"'{binding.target_method}': {message}"
                            ),
                            source_fqn=binding.source_method,
                            target_fqn=binding.target_method,
                        )
                    )
