"""Independent recursive AST visitor, verifying every Python input against Git blobs."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).resolve().parent
entries = {}
for row in subprocess.check_output(["git", "ls-tree", "-rz", "63bdb9640"], cwd=ROOT).split(b"\0"):
    if row:
        meta, path = row.split(b"\t", 1)
        if path.endswith(b".py"):
            entries[path.decode()] = meta.decode().split()[2]
counts = Counter()
duplicates = []
ambiguous = []
errors = []


class Visitor(ast.NodeVisitor):
    def visit_Dict(self, node):
        counts["dict_literals"] += 1
        values = []
        for key in node.keys:
            counts["key_slots"] += 1
            if key is None:
                counts["unpacks"] += 1
                continue
            try:
                value = ast.literal_eval(key)
                hash(value)
            except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                counts["nonliteral"] += 1
                continue
            counts["literal"] += 1
            # Pairwise equality is independent of the first census's hash-map method.
            for before, line in values:
                if before == value:
                    duplicates.append({"path": self.path, "dict_line": node.lineno, "first_line": line, "line": key.lineno, "key": repr(value)})
            values.append((value, key.lineno))
        self.generic_visit(node)


visitor = Visitor()
for path, expected in sorted(entries.items()):
    try:
        b = (ROOT/path).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
        if actual != expected:
            raise ValueError("working bytes differ from pinned Git blob")
        visitor.path = path
        visitor.visit(ast.parse(b, filename=path))
    except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
        errors.append({"path": path, "error": str(exc)})
first = json.loads((OUT.parent/"04-vocabularies/summary.json").read_text())
mapping = {"dict_literals": "dict_literals", "key_slots": "dict_key_slots", "unpacks": "unpack_key_slots", "nonliteral": "nonliteral_key_slots", "literal": "literal_key_slots"}
equal = all(counts[k] == first["dict_counts"][v] for k, v in mapping.items())
result = {"base": "63bdb9640", "method": "recursive NodeVisitor, pairwise literal equality, each file content-checked against Git blob", "python_file_denominator": len(entries), "all_input_bytes_match_base": not errors, "errors": errors, "counts": dict(counts), "duplicate_pairs": duplicates, "first_census_counts_agree": equal, "first_census_duplicates_agree": duplicates == first["duplicate_literal_pairs"], "exit_code": 0 if not errors and equal else 1}
(OUT/"duplicates-crosscheck.json").write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps(result, indent=2))
raise SystemExit(result["exit_code"])
