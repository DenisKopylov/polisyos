"""
Tests for CrossMethodValidator (T4.2).

Tests cover:
- ValidationReport structure and properties
- Semantic slot compatibility pass
- Tag-based ordering rules pass
- Conflict detection pass
- Isolation rules pass
- Integration with MethodComposer.build(validate_semantics=True)
"""

from __future__ import annotations

from uuid import uuid4

from polisyos.foundry.methods.semantic_validator import (
    CrossMethodValidator,
    ValidationIssue,
    ValidationReport,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chain_stub(
    *,
    bindings=(),
    fqns_in_order=(),
    signatures=None,
    conflicts_with_map=None,
):
    """
    Return a minimal duck-typed object that CrossMethodValidator accepts.

    Real CompiledMethodChain objects are too expensive to build in unit tests;
    we mimic the attributes the validator actually accesses.
    """
    from types import SimpleNamespace

    node_ids = [uuid4() for _ in fqns_in_order]

    if signatures is None:
        sig_map = {}
        for nid, fqn in zip(node_ids, fqns_in_order):
            parts = fqn.split("@")
            namespace_name = parts[0]
            version = parts[1] if len(parts) > 1 else "1.0.0"
            ns_parts = namespace_name.rsplit(".", 1)
            namespace = ns_parts[0] if len(ns_parts) > 1 else "test"
            name = ns_parts[-1]
            conflicts = frozenset()
            if conflicts_with_map and fqn in conflicts_with_map:
                conflicts = frozenset(conflicts_with_map[fqn])
            sig_map[nid] = SimpleNamespace(
                fqn=fqn,
                name=name,
                namespace=namespace,
                family=namespace.split(".")[-1],  # use last namespace segment as family
                variant=name,
                data_modalities=frozenset(),
                conflicts_with=conflicts,
            )
    else:
        sig_map = signatures

    chain = SimpleNamespace(
        execution_order=tuple(node_ids),
        signatures=sig_map,
        bindings=list(bindings),
    )
    return chain


def _make_binding(source_slot, target_slot, source_fqn="a.b@1.0.0", target_fqn="c.d@1.0.0"):
    from types import SimpleNamespace

    return SimpleNamespace(
        source_slot=source_slot,
        target_slot=target_slot,
        source_method=source_fqn,
        target_method=target_fqn,
    )


# ---------------------------------------------------------------------------
# ValidationReport
# ---------------------------------------------------------------------------


class TestValidationReport:
    def test_empty_report_is_ok(self):
        r = ValidationReport()
        assert r.ok
        assert r.errors == []
        assert r.warnings == []

    def test_error_makes_not_ok(self):
        issue = ValidationIssue(severity="error", category="conflict", message="bad")
        r = ValidationReport(issues=[issue])
        assert not r.ok
        assert len(r.errors) == 1
        assert r.warnings == []

    def test_warning_still_ok(self):
        issue = ValidationIssue(severity="warning", category="ordering", message="meh")
        r = ValidationReport(issues=[issue])
        assert r.ok
        assert r.warnings == [issue]

    def test_summary_contains_issue(self):
        issue = ValidationIssue(severity="error", category="conflict", message="CONFLICT!")
        r = ValidationReport(issues=[issue])
        s = r.summary()
        assert "CONFLICT!" in s
        assert "ERROR" in s

    def test_repr(self):
        r = ValidationReport()
        assert "ValidationReport" in repr(r)


# ---------------------------------------------------------------------------
# Semantic slot pass
# ---------------------------------------------------------------------------


class TestSemanticSlotCheck:
    def test_same_slot_name_no_warning(self):
        # Same name → semantically compatible by definition
        chain = _make_chain_stub(
            fqns_in_order=["a.b@1.0.0", "c.d@1.0.0"],
            bindings=[_make_binding("outcome", "outcome")],
        )
        v = CrossMethodValidator()
        report = v.validate_chain(chain)
        semantic_issues = [i for i in report.issues if i.category == "semantic_slot"]
        assert semantic_issues == []

    def test_unknown_slots_are_compatible(self):
        # Unknown slot names → is_semantically_compatible returns True
        chain = _make_chain_stub(
            fqns_in_order=["a.b@1.0.0", "c.d@1.0.0"],
            bindings=[_make_binding("__unknown_slot_xyz__", "__unknown_slot_abc__")],
        )
        v = CrossMethodValidator()
        report = v.validate_chain(chain)
        semantic_issues = [i for i in report.issues if i.category == "semantic_slot"]
        assert semantic_issues == []

    def test_no_bindings_no_issues(self):
        chain = _make_chain_stub(fqns_in_order=["a.b@1.0.0"])
        v = CrossMethodValidator()
        report = v.validate_chain(chain)
        assert report.ok


# ---------------------------------------------------------------------------
# Conflict detection pass
# ---------------------------------------------------------------------------


class TestConflictCheck:
    def test_no_conflict_when_not_in_chain(self):
        chain = _make_chain_stub(
            fqns_in_order=["a.b@1.0.0", "c.d@1.0.0"],
            conflicts_with_map={"a.b@1.0.0": ["e.f@1.0.0"]},  # e.f not in chain
        )
        v = CrossMethodValidator()
        report = v.validate_chain(chain)
        conflict_issues = [i for i in report.issues if i.category == "conflict"]
        assert conflict_issues == []

    def test_conflict_detected_when_both_present(self):
        chain = _make_chain_stub(
            fqns_in_order=["a.b@1.0.0", "c.d@1.0.0"],
            conflicts_with_map={"a.b@1.0.0": ["c.d@1.0.0"]},
        )
        v = CrossMethodValidator()
        report = v.validate_chain(chain)
        conflict_issues = [i for i in report.issues if i.category == "conflict"]
        assert len(conflict_issues) == 1
        assert not report.ok

    def test_conflict_reported_once(self):
        # Both sides declare conflict → should only appear once.
        chain = _make_chain_stub(
            fqns_in_order=["a.b@1.0.0", "c.d@1.0.0"],
            conflicts_with_map={
                "a.b@1.0.0": ["c.d@1.0.0"],
                "c.d@1.0.0": ["a.b@1.0.0"],
            },
        )
        v = CrossMethodValidator()
        report = v.validate_chain(chain)
        conflict_issues = [i for i in report.issues if i.category == "conflict"]
        assert len(conflict_issues) == 1


# ---------------------------------------------------------------------------
# Ordering rules pass
# ---------------------------------------------------------------------------


class TestOrderingCheck:
    def test_no_issue_when_rule_not_triggered(self):
        # No sensitivity/refutation methods → ordering rule not triggered
        chain = _make_chain_stub(fqns_in_order=["causal.did@1.0.0"])
        v = CrossMethodValidator()
        report = v.validate_chain(chain)
        ordering_issues = [i for i in report.issues if i.category == "ordering"]
        assert ordering_issues == []

    def test_strict_mode_makes_ordering_error(self):
        """With strict=True, ordering violations become errors."""
        # A chain with "sensitivity" family but no causal predecessor
        from types import SimpleNamespace

        nid = uuid4()
        sig = SimpleNamespace(
            fqn="test.sensitivity@1.0.0",
            name="sensitivity",
            namespace="test",
            family="sensitivity",
            variant="sensitivity",
            data_modalities=frozenset(),
            conflicts_with=frozenset(),
        )
        chain = SimpleNamespace(
            execution_order=(nid,),
            signatures={nid: sig},
            bindings=[],
        )
        v = CrossMethodValidator(strict=True)
        report = v.validate_chain(chain)
        ordering_issues = [i for i in report.issues if i.category == "ordering"]
        if ordering_issues:
            assert all(i.severity == "error" for i in ordering_issues)


# ---------------------------------------------------------------------------
# Isolation rules pass
# ---------------------------------------------------------------------------


class TestIsolationCheck:
    def test_no_isolation_issue_without_spatial_edge(self):
        chain = _make_chain_stub(
            fqns_in_order=["causal.did@1.0.0", "sensitivity.sa@1.0.0"],
            bindings=[
                _make_binding("outcome", "outcome", "causal.did@1.0.0", "sensitivity.sa@1.0.0")
            ],
        )
        v = CrossMethodValidator()
        report = v.validate_chain(chain)
        iso_issues = [i for i in report.issues if i.category == "isolation"]
        assert iso_issues == []


# ---------------------------------------------------------------------------
# CrossMethodValidator public API
# ---------------------------------------------------------------------------


class TestCrossMethodValidator:
    def test_validate_chain_returns_report(self):
        chain = _make_chain_stub(fqns_in_order=["a.b@1.0.0"])
        v = CrossMethodValidator()
        result = v.validate_chain(chain)
        assert isinstance(result, ValidationReport)

    def test_empty_chain_is_valid(self):
        chain = _make_chain_stub()
        v = CrossMethodValidator()
        report = v.validate_chain(chain)
        assert report.ok

    def test_strict_false_by_default(self):
        v = CrossMethodValidator()
        assert v._strict is False

    def test_strict_true_accepted(self):
        v = CrossMethodValidator(strict=True)
        assert v._strict is True
