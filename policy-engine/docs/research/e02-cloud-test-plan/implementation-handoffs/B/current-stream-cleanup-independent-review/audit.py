"""Read immutable B87 Git/source and captured native results; run no product code."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TEST_SHA = "a6ddddc114e195c7f1686042cf7c63ad99b9d5af"
PRODUCT_SHA = "f131958a71413154785823abeb0765d40499bad2"
ACTUAL_ROOT_SHA = "48e1f7170b04f1362e9b7e1d9b74eb9763151830"
HISTORIC_ROOT_SHA = "4e7a4924e6466e1b4eaa39b504435a1243aeb90b"
TEST_PATH = "policy-engine/tests/unit/fabric/data_plane/test_stream_pool_cleanup_oracle.py"
MODULES = {
    "polisyos.fabric.connectors.pool": "fabric/connectors/pool.py",
    "polisyos.fabric.data_plane.streaming": "fabric/data_plane/streaming.py",
    "polisyos.fabric.data_plane.cursor_store": "fabric/data_plane/cursor_store.py",
    "polisyos.fabric.connectors.sources.event_stream": "fabric/connectors/sources/event_stream.py",
}


def require(condition: bool, message: str) -> None:
    """Keep evidence checks active under Python optimization."""
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    """Verify captured evidence identities and the finite ownership discriminator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--author-ref", required=True)
    parser.add_argument("--stdout-path", required=True)
    parser.add_argument("--xml-path", required=True)
    parser.add_argument("--wrapper-path", required=True)
    args = parser.parse_args()
    git_executable = shutil.which("git")
    require(git_executable is not None, "Git executable unavailable")

    def git(*argv: str) -> bytes:
        # Fixed read-only Git verbs with structured argv, without a shell.
        return subprocess.run(  # noqa: S603
            [git_executable, *argv], cwd=args.repo, check=True, capture_output=True
        ).stdout

    def blob(ref: str, path: str) -> bytes:
        return git("show", f"{ref}:{path}")

    def identity(ref: str, path: str) -> dict[str, str | int]:
        raw = blob(ref, path)
        return {
            "ref": ref,
            "path": path,
            "git_blob": git("rev-parse", f"{ref}:{path}").decode().strip(),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    footprint = git("diff", "--name-status", f"{TEST_SHA}^", TEST_SHA).decode()
    require(footprint == f"A\t{TEST_PATH}\n", "test checkpoint footprint changed")
    require(
        not git("diff", "--name-only", PRODUCT_SHA, ACTUAL_ROOT_SHA, "--", "policy-engine/src"),
        "pinned and actual root production trees differ",
    )
    require(
        not git(
            "diff", "--name-only", HISTORIC_ROOT_SHA, ACTUAL_ROOT_SHA, "--", "policy-engine/src"
        ),
        "historical and actual root production trees differ",
    )
    source_ids = []
    for relative in ["fabric/connectors/pool.py", "fabric/data_plane/streaming.py"]:
        path = "policy-engine/src/polisyos/" + relative
        require(blob(PRODUCT_SHA, path) == blob(HISTORIC_ROOT_SHA, path), path)
    for relative in [
        *MODULES.values(),
        "fabric/connectors/_registry_lifecycle.py",
        "fabric/connectors/sources/_file_common.py",
        "core/artifacts/store.py",
    ]:
        source_ids.append(identity(PRODUCT_SHA, "policy-engine/src/polisyos/" + relative))

    raw_outputs = {
        name: blob(args.author_ref, path)
        for name, path in {
            "stdout": args.stdout_path,
            "xml": args.xml_path,
            "wrapper": args.wrapper_path,
        }.items()
    }
    stdout = raw_outputs["stdout"].decode()
    wrapper = json.loads(raw_outputs["wrapper"])
    require(wrapper["exit"] == 1, "native failed exit lost")
    require(wrapper["target_test_sha"] == TEST_SHA, "native test source mismatch")
    require(wrapper["product_source_sha"] == PRODUCT_SHA, "native product pointer mismatch")
    require(wrapper["actual_heads_before"] == wrapper["actual_heads_after"], "native HEAD drift")
    require(wrapper["actual_heads_before"]["root"] == ACTUAL_ROOT_SHA, "actual root pointer")
    require(
        wrapper["stdout"]["sha256"] == hashlib.sha256(raw_outputs["stdout"]).hexdigest(),
        "stdout hash",
    )
    require(wrapper["stdout"]["bytes"] == len(raw_outputs["stdout"]), "stdout size")
    origins = [
        json.loads(line.removeprefix("B87_ACTUAL_SOURCE "))
        for line in stdout.splitlines()
        if line.startswith("B87_ACTUAL_SOURCE ")
    ]
    require({row["module"] for row in origins} == set(MODULES), "same-child source denominator")
    require(len(origins) == len(MODULES), "duplicate source record")
    for row in origins:
        path = "policy-engine/src/polisyos/" + MODULES[row["module"]]
        require(row["sha256"] == hashlib.sha256(blob(PRODUCT_SHA, path)).hexdigest(), row["module"])
        require(row["origin"] == "/workspace/e02-B-current-coordination/" + path, "foreign origin")

    # XML bytes are hash-bound local captured evidence, not an untrusted network document.
    xml = ET.fromstring(raw_outputs["xml"])  # noqa: S314
    cases = list(xml.iter("testcase"))
    failures = [case for case in cases if case.find("failure") is not None]
    require(len(cases) == 8 and len(failures) == 1, "native case/failure denominator")
    require(not list(xml.iter("error")) and not list(xml.iter("skipped")), "error/skip changed")
    require(
        failures[0].get("name")
        == "test_process_file_stream_cleanup_ownership[process-disconnect-failure]",
        "wrong deciding failure",
    )
    observations = [
        json.loads(match)
        for match in re.findall(r"STREAM_CLEANUP_OBSERVATION (\{[^\n]+\})", stdout)
    ]
    require(len(observations) == 7, "process observation denominator")
    stages = {row["stage"]: row for row in observations}
    require(len(stages) == 7, "duplicate stage")
    failed = stages["process-disconnect-failure"]
    before = failed["before_retry"]
    pending = before["pending_cleanup"]
    require(len(pending) == 1, "one physical pending owner expected")
    owner = next(iter(pending))
    require(
        pending[owner] == {"closed": False, "pending_permit": False, "task_done": None},
        "physical owner predicate",
    )
    require(
        before["available_permits"] == 1 and before["pool_closed"] is True,
        "no semaphore occupancy claim",
    )
    require(before["registry_pending_owner_count"] == 0, "owner already transferred")
    require(failed["same_pool_acquire"] == "PoolClosedError", "closed pool control")
    after = failed["after_registry_retry"]
    require(
        after["pending_cleanup"] == pending and after["disconnect_calls"] == [owner],
        "registry retry reached owner",
    )
    require(after["actual_handles_without_disconnect_confirmation"] == [owner], "old owner changed")
    require(
        len(failed["during_fresh"]["actual_handles_without_disconnect_confirmation"]) == 2,
        "fresh real handle control",
    )
    require(
        failed["after_fresh"]["actual_handles_without_disconnect_confirmation"] == [owner],
        "fresh close rescued old owner",
    )
    require(failed["observer_final_cleanup"]["pending_cleanup"] == {}, "observer cleanup failed")
    require(
        failed["observer_final_cleanup"]["actual_handles_without_disconnect_confirmation"] == [],
        "observer handle remained",
    )
    for row in observations:
        require(row["fresh_real_file_rows"] == 2, "fresh file consumer rows")
        require(
            all(
                row[name]["jsonl_open_fds"] == []
                for name in [
                    "before_retry",
                    "after_registry_retry",
                    "during_fresh",
                    "after_fresh",
                    "observer_final_cleanup",
                ]
            ),
            "unexpected retained JSONL FD",
        )
    startup = stages["startup-owner-retry"]
    require(
        startup["primary_exception_is_injected"] and len(startup["primary_notes"]) == 3,
        "startup primary preservation",
    )
    require(
        startup["before_retry"]["registry_pending_owner_count"] == 1
        and startup["before_retry"]["available_permits"] == 0,
        "startup owner control",
    )
    require(
        startup["after_registry_retry"]["pending_cleanup"] == {}
        and startup["after_registry_retry"]["available_permits"] == 1,
        "startup registry retry",
    )
    direct = [
        json.loads(match) for match in re.findall(r"STREAM_DIRECT_RETRY (\{[^\n]+\})", stdout)
    ]
    require(
        len(direct) == 1 and direct[0]["before"]["session_closed"] is False,
        "direct retained owner input",
    )
    require(
        direct[0]["after"] == {"active": [], "pending": [], "permits": 1, "session_closed": True},
        "second close control",
    )
    sys.stdout.write(
        json.dumps(
            {
                "grade": (
                    "independent_immutable_source_and_captured_native_evidence_audit; "
                    "no_product_import_or_runtime"
                ),
                "git_executable": git_executable,
                "test_identity": identity(TEST_SHA, TEST_PATH),
                "test_tree": git("rev-parse", f"{TEST_SHA}^{{tree}}").decode().strip(),
                "footprint": footprint,
                "product_sha": PRODUCT_SHA,
                "actual_root_sha": ACTUAL_ROOT_SHA,
                "actual_root_tree": git("rev-parse", f"{ACTUAL_ROOT_SHA}^{{tree}}")
                .decode()
                .strip(),
                "actual_root_vs_pinned_production_diff": "ZERO_DIFF",
                "actual_root_vs_historic_production_diff": "ZERO_DIFF",
                "historic_root_vs_pinned_pool_stream_diff": "ZERO_DIFF",
                "source_identities": source_ids,
                "same_child_origins": origins,
                "author_evidence_identities": [
                    identity(args.author_ref, path)
                    for path in [args.stdout_path, args.xml_path, args.wrapper_path]
                ],
                "native_counts": {
                    "cases": 8,
                    "pass": 7,
                    "fail": 1,
                    "error": 0,
                    "skip": 0,
                    "exit": 1,
                },
                "case_names": [case.get("name") for case in cases],
                "observations": observations,
                "direct_observation": direct[0],
                "native_wrapper": wrapper,
                "limitations": [
                    "Author execution is inspected, not replayed by reviewer.",
                    "New session uses a new pool; old closed pool is not reopened.",
                    "EventStreamConnector holds no persistent FD; no FD leak inferred.",
                    "Caller cancellation is gated before the file generator reads.",
                    "No close_stream-specific fault or repeated cancellation claim.",
                    "Four module identities observed; full nested import trace not captured.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
