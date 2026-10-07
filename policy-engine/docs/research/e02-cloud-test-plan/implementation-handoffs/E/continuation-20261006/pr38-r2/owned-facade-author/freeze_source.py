import difflib
import hashlib
import json
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


OUT = Path(__file__).parent
POST = OUT / "postimage"
ROOT = Path("/workspace/e02-E-continuation-20261006")
BASE = "5e3e3727685132f270a3a07b9f63dd962a88cd96"
rows = []
chunks = []
for p in sorted(POST.rglob("*")):
    if not p.is_file():
        continue
    relative = str(p.relative_to(POST))
    after = p.read_bytes()
    exists = (
        subprocess.run(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
            [_resolve_executable("git"), "-C", str(ROOT), "cat-file", "-e", BASE + ":" + relative],
            capture_output=True,
        ).returncode
        == 0
    )
    before = (
        subprocess.check_output(  # noqa: S603 - source-bound fixture
            [_resolve_executable("git"), "-C", str(ROOT), "show", BASE + ":" + relative]
        )
        if exists
        else b""
    )
    if not (after != before):
        raise AssertionError(relative)
    rows.append(
        {
            "path": relative,
            "new_file": not exists,
            "base_git_blob": subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
                [_resolve_executable("git"), "-C", str(ROOT), "rev-parse", BASE + ":" + relative],
                text=True,
            ).strip()
            if exists
            else None,
            "before_sha256": hashlib.sha256(before).hexdigest() if exists else None,
            "after_sha256": hashlib.sha256(after).hexdigest(),
            "bytes": len(after),
        }
    )
    chunks.append("diff --git a/" + relative + " b/" + relative + "\n")
    if not exists:
        chunks.append("new file mode 100644\n")
    chunks.extend(
        difflib.unified_diff(
            before.decode().splitlines(keepends=True),
            after.decode().splitlines(keepends=True),
            fromfile="a/" + relative if exists else "/dev/null",
            tofile="b/" + relative,
        )
    )
patch = "".join(chunks).encode()
(OUT / "owned-facade-route.patch").write_bytes(patch)
manifest = {
    "schema": "policyos.e02.owned_facade_scratch_source_manifest.v1",
    "base": BASE,
    "base_tree": "3b63e778d5b6d17b2e9edc3b4bf91af079b32eb0",
    "source_state": "immutable scratch postimages; no implementation Git commit yet",
    "paths": rows,
    "patch_sha256": hashlib.sha256(patch).hexdigest(),
    "patch_bytes": len(patch),
}
(OUT / "postimage-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
run = subprocess.run(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    [
        _resolve_executable("git"),
        "-C",
        str(ROOT),
        "apply",
        "--check",
        str(OUT / "owned-facade-route.patch"),
    ],
    capture_output=True,
)
(OUT / "apply-check.json").write_text(
    json.dumps(
        {
            "argv": run.args,
            "root_HEAD": subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
                [_resolve_executable("git"), "-C", str(ROOT), "rev-parse", "HEAD"], text=True
            ).strip(),
            "exit_code": run.returncode,
            "stdout": run.stdout.decode(),
            "stderr": run.stderr.decode(),
        },
        indent=2,
    )
    + "\n"
)
_write_stdout(
    json.dumps(
        {
            "path_count": len(rows),
            "patch_bytes": len(patch),
            "patch_sha256": manifest["patch_sha256"],
            "git_apply_check_exit": run.returncode,
        },
        indent=2,
    )
)
raise SystemExit(run.returncode)
