"""Resolve the draft into a supplier-qualified, unapplied owned proposal."""
import ast
import difflib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tokenize

root = Path("/workspace/orch02-r2/c05/g-patch")
draft = json.loads((root / "reconciliation-draft.json").read_text())
repo = Path("/workspace/orch02-c05-r2-gproposal")


def tokens(text):
    answer = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type not in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER):
                answer.append((token.type, token.string))
    except (tokenize.TokenError, IndentationError):
        pass
    return answer


def resolve(text, path):
    lines = text.splitlines(keepends=True)
    result, controls = [], []
    i = 0
    while i < len(lines):
        if not lines[i].startswith("<<<<<<<"):
            result.append(lines[i]); i += 1; continue
        i += 1
        chunks = [[], [], []]
        part = 0
        while not lines[i].startswith(">>>>>>>"):
            if lines[i].startswith("|||||||"):
                part = 1
            elif lines[i].startswith("======="):
                part = 2
            else:
                chunks[part].append(lines[i])
            i += 1
        i += 1
        g, cat, own = map("".join, chunks)
        choice = "G unchanged semantic tokens" if tokens(cat) == tokens(own) else "owned changed contract"
        if path.endswith("proxy_penalties.py"):
            chosen = g.rstrip() + "\n" + own
            choice = "retain G resource import and owned material imports"
        else:
            chosen = g if tokens(cat) == tokens(own) else own
        result.append(chosen)
        controls.append({"G_sha256": hashlib.sha256(g.encode()).hexdigest(), "CAT_sha256": hashlib.sha256(cat.encode()).hexdigest(), "own_sha256": hashlib.sha256(own.encode()).hexdigest(), "resolution": choice})
    return "".join(result), controls


patches = []
for row in draft["paths"]:
    folder = Path(row["folder"])
    path = row["path"]
    text, controls = resolve((folder / "postimage").read_text(), path)
    if path.endswith("core_sources/loaders.py"):
        seam = "from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (\n    resolve_core_sources_compatibility_binding,\n)\n"
        if "    resolve_core_sources_compatibility_binding," not in text:
            text = text.replace("logger = get_logger(__name__)", seam + "\nlogger = get_logger(__name__)")
    if path.endswith("fabric/retrieval/service.py"):
        # Current G already exports another domain's CatalogSelectionError.
        # Request an additive alias for the exact run-profile selection owner.
        text = text.replace("catalog_read_api.CatalogSelectionError", "catalog_read_api.CatalogRunProfileSelectionError")
    target = text.encode()
    if path.endswith(".py"):
        ast.parse(text)
        compile(text, path, "exec")
    (folder / "postimage").write_bytes(target)
    before = (folder / "G").read_bytes()
    old_blob = subprocess.check_output(["git", "hash-object", "--stdin"], input=before, cwd=repo).decode().strip() if before else "0"*40
    new_blob = subprocess.check_output(["git", "hash-object", "--stdin"], input=target, cwd=repo).decode().strip()
    header = f"diff --git a/{path} b/{path}\n"
    if not before:
        header += "new file mode 100644\n"
    header += f"index {old_blob}..{new_blob}" + (" 100644" if before else "") + "\n"
    delta = "".join(difflib.unified_diff(before.decode().splitlines(keepends=True), text.splitlines(keepends=True), fromfile=f"a/{path}" if before else "/dev/null", tofile=f"b/{path}"))
    patches.append(header + delta)
    row.update({"preimage_blob": None if not before else old_blob, "postimage_blob": new_blob, "postimage_sha256": hashlib.sha256(target).hexdigest(), "postimage_bytes": len(target), "conflict_resolutions": controls})
raw_patch = "".join(patches).encode()
(root / "owned-g-proposal.patch").write_bytes(raw_patch)
check = subprocess.run(["git", "apply", "--check", str(root / "owned-g-proposal.patch")], cwd=repo, capture_output=True)
(root / "apply-check.stdout.txt").write_bytes(check.stdout)
(root / "apply-check.stderr.txt").write_bytes(check.stderr)
draft.update({"state": "UNAPPLIED_SUPPLIER_QUALIFIED_HELD", "git_apply_check_exit": check.returncode, "patch_sha256": hashlib.sha256(raw_patch).hexdigest(), "patch_bytes": len(raw_patch), "G_native_claim": False})
(root / "reconciliation.json").write_text(json.dumps(draft, indent=2) + "\n")
print(json.dumps({key: draft[key] for key in ("state", "G", "R2_tree", "git_apply_check_exit", "patch_sha256", "patch_bytes")}, indent=2))
if check.returncode:
    print(check.stderr.decode())
raise SystemExit(check.returncode)
