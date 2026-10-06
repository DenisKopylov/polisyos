"""Exercise the ordinary absent-report consumer without pytest collection."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from types import CodeType, FunctionType

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.methods.backtesting.adversarial import (
    STRATEGIC_GAMING_SUITE_ID,
    ChallengeCase,
    build_challenge_case_result,
    build_challenge_suite_result,
)
from polisyos.scientist.methods.doe.stress_report import StressTestReport, VulnerabilityType
from polisyos.scientist.nodes.builtins.decide import run_policy_blueprint_runtime as blueprint
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector


def main() -> int:
    mode, source_sha = sys.argv[1:]
    assert mode in {"positive", "invent_attempt"}
    repository = Path(
        subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
    )
    source_path = Path(blueprint.__file__).resolve()
    relative = str(source_path.relative_to(repository))
    original_bytes = subprocess.check_output(["git", "show", f"{source_sha}:{relative}"])
    assert source_path.read_bytes() == original_bytes
    function = blueprint._ensure_stress_test_report
    original_function = inspect.getsource(function)
    effective_function = original_function
    if mode == "invent_attempt":
        tree = ast.parse(original_function)
        changed = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "total_scenarios_evaluated":
                assert isinstance(node.value, ast.Constant) and node.value.value == 0
                node.value = ast.Constant(value=1)
                changed += 1
            if isinstance(node, ast.Dict):
                for index, key in enumerate(node.keys):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "base_total_scenarios_evaluated"
                    ):
                        assert isinstance(node.values[index], ast.Constant)
                        assert node.values[index].value == 0
                        node.values[index] = ast.Constant(value=1)
                        changed += 1
        assert changed == 2
        ast.fix_missing_locations(tree)
        effective_function = ast.unparse(tree)
        compiled = compile(tree, str(source_path) + "::invented-attempt-control", "exec")
        codes = [
            value
            for value in compiled.co_consts
            if isinstance(value, CodeType) and value.co_name == function.__name__
        ]
        assert len(codes) == 1 and not codes[0].co_freevars
        function = FunctionType(codes[0], dict(vars(blueprint)), function.__name__)
        function.__kwdefaults__ = blueprint._ensure_stress_test_report.__kwdefaults__
    cases = []
    for with_cases in (False, True):
        root = Path(tempfile.mkdtemp(prefix="e02-D-absent-report-", dir="/dev/shm"))
        store = FileSystemCAS(root)
        registry = build_default_registry_bundle(store).bundle_ref
        run_id = "absent-report-with-cases" if with_cases else "absent-report-empty"
        run = RunContext.start(store=store, registry_bundle=registry, run_id=run_id)
        context = ExecutionContext(store=store, run=run, logger=logging.getLogger(run_id))
        candidate = store.put_json(
            {"candidate": "declared-case-fixture"},
            PutOptions(kind="scientist.policy_candidate", media_type="application/json"),
        )
        supplemental = []
        if with_cases:
            case_results = [
                build_challenge_case_result(
                    case=ChallengeCase(
                        case_id=f"case-{index}",
                        challenge_family="strategic",
                        expected_outcome="declared_check",
                    ),
                    passed=index < 31,
                    summary="declared observed case result",
                )
                for index in range(32)
            ]
            supplemental.append(
                build_challenge_suite_result(
                    suite_id=STRATEGIC_GAMING_SUITE_ID,
                    suite_version="1.0",
                    candidate_ref=candidate,
                    loop_id=run_id,
                    challenge_family="strategic",
                    case_results=case_results,
                    primary_failure_rate_name="silent_static_fallback_rate",
                    vulnerability_type=VulnerabilityType.OBJECTIVE_COLLAPSE,
                ).stress_test_report
            )
        reference = function(
            context,
            ExperimentState(run_id=run_id),
            evaluation_vector=PolicyEvaluationVector(candidate_id="c"),
            supplemental_reports=supplemental,
        )
        reopened = FileSystemCAS(root)
        restored = StressTestReport.model_validate(
            from_canonical_bytes(reopened.get_bytes(reference.artifact_id))
        )
        schema = reopened.get_manifest(reference.artifact_id).artifact_schema
        checks = {
            "schema_1_1": restored.schema_version == "1.1",
            "manifest_body_schema_match": schema is not None
            and schema.version == restored.schema_version,
            "actual_count": restored.total_scenarios_evaluated == (32 if with_cases else 0),
            "no_invented_base_attempt": restored.metadata["base_total_scenarios_evaluated"] == 0,
            "unavailable_combined_score": restored.robustness_score is None,
            "partial": restored.set_adequacy_status == "partial" and not restored.is_robust,
        }
        if with_cases:
            component = restored.scenario_evidence_components[f"suite:{STRATEGIC_GAMING_SUITE_ID}"]
            checks["actual_case_component"] = (
                component is not None
                and component.finite_evaluated == 32
                and component.violated_scenarios == 1
                and component.observed_fraction == 31 / 32
            )
            checks["unknown_base_component_retained"] = any(
                value is None for value in restored.scenario_evidence_components.values()
            )
        else:
            checks["no_evidence_invented"] = restored.scenario_evidence is None
        cases.append(
            {
                "with_cases": with_cases,
                "cas_directory": str(root),
                "report_ref": str(reference.artifact_id),
                "report": restored.model_dump(mode="json"),
                "checks": checks,
            }
        )
    passed = all(all(case["checks"].values()) for case in cases)
    modules = {}
    for name in (
        "polisyos.core.registry.builder",
        "polisyos.core.run.context",
        "polisyos.scientist.methods.backtesting.adversarial",
        "polisyos.scientist.methods.doe.stress_report",
        "polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime",
        "polisyos.scientist.orchestration.engine.context",
        "polisyos.scientist.orchestration.engine.state",
        "polisyos.scientist.policy_design.objectives",
    ):
        path = Path(sys.modules[name].__file__).resolve()
        data = path.read_bytes()
        tracked = str(path.relative_to(repository))
        assert data == subprocess.check_output(["git", "show", f"{source_sha}:{tracked}"])
        modules[name] = {"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}
    print(
        json.dumps(
            {
                "mode": mode,
                "source_sha": source_sha,
                "executable": sys.executable,
                "python": sys.version,
                "outcome": "PASS" if passed else "FAIL",
                "cases": cases,
                "modules": modules,
                "original_function_sha256": hashlib.sha256(original_function.encode()).hexdigest(),
                "effective_function_sha256": hashlib.sha256(
                    effective_function.encode()
                ).hexdigest(),
                "effective_function_source": effective_function,
                "retained_markers": ["1.1", "unavailable", "partial", "base_scenario_basis"],
                "production_bytes_preserved": source_path.read_bytes() == original_bytes,
                "scope": "Real case adapter, ordinary RunContext/ExecutionContext, actual blueprint consumer, CAS persistence and fresh reader. No pytest collection or scientific case-law verification.",
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
