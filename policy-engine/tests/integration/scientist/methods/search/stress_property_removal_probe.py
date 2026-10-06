"""Remove an actual stress property in memory while retaining report markers."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path
from types import CodeType, FunctionType

import pytest


def main() -> int:
    mode, source_sha, *pytest_arguments = sys.argv[1:]
    if mode == "example_fraction":
        from polisyos.scientist.nodes.builtins.decide import run_policy_blueprint_runtime as module

        function = module._recompute_stress_test_report
    elif mode == "raw_bool":
        from polisyos.scientist.methods.backtesting import adversarial as module

        function = module.build_challenge_case_result
    else:
        raise ValueError("unknown removal mode")
    path = Path(module.__file__).resolve()
    repository = Path(
        subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
    )
    relative = str(path.relative_to(repository))
    original_file = subprocess.check_output(["git", "show", f"{source_sha}:{relative}"])
    assert path.read_bytes() == original_file, (
        "loaded property source differs from pinned Git bytes"
    )
    original_source = inspect.getsource(function)
    tree = ast.parse(original_source)
    if mode == "example_fraction":
        replacement = ast.parse(
            "(report.total_scenarios_evaluated - len(report.vulnerabilities)) / report.total_scenarios_evaluated if evidence is not None else None",
            mode="eval",
        ).body
        changed = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for index, key in enumerate(node.keys):
                    if isinstance(key, ast.Constant) and key.value == "robustness_score":
                        node.values[index] = replacement
                        changed += 1
        assert changed == 1
        retained = ("scenario_evidence", "schema_version", "score_scope", "score_status")
    else:
        definition = tree.body[0]
        assert isinstance(definition, ast.FunctionDef)
        guards = [node for node in definition.body if isinstance(node, ast.If)]
        assert len(guards) == 1
        definition.body.remove(guards[0])
        for node in ast.walk(definition):
            if isinstance(node, ast.keyword) and node.arg == "passed":
                node.value = ast.Call(
                    func=ast.Name(id="bool", ctx=ast.Load()),
                    args=[ast.Name(id="passed", ctx=ast.Load())],
                    keywords=[],
                )
        retained = ("ChallengeCaseResult", "status", "passed", "summary")
    ast.fix_missing_locations(tree)
    effective_source = ast.unparse(tree)
    namespace = dict(vars(module))
    compiled = compile(tree, str(path) + "::actual-property-removal", "exec")
    codes = [
        value
        for value in compiled.co_consts
        if isinstance(value, CodeType) and value.co_name == function.__name__
    ]
    assert len(codes) == 1 and codes[0].co_freevars == function.__code__.co_freevars
    replacement_function = FunctionType(
        codes[0], namespace, function.__name__, function.__defaults__, function.__closure__
    )
    replacement_function.__kwdefaults__ = function.__kwdefaults__
    setattr(module, function.__name__, replacement_function)
    print(
        json.dumps(
            {
                "mode": mode,
                "source_sha": source_sha,
                "file": relative,
                "original_file_sha256": hashlib.sha256(original_file).hexdigest(),
                "original_function_sha256": hashlib.sha256(original_source.encode()).hexdigest(),
                "effective_function_sha256": hashlib.sha256(effective_source.encode()).hexdigest(),
                "effective_function_source": effective_source,
                "retained_report_markers": list(retained),
                "scope": "Actual defining function mutation before test import; no production file writes; independent acceptance not claimed.",
            },
            sort_keys=True,
        ),
        flush=True,
    )
    outcome = int(pytest.main(pytest_arguments))
    print(
        json.dumps(
            {
                "mode": mode,
                "actual_pytest_exit": outcome,
                "mutation_detected": outcome == 1,
                "production_bytes_preserved": path.read_bytes() == original_file,
            }
        ),
        flush=True,
    )
    return outcome


if __name__ == "__main__":
    raise SystemExit(main())
