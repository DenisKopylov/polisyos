"""Reconcile complete unittest collection with an actual verbose graph test run."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


def _identities(suite: unittest.TestSuite) -> Iterator[str]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _identities(item)
        else:
            yield item.id()


def main() -> None:
    """Read the deciding command and compare every independently loaded identity."""
    record = json.loads(Path(sys.argv[1]).read_text())
    arguments = record["argv"][record["argv"].index("unittest") + 1 :]
    modules = [argument for argument in arguments if not argument.startswith("-")]
    loader = unittest.TestLoader()
    collected = list(_identities(loader.loadTestsFromNames(modules)))
    matches = re.findall(r"^test_\w+ \(([\w.]+)\) \.\.\. (.+)$", record["stderr"], re.MULTILINE)
    executed = [identity for identity, _ in matches]
    expected, observed = set(collected), set(executed)
    failures = [identity for identity, outcome in matches if outcome != "ok"]
    result = {
        "synthetic": True,
        "scope": "candidate_only_test_identity_reconciliation",
        "denominator": "complete TestLoader identities versus actual verbose execution identities",
        "path_denominator": [module.replace(".", "/") + ".py" for module in modules],
        "file_type_denominator": ".py",
        "execution_returncode": record["returncode"],
        "collection_errors": loader.errors,
        "collected_count": len(collected),
        "executed_count": len(executed),
        "collected_identity_hash": hashlib.sha256(
            json.dumps(sorted(expected), separators=(",", ":")).encode()
        ).hexdigest(),
        "executed_identity_hash": hashlib.sha256(
            json.dumps(sorted(observed), separators=(",", ":")).encode()
        ).hexdigest(),
        "missing_executions": sorted(expected - observed),
        "unexpected_executions": sorted(observed - expected),
        "nonpassing_executions": failures,
        "duplicate_collection_identities": {
            identity: count for identity, count in Counter(collected).items() if count > 1
        },
        "duplicate_execution_identities": {
            identity: count for identity, count in Counter(executed).items() if count > 1
        },
    }
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    if (
        record["returncode"]
        or loader.errors
        or expected != observed
        or failures
        or len(collected) != len(expected)
        or len(executed) != len(observed)
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
