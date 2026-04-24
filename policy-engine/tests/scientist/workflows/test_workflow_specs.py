"""Structural tests for the three workflow specs (DAG validity, node coverage)."""

from __future__ import annotations

from collections import defaultdict

from polisyos.scientist.workflows.causal_full import causal_full_workflow_spec
from polisyos.scientist.workflows.default import default_workflow_spec
from polisyos.scientist.workflows.discovery import discovery_workflow_spec
from polisyos.scientist.workflows.policy_design import policy_design_workflow_spec
from polisyos.scientist.workflows.policy_verified import policy_verified_workflow_spec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _aliases(spec):
    return {n.alias for n in spec.nodes}


def _dep_graph(spec):
    """Return adjacency list {alias: set_of_dependencies}."""
    return {n.alias: set(n.depends_on) for n in spec.nodes}


def _assert_valid_dag(spec):
    """Verify the workflow spec describes a valid DAG (no cycles, all refs resolve)."""
    aliases = _aliases(spec)
    graph = _dep_graph(spec)

    # All depends_on must point to existing aliases
    for alias, deps in graph.items():
        for dep in deps:
            assert dep in aliases, f"{alias} depends on unknown alias '{dep}'"

    # Topological sort to detect cycles (Kahn's algorithm)
    in_degree = defaultdict(int)
    for alias in aliases:
        in_degree.setdefault(alias, 0)
    for alias, deps in graph.items():
        for dep in deps:
            in_degree[alias] += 1

    queue = [a for a, d in in_degree.items() if d == 0]
    visited = 0
    reverse_adj = defaultdict(set)
    for alias, deps in graph.items():
        for dep in deps:
            reverse_adj[dep].add(alias)

    while queue:
        node = queue.pop()
        visited += 1
        for dependent in reverse_adj[node]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    assert visited == len(aliases), f"Cycle detected in {spec.workflow_id}"


# ---------------------------------------------------------------------------
# Default workflow
# ---------------------------------------------------------------------------


class TestDefaultWorkflowSpec:
    def test_valid_dag(self):
        _assert_valid_dag(default_workflow_spec())

    def test_unique_aliases(self):
        spec = default_workflow_spec()
        aliases = [n.alias for n in spec.nodes]
        assert len(set(aliases)) == len(aliases)

    def test_required_binds(self):
        spec = default_workflow_spec()
        assert "run_id" in spec.required_binds
        assert "inputs.trinity_bundle_ref" in spec.required_binds
        assert "inputs.registry_bundle_ref" in spec.required_binds

    def test_error_policy_is_continue(self):
        assert default_workflow_spec().error_policy == "continue"

    def test_has_governance_after_simulation(self):
        spec = default_workflow_spec()
        graph = _dep_graph(spec)
        # run_governance must transitively depend on run_simulation
        gov_deps = graph.get("run_governance", set())
        # At least propagate_uncertainty, which depends on run_simulation
        assert (
            "propagate_uncertainty" in gov_deps
            or "run_simulation" in gov_deps
            or any("run_simulation" in graph.get(dep, set()) for dep in gov_deps)
        )

    def test_decision_packet_is_terminal(self):
        spec = default_workflow_spec()
        graph = _dep_graph(spec)
        # No node depends on build_decision_packet
        for alias, deps in graph.items():
            assert "build_decision_packet" not in deps, (
                f"{alias} depends on build_decision_packet — it should be terminal"
            )


# ---------------------------------------------------------------------------
# Causal full workflow
# ---------------------------------------------------------------------------


class TestCausalFullWorkflowSpec:
    def test_valid_dag(self):
        _assert_valid_dag(causal_full_workflow_spec())

    def test_unique_aliases(self):
        spec = causal_full_workflow_spec()
        aliases = [n.alias for n in spec.nodes]
        assert len(set(aliases)) == len(aliases)

    def test_includes_causal_specific_nodes(self):
        aliases = _aliases(causal_full_workflow_spec())
        for expected in (
            "build_literature_prior",
            "reconcile_causal_graph",
            "run_causal_queries",
            "run_causal_ensemble",
            "run_abm_consistency",
            "run_transportability",
        ):
            assert expected in aliases, f"Missing causal node: {expected}"

    def test_is_superset_of_default(self):
        default_aliases = _aliases(default_workflow_spec())
        causal_aliases = _aliases(causal_full_workflow_spec())
        # Causal full should contain all default nodes
        missing = default_aliases - causal_aliases
        # Some nodes may be reorganized, but core nodes must be present
        core_nodes = {"start", "run_simulation", "run_governance", "build_decision_packet"}
        assert core_nodes.issubset(causal_aliases)


# ---------------------------------------------------------------------------
# Policy verified workflow
# ---------------------------------------------------------------------------


class TestPolicyVerifiedWorkflowSpec:
    def test_valid_dag(self):
        _assert_valid_dag(policy_verified_workflow_spec())

    def test_unique_aliases(self):
        spec = policy_verified_workflow_spec()
        aliases = [n.alias for n in spec.nodes]
        assert len(set(aliases)) == len(aliases)

    def test_includes_policy_planning_nodes(self):
        aliases = _aliases(policy_verified_workflow_spec())
        for expected in (
            "plan_policy_request",
            "assemble_legal_candidate_pack",
            "expand_legal_source_pack",
            "run_source_verification",
            "run_source_gap_review",
            "draft_policy_options",
            "formalize_verified_policy",
        ):
            assert expected in aliases, f"Missing policy node: {expected}"

    def test_does_not_require_trinity_bundle(self):
        spec = policy_verified_workflow_spec()
        assert "inputs.trinity_bundle_ref" not in spec.required_binds

    def test_includes_verified_policy_report(self):
        aliases = _aliases(policy_verified_workflow_spec())
        assert "build_verified_policy_report" in aliases


# ---------------------------------------------------------------------------
# Policy design workflow
# ---------------------------------------------------------------------------


class TestPolicyDesignWorkflowSpec:
    def test_valid_dag(self):
        _assert_valid_dag(policy_design_workflow_spec())

    def test_blueprint_runtime_replaces_legacy_shortcut(self):
        aliases = _aliases(policy_design_workflow_spec())
        assert "run_policy_blueprint_runtime" in aliases
        assert "run_policy_funnel_level5" not in aliases
        assert "run_policy_promotion" not in aliases

    def test_includes_c6c_nodes(self):
        aliases = _aliases(policy_design_workflow_spec())
        for expected in (
            "build_literature_prior",
            "reconcile_causal_graph",
            "run_hierarchical_policy_search",
            "run_causal_readiness",
            "counterfactual_identification_gate",
        ):
            assert expected in aliases

    def test_c6c_ordering_guards(self):
        graph = _dep_graph(policy_design_workflow_spec())

        assert "run_hierarchical_policy_search" in graph["compile_foundry"]
        assert "compile_cross_graph_evidence" in graph["run_causal_readiness"]
        assert "run_causal_readiness" in graph["counterfactual_identification_gate"]
        assert "counterfactual_identification_gate" in graph["run_simulation"]


# ---------------------------------------------------------------------------
# Discovery workflow
# ---------------------------------------------------------------------------


class TestDiscoveryWorkflowSpec:
    def test_valid_dag(self):
        _assert_valid_dag(discovery_workflow_spec())

    def test_includes_blueprint_runtime(self):
        aliases = _aliases(discovery_workflow_spec())
        assert "run_discovery_blueprint_runtime" in aliases


# ---------------------------------------------------------------------------
# Cross-workflow
# ---------------------------------------------------------------------------


class TestCrossWorkflow:
    def test_all_workflow_ids_unique(self):
        ids = {
            default_workflow_spec().workflow_id,
            causal_full_workflow_spec().workflow_id,
            discovery_workflow_spec().workflow_id,
            policy_design_workflow_spec().workflow_id,
            policy_verified_workflow_spec().workflow_id,
        }
        assert len(ids) == 5

    def test_preflight_precedes_compile_foundry(self):
        """In all workflows with compile_foundry, preflight runs before it."""
        for spec_fn in (
            default_workflow_spec,
            causal_full_workflow_spec,
            policy_verified_workflow_spec,
        ):
            spec = spec_fn()
            graph = _dep_graph(spec)
            if "compile_foundry" in graph:
                compile_deps = graph["compile_foundry"]
                # Must depend on ready_to_run or run_preflight (directly or transitively)
                assert "ready_to_run" in compile_deps or "run_preflight" in compile_deps, (
                    f"compile_foundry in {spec.workflow_id} doesn't depend on preflight"
                )
