"""Read-only full Python caller/registry census for C1; no source mutation."""
from __future__ import annotations

import ast
import hashlib
import io
import json
import subprocess
import sys
import tokenize
from pathlib import Path


ROOT = Path.cwd()
TERMINALS = {
    "ScientistNodeAdapter", "execute_candidate", "validate_adapter_semantic_preservation",
    "validate_scientist_node_adapter_shape", "build_workflow_playbook_registry",
    "_step_from_invocation", "admit_playbook_step", "PlaybookStep", "CandidatePlaybookStep",
}


def main() -> None:
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "src", "tools", "tests"]
    ).decode().split("\0")
    paths = {p for p in tracked if p.endswith(".py")}
    independent = {
        p for p in subprocess.check_output(
            ["rg", "--files", "--hidden", "--no-ignore", "src", "tools", "tests"]
        ).decode().splitlines() if p.endswith(".py") and p in set(tracked)
    }
    assert paths == independent, (sorted(paths-independent), sorted(independent-paths))
    unreadables = []
    all_calls = []
    ast_identities = set()
    token_identities = set()
    snapshots = {}
    for relative in sorted(paths):
        path = ROOT / relative
        try:
            raw = path.read_bytes()
            source = raw.decode("utf-8")
            tree = ast.parse(source, filename=relative)
        except (OSError, UnicodeError, SyntaxError) as exc:
            unreadables.append({"path": relative, "error": repr(exc)})
            continue
        snapshots[relative] = hashlib.sha256(raw).hexdigest()
        aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for name in node.names:
                    aliases[name.asname or name.name] = f"{node.module}.{name.name}"
            elif isinstance(node, ast.Import):
                for name in node.names:
                    aliases[name.asname or name.name.split(".")[0]] = (
                        name.name if name.asname else name.name.split(".")[0]
                    )

        def resolve(node):
            if isinstance(node, ast.Name):
                return aliases.get(node.id, node.id)
            if isinstance(node, ast.Attribute):
                return f"{resolve(node.value)}.{node.attr}"
            if isinstance(node, ast.Call):
                return resolve(node.func)
            return "<dynamic>"

        # Propagate constructor aliases and annotated parameters, including renamed imports.
        for _ in range(3):
            for node in ast.walk(tree):
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    value = node.value
                    target = resolve(value)
                    if target.endswith("ScientistNodeAdapter.from_node") or target.endswith("ScientistNodeAdapter"):
                        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                        for item in targets:
                            if isinstance(item, ast.Name):
                                aliases[item.id] = target.removesuffix(".from_node")
                elif isinstance(node, ast.arg) and node.annotation:
                    value = resolve(node.annotation)
                    if value.endswith("ScientistNodeAdapter"):
                        aliases[node.arg] = value
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            resolved = resolve(node.func)
            terminal = resolved.rsplit(".", 1)[-1]
            if terminal not in TERMINALS and not resolved.endswith("ScientistNodeAdapter.from_node"):
                continue
            end = node.func.end_lineno, node.func.end_col_offset
            identity = (relative, *end)
            ast_identities.add(identity)
            all_calls.append({
                "path": relative, "line": node.lineno, "column": node.col_offset,
                "call": ast.unparse(node.func), "resolved": resolved,
                "kind": "production" if relative.startswith("src/") else "tools_or_tests",
            })
        # Independently tokenize calls. No AST node traversal or AST call list here.
        tokens = [t for t in tokenize.generate_tokens(io.StringIO(source).readline)
                  if t.type not in {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                                    tokenize.INDENT, tokenize.DEDENT}]
        for index, token in enumerate(tokens[:-1]):
            if token.type != tokenize.NAME or tokens[index + 1].string != "(":
                continue
            if index and tokens[index - 1].string in {"def", "class"}:
                continue
            start = index
            while start >= 2 and tokens[start-1].string == "." and tokens[start-2].type == tokenize.NAME:
                start -= 2
            parts = [tokens[k].string for k in range(start, index+1, 2)]
            resolved = ".".join([aliases.get(parts[0], parts[0]), *parts[1:]])
            if resolved.rsplit(".", 1)[-1] in TERMINALS or resolved.endswith("ScientistNodeAdapter.from_node"):
                token_identities.add((relative, *token.end))
    changed = [p for p, digest in snapshots.items()
               if hashlib.sha256((ROOT/p).read_bytes()).hexdigest() != digest]

    if "--static-only" in sys.argv:
        print(json.dumps({
            "denominator": {"roots": ["src", "tools", "tests"], "file_type": "tracked .py",
                            "git_count": len(paths), "independent_rg_count": len(independent)},
            "source_changed_during_census": changed, "unreadables": unreadables,
            "call_identity_crosscheck": {"ast": len(ast_identities), "tokenize": len(token_identities),
                "only_ast": sorted(ast_identities-token_identities), "only_tokenize": sorted(token_identities-ast_identities)},
            "calls": sorted(all_calls, key=lambda item: (item["path"], item["line"], item["column"])),
        }, indent=2, sort_keys=True))
        assert not unreadables and not changed
        assert ast_identities == token_identities
        return

    from polisyos.runtime.quality.workspace.workflow_playbook_projection import (
        _phase2_workflow_specs, build_workflow_playbook_registry,
    )
    from polisyos.scientist.orchestration.workflows.builder import build_registry_with_builtin_nodes
    registry = build_registry_with_builtin_nodes(include_discovered_nodes=False)
    listed = {str(spec.metadata.component_id) for spec in registry.list()}
    independently_listed = {str(node.spec.metadata.component_id) for node in registry.values()}
    assert listed == independently_listed
    workflows = _phase2_workflow_specs()
    registry_errors = []
    try:
        playbooks = build_workflow_playbook_registry(node_registry=registry)
    except Exception as exc:
        playbooks = None
        registry_errors.append(repr(exc))
        from polisyos.scientist.orchestration.engine.registry import discover_nodes
        diagnostic = discover_nodes(registry, include_entry_points=False,
                                    include_builtin_nodes=True, include_dev_scan=False)
        registry_errors.append(repr(diagnostic))
    step_rows = []
    for playbook in (playbooks.playbooks.values() if playbooks else []):
        actual_invocations = {str(i.node_id): i for i in workflows[playbook.source_workflow_id].nodes}
        for step in playbook.steps:
            node = registry.get(step.node_id)
            actual = actual_invocations[step.node_id]
            assert actual.alias == step.legacy_alias
            step_rows.append({
                "step_id": step.step_id, "node_id": step.node_id,
                "type": type(step).__name__, "actual_node_class": type(node).__module__+"."+type(node).__qualname__,
                "state_reads": node.spec.state_reads, "produces": node.spec.produces,
                "state_writes": node.spec.state_writes,
            })
    output = {
        "denominator": {"roots": ["src", "tools", "tests"], "file_type": "tracked .py",
                        "git_count": len(paths), "independent_rg_count": len(independent)},
        "source_changed_during_census": changed,
        "unreadables": unreadables,
        "call_identity_crosscheck": {"ast": len(ast_identities), "tokenize": len(token_identities),
            "only_ast": sorted(ast_identities-token_identities), "only_tokenize": sorted(token_identities-ast_identities)},
        "calls": sorted(all_calls, key=lambda item: (item["path"], item["line"], item["column"])),
        "registry_node_denominator": {"registry_list": len(listed), "registry_values": len(independently_listed)},
        "registry_node_ids": sorted(listed),
        "registry_errors": registry_errors,
        "canonical_workflow_ids": sorted(workflows),
        "playbook_step_denominator": ({"flat": len(step_rows), "sum_lengths": sum(len(p.steps) for p in playbooks.playbooks.values())} if playbooks else {"status": "unreadable", "reason": registry_errors}),
        "playbook_steps": step_rows,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    assert not unreadables and not changed
    assert ast_identities == token_identities
    assert not registry_errors


if __name__ == "__main__":
    main()
