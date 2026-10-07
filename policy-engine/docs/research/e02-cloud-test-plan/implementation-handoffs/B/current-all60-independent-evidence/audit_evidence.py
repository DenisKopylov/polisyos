"Content-bind existing deciding receipts; no runtime execution or closure decision."

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter

ROOT = "99af508a5282854f3e609c5a94bc19ac55893dde"
PREFIX = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/"
SPECS = [
    ("run", ROOT, "current-runtime-retry.json"),
    ("run-executor", ROOT, "current-runtime-executor.json"),
    ("run-process", ROOT, "current-runtime-process-setup.json"),
    ("dur", ROOT, "current-durability.json"),
    ("dur-settlement", ROOT, "current-durability-settlement.json"),
    ("dur-independent", ROOT, "current-independent-budget-cas.json"),
    ("cas", ROOT, "cas-batch-completion.json"),
    ("cas-put", ROOT, "cas-current-put.json"),
    ("cas-admission", ROOT, "cas-current-admission.json"),
    ("cas-snapshot", ROOT, "cas-verification-snapshot.json"),
    ("adapters", ROOT, "current-adapters.json"),
    ("stream", ROOT, "current-pool-stream-contract.json"),
    ("receiver", ROOT, "current-receiver-consumer.json"),
    ("exe", ROOT, "current-cache-recovery.json"),
    ("resume", ROOT, "current-resume-oracle.json"),
    ("required", ROOT, "current-required-resume.json"),
    (
        "exe-owner",
        "e8a72c11bc608ab12fd1db21bd52fa881bace1a7",
        "current-exe-owner-independent-review/review.json",
    ),
    (
        "sta",
        "ee8c7a8a228593e4009e5a2f1e54df3226fa82af",
        "current-sta-independent-review/review-final.json",
    ),
    ("cmp", "41fd9c0479606c4e1b461489b55190a1c43e03e7", "current-composition-final.json"),
    ("payload", ROOT, "current-composition-payload.json"),
    ("publication", ROOT, "current-composition-publication-roots.json"),
    ("identity", "612351236667277f0f73573a19da9692d045e579", "current-composition-identity.json"),
    ("jit", "6e217365951ab6d61910ae84714ca1f6d3abf33c", "current-composition-jit.json"),
    (
        "solver",
        "16b1b982471508feef149eefc70203562c6a2a6f",
        "current-durability-evidence/composition-acceptance-review/solver-54ef-review.json",
    ),
    (
        "source-graph",
        "8495fe40a4c8655b7b9c76a6e6008d275d9697b2",
        "current-durability-evidence/b74-review/successor-061-review.json",
    ),
    (
        "snapshot-independent",
        "8580742814246ecccaca938e51dd0ff614796b3c",
        "current-durability-evidence/b152-review/receipt.json",
    ),
]


def git(*args: str) -> bytes:
    # Fixed Git executable and immutable repository metadata arguments; no shell.
    return subprocess.check_output(["/usr/local/bin/git", *args], stderr=subprocess.DEVNULL)  # noqa: S603


def full(ref: str) -> str:
    return git("rev-parse", ref).decode().strip()


def blob(ref: str, path: str) -> bytes:
    return git("show", f"{ref}:{path}")


def bound_artifacts(value: object, ref: str) -> list[dict]:
    result = []
    if isinstance(value, dict):
        path = value.get("path", value.get("ref"))
        sha = value.get("sha256")
        if (
            isinstance(path, str)
            and path.startswith(PREFIX)
            and isinstance(sha, str)
            and (len(sha) == 64)
        ):
            artifact_ref = value.get("git_ref", value.get("git_sha", ref))
            raw = blob(artifact_ref, path)
            actual = hashlib.sha256(raw).hexdigest()
            if not actual == sha:
                raise ValueError((path, "hash mismatch", actual, sha))
            if not value.get("bytes", len(raw)) == len(raw):
                raise ValueError((path, "size mismatch"))
            result.append(
                {"git_sha": full(artifact_ref), "path": path, "sha256": actual, "bytes": len(raw)}
            )
        for nested in value.values():
            if isinstance(nested, (list, dict)):
                result.extend(bound_artifacts(nested, ref))
    elif isinstance(value, list):
        for nested in value:
            result.extend(bound_artifacts(nested, ref))
    return result


def main() -> None:
    receipts = {}
    all_artifacts = {}
    for key, ref, suffix in SPECS:
        ref = full(ref)
        path = PREFIX + suffix
        raw = blob(ref, path)
        record = json.loads(raw)
        checks = []
        for index, check in enumerate(record.get("checks", [])):
            artifacts = bound_artifacts(check, ref)
            output = check.get("output")
            if isinstance(output, str) and output.startswith(PREFIX):
                output_raw = blob(ref, output)
                artifacts.append(
                    {
                        "git_sha": ref,
                        "path": output,
                        "sha256": hashlib.sha256(output_raw).hexdigest(),
                        "bytes": len(output_raw),
                        "hash_basis": (
                            "independently computed committed blob; no absent author hash invented"
                        ),
                    }
                )
            cases = []
            for item in artifacts:
                all_artifacts[item["git_sha"], item["path"]] = item
                if item["path"].endswith(".xml"):
                    xml = blob(item["git_sha"], item["path"])
                    if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                        raise ValueError(
                            "XML entity declarations are outside this evidence profile"
                        )
                    # Hash-bound repository JUnit XML; entity declarations rejected above.
                    tree = ET.fromstring(xml)  # noqa: S314
                    for case in tree.iter("testcase"):
                        state = "PASS"
                        for tag in ("failure", "error", "skipped"):
                            if case.find(tag) is not None:
                                state = tag.upper()
                        cases.append(
                            {
                                "nodeid": case.attrib.get("classname", "")
                                + "::"
                                + case.attrib.get("name", ""),
                                "state": state,
                            }
                        )
            target = check.get(
                "target_sha",
                check.get("source_before", {}).get("sha", record.get("execution_target_sha")),
            )
            wrappers = []
            for item in artifacts:
                if item["path"].endswith(".json") and any(
                    part in item["path"] for part in ("wrapper", "capture")
                ):
                    wrappers.append(
                        {
                            "artifact": item,
                            "record": json.loads(blob(item["git_sha"], item["path"])),
                        }
                    )
            wrapper = wrappers[0]["record"] if wrappers else {}
            command = wrapper.get("argv", check.get("command", check.get("command_argv")))
            environment = check.get("environment", wrapper.get("environment", wrapper.get("env")))
            input_closure = check.get("input_closure", record.get("input_closure"))
            if input_closure is None:
                input_closure = {
                    "basis": (
                        "independently reconciled immutable original "
                        "command/source/test/probe/artifact identities; no "
                        "missing author declaration invented"
                    ),
                    "command": command,
                    "source_before": check.get("source_before", wrapper.get("source_before")),
                    "test_source_commit": check.get("test_source_commit"),
                    "test_source_sha256": wrapper.get("test_source_sha256"),
                    "artifacts": artifacts,
                    "original_check_pointer": f"{ref}:{path}#/checks/{index}",
                    "scope": (
                        "Named bounded test/probe inputs only; retain original "
                        "overlay/fixture/source qualifications, no "
                        "production-data or backend inference."
                    ),
                }
            checks.append(
                {
                    "index": index,
                    "name": check.get("id", check.get("name", check.get("kind"))),
                    "receipt_pointer": f"#/checks/{index}",
                    "target_sha": target,
                    "target_tree": full(target + "^{tree}") if target else None,
                    "command": command,
                    "cwd": check.get(
                        "cwd", wrapper.get("cwd", check.get("environment", {}).get("cwd"))
                    ),
                    "environment": environment,
                    "input_closure": input_closure,
                    "wrapper_identities": [item["artifact"] for item in wrappers],
                    "outcome": check.get("outcome"),
                    "actual_committed_artifacts": artifacts,
                    "native_xml_census": {
                        "cases": len(cases),
                        "states": dict(Counter(case["state"] for case in cases)),
                        "node_state_list_sha256": hashlib.sha256(
                            json.dumps(cases, sort_keys=True).encode()
                        ).hexdigest(),
                        "case_locators": (
                            "Exact classname/name/status remain in the bound "
                            "committed XML artifacts; no all-green criterion "
                            "inference."
                        ),
                    },
                    "qualification": (
                        "Read exact source/input/overlay and procedural "
                        "qualifications at this immutable check pointer; "
                        "count/exit alone has no closure authority."
                    ),
                }
            )
        receipts[key] = {
            "git_sha": ref,
            "git_tree": full(ref + "^{tree}"),
            "path": path,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "checks": checks,
            "admission_qualification": record.get(
                "admission",
                (
                    "No blanket admission claim inferred; retain original "
                    "per-check source/projection/resume qualification."
                ),
            ),
            "closure_ids": record.get("closure_ids", []),
        }
    json.dump(
        {
            "schema": "polisyos.e02.B.independent.evidence-catalog.v1",
            "root_source_sha": ROOT,
            "receipts": receipts,
            "check_count": sum(len(r["checks"]) for r in receipts.values()),
            "unique_check_artifacts": len(all_artifacts),
            "unique_check_artifact_bytes": sum(a["bytes"] for a in all_artifacts.values()),
            "scope": (
                "Existing immutable receipts/deciding output bytes and "
                "native XML names read only. No runtime rerun, "
                "product/source edit, new checkout or admission "
                "reconstruction."
            ),
            "closure_ids": [],
        },
        sys.stdout,
        ensure_ascii=False,
        indent=2,
    )
    sys.stdout.write("" + "\n")


if __name__ == "__main__":
    main()
