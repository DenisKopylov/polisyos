"""Complete tracked Python census of the F1 owner's predecessor references."""
import ast
import hashlib
import json
import subprocess
from pathlib import Path

root = Path.cwd()
all_tracked = subprocess.check_output(["git", "ls-files", "-z"], text=True).split("\0")
paths = {name for name in all_tracked if name.endswith(".py")}
independent = set(subprocess.check_output(["git", "ls-files", "-z", "--", "*.py"], text=True).split("\0")) - {""}
assert paths == independent
predecessors = {"_deterministic_uuid_sequence", "_production_loop_fields"}
owner_path = "tools/quality/validation/check_layer3_workflow_failure_authority.py"
owner_module = owner_path.removesuffix(".py").replace("/", ".")
findings, errors, homonyms = [], [], []
parsed = 0
for name in sorted(paths):
    try:
        source = (root / name).read_text(encoding="utf-8")
        # Every file is read. Only files that can name either owner or predecessor need AST work.
        if not any(token in source for token in (*predecessors, owner_module.rsplit(".", 1)[-1])):
            continue
        tree = ast.parse(source, filename=name)
        parsed += 1
    except (OSError, UnicodeError, SyntaxError) as exc:
        errors.append({"path": name, "disposition": "ambiguous", "error": str(exc)})
        continue
    aliases = {}
    nodes = list(ast.walk(tree))
    for node in nodes:
        if isinstance(node, ast.ImportFrom):
            for member in node.names:
                aliases[member.asname or member.name] = f"{node.module}.{member.name}"
        elif isinstance(node, ast.Import):
            for member in node.names:
                aliases[member.asname or member.name] = member.name
    def qualify(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return qualify(node.value) + "." + node.attr
        return ""
    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        target = qualify(node.func)
        short = target.rsplit(".", 1)[-1]
        if target in {owner_module + "." + symbol for symbol in predecessors} or (
            name == owner_path and short in predecessors | {"launch_nl_run"}
        ):
            findings.append({"path": name, "line": node.lineno, "call": target})
        elif short in predecessors:
            homonyms.append({"path": name, "line": node.lineno, "call": target,
                             "disposition": "different_module_local_symbol_not_F1_predecessor"})
print(json.dumps({
    "scope": "every tracked .py read; complete AST calls in all files mentioning F1 owner or predecessor; imports qualified",
    "file_denominator": len(paths), "independent_file_denominator": len(independent),
    "ast_file_denominator": parsed,
    "old_private_canonical_symbols": sorted(owner_module + "." + key for key in predecessors),
    "old_request_scope": owner_path + "::launch_nl_run",
    "source_base": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "current_owner_sha256": hashlib.sha256((root / owner_path).read_bytes()).hexdigest(),
    "unreadable": errors, "remaining_callers": findings, "different_owner_homonyms": homonyms,
}, sort_keys=True))
raise SystemExit(1 if errors or findings else 0)
