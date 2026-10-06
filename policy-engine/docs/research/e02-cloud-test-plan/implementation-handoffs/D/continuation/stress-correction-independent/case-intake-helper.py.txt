"""Exercise raw case intake without importing unrelated blueprint consumers."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path
from types import CodeType, FunctionType

from polisyos.scientist.methods.backtesting import adversarial as module


def main() -> int:
    mode, source_sha = sys.argv[1:]
    assert mode in {"positive", "remove_strict_bool"}
    function = module.build_challenge_case_result
    path = Path(module.__file__).resolve()
    repository = Path(
        subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
    )
    relative = str(path.relative_to(repository))
    original_file = subprocess.check_output(["git", "show", f"{source_sha}:{relative}"])
    assert path.read_bytes() == original_file
    original_function = inspect.getsource(function)
    effective_source = original_function
    if mode == "remove_strict_bool":
        tree = ast.parse(original_function)
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
        ast.fix_missing_locations(tree)
        effective_source = ast.unparse(tree)
        compiled = compile(tree, str(path) + "::actual-intake-removal", "exec")
        codes = [
            value
            for value in compiled.co_consts
            if isinstance(value, CodeType) and value.co_name == function.__name__
        ]
        assert len(codes) == 1 and not codes[0].co_freevars
        function = FunctionType(codes[0], dict(vars(module)), function.__name__)
        function.__kwdefaults__ = module.build_challenge_case_result.__kwdefaults__
    case = module.ChallengeCase(
        case_id="raw", challenge_family="strategic", expected_outcome="declared_check"
    )
    positive = function(case=case, passed=False, summary="declared observed failure")
    assert positive.passed is False and positive.status == "failed"
    results = []
    for malformed in (1, "false", float("nan"), float("inf")):
        try:
            function(case=case, passed=malformed, summary="raw intake")
        except TypeError as error:
            results.append({"input": repr(malformed), "refused": "passed" in str(error)})
        else:
            results.append({"input": repr(malformed), "refused": False})
    passed = all(item["refused"] for item in results)
    print(
        json.dumps(
            {
                "mode": mode,
                "source_sha": source_sha,
                "executable": sys.executable,
                "python": sys.version,
                "origin": str(path),
                "path": relative,
                "file_sha256": hashlib.sha256(original_file).hexdigest(),
                "original_function_sha256": hashlib.sha256(original_function.encode()).hexdigest(),
                "effective_function_sha256": hashlib.sha256(effective_source.encode()).hexdigest(),
                "effective_function_source": effective_source,
                "retained_markers": ["ChallengeCaseResult", "status", "passed", "summary"],
                "strict_false_positive_control": True,
                "invalid_input_results": results,
                "outcome": "PASS" if passed else "FAIL",
                "production_bytes_preserved": path.read_bytes() == original_file,
                "scope": "Actual case helper and classes only; no full blueprint/backend execution claim.",
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
