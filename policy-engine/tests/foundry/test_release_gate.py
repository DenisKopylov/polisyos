from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.testing.golden_yaml import GoldenRegistry

_KEY_RELEASE_GATE_GOLDEN_DOMAINS = ("bayesian", "ml", "optimization", "survey")
_NO_SKIP_GOLDEN_DOMAINS = ("bayesian", "econometrics", "network", "optimization", "spatial")


@pytest.fixture(scope="session")
def release_gate_golden_registry() -> GoldenRegistry:
    return GoldenRegistry(Path("/Users/deniskopylov/polisyos/policy-engine/tests/foundry/golden"))


@pytest.fixture(scope="session")
def release_gate_method_registry() -> MethodRegistry:
    registry = MethodRegistry.get_instance()
    ensure_all_methods_registered(registry)
    return registry


def test_release_gate_domains_have_non_skipped_goldens(
    release_gate_golden_registry: GoldenRegistry,
) -> None:
    for domain in _KEY_RELEASE_GATE_GOLDEN_DOMAINS:
        cases = release_gate_golden_registry.cases_by_domain(domain)
        assert cases
        assert any(case.skip_reason is None for case in cases)


def test_release_gate_domains_have_no_deferred_golden_skips(
    release_gate_golden_registry: GoldenRegistry,
) -> None:
    for domain in _NO_SKIP_GOLDEN_DOMAINS:
        cases = release_gate_golden_registry.cases_by_domain(domain)
        assert cases, f"{domain} must ship golden coverage"
        deferred = [case.id for case in cases if case.skip_reason is not None]
        assert not deferred, f"{domain} still has deferred golden skips: {deferred}"


@pytest.mark.parametrize("domain", _KEY_RELEASE_GATE_GOLDEN_DOMAINS)
def test_release_gate_golden_cases_pass_for_key_domains(
    domain: str,
    release_gate_golden_registry: GoldenRegistry,
    release_gate_method_registry: MethodRegistry,
) -> None:
    cases = [
        case
        for case in release_gate_golden_registry.cases_by_domain(domain)
        if case.skip_reason is None
    ]

    assert cases, f"{domain} must ship at least one executable golden case"

    for case in cases:
        result = release_gate_golden_registry.verify_case(case, release_gate_method_registry)
        assert result.passed, (
            f"Release-gate golden FAILED for {case.id} ({case.method_fqn}):\n"
            f"  {result.message}\n" + "\n".join(f"  - {m}" for m in result.mismatches)
        )


def test_release_gate_workflow_publishes_operator_and_numerical_evidence() -> None:
    workflow_path = Path(
        "/Users/deniskopylov/polisyos/policy-engine/.github/workflows/foundry-release-gate.yml"
    )
    payload = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    jobs = payload["jobs"]
    assert "correctness-and-capabilities" in jobs
    assert "scheduled-numerical-matrix" in jobs

    correctness_steps = jobs["correctness-and-capabilities"]["steps"]
    correctness_run_text = "\n".join(
        str(step.get("run", "")) for step in correctness_steps if isinstance(step, dict)
    )
    workflow_events = payload.get("on") or payload.get(True)
    trigger_paths = [
        path for event in ("pull_request", "push") for path in workflow_events[event]["paths"]
    ]
    assert "polisyos-foundry capabilities --json" in correctness_run_text
    assert "polisyos-foundry evidence --json" in correctness_run_text
    assert "tests/ukraine_data/test_builders.py" in correctness_run_text
    assert "-k release_acceptance_roundtrip" in correctness_run_text
    assert "tests/foundry/test_frontier_namespace_hygiene.py" in correctness_run_text
    assert "tests/foundry/test_fidelity_tiers.py" in correctness_run_text
    assert "tests/foundry/test_skip_marker_audit.py" in correctness_run_text
    assert "tests/foundry/test_trinity_field_coverage.py" in correctness_run_text
    assert "tests/foundry/compile/test_lowering.py" in correctness_run_text
    assert "tests/foundry/test_loss_numeric.py" in correctness_run_text
    assert "tests/foundry/test_treasury.py" in correctness_run_text
    assert "tests/foundry/test_labor.py" in correctness_run_text
    assert "tests/foundry/test_method_contracts.py" in correctness_run_text
    assert "tests/foundry/test_catalog_snapshot.py" in correctness_run_text
    assert "tests/foundry/agent_sim/test_graph_mechanisms.py" in correctness_run_text
    assert "tests/foundry/agent_sim/test_actor_critic_numerics.py" in correctness_run_text
    assert "tests/foundry/agent_sim/test_jit_compatibility.py" in correctness_run_text
    assert "tests/foundry/methods/backends/test_backends.py" in correctness_run_text
    assert "tests/foundry/methods/test_foundry_purity.py" in correctness_run_text
    assert "tests/foundry/methods/catalog/policy/test_frontier.py" in correctness_run_text
    assert "tests/foundry/methods/catalog/causal/test_frontier_methods.py" in correctness_run_text
    assert "tests/foundry/methods/catalog/ml/test_frontier.py" in correctness_run_text
    assert "tests/foundry/methods/catalog/bayesian/test_methods.py" in correctness_run_text
    assert "ep_svgd_flow_and_factor_graph_frontier_methods_run" in correctness_run_text
    assert "tests/foundry/methods/test_selection_advisor.py" in correctness_run_text
    assert "src/polisyos/ukraine_data/**" in trigger_paths
    assert "tests/ukraine_data/test_builders.py" in trigger_paths

    artifact_names = {
        step.get("with", {}).get("name") for step in correctness_steps if isinstance(step, dict)
    }
    assert "foundry-capability-matrix" in artifact_names
    assert "foundry-operator-evidence" in artifact_names
    assert "foundry-release-acceptance" in artifact_names

    scheduled_steps = jobs["scheduled-numerical-matrix"]["steps"]
    scheduled_run_text = "\n".join(
        str(step.get("run", "")) for step in scheduled_steps if isinstance(step, dict)
    )
    assert "--junitxml=foundry-numerical-matrix.xml" in scheduled_run_text
