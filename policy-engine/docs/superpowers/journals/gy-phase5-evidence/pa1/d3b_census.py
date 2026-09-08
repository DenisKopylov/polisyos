"""Reconcile complete source and head-schema identities for the temporal bridge."""
from __future__ import annotations

import ast
import io
import json
import subprocess
import tokenize
from pathlib import Path

from polisyos.runtime.http.services.control.generation_cycle import NormativeGenerationHead

root = Path.cwd()
fs = {path.relative_to(root).as_posix() for path in (root / "src").rglob("*.py")}
git = {p for p in subprocess.check_output(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard", "src"], text=True
).splitlines() if p.endswith(".py")}
assert fs == git, {"fs_only": sorted(fs - git), "git_only": sorted(git - fs)}
watched = {
    "_current_normative_job_record", "_normative_owned_job_source", "get_normative_evidence_head",
    "append_normative_evidence_head", "submit_normative_evidence", "_publish_generation_run",
}
ast_refs, token_refs, ambiguous = set(), set(), []
fields_ast = None
for relative in sorted(fs):
    try:
        source = (root / relative).read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Attribute):
                name = node.attr
            elif isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                name = node.value
            if name in watched:
                ast_refs.add((relative, node.lineno, name))
            if isinstance(node, ast.ClassDef) and node.name == "NormativeGenerationHead":
                assert fields_ast is None
                fields_ast = {item.target.id for item in node.body
                              if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
                              and item.target.id != "model_config"}
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.NAME:
                value = token.string
            elif token.type == tokenize.STRING:
                value = ast.literal_eval(token.string)
            else:
                continue
            if isinstance(value, str) and value in watched:
                token_refs.add((relative, token.start[0], value))
    except Exception as exc:
        ambiguous.append({"path": relative, "error": repr(exc)})
fields_model = set(NormativeGenerationHead.model_fields)
result = {
    "source_denominator": {"file_type": ".py", "root": "src", "fs_count": len(fs), "git_count": len(git), "identity_sets_equal": fs == git},
    "ambiguous": ambiguous,
    "source_ast_identities": sorted(ast_refs), "source_token_identities": sorted(token_refs),
    "source_identity_sets_equal": ast_refs == token_refs,
    "head_field_ast_identities": sorted(fields_ast), "head_field_pydantic_identities": sorted(fields_model),
    "head_field_identity_sets_equal": fields_ast == fields_model,
    "head_field_count": len(fields_model),
    "postgres_live_transaction_verification": "not_established: no PostgreSQL integration executed; SQLite actual independent-connection race is the measured backend",
}
print(json.dumps(result, indent=2))
assert not ambiguous
assert ast_refs == token_refs
assert fields_ast == fields_model
