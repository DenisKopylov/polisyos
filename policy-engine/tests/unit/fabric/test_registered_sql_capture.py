"""Behavioral tests for the fresh registered SQL acquisition boundary."""

from __future__ import annotations

import sqlite3

import pytest

from polisyos.fabric import fabric_get_fresh_registered_sql_data
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.sql_query import SQLQueryConnector


def test_fresh_registered_sql_executes_real_sql_and_rejects_unapplied_scope(tmp_path):
    database = tmp_path / "source.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs(income REAL NOT NULL, note TEXT)")
        connection.executemany(
            "INSERT INTO policy_inputs VALUES (?, ?)",
            ((12.5, "first"), (25.0, None)),
        )

    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(
            url=f"sqlite:///{database}",
            headers={"X-SQL-Table": "policy_inputs"},
        ),
    )

    result = fabric_get_fresh_registered_sql_data(
        dataset_id="policy_inputs",
        connector_id="sql.query",
        constraints={"page_size": 3},
        registry=registry,
    )

    assert result.row_count == 2
    assert result.data.to_dict(orient="records") == [
        {"income": 12.5, "note": "first"},
        {"income": 25.0, "note": None},
    ]
    with pytest.raises(ValueError, match="registered_sql_requested_scope_not_executed"):
        fabric_get_fresh_registered_sql_data(
            dataset_id="policy_inputs",
            connector_id="sql.query",
            constraints={"filters": {"income": ["12.5"]}},
            registry=registry,
        )


def test_relative_sqlite_path_cannot_change_with_process_working_directory(monkeypatch):
    """A registered source location cannot depend on a mutable process cwd."""
    registry = ConnectorRegistry()
    registry.register(SQLQueryConnector, ConnectionConfig(url="relative.sqlite"))

    def must_not_connect(*_args, **_kwargs):
        raise AssertionError("a cwd-dependent source reached SQLite")

    monkeypatch.setattr(sqlite3, "connect", must_not_connect)
    with pytest.raises(ValueError, match="registered_sql_connection_profile_not_supported"):
        fabric_get_fresh_registered_sql_data(
            dataset_id="policy_inputs",
            connector_id="sql.query",
            constraints={"page_size": 3},
            registry=registry,
        )


def test_running_event_loop_cannot_detach_sql_from_the_event_fence(tmp_path, monkeypatch):
    """An unsupported async caller is rejected before any driver execution."""
    import asyncio

    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector, ConnectionConfig(url=f"sqlite:///{tmp_path / 'db.sqlite'}")
    )

    def must_not_connect(*_args, **_kwargs):
        raise AssertionError("the async caller reached the SQL driver")

    monkeypatch.setattr(sqlite3, "connect", must_not_connect)

    async def run():
        with pytest.raises(ValueError, match="registered_sql_async_caller_not_supported"):
            fabric_get_fresh_registered_sql_data(
                dataset_id="policy_inputs",
                connector_id="sql.query",
                constraints={"page_size": 3},
                registry=registry,
            )

    asyncio.run(run())


def test_configured_query_cannot_claim_an_unapplied_page_limit(tmp_path):
    database = tmp_path / "source.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs(income REAL NOT NULL)")
        connection.executemany("INSERT INTO policy_inputs VALUES (?)", ((12.5,), (25.0,)))

    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(
            url=f"sqlite:///{database}",
            headers={"X-SQL-Query": "SELECT * FROM policy_inputs"},
        ),
    )

    with pytest.raises(ValueError, match="registered_sql_configured_query_ignores_page_size"):
        fabric_get_fresh_registered_sql_data(
            dataset_id="policy_inputs",
            connector_id="sql.query",
            constraints={"page_size": 1},
            registry=registry,
        )


def test_aba_default_config_cannot_change_the_executed_view(tmp_path, monkeypatch):
    """The actual driver must execute A even if the mutable default goes A/B/A."""
    database = tmp_path / "aba.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs(income REAL NOT NULL)")
        connection.executemany("INSERT INTO policy_inputs VALUES (?)", [(12.5,), (25.0,)])
        connection.execute("CREATE TABLE wrong_inputs(income REAL NOT NULL)")
        connection.execute("INSERT INTO wrong_inputs VALUES (999.0)")
    config_a = ConnectionConfig(
        url=f"sqlite:///{database}", headers={"X-SQL-Table": "policy_inputs"}
    )
    config_b = ConnectionConfig(
        url=f"sqlite:///{database}", headers={"X-SQL-Query": "SELECT * FROM wrong_inputs"}
    )
    registry = ConnectorRegistry()
    registry.register(SQLQueryConnector, config_a)
    original_get = registry.get
    original_get_connection = registry.get_connection
    original_sql_connect = sqlite3.connect
    statements = []

    def connect_with_trace(*args, **kwargs):
        connection = original_sql_connect(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    def swap_after_connector_selection(*args, **kwargs):
        connector = original_get(*args, **kwargs)
        registry.set_default_config("sql.query", config_b)
        return connector

    async def restore_after_connection(*args, **kwargs):
        # B stays installed during the original connection-selection call. A
        # mutable-default reread therefore gets B, while an explicit captured
        # config still selects A. Restore only after the handle is acquired.
        handle = await original_get_connection(*args, **kwargs)
        registry.set_default_config("sql.query", config_a)
        return handle

    monkeypatch.setattr(sqlite3, "connect", connect_with_trace)
    monkeypatch.setattr(registry, "get", swap_after_connector_selection)
    monkeypatch.setattr(registry, "get_connection", restore_after_connection)
    actual = fabric_get_fresh_registered_sql_data(
        dataset_id="policy_inputs",
        connector_id="sql.query",
        constraints={"page_size": 3},
        registry=registry,
    )
    assert actual.data["income"].tolist() == [12.5, 25.0]
    assert registry.get_default_config("sql.query") == config_a
    driver_selects = [s for s in statements if "select" in s.lower()]
    assert len(driver_selects) == 1
    assert "policy_inputs" in driver_selects[0].lower()
    assert "limit 3" in driver_selects[0].lower()
    assert "wrong_inputs" not in driver_selects[0].lower()


def test_in_place_config_aba_cannot_change_driver_database(tmp_path, monkeypatch):
    """A caller holding the original dataclass cannot replace the copied profile."""
    database_a = tmp_path / "source-a.sqlite"
    database_b = tmp_path / "source-b.sqlite"
    for database, value in ((database_a, 12.5), (database_b, 999.0)):
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE policy_inputs(income REAL NOT NULL)")
            connection.execute("INSERT INTO policy_inputs VALUES (?)", (value,))
    config = ConnectionConfig(url=f"sqlite:///{database_a}")
    registry = ConnectorRegistry()
    registry.register(SQLQueryConnector, config)
    original_get = registry.get
    original_connection = registry.get_connection
    original_connect = sqlite3.connect
    actual_paths = []

    def select_then_mutate(*args, **kwargs):
        connector = original_get(*args, **kwargs)
        object.__setattr__(config, "url", f"sqlite:///{database_b}")
        return connector

    async def restore_after_handle(*args, **kwargs):
        try:
            return await original_connection(*args, **kwargs)
        finally:
            object.__setattr__(config, "url", f"sqlite:///{database_a}")

    def capture_path(path, *args, **kwargs):
        actual_paths.append(path)
        return original_connect(path, *args, **kwargs)

    monkeypatch.setattr(registry, "get", select_then_mutate)
    monkeypatch.setattr(registry, "get_connection", restore_after_handle)
    monkeypatch.setattr(sqlite3, "connect", capture_path)
    try:
        actual = fabric_get_fresh_registered_sql_data(
            dataset_id="policy_inputs",
            connector_id="sql.query",
            constraints={"page_size": 3},
            registry=registry,
        )
    finally:
        object.__setattr__(config, "url", f"sqlite:///{database_a}")
    assert actual.data["income"].tolist() == [12.5]
    assert actual_paths == [str(database_a)]


def test_configured_fallback_is_legacy_only_and_never_fresh_sql(tmp_path):
    """A plausible fallback may serve legacy but cannot mint a SQL occurrence."""
    from datetime import UTC, datetime

    from polisyos.fabric import fabric_get_data
    from polisyos.fabric.connectors.resilience import FallbackChain, MockFallback, ResilienceConfig
    from polisyos.ir.connectors import DataVersion, FetchResult, VersionStrategy

    database = tmp_path / "fallback.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE unrelated(x INTEGER)")
    now = datetime.now(UTC)
    fallback = FetchResult(
        data=[{"income": 999.0}],
        row_count=1,
        schema_id="fallback.schema",
        schema_version="1.0.0",
        version=DataVersion(strategy=VersionStrategy.TIMESTAMP, value="fallback", timestamp=now),
        fetched_at=now,
        completeness=1.0,
    )
    connector = SQLQueryConnector()
    connector.resilience_config = ResilienceConfig(
        fallback_chain=FallbackChain([MockFallback(mock_data=fallback)])
    )
    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(url=f"sqlite:///{database}", headers={"X-SQL-Table": "missing"}),
        factory=lambda: connector,
    )
    legacy = fabric_get_data(dataset_id="missing", connector_id="sql.query", registry=registry)
    assert legacy.row_count == 1
    assert legacy.data == [{"income": 999.0}]
    with pytest.raises(ValueError, match="registered_sql_execution_origin_not_established"):
        fabric_get_fresh_registered_sql_data(
            dataset_id="missing",
            connector_id="sql.query",
            registry=registry,
            constraints={"page_size": 2},
        )


def test_registered_execution_observes_real_driver_query_and_output(tmp_path, monkeypatch):
    """The capture and result derive from the same actual SQLite statement."""
    import json

    from polisyos.fabric.api import _execute_registered_sql

    database = tmp_path / "capture.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs(income REAL NOT NULL)")
        connection.executemany("INSERT INTO policy_inputs VALUES (?)", [(12.5,), (25.0,)])
    config = ConnectionConfig(url=f"sqlite:///{database}", headers={"X-SQL-Table": "policy_inputs"})
    registry = ConnectorRegistry()
    registry.register(SQLQueryConnector, config)
    real_connect = sqlite3.connect
    queries = []

    def traced_connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        connection.set_trace_callback(queries.append)
        return connection

    monkeypatch.setattr(sqlite3, "connect", traced_connect)
    observed = _execute_registered_sql(
        dataset_id="policy_inputs",
        connector_id="sql.query",
        constraints={"page_size": 3},
        registry=registry,
    )
    executed = [query for query in queries if "policy_inputs" in query.lower()]
    assert executed == [observed.query]
    assert observed.parameters == ()
    assert observed.config_fingerprint == config.cache_scope_fingerprint
    assert json.loads(observed.output_json) == [{"income": 12.5}, {"income": 25.0}]
    assert observed.result.data.to_dict(orient="records") == [{"income": 12.5}, {"income": 25.0}]
    assert observed.result.completeness == 0.0
    assert "source_completeness_unknown" in observed.result.quality_flags
    assert observed.output_json == json.dumps(
        observed.result.data.to_dict(orient="records"),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def test_registered_table_override_cannot_replace_the_requested_dataset(tmp_path):
    """A valid table B cannot stand in for a request for table A."""
    database = tmp_path / "tables.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs(income REAL NOT NULL)")
        connection.execute("CREATE TABLE other_inputs(income REAL NOT NULL)")
        connection.execute("INSERT INTO other_inputs VALUES (999.0)")
    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(url=f"sqlite:///{database}", headers={"X-SQL-Table": "other_inputs"}),
    )
    with pytest.raises(ValueError, match="registered_sql_requested_dataset_not_executed"):
        fabric_get_fresh_registered_sql_data(
            dataset_id="policy_inputs",
            connector_id="sql.query",
            registry=registry,
            constraints={"page_size": 2},
        )


def test_registered_full_page_refuses_unknown_continuation(tmp_path):
    """A full page is ambiguous even when the table happens to contain only N rows."""
    database = tmp_path / "full-page.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs(income REAL NOT NULL)")
        connection.execute("INSERT INTO policy_inputs VALUES (12.5)")
    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(url=f"sqlite:///{database}", headers={"X-SQL-Table": "policy_inputs"}),
    )
    with pytest.raises(ValueError, match="registered_sql_page_continuation_not_established"):
        fabric_get_fresh_registered_sql_data(
            dataset_id="policy_inputs",
            connector_id="sql.query",
            registry=registry,
            constraints={"page_size": 1},
        )


def test_sql_observation_cannot_be_reconstructed_from_matching_fields(tmp_path):
    """A caller-created copy is not an observation of the canonical driver call."""
    from dataclasses import replace

    from polisyos.fabric.api import _execute_registered_sql, _require_registered_sql_execution

    database = tmp_path / "identity.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs(income REAL NOT NULL)")
        connection.execute("INSERT INTO policy_inputs VALUES (12.5)")
    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(url=f"sqlite:///{database}", headers={"X-SQL-Table": "policy_inputs"}),
    )
    actual = _execute_registered_sql(
        dataset_id="policy_inputs",
        connector_id="sql.query",
        registry=registry,
        constraints={"page_size": 2},
    )
    _require_registered_sql_execution(actual)
    with pytest.raises(ValueError, match="registered_sql_execution_not_observed"):
        _require_registered_sql_execution(replace(actual))


def test_observation_is_reconciled_against_live_config_and_actual_rows(tmp_path):
    """An actual observation becomes unusable after its rows or config change."""
    from polisyos.fabric.api import _execute_registered_sql, _require_registered_sql_execution

    database = tmp_path / "stale.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs(income REAL NOT NULL)")
        connection.execute("INSERT INTO policy_inputs VALUES (12.5)")
    config = ConnectionConfig(url=f"sqlite:///{database}", headers={"X-SQL-Table": "policy_inputs"})
    registry = ConnectorRegistry()
    registry.register(SQLQueryConnector, config)
    actual = _execute_registered_sql(
        dataset_id="policy_inputs",
        connector_id="sql.query",
        registry=registry,
        constraints={"page_size": 2},
    )
    actual.result.data.loc[0, "income"] = 12.500000000001
    with pytest.raises(ValueError, match="registered_sql_execution_changed"):
        _require_registered_sql_execution(actual)

    other = _execute_registered_sql(
        dataset_id="policy_inputs",
        connector_id="sql.query",
        registry=registry,
        constraints={"page_size": 2},
    )
    registry.set_default_config(
        "sql.query", ConnectionConfig(url=f"sqlite:///{database}", headers={})
    )
    with pytest.raises(ValueError, match="registered_sql_effective_config_changed"):
        _require_registered_sql_execution(other)


def test_sql_observation_does_not_round_high_precision_produced_values(tmp_path):
    """Close values cannot collapse to pandas' default JSON precision."""
    import json

    from polisyos.fabric.api import _execute_registered_sql

    database = tmp_path / "precision.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs(income REAL NOT NULL)")
        connection.execute("INSERT INTO policy_inputs VALUES (?)", (0.10000000000000002,))
    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(url=f"sqlite:///{database}", headers={"X-SQL-Table": "policy_inputs"}),
    )
    actual = _execute_registered_sql(
        dataset_id="policy_inputs",
        connector_id="sql.query",
        registry=registry,
        constraints={"page_size": 2},
    )
    assert json.loads(actual.output_json) == [{"income": 0.10000000000000002}]


@pytest.mark.parametrize(
    "override",
    [
        {"headers": {"X-SQL-Table": "policy_inputs", "X-Ignored-Policy": "required"}},
        {"auth_method": "token", "auth_credentials": {"token": "unit-test"}},
        {"max_retries": 4},
        {"rate_limit_rps": 1.0},
        {"verify_ssl": False},
        {"ca_bundle_path": "/not-applied"},
        {"keepalive_seconds": 5},
        {"timeout_seconds": 0},
        {"url": "duckdb:///not-used"},
    ],
)
def test_registered_sql_refuses_unapplied_connection_options(tmp_path, monkeypatch, override):
    """Ignored connection settings must fail before a driver call."""
    from dataclasses import replace

    database = tmp_path / "profile.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs(income REAL)")
    config = ConnectionConfig(url=f"sqlite:///{database}", headers={"X-SQL-Table": "policy_inputs"})
    registry = ConnectorRegistry()
    registry.register(SQLQueryConnector, replace(config, **override))

    def unexpected(*args, **kwargs):
        raise AssertionError("unsupported config reached the SQL driver")

    monkeypatch.setattr(sqlite3, "connect", unexpected)
    with pytest.raises(ValueError, match="registered_sql_connection_profile_not_supported"):
        fabric_get_fresh_registered_sql_data(
            dataset_id="policy_inputs",
            connector_id="sql.query",
            registry=registry,
            constraints={"page_size": 2},
        )


def test_registered_sql_applies_configured_sqlite_timeout(tmp_path, monkeypatch):
    """The observed driver uses the selected connection timeout."""
    database = tmp_path / "timeout.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs(income REAL)")
        connection.execute("INSERT INTO policy_inputs VALUES (12.5)")
    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(
            url=f"sqlite:///{database}",
            headers={"X-SQL-Table": "policy_inputs"},
            timeout_seconds=7,
        ),
    )
    actual_connect = sqlite3.connect
    seen = []

    def observe(*args, **kwargs):
        timeout = kwargs.get("timeout")
        connection = actual_connect(*args, **kwargs)
        connection.set_trace_callback(lambda sql: seen.append((timeout, sql)))
        return connection

    monkeypatch.setattr(sqlite3, "connect", observe)
    fabric_get_fresh_registered_sql_data(
        dataset_id="policy_inputs",
        connector_id="sql.query",
        registry=registry,
        constraints={"page_size": 2},
    )
    assert [timeout for timeout, sql in seen if "policy_inputs" in sql.lower()] == [7.0]


@pytest.mark.parametrize("page_size", [None, 0, -1, 10001, True])
def test_registered_sql_requires_a_bounded_integer_page(tmp_path, page_size):
    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(
            url=f"sqlite:///{tmp_path / 'unused.sqlite'}",
            headers={"X-SQL-Table": "policy_inputs"},
        ),
    )
    with pytest.raises(ValueError, match="registered_sql_page_size_invalid"):
        fabric_get_fresh_registered_sql_data(
            dataset_id="policy_inputs",
            connector_id="sql.query",
            registry=registry,
            constraints={"page_size": page_size},
        )
