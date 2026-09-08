"""Complete, independently cross-checked PR1 source identity census."""

import ast
import json
from pathlib import Path
import re
import subprocess


root = Path.cwd()
tracked = set(subprocess.check_output(["git", "ls-files", "src/"], text=True).splitlines())
tracked_py = {item for item in tracked if item.endswith(".py")}
walked_py = {str(item) for item in Path("src").rglob("*.py") if item.is_file()}
assert tracked_py == walked_py, {"tracked_only": sorted(tracked_py - walked_py), "walked_only": sorted(walked_py - tracked_py)}
terms = (
    "admissibility", "effective_independence", "n5_coupling_blocked",
    "joint_obligation_inconsistency", "ValueGateReceipt", "value_ready",
    "effective_independence_writer_input", "measurement_root_writer_input",
    "effect_obligation_writer_input", "CanonicalN9PromotionPort",
    "persist_effect_obligation", "persist_measurement_root", "persist_effective_independence",
    "EvalSafetyVerifierRegistry", "EvidenceVerifier", "EvalSafetyCertificate",
    "_ControlEvaluationSafetyVerifierRegistry", "verify_evaluation_safety_requirements",
)
pattern = "\\b(?:" + "|".join(terms) + ")\\b"
read_errors = []
identities = {term: set() for term in terms}
syntax_errors = []
calls = {term: [] for term in terms}
for path in sorted(tracked_py):
    try:
        content = Path(path).read_text()
    except Exception as error:
        read_errors.append({"path": path, "error": repr(error)})
        continue
    for lineno, line in enumerate(content.splitlines(), 1):
        for match in re.finditer(pattern, line):
            identities[match.group()].add(f"{path}:{lineno}:{match.start() + 1}")
    try:
        tree = ast.parse(content, filename=path)
    except Exception as error:
        syntax_errors.append({"path": path, "error": repr(error)})
        continue
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                aliases[alias.asname or alias.name] = alias.name
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Name):
            name = aliases.get(function.id, function.id)
        elif isinstance(function, ast.Attribute):
            name = function.attr
            if isinstance(function.value, ast.Name):
                base = aliases.get(function.value.id, function.value.id)
                if base in terms:
                    name = base
        else:
            continue
        if name in calls:
            calls[name].append({"identity": f"{path}:{node.lineno}:{node.col_offset + 1}", "expression": ast.get_source_segment(content, node)})
result = subprocess.run(["rg", "--json", pattern, "src", "--glob", "*.py"], text=True, capture_output=True)
assert result.returncode in {0, 1}, result.stderr
crosscheck = {term: set() for term in terms}
for line in result.stdout.splitlines():
    event = json.loads(line)
    if event["type"] != "match":
        continue
    data = event["data"]
    for match in data["submatches"]:
        term = match["match"]["text"]
        crosscheck[term].add(f"{data['path']['text']}:{data['line_number']}:{match['start'] + 1}")
assert identities == crosscheck, {term: {"reader_only": sorted(identities[term] - crosscheck[term]), "rg_only": sorted(crosscheck[term] - identities[term])} for term in terms if identities[term] != crosscheck[term]}
report = {
    "denominator": {"path": "src/", "file_type": ".py", "tracked_count": len(tracked_py), "filesystem_count": len(walked_py), "identity_sets_equal": True},
    "ambiguous_read_errors": read_errors,
    "ambiguous_ast_errors": syntax_errors,
    "literal_crosscheck": "Python regex vs rg --json; path:line:column identity sets exactly equal for every term",
    "terms": {term: {"count": len(values), "identities": sorted(values)} for term, values in identities.items()},
    "alias_aware_calls": calls,
}
print(json.dumps(report, indent=2))
assert not read_errors and not syntax_errors
