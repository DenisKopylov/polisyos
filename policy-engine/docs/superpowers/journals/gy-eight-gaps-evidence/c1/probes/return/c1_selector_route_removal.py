"""Remove the real causal selector route while preserving current consumer markers."""
from __future__ import annotations
import ast
import hashlib
import json
import subprocess
from pathlib import Path
import pytest
from polisyos.runtime.quality.workspace import loop


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    relative = "src/polisyos/runtime/quality/workspace/loop.py"
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    source = subprocess.check_output(["git", "show", f"{base}:policy-engine/{relative}"], cwd=root, text=True)
    matches = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "_phase2_value_method_selection"]
    assert len(matches) == 1
    current_hash = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    print(json.dumps({"removed_property": "causal_ESTIMATE_routes_by_actual_input_contract",
        "replacement": f"{relative}@{base}", "preserved_current_source_sha256": current_hash,
        "production_files_changed": False, "unchanged_markers": ["current_candidate_contract", "real_playbook", "real_registry", "real_input_owner"]}))
    original = loop._phase2_value_method_selection
    try:
        exec(compile(ast.Module(body=matches, type_ignores=[]), f"{relative}@{base}", "exec"), loop.__dict__)
        result = pytest.main(["-q", "-rA", "--show-capture=no", "--tb=short",
            "tests/unit/runtime/quality/test_workspace_workflow_playbook_projection.py::test_phase2_explicit_causal_method_uses_contract_route_not_value_population",
            "tests/unit/runtime/quality/test_workspace_workflow_playbook_projection.py::test_phase2_default_method_accepts_actual_recorded_input_and_report_port"])
    finally:
        loop._phase2_value_method_selection = original
    assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == current_hash
    return result


if __name__ == "__main__":
    raise SystemExit(main())
