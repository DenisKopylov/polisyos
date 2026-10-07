"""Audit the portable B87 observation delta and captured results without runtime."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = "a6ddddc114e195c7f1686042cf7c63ad99b9d5af"
TEST = "724ed196e2058d48e7f35e8d141f72bcd631cad0"
OLD_PRODUCT = "f131958a71413154785823abeb0765d40499bad2"
PRODUCT = "205bb6ddd67b52f2f359e3f7aab7ab7aafb0dbe7"
OLD_PUBLICATION = "67c4a6f6f4e396c61d26846c51127cc4724978e1"
TEST_PATH = "policy-engine/tests/unit/fabric/data_plane/test_stream_pool_cleanup_oracle.py"
EVIDENCE = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/"
    "current-stream-cleanup-consumer-evidence/portable-205/"
)


def require(condition: bool, message: str) -> None:
    """Keep evidence predicates active with optimization enabled."""
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    """Read immutable AST, Git objects, and captured author outputs only."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--author-ref", required=True)
    args = parser.parse_args()
    executable = shutil.which("git")
    require(executable is not None, "Git unavailable")

    def git(*argv: str) -> bytes:
        # Fixed read-only verbs and structured argv, without a shell.
        return subprocess.run(  # noqa: S603
            [executable, *argv], cwd=args.repo, capture_output=True, check=True
        ).stdout

    def blob(ref: str, path: str) -> bytes:
        return git("show", f"{ref}:{path}")

    def identity(ref: str, path: str) -> dict[str, str | int]:
        data = blob(ref, path)
        return {
            "source_sha": ref,
            "path": path,
            "git_blob": git("rev-parse", f"{ref}:{path}").decode().strip(),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    changed = git("diff", "--name-only", f"{TEST}^", TEST).decode().splitlines()
    require(changed == [TEST_PATH], "portable checkpoint footprint")
    old = ast.parse(blob(BASE, TEST_PATH))
    new = ast.parse(blob(TEST, TEST_PATH))
    excluded = {"_file_fds", "_snapshot"}
    remaining = []
    for module in [old, new]:
        module.body = [node for node in module.body if getattr(node, "name", None) not in excluded]
        remaining.append(ast.dump(module, include_attributes=False))
    require(remaining[0] == remaining[1], "consumer, assertions, or fault profile changed")
    source_delta = git("diff", OLD_PRODUCT, PRODUCT, "--", "policy-engine/src").decode()
    paths = (
        git("diff", "--name-only", OLD_PRODUCT, PRODUCT, "--", "policy-engine/src")
        .decode()
        .splitlines()
    )
    require(
        paths
        == [
            "policy-engine/src/polisyos/core/artifacts/README.md",
            "policy-engine/src/polisyos/core/artifacts/_integrity_ops.py",
            "policy-engine/src/polisyos/core/artifacts/store.py",
        ],
        "new input production scope",
    )
    handoff_root = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/"
    locator_qualifications = []
    for name in [
        "current-all60-independent-adjudication.json",
        "current-final-open-delta-review.json",
        "current-stream-cleanup-consumer-oracle.json",
    ]:
        previous = json.loads(blob(OLD_PUBLICATION, handoff_root + name))
        current = json.loads(blob(args.author_ref, handoff_root + name))
        if name == "current-stream-cleanup-consumer-oracle.json":
            old_basis = previous["finding_dispositions"][0]["canonical_source_basis"]
            new_basis = current["finding_dispositions"][0]["canonical_source_basis"]
        else:
            old_basis = previous["canonical_source_basis"]
            new_basis = current["canonical_source_basis"]
        old_locator = old_basis.pop("criterion_locator")
        new_locator = new_basis.pop("criterion_locator")
        require(previous == current, "metadata changed beyond locator convention")
        locator_qualifications.append(
            {
                "path": handoff_root + name,
                "old": old_locator,
                "new": new_locator,
                "otherwise_object_equivalent": True,
            }
        )
    for name in ["native.txt", "native.xml", "native-wrapper.json"]:
        path = handoff_root + "current-stream-cleanup-consumer-evidence/" + name
        require(blob(OLD_PUBLICATION, path) == blob(args.author_ref, path), "old native drift")

    records = {
        name: blob(args.author_ref, EVIDENCE + name)
        for name in ["native.txt", "native.xml", "native-wrapper.json"]
    }
    stdout = records["native.txt"].decode()
    wrapper = json.loads(records["native-wrapper.json"])
    require(
        wrapper["target_test_sha"] == TEST and wrapper["product_source_sha"] == PRODUCT,
        "new executed source",
    )
    require(wrapper["actual_heads_before"] == wrapper["actual_heads_after"], "HEAD drift")
    require(wrapper["exit"] == 1, "failed native exit lost")
    require(
        hashlib.sha256(records["native.txt"]).hexdigest() == wrapper["stdout"]["sha256"],
        "stdout hash",
    )
    origins = [
        json.loads(line.removeprefix("B87_ACTUAL_SOURCE "))
        for line in stdout.splitlines()
        if line.startswith("B87_ACTUAL_SOURCE ")
    ]
    require(
        len(origins) == 4 and len({row["module"] for row in origins}) == 4, "origin denominator"
    )
    for row in origins:
        path = "policy-engine/src/" + row["module"].replace(".", "/") + ".py"
        require(row["origin"] == "/workspace/e02-B-current-coordination/" + path, "module origin")
        require(blob(OLD_PRODUCT, path) == blob(PRODUCT, path), "four backing source change")
        require(
            hashlib.sha256(blob(PRODUCT, path)).hexdigest() == row["sha256"],
            "observed backing hash",
        )
    # Local captured bytes are bound to immutable Git objects above.
    xml = ET.fromstring(records["native.xml"])  # noqa: S314
    cases = list(xml.iter("testcase"))
    failed = [case for case in cases if case.find("failure") is not None]
    require(len(cases) == 8 and len(failed) == 1, "native denominator")
    require(not list(xml.iter("error")) and not list(xml.iter("skipped")), "error/skip drift")
    require(
        failed[0].get("name")
        == "test_process_file_stream_cleanup_ownership[process-disconnect-failure]",
        "failure changed",
    )
    rows = [
        json.loads(match)
        for match in re.findall(r"STREAM_CLEANUP_OBSERVATION (\{[^\n]+\})", stdout)
    ]
    require(len(rows) == 7 and len({row["stage"] for row in rows}) == 7, "observation denominator")
    for row in rows:
        require(row["fresh_real_file_rows"] == 2, "file consumer changed")
        for phase in [
            "before_retry",
            "after_registry_retry",
            "during_fresh",
            "after_fresh",
            "observer_final_cleanup",
        ]:
            require(
                row[phase]["jsonl_open_fds"] == []
                and row[phase]["jsonl_fd_observation"] == "observed",
                "Linux FD observation",
            )
    row = next(row for row in rows if row["stage"] == "process-disconnect-failure")
    before = row["before_retry"]
    require(
        len(before["pending_cleanup"]) == 1 and before["available_permits"] == 1,
        "pending owner quantity",
    )
    owner = next(iter(before["pending_cleanup"]))
    require(
        before["pending_cleanup"][owner]["pending_permit"] is False
        and before["registry_pending_owner_count"] == 0,
        "owner predicate",
    )
    require(
        row["after_registry_retry"]["pending_cleanup"] == before["pending_cleanup"],
        "production retry retired owner",
    )
    require(
        row["after_registry_retry"]["disconnect_calls"] == [owner],
        "production retry reached old owner",
    )
    require(
        len(row["during_fresh"]["actual_handles_without_disconnect_confirmation"]) == 2,
        "fresh handle control",
    )
    require(
        row["after_fresh"]["actual_handles_without_disconnect_confirmation"] == [owner],
        "fresh close rescued old owner",
    )
    require(row["observer_final_cleanup"]["pending_cleanup"] == {}, "observer cleanup failed")
    result = {
        "grade": "independent delta source and captured output audit; no product/runtime imports",
        "base": identity(BASE, TEST_PATH),
        "candidate": identity(TEST, TEST_PATH),
        "candidate_tree": git("rev-parse", f"{TEST}^{{tree}}").decode().strip(),
        "unchanged_module_outside_observer_functions": True,
        "assertions_and_fault_profiles": "AST_IDENTICAL",
        "source_delta": source_delta,
        "locator_qualifications": locator_qualifications,
        "old_native_companions": "BYTE_IDENTICAL",
        "production_changed_paths": paths,
        "new_product_sha": PRODUCT,
        "new_product_tree": git("rev-parse", f"{PRODUCT}^{{tree}}").decode().strip(),
        "same_child_origins": origins,
        "native_counts": {"cases": 8, "pass": 7, "fail": 1, "error": 0, "skip": 0, "exit": 1},
        "observations": rows,
        "native_wrapper": wrapper,
        "case_names": [case.get("name") for case in cases],
        "output_refs": [identity(args.author_ref, EVIDENCE + name) for name in records],
        "platform_limit": (
            "Linux FD rows observed; procfs absence is source-reviewed UNRUN capability, "
            "not executed Mac proof."
        ),
        "equivalence_limit": (
            "Old full production equivalence does not apply to this new snapshot; "
            "four loaded backings are unchanged."
        ),
    }
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
