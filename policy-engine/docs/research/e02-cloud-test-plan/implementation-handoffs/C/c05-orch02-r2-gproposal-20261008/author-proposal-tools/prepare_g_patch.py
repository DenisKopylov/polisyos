"""Build an unapplied owned G proposal by three-way, pathwise reconciliation."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

repo = Path("/workspace/orch02-c05")
out = Path("/workspace/orch02-r2/c05/g-patch")
out.mkdir(parents=True, exist_ok=True)
G = "dee58973f7673299070b7c7374f419b0adb8175c"
CAT = "8dfa7f3c544461c0ff081861848fcc5d8523da5b"
R2 = "dac1d82c7761d0f8e11e19f1ee448133d606d73d"
prior = json.loads(Path("/workspace/orch02-recovery/reviews/c05-source-binding-66151f3b.json").read_text())
paths = prior["full_changed_paths"] + [
    "policy-engine/release-fragments/unreleased/2026-10-08-e02-c05-loader-contracts-r2.toml",
    "policy-engine/src/polisyos/data_forge/kernel/io/generation_basis.py",
    "policy-engine/src/polisyos/data_forge/kernel/pipeline/manifests.py",
    "policy-engine/src/polisyos/data_forge/domains/catalog/selection.py",
]


def raw(ref, path):
    result = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=repo, capture_output=True)
    return result.stdout if result.returncode == 0 else b""


records = []
for i, path in enumerate(paths):
    g, cat, target = raw(G, path), raw(CAT, path), raw(R2, path)
    folder = out / f"{i:02}"
    folder.mkdir(exist_ok=True)
    for label, content in (("G", g), ("CAT", cat), ("R2", target)):
        (folder / label).write_bytes(content)
    if path.endswith(("generation_basis.py", "manifests.py", "selection.py")):
        # These are exact selected predecessor contracts, separately itemized.
        target = cat
        result_code = 0
    else:
        merge = subprocess.run(["git", "merge-file", "-p", "--diff3", str(folder / "G"), str(folder / "CAT"), str(folder / "R2")], capture_output=True)
        target = merge.stdout
        result_code = merge.returncode
    (folder / "postimage").write_bytes(target)
    records.append({"path": path, "folder": str(folder), "merge_exit": result_code, "G_sha256": hashlib.sha256(g).hexdigest() if g else None, "CAT_sha256": hashlib.sha256(cat).hexdigest() if cat else None, "R2_sha256": hashlib.sha256(raw(R2, path)).hexdigest(), "postimage_sha256": hashlib.sha256(target).hexdigest(), "postimage_bytes": len(target)})
(out / "reconciliation-draft.json").write_text(json.dumps({"G": G, "CAT": CAT, "R2_tree": R2, "state": "UNAPPLIED_DRAFT_NOT_REVIEWED", "paths": records}, indent=2) + "\n")
print(json.dumps(records, indent=2))
