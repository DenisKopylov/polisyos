import hashlib
import json
import os
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


LANE = Path("/workspace/e02-E-doe-20261006")
OUT = Path("/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer/doe-budget")
SOURCE = "70c4a14fc872f5ef66437d958ba63884ecdda168"
BASE = "a2677935015e8a0e7f2dfd5412b671e13fb3175a"
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
        [_resolve_executable("git"), "-C", str(LANE), *args], text=True
    ).strip()


def snapshot() -> object:
    paths = git("ls-files", "policy-engine/src").splitlines()
    items = {p: hashlib.sha256((LANE / p).read_bytes()).hexdigest() for p in paths}
    return {
        "head": git("rev-parse", "HEAD"),
        "tree": git("rev-parse", "HEAD^{tree}"),
        "source_count": len(items),
        "source_digest": hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest(),
        "frozen_source_delta": git("diff", SOURCE, "--", "policy-engine/src"),
        "changed_source_sha256": {
            p: items[p]
            for p in git(
                "diff", "--name-only", BASE, SOURCE, "--", "policy-engine/src"
            ).splitlines()
        },
    }


before = snapshot()
if before["frozen_source_delta"]:
    raise AssertionError
env = dict(
    os.environ,
    UV_NO_SYNC="1",
    PYTHONPATH=str(LANE / "policy-engine/src"),
    REVIEW_LANE=str(LANE),
    REVIEW_SOURCE=SOURCE,
    REVIEW_OUTPUT=str(OUT / (label + "-origins-artifacts.json")),
)
start = time.monotonic()
with (OUT / (label + ".stdout.txt")).open("w") as stream:
    p = subprocess.run(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        argv, cwd=LANE / "policy-engine", env=env, stdout=stream, stderr=subprocess.STDOUT
    )
after = snapshot()
if not (before["source_digest"] == after["source_digest"] and not after["frozen_source_delta"]):
    raise AssertionError
dictout = {
    "label": label,
    "base": BASE,
    "candidate": SOURCE,
    "tree": git("rev-parse", SOURCE + "^{tree}"),
    "argv": argv,
    "cwd": str(LANE / "policy-engine"),
    "exit_code": p.returncode,
    "wall_seconds": time.monotonic() - start,
    "before": before,
    "after": after,
    "source_unchanged": True,
    "environment": {
        k: env.get(k)
        for k in [
            "PYTHONPATH",
            "UV_NO_SYNC",
            "OMP_NUM_THREADS",
            "MKL_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "XLA_FLAGS",
            "REVIEW_OUTPUT",
        ]
    },
    "wrapper_executable": sys.executable,
    "wrapper_python": sys.version,
    "stdout_sha256": hashlib.sha256((OUT / (label + ".stdout.txt")).read_bytes()).hexdigest(),
}
(OUT / (label + "-receipt.json")).write_text(json.dumps(dictout, indent=2) + "\n")
_write_stdout(
    json.dumps(
        {
            k: dictout[k]
            for k in ["label", "candidate", "exit_code", "wall_seconds", "source_unchanged"]
        },
        indent=2,
    )
)
_write_stdout((OUT / (label + ".stdout.txt")).read_text()[-6000:])
sys.exit(p.returncode)
