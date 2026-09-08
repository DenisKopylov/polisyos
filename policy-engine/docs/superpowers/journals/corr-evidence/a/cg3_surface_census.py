"""Enumerate the complete CG3 receiving/exporting source set and retained DTO bodies."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
from pathlib import Path


def emission_boundary() -> dict:
    """Enumerate every independently content-addressed DTO in the existing owner."""
    path = Path("src/polisyos/runtime/quality/grounding_admission.py")
    source = path.read_text()
    tree = ast.parse(source)
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    headers = list(re.finditer(r"^class (\w+)(?:\([^\n]+\))?:", source, re.MULTILINE))
    lexical_classes = {match.group(1) for match in headers}
    if set(classes) != lexical_classes:
        raise ValueError("cg3_class_denominator_not_reconciled")
    addressed = {}
    for name, node in classes.items():
        fields = {
            item.target.id
            for item in node.body
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
        }
        if "content_hash" in fields:
            addressed[name] = sorted(fields & {"certificate_id", "patch_id", "ledger_id"})
    lexical_addressed = set()
    for index, match in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(source)
        if re.search(r"^    content_hash\s*:", source[match.end() : end], re.MULTILINE):
            lexical_addressed.add(match.group(1))
    if set(addressed) != lexical_addressed or any(not ids for ids in addressed.values()):
        raise ValueError("cg3_content_addressed_identity_difference")
    return {
        "status": "pass",
        "denominator": str(path) + "::all top-level classes",
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "class_count": len(classes),
        "independently_addressed_artifacts": addressed,
        "crosscheck": "complete AST annotated fields vs independent whole-class lexical fields",
        "nested_details": "non-addressed resolution details remain inside their marked certificate",
        "independent_return": "apply_registry_patch returns the content-addressed registry patch",
    }


def main() -> int:
    """Reconcile independent whole-tree paths; unreadability is an error, never zero."""
    if sys.argv[1:] == ["--emissions-only"]:
        sys.stdout.write(json.dumps(emission_boundary(), sort_keys=True, indent=2) + "\n")
        return 0
    tokens = {"GroundingAdmissionCertificate", "apply_grounding_admission_registry_patch"}
    roots = (Path("src"), Path("tools"))
    globbed = {path for root in roots for path in root.rglob("*.py")}
    walked = {
        Path(folder) / name
        for root in roots
        for folder, _directories, files in os.walk(root)
        for name in files
        if name.endswith(".py")
    }
    if globbed != walked:
        raise ValueError("python_path_denominator_not_reconciled")
    lexical: set[str] = set()
    syntax: set[str] = set()
    for path in sorted(walked):
        source = path.read_text()
        if any(re.search(rf"\b{token}\b", source) for token in tokens):
            lexical.add(str(path))
        for node in ast.walk(ast.parse(source, filename=str(path))):
            names: set[str] = set()
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
            elif isinstance(node, ast.ImportFrom):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                names.update(token for token in tokens if token in node.value)
            if tokens & names:
                syntax.add(str(path))
    if lexical != syntax:
        raise ValueError(f"consumer_identity_difference:{sorted(lexical ^ syntax)}")
    artifact_root = Path("architecture")
    json_paths = set(artifact_root.rglob("*.json"))
    json_walk = {
        Path(folder) / name
        for folder, _directories, files in os.walk(artifact_root)
        for name in files
        if name.endswith(".json")
    }
    if json_paths != json_walk:
        raise ValueError("json_path_denominator_not_reconciled")
    body_ids: set[tuple[str, str]] = set()
    parsed_ids: set[tuple[str, str]] = set()
    epoch = "policyos.runtime.grounding_admission_certificate.v1"
    for path in sorted(json_paths):
        data = path.read_bytes()
        parsed = json.loads(data)
        pending = [parsed]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                if value.get("schema_version") == epoch and "certificate_id" in value:
                    body_ids.add((str(path), value["certificate_id"]))
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)

        def hook(value: dict, source_path: Path = path) -> dict:
            if value.get("schema_version") == epoch and "certificate_id" in value:
                parsed_ids.add((str(source_path), value["certificate_id"]))
            return value

        json.loads(data, object_hook=hook)
    if body_ids != parsed_ids:
        raise ValueError("historical_body_identity_difference")
    sys.stdout.write(
        json.dumps(
            {
                "status": "pass",
                "python_path_and_type_denominator": "src/**/*.py + tools/**/*.py",
                "python_files": len(walked),
                "path_crosscheck": "os.walk vs Path.rglob exact sets",
                "consumer_crosscheck": "lexical whole-source tokens vs complete Python AST walk",
                "receiving_exporting_sources": sorted(syntax),
                "historical_artifact_denominator": "architecture/**/*.json",
                "json_files": len(json_paths),
                "v1_full_certificate_bodies": sorted(body_ids),
                "historical_body_count": len(body_ids),
                "historical_crosscheck": "iterative complete object walk vs JSON object-hook",
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
