from __future__ import annotations

from polisyos.scientist.workflows.default import default_workflow_spec


def test_default_workflow_runs_governance_after_causal_evaluation() -> None:
    spec = default_workflow_spec()
    by_alias = {node.alias: node for node in spec.nodes}

    assert "run_causal_evaluation" in by_alias
    assert "legal_check" in by_alias
    assert "run_normative_arbitration" in by_alias
    assert "run_governance" in by_alias
    assert "resolve_parameters" in by_alias
    assert "resolve_parameters" in by_alias["run_simulation"].depends_on
    assert by_alias["legal_check"].depends_on == ["run_simulation"]
    assert "legal_check" in by_alias["run_normative_arbitration"].depends_on
    assert "legal_check" in by_alias["run_governance"].depends_on
    assert "run_normative_arbitration" in by_alias["run_governance"].depends_on
    assert "run_causal_evaluation" in by_alias["run_governance"].depends_on
