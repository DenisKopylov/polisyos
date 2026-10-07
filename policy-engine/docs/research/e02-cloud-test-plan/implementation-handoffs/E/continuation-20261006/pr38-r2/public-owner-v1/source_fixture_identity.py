import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_executable(name: str) -> str:
    (
        "Resolve an admitted executable and refus"  # Exact bound literal continuation.
        "e an unavailable program before invocati"  # Exact bound literal continuation.
        "on."  # Exact bound literal continuation.
    )
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact bound literal continuation.
        "y flush without logging side effects."  # Exact bound literal continuation.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


observed_o = Path(__file__).parent
R = Path("/workspace/e02-E-continuation-20261006")
F = observed_o / "fixture-current"
ref = "c0f146702219cd3280c3b7d06e9d2bc4c7b95dd6"
paths = [
    "policy-engine/src",
    "policy-engine/tools/devx/architecture",
    "policy-engine/tools/lib",
    "policy-engine/architecture/public_surface/contract.toml",
    "policy-engine/architecture/generated_artifacts.toml",
    "policy-engine/pyproject.toml",
    (
        "policy-engine/architecture/production_qu"  # Exact bound literal continuation.
        "ality/method_catalog_dependency_digest_d"  # Exact bound literal continuation.
        "omains.toml"  # Exact bound literal continuation.
    ),
    "policy-engine/ruff.toml",
    "policy-engine/architecture/tooling/ruff/generated.toml",
]
rows = []
differences = []
for raw in subprocess.check_output(  # noqa: S603 - source-bound fixture
    [_resolve_executable("git"), "ls-tree", "-r", "-z", ref, "--", *paths], cwd=R
).split(b"\0"):
    if not raw:
        continue
    metadata, path = raw.decode().split("\t")
    mode, kind, expected = metadata.split()
    p = F / path
    data = os.readlink(p).encode() if p.is_symlink() else p.read_bytes()
    actual = hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\0" + data, usedforsecurity=False
    ).hexdigest()
    if expected != actual:
        differences.append(path)
    rows.append({"path": path, "git_blob": expected, "sha256": hashlib.sha256(data).hexdigest()})
if differences:
    raise AssertionError(differences)
py_expected = {r["path"] for r in rows if r["path"].endswith(".py")}
py_actual = {
    str(p.relative_to(F))
    for root in [
        "policy-engine/src",
        "policy-engine/tools/devx/architecture",
        "policy-engine/tools/lib",
    ]
    for p in (F / root).rglob("*.py")
    if "__pycache__" not in p.parts
}
if not (py_actual == py_expected):
    raise AssertionError((py_actual - py_expected, py_expected - py_actual))
result = {
    "candidate_sha": ref,
    "candidate_tree": subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [_resolve_executable("git"), "rev-parse", ref + "^{tree}"], cwd=R, text=True
    ).strip(),
    "tracked_source_subtree": subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [_resolve_executable("git"), "rev-parse", ref + ":policy-engine/src"], cwd=R, text=True
    ).strip(),
    "full_input_paths": paths,
    "all_selected_git_blobs_match": True,
    "selected_file_count": len(rows),
    "python_file_count": len(py_expected),
    "extra_or_missing_python_paths": [],
    "source_identity_index_sha256": hashlib.sha256(
        json.dumps(rows, sort_keys=True).encode()
    ).hexdigest(),
    "full_index_scratch_file": str(observed_o / "source-fixture-full-index.json"),
    "fixture_is_git_checkout": False,
}
(observed_o / "source-fixture-full-index.json").write_text(json.dumps(rows, indent=2) + "\n")
(observed_o / "source-fixture-identity.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(json.dumps(result, indent=2))
