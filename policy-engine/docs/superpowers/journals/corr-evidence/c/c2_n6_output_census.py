"""Reconcile all direct N6 report emission sites with the generated-family declaration."""

import ast
import hashlib
import json
import sys
import tomllib
from pathlib import Path


def main() -> None:
    path = Path("tools/quality/validation/check_layer3_gy_generation_cycle_contract.py")
    raw = path.read_bytes()
    tree = ast.parse(raw)
    walked = {
        (node.lineno, node.col_offset, ast.unparse(node.func))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    visited = set()

    class Calls(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            visited.add((node.lineno, node.col_offset, ast.unparse(node.func)))
            self.generic_visit(node)

    Calls().visit(tree)
    if walked != visited:
        raise ValueError("independent_call_identity_sets_disagree")
    declarations = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    output_fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "declared_outputs"
    )
    returned = next(node.value for node in output_fn.body if isinstance(node, ast.Return))
    if not isinstance(returned, ast.List):
        raise ValueError("declared_output_shape_ambiguous")
    declared = {declarations[node.id] for node in returned.elts if isinstance(node, ast.Name)}
    if len(declared) != len(returned.elts):
        raise ValueError("declared_output_identity_ambiguous")
    writes = [
        (line, column, function)
        for line, column, function in walked
        if function.endswith((".write_text", ".write_bytes", ".write", ".writelines"))
        or function in {"open", "io.open"}
    ]
    writer = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "write"
    )
    expected_target = next(node.value for node in writer.body if isinstance(node, ast.Assign))
    if not isinstance(expected_target, ast.BinOp) or not isinstance(
        expected_target.right, ast.Name
    ):
        raise ValueError("write_target_shape_ambiguous")
    derived_writes = {declarations[expected_target.right.id]}
    if len(writes) != 1 or writes[0][2] != "path.write_text":
        raise ValueError("write_site_denominator_changed")
    registry = tomllib.loads(Path("architecture/generated_artifacts.toml").read_text())
    family = [item for item in registry["family"] if item.get("workflow") == str(path)]
    if len(family) != 1:
        raise ValueError("registered_family_ambiguous")
    if not declared == derived_writes == set(family[0]["outputs"]):
        raise ValueError("output_identity_sets_disagree")
    sys.stdout.write(
        json.dumps(
            {
                "denominator": {"path": str(path), "file_type": ".py", "complete_files": 1},
                "source_sha256": hashlib.sha256(raw).hexdigest(),
                "complete_call_identity_sets_equal": True,
                "call_identity_sha256": hashlib.sha256(
                    json.dumps(sorted(walked)).encode()
                ).hexdigest(),
                "complete_call_function_vocabulary": sorted({item[2] for item in walked}),
                "direct_write_sites": sorted(writes),
                "declared_outputs": sorted(declared),
                "independently_derived_write_outputs": sorted(derived_writes),
                "registered_family": family[0]["id"],
                "registered_outputs": family[0]["outputs"],
                "stdout_stderr_sites": sorted(item for item in walked if item[2] == "print"),
                "diagnostic_surface_scope": (
                    "main emits validation status/issues/timing/output paths; rederive_audit adds "
                    "compute economics. These do not export a separate source/report body. "
                    "The sole full report envelope is produced in "
                    "_build_live_payload_in_verification_namespace and serialized by "
                    "build_contract_json_for_write into the one declared canonical artifact."
                ),
            },
            sort_keys=True,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
