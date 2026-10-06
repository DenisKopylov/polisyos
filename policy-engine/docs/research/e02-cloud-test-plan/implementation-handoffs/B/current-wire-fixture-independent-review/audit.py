"""Inspect immutable WIRE fixture/source objects and captured outputs only.

This driver never imports product modules, executes pytest, or runs a decoder.
Runtime observations belong to the author/root whose complete outputs it reads.
"""

import ast
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path("/workspace/e02-B-current-runtime")
BASE = "562ca2c25ca68fd90c4d5225b1b33fdd5b161940"
TARGET = "a4dd3b25c369be19c80727395c689a121950fc64"
ROOT = "4e7a4924e6466e1b4eaa39b504435a1243aeb90b"
TEST = "policy-engine/tests/unit/remediation/test_wire_01.py"
FUNCTION = "test_artifact_ref_and_artifact_id_tags_are_compatible"
PREFIX = "policy-engine/src/polisyos/scientist/orchestration/engine/"
ROOT_XML = Path(
    "/workspace/e02-B-current-coordination/.polisyos/e02-B-current/raw/review/final-B-cohort.xml"
)
ROOT_XML_HASH = "f7fa098c6b921b7b9c0188f03997bc6962db1f3849826fd3e9fa61e9b6c6800b"
PUBLICATION = "dfb1fa67a6d28bb3fb53712588666254c42b6ab2"
DOCUMENTS = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/"
HANDOFF = DOCUMENTS + "current-wire-envelope-consumer.json"
EVIDENCE = DOCUMENTS + "current-wire-envelope-consumer-evidence/"


def _require(condition: bool) -> None:
    if not condition:
        raise RuntimeError("Captured evidence invariant mismatch")


def git(*args: str) -> bytes:
    # All callers use fixed read-only Git commands and immutable SHA/path values.
    return subprocess.check_output(["/usr/bin/git", *args], cwd=REPO)  # noqa: S603


def raw(sha: str, path: str) -> bytes:
    return git("show", sha + ":" + path)


def ref(sha: str, path: str) -> dict[str, str | int]:
    data = raw(sha, path)
    return {
        "source_sha": sha,
        "path": path,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def assertions(node: ast.AST) -> list[str]:
    return [
        ast.dump(row, include_attributes=False)
        for row in ast.walk(node)
        if isinstance(row, ast.Assert)
    ]


def author_evidence() -> dict[str, object]:
    handoff = json.loads(raw(PUBLICATION, HANDOFF))
    bound = []
    for expected in handoff["evidence_files"]:
        actual = ref(PUBLICATION, expected["path"])
        _require(all(actual[key] == expected[key] for key in ("path", "bytes", "sha256")))
        bound.append(actual)
    _require(len(bound) == 18)
    context = json.loads(raw(PUBLICATION, EVIDENCE + "source-context.json"))
    identity_count = 0
    absent_count = 0
    for root in context["roots"]:
        for identity in root["identities"]:
            if identity["state"] == "present":
                actual = ref(identity["source_sha"], identity["path"])
                _require(all(actual[key] == identity[key] for key in actual))
                _require(
                    git("rev-parse", identity["source_sha"] + ":" + identity["path"])
                    .decode()
                    .strip()
                    == identity["git_blob"]
                )
                identity_count += 1
            else:
                # Read-only existence lookup on the authenticated Git object locator.
                result = subprocess.run(  # noqa: S603
                    [
                        "/usr/bin/git",
                        "cat-file",
                        "-e",
                        identity["source_sha"] + ":" + identity["path"],
                    ],
                    cwd=REPO,
                    capture_output=True,
                    check=False,
                )
                _require(result.returncode != 0)
                absent_count += 1
    profile_summary = []
    profile_packet = json.loads(raw(PUBLICATION, EVIDENCE + "actual-profiles.json"))
    for mode in ("native", "remove"):
        wrapper = json.loads(raw(PUBLICATION, EVIDENCE + mode + ".json"))
        _require(wrapper["target_sha"] == TARGET == wrapper["head_after"])
        _require(wrapper["target_tree"] == git("rev-parse", TARGET + "^{tree}").decode().strip())
        stdout = raw(PUBLICATION, EVIDENCE + mode + ".txt")
        _require(len(stdout) == wrapper["stdout"]["bytes"])
        _require(hashlib.sha256(stdout).hexdigest() == wrapper["stdout"]["sha256"])
        leading = json.loads(stdout.decode().splitlines()[0])
        _require(
            leading["driver_sha256"] == ref(PUBLICATION, EVIDENCE + "run_wire_profile.py")["sha256"]
        )
        _require(
            leading["wire_sha256"] == ref(TARGET, PREFIX + "runner/serialization.py")["sha256"]
        )
        # XML bytes are already bound to authenticated captured-output hashes.
        xml = ET.fromstring(raw(PUBLICATION, EVIDENCE + mode + ".xml"))  # noqa: S314
        cases = xml.findall(".//testcase")
        keys = {(case.get("classname"), case.get("name")) for case in cases}
        _require(len(keys) == len(cases))
        counts = Counter()
        file_counts = defaultdict(Counter)
        selected = []
        workers = []
        for case in cases:
            if case.find("error") is not None:
                grade = "ERROR"
            elif case.find("failure") is not None:
                grade = "FAIL"
            elif case.find("skipped") is not None:
                grade = "SKIP"
            else:
                grade = "PASS"
            counts[grade] += 1
            file_counts[case.get("classname").split(".Test")[0]][grade] += 1
            row = {"attributes": case.attrib, "grade": grade}
            if FUNCTION in case.get("name", ""):
                failure = case.find("failure")
                if failure is not None:
                    row["message"] = failure.get("message")
                    _require("Unsupported runner wire type tag: 'model'" in row["message"])
                    _require("restored = deserialize_state(payload)" in failure.text)
                    _require("_decode_wire_tag" in failure.text)
                selected.append(row)
            if "test_real_worker_process_consumes_state_and_emits_exact_typed_outcome" in case.get(
                "name", ""
            ):
                workers.append(row)
        _require(counts == ({"PASS": 119} if mode == "native" else {"FAIL": 6}))
        _require(wrapper["actual_child_exit"] == (0 if mode == "native" else 1))
        packet_profile = next(row for row in profile_packet["profiles"] if row["mode"] == mode)
        _require(counts == packet_profile["case_counts"])
        _require(wrapper == packet_profile["wrapper"])
        _require(len(selected) == 6)
        _require(len(workers) == (2 if mode == "native" else 0))
        profile_summary.append(
            {
                "mode": mode,
                "case_counts": counts,
                "whole_file_counts": file_counts,
                "actual_child_exit": wrapper["actual_child_exit"],
                "wall_seconds": wrapper["wall_s"],
                "rss_kib": wrapper["maxrss_kib"],
                "six_actual_reader_cases": selected,
                "actual_own_worker_cases": workers,
                "wrapper": wrapper,
            }
        )
    native_keys = {
        row["attributes"]["name"] for row in profile_summary[0]["six_actual_reader_cases"]
    }
    removed_keys = {
        row["attributes"]["name"] for row in profile_summary[1]["six_actual_reader_cases"]
    }
    _require(native_keys == removed_keys)
    source = raw(TARGET, PREFIX + "runner/serialization.py").decode()
    function = next(
        row for row in ast.parse(source).body if getattr(row, "name", None) == "_decode_wire_tag"
    )
    original = "\n".join(source.splitlines()[function.lineno - 1 : function.end_lineno]) + "\n"
    tree = ast.parse(original)
    removed = [
        row
        for row in tree.body[0].body
        if isinstance(row, ast.If) and ast.unparse(row.test) == "kind == _WIRE_MODEL"
    ]
    _require(len(removed) == 1)
    tree.body[0].body.remove(removed[0])
    remove_log = raw(PUBLICATION, EVIDENCE + "remove.txt").decode()
    overlay_record = json.loads(remove_log.splitlines()[1])
    _require(
        hashlib.sha256(original.encode()).hexdigest() == overlay_record["original_function_sha256"]
    )
    _require(
        hashlib.sha256(ast.dump(tree).encode()).hexdigest() == overlay_record["overlay_ast_sha256"]
    )
    return {
        "publication_sha": PUBLICATION,
        "publication_tree": git("rev-parse", PUBLICATION + "^{tree}").decode().strip(),
        "handoff": ref(PUBLICATION, HANDOFF),
        "bound_companion_count": len(bound),
        "bound_companion_bytes": sum(row["bytes"] for row in bound),
        "bound_companions": bound,
        "source_context_present_identities_verified": identity_count,
        "source_context_absent_identities_verified": absent_count,
        "author_profiles": profile_summary,
        "reader_removal_canonical_AST_matches_recorded_overlay": True,
        "reviewer_runtime_execution": False,
    }


def main() -> None:
    before = ast.parse(raw(BASE, TEST))
    after = ast.parse(raw(TARGET, TEST))
    old_function = next(row for row in before.body if getattr(row, "name", None) == FUNCTION)
    new_function = next(row for row in after.body if getattr(row, "name", None) == FUNCTION)
    old_asserts = assertions(old_function)
    new_asserts = assertions(new_function)
    _require(len(old_asserts) == 8 and len(new_asserts) == 15)
    _require(all(row in new_asserts for row in old_asserts))
    old_other = [
        ast.dump(row, include_attributes=False)
        for row in before.body
        if getattr(row, "name", None) != FUNCTION
    ]
    new_other = [
        ast.dump(row, include_attributes=False)
        for row in after.body
        if getattr(row, "name", None) != FUNCTION
    ]
    _require(old_other == new_other)
    changed = git("diff", "--name-only", BASE, TARGET).decode().splitlines()
    _require(changed == [TEST])
    _require(git("diff", "--name-only", BASE, TARGET, "--", "policy-engine/src") == b"")
    paths = [
        PREFIX + "runner/serialization.py",
        "policy-engine/tests/unit/scientist/orchestration/engine/runner/test_serialization.py",
        "policy-engine/tests/unit/scientist/orchestration/engine/runner/test_serialization_e02.py",
        PREFIX + "retry.py",
        PREFIX + "runner/_activity_worker.py",
        "policy-engine/src/polisyos/core/artifacts/ids.py",
        "policy-engine/src/polisyos/core/artifacts/manifest.py",
        PREFIX + "state.py",
        TEST,
    ]
    identities = [
        {
            "path": path,
            "root4e": ref(ROOT, path),
            "candidate": ref(TARGET, path),
            "same_bytes": raw(ROOT, path) == raw(TARGET, path),
        }
        for path in paths
    ]
    xml_bytes = ROOT_XML.read_bytes()
    _require(len(xml_bytes) == 1333443)
    _require(hashlib.sha256(xml_bytes).hexdigest() == ROOT_XML_HASH)
    root_cases = []
    root_worker_cases = []
    root_file_counts = defaultdict(Counter)
    # The complete local XML digest/size was checked immediately above.
    for case in ET.fromstring(xml_bytes).iter("testcase"):  # noqa: S314
        classname = case.get("classname", "")
        if classname.startswith(
            (
                "tests.unit.remediation.test_wire_01",
                "tests.unit.scientist.orchestration.engine.runner.test_serialization",
            )
        ):
            if case.find("error") is not None:
                grade = "ERROR"
            elif case.find("failure") is not None:
                grade = "FAIL"
            elif case.find("skipped") is not None:
                grade = "SKIP"
            else:
                grade = "PASS"
            root_file_counts[classname.split(".Test")[0]][grade] += 1
            if "test_real_worker_process_consumes_state_and_emits_exact_typed_outcome" in case.get(
                "name", ""
            ):
                root_worker_cases.append({"attributes": case.attrib, "grade": grade})
        if FUNCTION in case.get("name", ""):
            root_cases.append(
                {
                    "attributes": case.attrib,
                    "reports": [
                        {"tag": row.tag, "attributes": row.attrib, "text": row.text} for row in case
                    ],
                }
            )
    _require(len(root_cases) == 2)
    _require(
        all(
            row["reports"][0]["attributes"]["message"] == "KeyError: 'inputs'" for row in root_cases
        )
    )
    sys.stdout.write(
        json.dumps(
            {
                "result": "PASS_BOUNDED_SOURCE_AND_CAPTURED_OUTPUT_CONSISTENCY",
                "mode": (
                    "Read-only Git/AST/hash/XML; no product imports, decoder or pytest execution"
                ),
                "base_sha": BASE,
                "candidate_sha": TARGET,
                "candidate_tree": git("rev-parse", TARGET + "^{tree}").decode().strip(),
                "changed_tracked_paths": changed,
                "source_changed_paths": [],
                "ast": {
                    "all_other_module_statements_identical": True,
                    "original_assertions": len(old_asserts),
                    "candidate_assertions": len(new_asserts),
                    "all_original_assertions_preserved": True,
                    "old_assertion_source": [
                        ast.unparse(row)
                        for row in ast.walk(old_function)
                        if isinstance(row, ast.Assert)
                    ],
                },
                "source_inputs": identities,
                "root4e_junit_input": {
                    "path": str(ROOT_XML),
                    "bytes": len(xml_bytes),
                    "sha256": ROOT_XML_HASH,
                    "scope": "Captured root execution, not runtime executed by this reviewer",
                },
                "root4e_exact_cases": root_cases,
                "root4e_selected_whole_file_counts": root_file_counts,
                "root4e_actual_worker_cases": root_worker_cases,
                "author_evidence_audit": author_evidence(),
                "historical_qualification": (
                    "Both captured failures precede deserialize_state; preserve literal FAIL. "
                    "Revised fixture supplies the unchanged producer's actual v2 envelope "
                    "and independently authored legacy inputs; it does not retroactively "
                    "alter root4e or prove full B94 closure."
                ),
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
