"""Compare independent complete pytest collection and executed JUnit identities."""

import hashlib
import io
import json
import sys
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from xml.etree import ElementTree

import pytest


class Collection:
    """Retain the actual collection, including every parameter identity."""

    def __init__(self) -> None:
        self.nodes = []

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        """Retain all actual pytest node identities at the collection boundary."""
        self.nodes = [item.nodeid for item in session.items]


def main() -> None:
    """Collect the exact prior invocation and reconcile its own emitted cases."""
    record = json.loads(Path(sys.argv[1]).read_text())
    argv = record["argv"]
    arguments = argv[argv.index("pytest") + 1 :]
    junit = next(arg.split("=", 1)[1] for arg in arguments if arg.startswith("--junitxml="))
    arguments = [arg for arg in arguments if not arg.startswith("--junitxml=")]
    collected = Collection()
    compact = "--compact" in sys.argv[2:]
    collection_stdout, collection_stderr = io.StringIO(), io.StringIO()
    if compact:
        with redirect_stdout(collection_stdout), redirect_stderr(collection_stderr):
            rc = pytest.main([*arguments, "--collect-only"], plugins=[collected])
    else:
        rc = pytest.main([*arguments, "--collect-only"], plugins=[collected])
    cases = ElementTree.parse(junit).findall(".//testcase")  # noqa: S314 - local pytest output
    expected = set(collected.nodes)
    # Resolve JUnit's dotted class path against the complete collected identities.
    index = {}
    for node in expected:
        parts = node.split("::")
        key = (".".join([parts[0][:-3].replace("/", "."), *parts[1:-1]]), parts[-1])
        if key in index:
            raise RuntimeError("ambiguous JUnit identity mapping")
        index[key] = node
    executed = []
    unresolved = []
    failures = []
    for case in cases:
        key = (case.attrib.get("classname"), case.attrib.get("name"))
        if key not in index:
            unresolved.append(case.attrib)
            continue
        node = index[key]
        executed.append(node)
        if list(case):
            failures.append({"nodeid": node, "outcomes": [child.tag for child in case]})
    observed = set(executed)
    result = {
        "denominator": (
            "complete actual pytest collection versus complete executed JUnit testcase set"
        ),
        "collection_returncode": int(rc),
        "execution_returncode": record["returncode"],
        "collected_identities": sorted(expected),
        "executed_identities": sorted(observed),
        "missing_executions": sorted(expected - observed),
        "unexpected_executions": sorted(observed - expected),
        "ambiguous_or_unresolved": unresolved,
        "duplicate_collection": len(collected.nodes) != len(expected),
        "duplicate_execution": len(executed) != len(observed),
        "nonpassing_executions": failures,
    }
    if compact:
        result.pop("collected_identities")
        result.pop("executed_identities")
        result.update({
            "collected_count": len(expected),
            "executed_count": len(observed),
            "collected_identity_hash": hashlib.sha256(
                json.dumps(sorted(expected), separators=(",", ":")).encode()
            ).hexdigest(),
            "executed_identity_hash": hashlib.sha256(
                json.dumps(sorted(observed), separators=(",", ":")).encode()
            ).hexdigest(),
            "duplicate_collection_identities": {
                key: count for key, count in Counter(collected.nodes).items() if count > 1
            },
            "duplicate_execution_identities": {
                key: count for key, count in Counter(executed).items() if count > 1
            },
        })
        if rc:
            result["failed_collection_stdout"] = collection_stdout.getvalue()
            result["failed_collection_stderr"] = collection_stderr.getvalue()
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    if (
        rc
        or expected != observed
        or unresolved
        or result["duplicate_collection"]
        or result["duplicate_execution"]
    ):
        raise SystemExit(1)
    # Collection reconciliation is not a green claim about the separately recorded execution.


if __name__ == "__main__":
    main()
