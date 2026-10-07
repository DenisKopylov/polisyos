import hashlib
import json
import os
import resource
import shutil
import subprocess
import sys
import time
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


lane = Path("/workspace/e02-E-backtest-20261006")
out = Path("/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer/welfare")
label = sys.argv[1]
argv = sys.argv[2:]


def _admit_git_object_arguments(arguments: tuple[str, ...]) -> None:
    """Keep object reads from interpreting record refs as Git options.

    Named/abbreviated refs remain available to retired source-pinned replay
    scripts; live packet admissions separately require full immutable SHAs.
    """
    if not arguments or arguments[0] not in {"show", "rev-parse"}:
        return
    safe_information_flags = {"--show-toplevel", "--git-dir", "--git-common-dir"}
    for value in arguments[1:]:
        if not isinstance(value, str) or not value or "\0" in value:
            raise ValueError("Git object argument must be a nonempty string")
        if value.startswith("-"):
            if arguments[0] == "rev-parse" and value in safe_information_flags:
                continue
            raise ValueError("Git object reference must never be an option")
        if ":" in value:
            _, relative = value.split(":", 1)
            path = Path(relative)
            if (
                not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or path.as_posix() != relative
                or "\0" in relative
            ):
                raise ValueError("Git object path must be repository relative")


def git(*args: object) -> object:
    _admit_git_object_arguments(args)
    return subprocess.check_output(  # noqa: S603 - source-bound fixture
        [_resolve_executable("git"), "-C", str(lane), *args], text=True
    ).strip()


def snapshot() -> object:
    paths = git("ls-files", "policy-engine/src/polisyos").splitlines()
    items = {p: hashlib.sha256((lane / p).read_bytes()).hexdigest() for p in paths}
    changed = git(
        "diff",
        "--name-only",
        "5d4e01011a0b7e0a3954decdb622a9e9cf1fb787",
        "884681db485b7466b183a206f83bbe0635f86ca3",
        "--",
        "policy-engine/src",
    ).splitlines()
    return {
        "head": git("rev-parse", "HEAD"),
        "tree": git("rev-parse", "HEAD^{tree}"),
        "src_file_count": len(items),
        "src_sha256": hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest(),
        "changed_source_sha256": {p: items[p] for p in changed},
        "diff_from_frozen": git(
            "diff", "884681db485b7466b183a206f83bbe0635f86ca3", "--", "policy-engine/src"
        ),
    }


before = snapshot()
env = dict(
    os.environ,
    UV_NO_SYNC="1",
    PYTHONPATH=str(lane / "policy-engine/src"),
    WELFARE_REVIEW_OUTPUT=str(out / (label + "-origins-artifacts.json")),
)
start = time.monotonic()
with (out / (label + ".log")).open("w") as stream:
    process = subprocess.run(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        argv, cwd=lane / "policy-engine", env=env, stdout=stream, stderr=subprocess.STDOUT
    )
after = snapshot()
rusage = resource.getrusage(resource.RUSAGE_CHILDREN)
receipt = {
    "label": label,
    "argv": argv,
    "cwd": str(lane / "policy-engine"),
    "exit_code": process.returncode,
    "wall_seconds": time.monotonic() - start,
    "maxrss_kib": rusage.ru_maxrss,
    "source_base": "5d4e01011a0b7e0a3954decdb622a9e9cf1fb787",
    "source_candidate": "884681db485b7466b183a206f83bbe0635f86ca3",
    "source_tree": "b9cdce22cd8af3bee3cda176207242a8381cbe1b",
    "before": before,
    "after": after,
    "source_unchanged": before["src_sha256"] == after["src_sha256"]
    and not after["diff_from_frozen"],
    "environment": {
        k: env.get(k)
        for k in (
            "PYTHONPATH",
            "UV_NO_SYNC",
            "WELFARE_REVIEW_OUTPUT",
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "XLA_FLAGS",
        )
    },
    "python": sys.version,
    "executable": sys.executable,
    "stdout_sha256": hashlib.sha256((out / (label + ".log")).read_bytes()).hexdigest(),
}
(out / (label + "-receipt.json")).write_text(json.dumps(receipt, indent=2))
_write_stdout(
    json.dumps(
        {k: receipt[k] for k in ("label", "exit_code", "wall_seconds", "source_unchanged")},
        indent=2,
    )
)
_write_stdout((out / (label + ".log")).read_text()[-6500:])
sys.exit(process.returncode)
