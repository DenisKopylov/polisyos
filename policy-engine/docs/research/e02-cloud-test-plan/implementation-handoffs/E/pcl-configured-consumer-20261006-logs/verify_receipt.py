"""Recompute the source, footprint, and moderate evidence identities of this receipt."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def verify(repo: Path, receipt: dict, index: dict) -> dict:
    """Reject a stale or forged footprint, source identity, or evidence digest."""

    def git(*args: str) -> str:
        return subprocess.check_output(  # noqa: S603 -- fixed Git executable, receipt arguments, no shell
            ["/usr/bin/git", "-C", str(repo), *args], text=True
        ).strip()

    def check_ref(ref: dict) -> None:
        path = (repo / ref["path"]).resolve()
        path.relative_to(repo.resolve())
        data = path.read_bytes()
        if not len(data) == ref["bytes"]:
            raise ValueError(f"Size mismatch: {ref['path']}")
        if not hashlib.sha256(data).hexdigest() == ref["sha256"]:
            raise ValueError(f"Digest mismatch: {ref['path']}")

    candidate = receipt["candidate_sha"]
    if not git("rev-parse", candidate + "^{tree}") == receipt["candidate_tree_sha"]:
        raise ValueError("Receipt verification failed")
    subprocess.check_call(  # noqa: S603 -- fixed Git executable, no shell
        [
            "/usr/bin/git",
            "-C",
            str(repo),
            "merge-base",
            "--is-ancestor",
            receipt["slice_base_sha"],
            candidate,
        ]
    )
    footprint = git("diff", "--name-only", receipt["slice_base_sha"], candidate).splitlines()
    if not footprint == receipt["complete_base_candidate_diff_paths"]:
        raise ValueError("Receipt verification failed")
    for source in receipt["source_environment_input_identity"]["source_inputs"]:
        if not git("rev-parse", candidate + ":" + source["path"]) == source["git_blob_sha"]:
            raise ValueError("Receipt verification failed")
        data = subprocess.check_output(  # noqa: S603 -- fixed Git executable, receipt arguments, no shell
            ["/usr/bin/git", "-C", str(repo), "show", candidate + ":" + source["path"]]
        )
        if not hashlib.sha256(data).hexdigest() == source["sha256"]:
            raise ValueError("Receipt verification failed")
    for record in index["files"]:
        check_ref(record)
    for check in receipt["checks"]:
        check_ref(check["output"])
        check_ref(check["execution_receipt"])
        runner = json.loads((repo / check["execution_receipt"]["path"]).read_text())
        if not runner["candidate_sha"] == check["target_sha"]:
            raise ValueError("Receipt verification failed")
        if not runner["command"] == check["command"]:
            raise ValueError("Receipt verification failed")
        if not runner["stdout_sha256"] == check["output"]["sha256"]:
            raise ValueError("Receipt verification failed")
        if not runner["stdout_bytes"] == check["output"]["bytes"]:
            raise ValueError("Receipt verification failed")
        if runner["source_immutable"] is not True:
            raise ValueError("Receipt verification failed")
        if check["outcome"] == "UNRUN":
            if not runner["exit_code"] == -15:
                raise ValueError("Receipt verification failed")
            if not check["product_failure_attribution"] == "not_established":
                raise ValueError("Receipt verification failed")
        else:
            if not runner["outcome"] == check["outcome"] == check["expected_outcome"]:
                raise ValueError("Receipt verification failed")
            if not runner["exit_code"] == (0 if check["outcome"] == "PASS" else 1):
                raise ValueError("Receipt verification failed")
    native = next(item for item in receipt["checks"] if item["name"] == "native")
    if "151 passed" not in (repo / native["output"]["path"]).read_text():
        raise ValueError("Receipt verification failed")
    removal = next(item for item in receipt["checks"] if item["name"] == "removal-focused")
    if "2 failed, 1 deselected" not in (repo / removal["output"]["path"]).read_text():
        raise ValueError("Receipt verification failed")
    return {
        "source_and_footprint": "PASS",
        "moderate_files": len(index["files"]),
        "checks": len(receipt["checks"]),
    }


def main() -> None:
    repo = Path(sys.argv[1]).resolve()
    folder = Path(__file__).resolve().parent
    receipt = json.loads(folder.with_name("pcl-configured-consumer-20261006.json").read_text())
    index = json.loads((folder / "copy-index.json").read_text())
    result = verify(repo, receipt, index)
    corrupt = copy.deepcopy(index)
    corrupt["files"][0]["sha256"] = "0" * 64
    try:
        verify(repo, receipt, corrupt)
    except ValueError as exc:
        result["corrupt_digest_negative"] = {"result": "REJECTED", "reason": str(exc)}
    else:
        raise ValueError("Integrity-valid schema with forged digest was accepted")
    (folder / "receipt-validation.json").write_text(json.dumps(result, indent=2) + "\n")
    sys.stdout.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main()
