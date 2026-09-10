"""Confirm C1 leaves the closed Lex artifact and its producer body unchanged."""
import ast
import hashlib
import json
import subprocess
from pathlib import Path

BASE = "ffbd99321"
ARTIFACT = "architecture/policy_design_case/layer3_gy_phase2_lex_bounds_strangle_receipt.json"
PRODUCER = "tools/quality/validation/check_layer3_gy_phase2_artifacts.py"


def historical(path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{BASE}:policy-engine/{path}"])


def body(source: bytes) -> bytes:
    text = source.decode()
    function = next(node for node in ast.parse(text).body
                    if isinstance(node, ast.FunctionDef) and node.name == "_build_lex_bounds_strangle_receipt")
    return ast.get_source_segment(text, function).encode()


current = Path(ARTIFACT).read_bytes()
previous = historical(ARTIFACT)
assert current == previous
current_body = body(Path(PRODUCER).read_bytes())
previous_body = body(historical(PRODUCER))
assert current_body == previous_body
subprocess.run(["git", "diff", "--exit-code", BASE, "--", ARTIFACT], check=True)
print(json.dumps({
    "base": BASE, "artifact": ARTIFACT,
    "artifact_sha256": hashlib.sha256(current).hexdigest(),
    "artifact_exact_bytes_equal": current == previous,
    "independent_git_diff_exit": 0,
    "lex_producer_body_sha256": hashlib.sha256(current_body).hexdigest(),
    "lex_producer_body_exact_bytes_equal": current_body == previous_body,
}, indent=2, sort_keys=True))
