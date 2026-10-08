"""Remove only operation-bound WVS response-policy forwarding, keeping real SQL."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

TARGET = "test_wvs_bulk_resolves_current_policy_once_per_operation"
EVENTS = []
ORIGINALS = []
CURRENT = None


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    global CURRENT
    if item.originalname != TARGET:
        return
    CURRENT = item.nodeid
    from polisyos.data_forge.domains.catalog.batch.core_sources import loaders
    original = loaders._normalize_wvs_response_value_typed
    original_bulk = loaders._load_wvs_bulk_duckdb
    original_snapshot = loaders._material_file_snapshot

    def normalize(indicator, raw_value, **kwargs):
        result = original(indicator, raw_value)
        EVENTS.append({"nodeid": CURRENT, "kind": "actual_normalizer_without_forwarding", "indicator": indicator,
                       "raw_value": raw_value, "omitted_response_type": kwargs.get("response_type"), "actual_result": result})
        return result

    def snapshot(path, **kwargs):
        result = original_snapshot(path, **kwargs)
        EVENTS.append({"nodeid": CURRENT, "kind": "actual_policy_snapshot_read", "path": str(path)})
        return result

    def bulk(*args, **kwargs):
        result = original_bulk(*args, **kwargs)
        EVENTS.append({"nodeid": CURRENT, "kind": "actual_duckdb_bulk_result", "actual_rows": result})
        return result

    ORIGINALS.extend([(loaders, "_normalize_wvs_response_value_typed", original),
                      (loaders, "_load_wvs_bulk_duckdb", original_bulk),
                      (loaders, "_material_file_snapshot", original_snapshot)])
    loaders._normalize_wvs_response_value_typed = normalize
    loaders._load_wvs_bulk_duckdb = bulk
    loaders._material_file_snapshot = snapshot


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_teardown(item, nextitem):
    global CURRENT
    yield
    if item.originalname == TARGET:
        for owner, name, original in reversed(ORIGINALS):
            setattr(owner, name, original)
        ORIGINALS.clear()
        CURRENT = None


def pytest_sessionfinish(session, exitstatus):
    (Path(os.environ["ORCH02_OUTPUT_DIR"]) / "wvs-events.json").write_text(json.dumps({
        "schema": "orch02r2.actual-wvs-operation-policy-removal.v1", "raw_pytest_exitstatus": int(exitstatus),
        "removed_quantity": "Only response_type forwarding; original normalizer reloads actual policy for each real SQL cell",
        "retained": ["real DuckDB CSV relation/filter/aggregation", "actual current snapshot policy reader", "unchanged source/test bytes/markers/owned assertions"],
        "events": EVENTS,
    }, indent=2) + "\n")
