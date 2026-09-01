"""Emit the exact path-to-node identity collected by one timed pytest child."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from tools.lib.fs import atomic_write_text
from tools.lib.timing import (
    PYTEST_WORKLOAD_PREDICATE_PROVENANCE,
    PYTEST_WORKLOAD_SCHEMA_VERSION,
)
from tools.lib.timing import (
    pytest_node_map_digest as _pytest_node_map_digest,
)

_ATTEMPT_ID_ENV = "POLISYOS_PYTEST_RECEIPT_ATTEMPT_ID"
_OUTPUT_PATH_ENV = "POLISYOS_PYTEST_RECEIPT_SIDECAR"
_REPO_ROOT_ENV = "POLISYOS_PYTEST_RECEIPT_REPO_ROOT"
_TEST_PATHS_ENV = "POLISYOS_PYTEST_RECEIPT_TEST_PATHS"
_COLLECTED_NODE_IDS: tuple[str, ...] | None = None


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Remember the complete pre-deselection collection for the receipt gate."""

    global _COLLECTED_NODE_IDS  # noqa: PLW0603 - one isolated pytest child owns this plugin.
    _COLLECTED_NODE_IDS = tuple(item.nodeid for item in items)


def pytest_collection_finish(session: pytest.Session) -> None:
    """Persist the exact nodes pytest retained for execution in this child."""

    repo_root = Path(os.environ[_REPO_ROOT_ENV]).resolve()
    output_path = Path(os.environ[_OUTPUT_PATH_ENV]).resolve()
    output_path.relative_to(repo_root)
    selected = json.loads(os.environ[_TEST_PATHS_ENV])
    if (
        not isinstance(selected, list)
        or not selected
        or any(not isinstance(path, str) for path in selected)
        or len(selected) != len(set(selected))
    ):
        raise ValueError("timed pytest receipt requires unique selected test paths")

    selected_by_absolute = {
        (repo_root / path).resolve(): path
        for path in selected
    }
    node_ids_by_path: dict[str, list[str]] = {path: [] for path in selected}
    unmatched_node_ids: list[str] = []
    final_node_ids = tuple(item.nodeid for item in session.items)
    if (
        _COLLECTED_NODE_IDS is None
        or len(_COLLECTED_NODE_IDS) != len(final_node_ids)
        or set(_COLLECTED_NODE_IDS) != set(final_node_ids)
    ):
        raise ValueError(
            "pytest receipt selection changed the complete collected workload"
        )
    for item in session.items:
        selected_path = selected_by_absolute.get(Path(str(item.path)).resolve())
        if selected_path is None:
            unmatched_node_ids.append(item.nodeid)
            continue
        node_ids_by_path[selected_path].append(item.nodeid)
    if unmatched_node_ids:
        raise ValueError(
            "pytest receipt collected nodes outside the selected paths:"
            + repr(unmatched_node_ids)
        )
    if any(not node_ids for node_ids in node_ids_by_path.values()):
        raise ValueError("timed pytest receipt collected no nodes for a selected path")
    if sum(len(node_ids) for node_ids in node_ids_by_path.values()) != len(session.items):
        raise ValueError("pytest receipt node map does not cover the executed session")

    config_source = session.config.inipath
    if config_source is None:
        raise ValueError("timed pytest receipt requires an explicit pytest config")
    config_path = config_source.resolve().relative_to(repo_root).as_posix()
    source_digests = {
        path: _sha256((repo_root / path).read_bytes())
        for path in selected
    }
    workload_identity = {
        "schema_version": PYTEST_WORKLOAD_SCHEMA_VERSION,
        "predicate_provenance": PYTEST_WORKLOAD_PREDICATE_PROVENANCE,
        "test_paths": selected,
        "source_digests": source_digests,
        "pytest_version": pytest.__version__,
        "config_path": config_path,
        "config_digest": _sha256(config_source.read_bytes()),
        "node_map_digest": _pytest_node_map_digest(node_ids_by_path),
    }
    payload = {
        "attempt_id": os.environ[_ATTEMPT_ID_ENV],
        "node_ids_by_path": node_ids_by_path,
        "workload_identity": workload_identity,
    }
    atomic_write_text(
        output_path,
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
    )
