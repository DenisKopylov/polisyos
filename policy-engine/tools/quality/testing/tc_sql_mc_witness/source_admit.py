"""Bind selected actual checkout bytes and a Git index before any test execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--root", required=True)
ap.add_argument("--base", required=True)
ap.add_argument("--tree", required=True)
ap.add_argument("--pins", required=True)
ap.add_argument("--pins-sha256", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--scratch", required=True)
a = ap.parse_args()
root, out, scratch = Path(a.root).resolve(), Path(a.out).resolve(), Path(a.scratch).resolve()


def git(*args: str) -> bytes:
    """Read Git facts from the selected checkout without mutating it."""
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True).stdout


head = git("rev-parse", "HEAD").decode().strip()
tree = git("rev-parse", "HEAD^{tree}").decode().strip()
base_tree = git("rev-parse", a.base + "^{tree}").decode().strip()
if head != a.base or tree != a.tree or base_tree != a.tree:
    raise SystemExit("source_admission_head_or_tree_mismatch")
pins_bytes = Path(a.pins).read_bytes()
if hashlib.sha256(pins_bytes).hexdigest() != a.pins_sha256:
    raise SystemExit("source_admission_pin_manifest_sha_mismatch")
pins = json.loads(pins_bytes)
rows = []
for pin in pins["files"]:
    rel = pin["path"]
    path = root / rel
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        raise SystemExit("source_admission_path_invalid:" + rel)
    actual = path.read_bytes()
    gitbytes = git("show", a.base + ":" + rel)
    digest = hashlib.sha256(actual).hexdigest()
    blob = hashlib.sha1(
        b"blob " + str(len(actual)).encode() + b"\0" + actual, usedforsecurity=False
    ).hexdigest()
    if actual != gitbytes or digest != pin["sha256"] or blob != pin["git_blob"]:
        raise SystemExit("source_admission_bytes_mismatch:" + rel)
    rows.append({"path": rel, "sha256": digest, "git_blob": blob, "bytes": len(actual)})
paths = [
    "policy-engine/src",
    "policy-engine/tests",
    "policy-engine/tools",
    "policy-engine/pytest.ini",
    "policy-engine/pyproject.toml",
    "policy-engine/uv.lock",
]
diff = git("diff", "--name-only", a.base, "--", *paths).decode().splitlines()
untracked = [
    path
    for path in git(
        "ls-files",
        "--others",
        "--",
        "policy-engine/src",
        "policy-engine/tests",
        "policy-engine/tools",
    )
    .decode()
    .splitlines()
    if Path(path).suffix in (".py", ".pyi", ".so", ".pyd")
]
if diff or untracked:
    raise SystemExit(
        "source_admission_unexpected_worktree:" + json.dumps({"diff": diff, "untracked": untracked})
    )
index = {}
for line in (
    git(
        "ls-tree",
        "-r",
        "--full-tree",
        a.base,
        "--",
        "policy-engine/src",
        "policy-engine/tests",
        "policy-engine/tools",
    )
    .decode()
    .splitlines()
):
    left, path = line.split("\t", 1)
    mode, kind, blob = left.split()
    if kind == "blob":
        index[path] = blob
scratch.mkdir(parents=True, exist_ok=True)
(scratch / "git-input-index.json").write_text(json.dumps(index, sort_keys=True) + "\n")
cache = scratch / "initial-pycache"
cache.mkdir()
result = {
    "base": a.base,
    "head": head,
    "tree": tree,
    "pins": rows,
    "tracked_changed": diff,
    "untracked_source": untracked,
    "git_index_entries": len(index),
    "initial_pycache_empty": not any(cache.iterdir()),
    "scope": "Named pins plus tracked paths under source/tests/tools; source-module origin maps are observed separately per process.",
}
(out / "source-admission.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": "PASS", "pin_count": len(rows), "git_index_entries": len(index)}))
