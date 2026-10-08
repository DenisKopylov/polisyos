"""Observe canonical cache/real sessions and optionally remove only handle reuse."""
from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

import pytest

LEGACY = "test_real_catalog_session_is_reused_and_closed_by_legacy_api"
PARALLEL = "test_parallel_observation_ingest_uses_eurostat_async_path"
EVENTS = []
REPORTS = []
RESTORE = []
CURRENT = None


def record(kind, **data):
    EVENTS.append({"nodeid": CURRENT, "kind": kind, **data})


def patch(owner, name, value):
    had_local = name in vars(owner)
    prior = vars(owner).get(name) if had_local else None
    RESTORE.append((owner, name, had_local, prior))
    setattr(owner, name, value)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    global CURRENT
    if item.originalname not in {LEGACY, PARALLEL}:
        return
    CURRENT = item.nodeid
    import duckdb
    from polisyos.data_forge.domains.catalog.batch.core_sources import api, writers
    from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
    from polisyos.fabric.connectors.sources.eurostat import EurostatConnector
    mode = os.environ.get("ORCH02_C05_SESSION", "observe")
    if mode not in {"observe", "remove_reuse"}:
        raise ValueError("ORCH02_C05_SESSION must be observe or remove_reuse")
    original_get = writers._ConnectorSessionCache.get_worldbank
    original_close = writers._ConnectorSessionCache.close
    original_ingest = api._ingest_catalog_observations
    sessions = {}
    orphans = {}

    def session_spy(original, label):
        async def call(connector, handle, *args, **kwargs):
            session = await original(connector, handle, *args, **kwargs)
            sessions[id(handle)] = session
            record("actual_connector_session", connector=label, handle_id=id(handle),
                   session_id=id(session), native_type=type(session).__module__ + "." + type(session).__name__,
                   closed=bool(session.closed))
            return session
        return call

    patch(WorldBankConnector, "_get_session", session_spy(WorldBankConnector._get_session, "worldbank"))
    patch(EurostatConnector, "_get_session", session_spy(EurostatConnector._get_session, "eurostat"))

    async def get(cache):
        previous = cache.worldbank
        if mode == "remove_reuse" and previous is not None:
            orphans.setdefault(id(cache), []).append(previous)
            cache.worldbank = None
        result = await original_get(cache)
        record("actual_canonical_cache_get", cache_id=id(cache), handle_id=id(result[1]),
               previous_handle_id=id(previous[1]) if previous else None,
               reuse_removed=mode == "remove_reuse")
        return result

    async def close(cache):
        await original_close(cache)
        # Isolation cleanup for a handle orphaned by the deliberate reuse removal.
        # This runs on the same event loop after the product's real close method;
        # it does not fake the observed connect/reuse/consumer assertions.
        cleaned = []
        for connector, handle in orphans.pop(id(cache), []):
            await connector.disconnect(handle)
            cleaned.append(id(handle))
        record("actual_canonical_cache_close", cache_id=id(cache),
               all_observed_sessions_closed=all(session.closed for session in sessions.values()),
               observed_sessions={str(handle): {"session_id": id(session), "closed": bool(session.closed)} for handle, session in sessions.items()},
               deliberate_mutant_orphan_cleanup_handles=cleaned,
               worldbank_session_state_none=cache.worldbank is None or cache.worldbank[1].get_state("session") is None)

    async def ingest(*args, **kwargs):
        result = await original_ingest(*args, **kwargs)
        config = kwargs["config"]
        with duckdb.connect(str(config.db_path), read_only=True) as con:
            rows = con.execute("SELECT value FROM ds_observations ORDER BY dataset_id").fetchall()
        record("actual_persisted_ingest", completed_shards=result.completed_shards,
               failures=result.failures, observations=result.observations,
               actual_sql_values=[list(row) for row in rows])
        return result

    patch(writers._ConnectorSessionCache, "get_worldbank", get)
    patch(writers._ConnectorSessionCache, "close", close)
    patch(api, "_ingest_catalog_observations", ingest)
    record("fixture_setup", mode=mode, canonical_cache_origin=inspect.getfile(writers._ConnectorSessionCache))


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_teardown(item, nextitem):
    global CURRENT
    yield
    if item.originalname in {LEGACY, PARALLEL}:
        for owner, name, had_local, prior in reversed(RESTORE):
            if had_local:
                setattr(owner, name, prior)
            else:
                delattr(owner, name)
        RESTORE.clear()
        CURRENT = None


def pytest_runtest_logreport(report):
    if LEGACY in report.nodeid or PARALLEL in report.nodeid:
        REPORTS.append({"nodeid": report.nodeid, "when": report.when, "outcome": report.outcome})


def pytest_sessionfinish(session, exitstatus):
    out = Path(os.environ["ORCH02_OUTPUT_DIR"])
    (out / "session-events.json").write_text(json.dumps({
        "schema": "orch02r2.actual-c05-session-probe.v1", "mode": os.environ.get("ORCH02_C05_SESSION", "observe"),
        "raw_pytest_exitstatus": int(exitstatus), "events": EVENTS, "reports": REPORTS,
        "removed_quantity": "Only worldbank existing-cache reuse; force canonical connect per request" if os.environ.get("ORCH02_C05_SESSION") == "remove_reuse" else None,
        "actual_retained": ["canonical cache class and original connect/get_session/fetch/disconnect", "owned API dispatch/lifecycle", "real ClientSession and DuckDB rows", "unchanged owned assertions"],
        "parallel_boundary": "Borrowed Eurostat async transport/capability callbacks controlled by its owned fixture; observe actual API cache-close/SQL/lease assertions, no claim an absent lazy HTTP session was created",
        "source_files_changed": False,
    }, indent=2) + "\n")
