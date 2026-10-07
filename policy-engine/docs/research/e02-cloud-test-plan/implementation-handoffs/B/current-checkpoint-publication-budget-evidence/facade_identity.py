"""Observe exact artifact facade identity in both fresh import orders."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import inspect
import json
import subprocess
from pathlib import Path
from typing import get_type_hints


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--order", choices=["checkpoint-first", "facade-first"], required=True)
    args = parser.parse_args()
    repo = Path("/workspace/e02-B-current-execution-state")
    target = "bc958e8efface67193a1347e867cc7567dbfc8bc"
    actual = subprocess.check_output(  # noqa: S603 - fixed read-only Git observations
        ["/usr/bin/git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    assert actual == target  # noqa: S101 - exact source and identity oracle
    names = ["polisyos.scientist.orchestration.engine.checkpoint", "polisyos.core.artifacts"]
    if args.order == "facade-first":
        names.reverse()
    for name in names:
        importlib.import_module(name)
    checkpoint = importlib.import_module("polisyos.scientist.orchestration.engine.checkpoint")
    facade = importlib.import_module("polisyos.core.artifacts")
    canonical = importlib.import_module("polisyos.core.artifacts.async_store")
    identities = {
        name: getattr(checkpoint, name) is getattr(facade, name) is getattr(canonical, name)
        for name in [
            "AsyncArtifactStoreAdapter",
            "AsyncFileSystemArtifactStore",
            "ensure_async_artifact_store",
        ]
    }
    assert all(identities.values())  # noqa: S101 - exact source and identity oracle
    origins = {}
    for module in [checkpoint, facade, canonical]:
        path = Path(module.__file__).resolve()
        relative = path.relative_to(repo).as_posix()
        expected = subprocess.check_output(  # noqa: S603 - fixed read-only Git observations
            ["/usr/bin/git", "-C", str(repo), "show", f"{target}:{relative}"]
        )
        assert expected == path.read_bytes()  # noqa: S101 - exact source and identity oracle
        origins[module.__name__] = {
            "path": relative,
            "sha256": hashlib.sha256(expected).hexdigest(),
        }
    annotations = get_type_hints(checkpoint.CheckpointPublicationBudget)
    assert set(annotations) == {"deadline_monotonic", "owner_is_current", "caller_cancelled"}  # noqa: S101 - exact source and identity oracle
    print(  # noqa: T201 - complete deciding stdout
        json.dumps(
            {
                "target_sha": target,
                "order": args.order,
                "object_identity": identities,
                "origins": origins,
                "budget_annotations": {k: str(v) for k, v in annotations.items()},
                "fixed_legacy_node_signature": str(
                    inspect.signature(checkpoint.AsyncCheckpointHook.on_node_complete_async)
                ),
                "import_cycle_observed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
