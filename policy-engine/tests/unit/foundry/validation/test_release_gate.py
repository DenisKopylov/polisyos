from __future__ import annotations

import ast
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.foundry._quickstart import build_trivial_trinity_bundle
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.testing.golden_yaml import GoldenRegistry
from polisyos.foundry.validation.release_acceptance import ReleaseAcceptanceRunner

_KEY_RELEASE_GATE_GOLDEN_DOMAINS = ("bayesian", "ml", "optimization", "survey")
_NO_SKIP_GOLDEN_DOMAINS = ("bayesian", "econometrics", "network", "optimization", "spatial")
_REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="session")
def release_gate_golden_registry() -> GoldenRegistry:
    return GoldenRegistry(_REPO_ROOT / "tests" / "_golden" / "foundry" / "methods")


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
    workflow_path = (
        _REPO_ROOT / "ops" / "ci" / "templates" / "workflows" / "foundry-release-gate.yml"
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
    assert "tests/unit/data_forge/domains/ukraine/test_builders.py" in correctness_run_text
    assert "-k release_acceptance_roundtrip" in correctness_run_text
    assert "tests/unit/foundry/hygiene/test_frontier_namespace_hygiene.py" in correctness_run_text
    assert "tests/unit/foundry/contracts/test_fidelity_tiers.py" in correctness_run_text
    assert "tests/unit/foundry/hygiene/test_skip_marker_audit.py" in correctness_run_text
    assert "tests/unit/foundry/compile/test_trinity_field_coverage.py" in correctness_run_text
    assert "tests/unit/foundry/compile/test_lowering.py" in correctness_run_text
    assert "tests/unit/foundry/analysis/test_loss_numeric.py" in correctness_run_text
    assert "tests/unit/foundry/mechanisms/test_treasury.py" in correctness_run_text
    assert "tests/unit/foundry/mechanisms/test_labor.py" in correctness_run_text
    assert "tests/unit/foundry/methods/test_method_contracts.py" in correctness_run_text
    assert "tests/unit/foundry/methods/test_catalog_snapshot.py" in correctness_run_text
    assert "tests/unit/foundry/agent_sim/test_graph_mechanisms.py" in correctness_run_text
    assert "tests/unit/foundry/agent_sim/test_actor_critic_numerics.py" in correctness_run_text
    assert "tests/unit/foundry/agent_sim/test_jit_compatibility.py" in correctness_run_text
    assert "tests/unit/foundry/methods/backends/test_backends.py" in correctness_run_text
    assert "tests/unit/foundry/methods/test_foundry_purity.py" in correctness_run_text
    assert "tests/unit/foundry/methods/catalog/policy/test_frontier.py" in correctness_run_text
    assert (
        "tests/unit/foundry/methods/catalog/causal/test_frontier_methods.py" in correctness_run_text
    )
    assert "tests/unit/foundry/methods/catalog/ml/test_frontier.py" in correctness_run_text
    assert "tests/unit/foundry/methods/catalog/bayesian/test_methods.py" in correctness_run_text
    assert "ep_svgd_flow_and_factor_graph_frontier_methods_run" in correctness_run_text
    assert "tests/unit/foundry/methods/test_selection_advisor.py" in correctness_run_text
    assert "src/polisyos/data_forge/domains/ukraine/**" in trigger_paths
    assert "tests/unit/data_forge/domains/ukraine/test_builders.py" in trigger_paths

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


def test_release_acceptance_runs_compile_execute_replay_from_cas_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")

    def _parquet_bytes(frame: pd.DataFrame) -> bytes:
        buffer = BytesIO()
        frame.to_parquet(buffer, index=False)
        return buffer.getvalue()

    runtime_agents_ref = store.put_bytes(
        _parquet_bytes(pd.DataFrame({"agent_id": ["a1", "a2"], "cell_id": ["c1", "c2"]})),
        PutOptions(kind="data_forge.ukraine.release_bundle_file_snapshot", media_type="application/vnd.apache.parquet"),
    )
    cell_registry_ref = store.put_bytes(
        _parquet_bytes(pd.DataFrame({"cell_id": ["c1", "c2"]})),
        PutOptions(kind="data_forge.ukraine.release_bundle_file_snapshot", media_type="application/vnd.apache.parquet"),
    )
    manifest_ref = store.put_bytes(
        b'{"artifact_name":"release_manifest_v1.json"}',
        PutOptions(kind="data_forge.ukraine.release_manifest_snapshot", media_type="application/json"),
    )
    trinity = build_trivial_trinity_bundle("sha256:" + "0" * 64)
    trinity_ref = store.put_json(
        trinity,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=trinity.schema_version),
        ),
    )

    read_bytes = Path.read_bytes

    def _cas_only_read(path: Path) -> bytes:
        if path.resolve().is_relative_to(store.root.resolve()):
            return read_bytes(path)
        raise AssertionError("Foundry reopened a producer path instead of using CAS")

    monkeypatch.setattr(Path, "read_bytes", _cas_only_read)
    report = ReleaseAcceptanceRunner(store).run(
        release_manifest_ref=manifest_ref,
        runtime_agent_registry_ref=runtime_agents_ref,
        cell_registry_ref=cell_registry_ref,
        trinity_bundle_ref=trinity_ref,
        manifest_path="producer/release_manifest_v1.json",
        release_bundle_root="producer/d5",
    )

    assert type(report).__name__ == "FoundryReleaseAcceptanceReceipt"
    assert report.technical_passed is True
    assert report.authority_purpose == "foundry_technical_acceptance_receipt"
    assert report.authoritative_for == ()
    assert report.verified_for == (
        "technical_compilation",
        "technical_execution",
        "technical_replay",
    )
    assert report.may_not_use_for == (
        "release_admissibility",
        "governance_admissibility",
        "publication_authorization",
    )
    assert report.execution_artifacts["release_manifest_ref"] == str(manifest_ref.artifact_id)
    assert report.execution_artifacts["trinity_bundle_ref"] == str(trinity_ref.artifact_id)
    assert report.original_simulation_result_ref
    assert report.replay_simulation_result_ref
    assert report.replay_verification["passed"] is True
    with pytest.raises(ValidationError, match="technical_passed"):
        type(report).model_validate(
            {
                **report.model_dump(mode="json"),
                "replay_verification": {**report.replay_verification, "passed": False},
            }
        )
    with pytest.raises(ValidationError, match="frozen"):
        report.technical_passed = False


def test_release_acceptance_has_no_data_forge_or_scientist_imports() -> None:
    source = _REPO_ROOT / "src" / "polisyos" / "foundry" / "validation" / "release_acceptance.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not any(
        module.startswith(("polisyos.data_forge", "polisyos.scientist"))
        for module in imported
    )
