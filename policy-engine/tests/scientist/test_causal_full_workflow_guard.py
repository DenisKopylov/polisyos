from __future__ import annotations

from polisyos.scientist.workflows.causal_full import causal_full_workflow_spec
from polisyos.scientist.workflows.default import default_workflow_spec


def test_causal_full_workflow_contains_phase9_nodes() -> None:
    spec = causal_full_workflow_spec()
    by_alias = {node.alias: node for node in spec.nodes}

    assert spec.workflow_id == "scientist_causal_full"
    assert "build_literature_prior" in by_alias
    assert "reconcile_causal_graph" in by_alias
    assert "run_causal_queries" in by_alias
    assert "run_causal_ensemble" in by_alias
    assert "run_abm_consistency" in by_alias
    assert "run_transportability" in by_alias
    assert "run_normative_arbitration" in by_alias
    assert "resolve_parameters" in by_alias
    assert "build_literature_prior" in by_alias["reconcile_causal_graph"].depends_on
    assert "reconcile_causal_graph" in by_alias["run_governance"].depends_on
    assert "run_causal_evaluation" in by_alias["run_causal_queries"].depends_on
    assert "run_causal_queries" in by_alias["run_causal_ensemble"].depends_on
    assert "run_causal_ensemble" in by_alias["run_abm_consistency"].depends_on
    assert "run_abm_consistency" in by_alias["run_transportability"].depends_on
    assert "reconcile_causal_graph" in by_alias["resolve_parameters"].depends_on
    assert "resolve_parameters" in by_alias["run_simulation"].depends_on
    assert "run_causal_ensemble" in by_alias["run_governance"].depends_on
    assert "run_abm_consistency" in by_alias["run_governance"].depends_on
    assert "run_transportability" in by_alias["run_governance"].depends_on
    assert "run_normative_arbitration" in by_alias["run_governance"].depends_on


def test_default_workflow_does_not_include_phase9_nodes() -> None:
    spec = default_workflow_spec()
    aliases = {node.alias for node in spec.nodes}

    assert "build_literature_prior" not in aliases
    assert "reconcile_causal_graph" not in aliases
    assert "run_causal_queries" not in aliases
    assert "run_causal_ensemble" not in aliases
    assert "run_abm_consistency" not in aliases
    assert "run_transportability" not in aliases
    assert "resolve_parameters" in aliases


def test_causal_full_workflow_runs_transportability_before_governance() -> None:
    spec = causal_full_workflow_spec()
    aliases_in_order = [node.alias for node in spec.nodes]

    assert aliases_in_order.index("run_transportability") < aliases_in_order.index("run_governance")
