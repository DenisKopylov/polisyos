"""Enumerate the complete N9 evidence vocabulary and its actual persistence sites."""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path


def main() -> None:
    path = Path("src/polisyos/runtime/quality/promotion_sequence.py")
    raw = path.read_bytes()
    tree = ast.parse(raw)
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    alias = next(
        node.value for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "_PromotionEvidenceKind"
                for target in node.targets)
    )
    if not isinstance(alias, ast.Subscript) or not isinstance(alias.slice, ast.Tuple):
        raise ValueError("ambiguous_evidence_kind_declaration")
    declared = {ast.literal_eval(item) for item in alias.slice.elts}
    persisted: set[str] = set()
    emitted: dict[str, str] = {}
    owner = classes["N9PromotionEvidenceBridgeRepository"]
    for method in owner.body:
        if not isinstance(method, ast.FunctionDef):
            continue
        constructors = {
            target.id: statement.value.func.id
            for statement in ast.walk(method)
            if isinstance(statement, ast.Assign)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Name)
            and statement.value.func.id in classes
            for target in statement.targets if isinstance(target, ast.Name)
        }
        for call in ast.walk(method):
            if not isinstance(call, ast.Call):
                continue
            if isinstance(call.func, ast.Attribute) and call.func.attr == "_persist_bridge":
                persisted.add(ast.literal_eval(next(
                    keyword.value for keyword in call.keywords if keyword.arg == "evidence_kind"
                )))
            if isinstance(call.func, ast.Name) and call.func.id == "_persist_model":
                value = next(keyword.value for keyword in call.keywords if keyword.arg == "value")
                if not isinstance(value, ast.Name) or value.id not in constructors:
                    raise ValueError("ambiguous_persisted_source_constructor")
                emitted[method.name] = constructors[value.id]
    writer_specs = next(
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        and node.target.id == "evidence_specs"
    )
    wired = {ast.literal_eval(row.elts[0]) for row in writer_specs.elts}
    sys.stdout.write(json.dumps({
        "source": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
        "file_type_denominator": "complete Python module AST",
        "evidence_kind_denominator": len(declared),
        "declaration_vs_producer_missing": sorted(declared - persisted),
        "producer_vs_declaration_missing": sorted(persisted - declared),
        "declaration_vs_wiring_missing": sorted(declared - wired),
        "wiring_vs_declaration_missing": sorted(wired - declared),
        "owned_cas_emissions": emitted,
        "marker_at_owned_emissions": {
            method: any(isinstance(field, ast.AnnAssign)
                        and isinstance(field.target, ast.Name)
                        and field.target.id == "synthetic"
                        for field in classes[model].body)
            for method, model in emitted.items()
        },
        "scope": "static source denominator; runtime authority requires the independent probes",
    }, indent=2, sort_keys=True) + "\n")
    if not declared == persisted == wired:
        raise ValueError("evidence_kind_identity_denominator_mismatch")


if __name__ == "__main__":
    main()
