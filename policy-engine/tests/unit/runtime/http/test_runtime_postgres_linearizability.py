"""Real-PostgreSQL proofs for DS20 durable authorization state."""

from __future__ import annotations

import importlib
import os
import threading
import time
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.runtime import ScenarioManifest
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from tests.unit.runtime.http import test_control_plane_store_evaluation_frontier as frontier_helpers

if TYPE_CHECKING:
    from pathlib import Path


_REPRO_COMMAND = (
    "POLISYOS_DS9_REQUIRE_PG=1 POLISYOS_TEST_PG_DSN='postgresql://...' "
    "uv run --extra test --extra runtime --extra multi-tenant pytest -q "
    "tests/unit/runtime/http/test_runtime_postgres_linearizability.py"
)


@pytest.fixture
def postgres_dsn() -> Iterator[str]:
    """Provision an isolated schema on an explicit real PostgreSQL endpoint."""
    require_ds9_pg = os.getenv("POLISYOS_DS9_REQUIRE_PG", "").strip() == "1"

    def _blocked(reason: str) -> None:
        message = f"DS9-PG-PROOF-NONRECEIPT: {reason}; {_REPRO_COMMAND}"
        if require_ds9_pg:
            pytest.fail(message, pytrace=False)
        pytest.skip(f"environment_blocked: {reason}; {_REPRO_COMMAND}")

    dsn = os.getenv("POLISYOS_TEST_PG_DSN", "").strip()
    if not dsn:
        _blocked("POLISYOS_TEST_PG_DSN is absent")
    try:
        psycopg = importlib.import_module("psycopg")
    except ModuleNotFoundError:
        _blocked("psycopg is unavailable")
    conninfo = importlib.import_module("psycopg.conninfo")
    postgres_sql = importlib.import_module("psycopg.sql")
    schema = f"ds20b_{uuid.uuid4().hex}"
    identifier = postgres_sql.Identifier(schema)
    try:
        with (
            psycopg.connect(dsn, autocommit=True) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(postgres_sql.SQL("CREATE SCHEMA {}").format(identifier))
    except psycopg.Error:
        _blocked("PostgreSQL connection/schema provisioning failed")
    try:
        parsed_conninfo = conninfo.conninfo_to_dict(dsn)
        existing_options = str(parsed_conninfo.get("options") or "").strip()
        schema_option = f"-csearch_path={schema}"
        options = f"{existing_options} {schema_option}".strip()
        isolated_dsn = conninfo.make_conninfo(dsn, options=options)
        yield isolated_dsn
    finally:
        with (
            psycopg.connect(dsn, autocommit=True) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(postgres_sql.SQL("DROP SCHEMA {} CASCADE").format(identifier))


def _configure_postgres_runtime(monkeypatch: pytest.MonkeyPatch, *, dsn: str) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "postgres")
    monkeypatch.setenv("POLISYOS_CONTROL_POSTGRES_DSN", dsn)


def _scenario_quantity(runtime_api_env: dict[str, Any]) -> dict[str, Any]:
    response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/quantities"
    )
    assert response.status_code == 200, response.text
    return next(
        item for item in response.json()["quantities"] if item["metric_id"] == "policy_cost"
    )


def _authenticated_client(
    runtime_api_env: dict[str, Any],
    *,
    opa_client: Any,
    bearer: str,
    jti: str,
):
    from tests.unit.runtime.http.test_runtime_api_authz import _build_secure_client, _claims

    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa_client,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti=jti,
        ),
    )
    return client


def _authorization_headers(runtime_api_env: dict[str, Any], *, bearer: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }


def _scenario_head_store(client: Any) -> ControlPlaneStore:
    app = cast("Any", client.app)
    return cast("ControlPlaneStore", app.state._control_service.scenario_head_store)


def test_postgres_step_up_one_use_has_exactly_one_winner_across_store_instances(
    postgres_dsn: str,
    tmp_path: Path,
) -> None:
    """Prove one assertion cannot be consumed twice by separate PostgreSQL stores."""
    stores = (
        ControlPlaneStore(
            backend="postgres",
            sqlite_path=tmp_path / "unused-first.sqlite3",
            postgres_dsn=postgres_dsn,
        ),
        ControlPlaneStore(
            backend="postgres",
            sqlite_path=tmp_path / "unused-second.sqlite3",
            postgres_dsn=postgres_dsn,
        ),
    )
    assert all(store.backend == "postgres" for store in stores)
    assertion_id = f"ds20b-postgres-step-up-{uuid.uuid4().hex}"
    expires_at = int(time.time()) + 60
    barrier = threading.Barrier(2)

    def _consume(store: ControlPlaneStore) -> bool:
        barrier.wait(timeout=10)
        return store.consume_step_up_assertion(
            assertion_id=assertion_id,
            expires_at=expires_at,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(_consume, stores))

    assert sorted(outcomes) == [False, True]


def test_human_decision_concurrent_reservation_has_one_postgres_winner(
    postgres_dsn: str,
    tmp_path: Path,
) -> None:
    """The reservation CAS remains linearizable across PostgreSQL connections."""

    stores = (
        ControlPlaneStore(
            backend="postgres",
            sqlite_path=tmp_path / "unused-human-decision-first.sqlite3",
            postgres_dsn=postgres_dsn,
        ),
        ControlPlaneStore(
            backend="postgres",
            sqlite_path=tmp_path / "unused-human-decision-second.sqlite3",
            postgres_dsn=postgres_dsn,
        ),
    )
    barrier = threading.Barrier(2)
    now = datetime(2026, 8, 24, 12, tzinfo=UTC)

    def _reserve(index: int):
        barrier.wait(timeout=10)
        return stores[index].reserve_human_decision_action(
            tenant_id="tenant-postgres",
            governed_action_key="sha256:" + "9" * 64,
            reservation_id=f"postgres-reservation-{uuid.uuid4().hex}",
            binding_sha256="sha256:" + "8" * 64,
            now=now,
            lease_seconds=30,
            record_valid_until=now + timedelta(hours=1),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(_reserve, range(2)))

    assert sorted(result.acquired for result in results) == [False, True]
    losing = next(result for result in results if not result.acquired)
    assert losing.issue_code == "DS9-OVERLAPPING-REISSUE"


def test_human_decision_later_generation_postgres_loser_returns_typed_overlap(
    postgres_dsn: str,
    tmp_path: Path,
) -> None:
    """Two writers racing for v2 produce one winner and one typed loser."""

    stores = (
        ControlPlaneStore(
            backend="postgres",
            sqlite_path=tmp_path / "unused-human-decision-v2-first.sqlite3",
            postgres_dsn=postgres_dsn,
        ),
        ControlPlaneStore(
            backend="postgres",
            sqlite_path=tmp_path / "unused-human-decision-v2-second.sqlite3",
            postgres_dsn=postgres_dsn,
        ),
    )
    started_at = datetime(2026, 8, 24, 12, tzinfo=UTC)
    governed_action_key = "sha256:" + "7" * 64
    binding_sha256 = "sha256:" + "6" * 64
    first = stores[0].reserve_human_decision_action(
        tenant_id="tenant-postgres",
        governed_action_key=governed_action_key,
        reservation_id="postgres-generation-1",
        binding_sha256=binding_sha256,
        now=started_at,
        lease_seconds=1,
        record_valid_until=started_at + timedelta(hours=1),
    )
    assert first.acquired is True
    recovery = stores[0].reserve_human_decision_action(
        tenant_id="tenant-postgres",
        governed_action_key=governed_action_key,
        reservation_id="postgres-generation-1-retry",
        binding_sha256=binding_sha256,
        now=started_at + timedelta(seconds=2),
        lease_seconds=1,
        record_valid_until=started_at + timedelta(hours=1),
    )
    assert recovery.acquired is False
    assert recovery.issue_code == "DS9-RESERVATION-RECOVERY-REQUIRED"
    reconciled = stores[0]._reconcile_empty_human_decision_reservation(
        tenant_id="tenant-postgres",
        governed_action_key=governed_action_key,
        reservation_id=first.reservation.reservation_id,
        reservation_version=first.reservation.reservation_version,
        reconciled_at=started_at + timedelta(seconds=3),
    )
    assert reconciled.state == "reconciled_empty"
    barrier = threading.Barrier(2)

    def _reserve_generation_2(index: int):
        barrier.wait(timeout=10)
        return stores[index].reserve_human_decision_action(
            tenant_id="tenant-postgres",
            governed_action_key=governed_action_key,
            reservation_id=f"postgres-generation-2-{index}",
            binding_sha256=binding_sha256,
            now=started_at + timedelta(seconds=4),
            lease_seconds=30,
            record_valid_until=started_at + timedelta(hours=1),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(_reserve_generation_2, range(2)))

    assert sorted(result.acquired for result in results) == [False, True]
    winner = next(result for result in results if result.acquired)
    loser = next(result for result in results if not result.acquired)
    assert winner.reservation.reservation_version == 2
    assert loser.issue_code == "DS9-OVERLAPPING-REISSUE"
    assert loser.reservation.reservation_version == 2
    assert loser.reservation.reservation_id == winner.reservation.reservation_id


def test_postgres_scenario_cas_two_apps_allows_one_mutation_and_one_conflict(
    postgres_dsn: str,
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove two runtime apps cannot both claim the same scenario revision."""
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _BarrierOPA,
        _fixture_bearer,
        _scenario_create_body,
    )

    _configure_postgres_runtime(monkeypatch, dsn=postgres_dsn)
    barrier = threading.Barrier(2)
    first_opa = _BarrierOPA(barrier)
    second_opa = _BarrierOPA(barrier)
    suffix = uuid.uuid4().hex
    bearer = _fixture_bearer(f"postgres-scenario-race-{suffix}")
    first_client = _authenticated_client(
        runtime_api_env,
        opa_client=first_opa,
        bearer=bearer,
        jti=f"jwt-postgres-scenario-race-first-{suffix}",
    )
    second_client = _authenticated_client(
        runtime_api_env,
        opa_client=second_opa,
        bearer=bearer,
        jti=f"jwt-postgres-scenario-race-second-{suffix}",
    )
    quantity = _scenario_quantity(runtime_api_env)
    scenario_id = f"scn_ds20b_pg_race_{suffix}"
    first_body = _scenario_create_body(scenario_id=scenario_id, quantity=quantity)
    first_body["policy_question"] = "First PostgreSQL contender"
    second_body = _scenario_create_body(scenario_id=scenario_id, quantity=quantity)
    second_body["policy_question"] = "Second PostgreSQL contender"
    path = f"/api/v1/runs/{runtime_api_env['core_run_id']}/scenarios"
    headers = _authorization_headers(runtime_api_env, bearer=bearer)

    def _post(client: Any, body: dict[str, Any]):
        return client.post(path, headers=headers, json=body)

    with first_client, second_client:
        stores = (
            _scenario_head_store(first_client),
            _scenario_head_store(second_client),
        )
        assert all(store.backend == "postgres" for store in stores)
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = tuple(
                executor.map(
                    lambda contender: _post(*contender),
                    ((first_client, first_body), (second_client, second_body)),
                )
            )
        heads = tuple(store.get_scenario_head(scenario_id) for store in stores)

    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response for response in responses if response.status_code == 200)
    loser = next(response for response in responses if response.status_code == 409)
    assert loser.json()["code"] == "scenario_authorization_binding_changed"
    assert heads[0] is not None and heads[0] == heads[1]
    assert heads[0].revision == 1
    assert heads[0].manifest_hash == winner.json()["scenario"]["manifest_hash"]
    assert len(first_opa.inputs) == 1
    assert len(second_opa.inputs) == 1


def test_postgres_corrupted_scenario_head_is_denied_before_opa(
    postgres_dsn: str,
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove a PostgreSQL head that fails content binding cannot authorize mutation."""
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _CaptureOPA,
        _fixture_bearer,
        _scenario_create_body,
    )

    _configure_postgres_runtime(monkeypatch, dsn=postgres_dsn)
    suffix = uuid.uuid4().hex
    scenario_id = f"scn_ds20b_pg_corrupt_{suffix}"
    bearer = _fixture_bearer(f"postgres-corrupted-head-{suffix}")
    opa = _CaptureOPA()
    client = _authenticated_client(
        runtime_api_env,
        opa_client=opa,
        bearer=bearer,
        jti=f"jwt-postgres-corrupted-head-{suffix}",
    )
    body = _scenario_create_body(
        scenario_id=scenario_id,
        quantity=_scenario_quantity(runtime_api_env),
    )
    path = f"/api/v1/runs/{runtime_api_env['core_run_id']}/scenarios"
    headers = _authorization_headers(runtime_api_env, bearer=bearer)

    with client:
        store = _scenario_head_store(client)
        assert store.backend == "postgres"
        created = client.post(path, headers=headers, json=body)
        assert created.status_code == 200, created.text
        opa.inputs.clear()

        psycopg = importlib.import_module("psycopg")
        with psycopg.connect(postgres_dsn, autocommit=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE runtime_scenario_heads
                    SET manifest_hash = %s
                    WHERE scenario_id = %s
                    """,
                    ("sha256:corrupted-postgres-head", scenario_id),
                )
                assert cursor.rowcount == 1
            connection.commit()

        response = client.post(path, headers=headers, json=body)

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "scenario_head_content_mismatch"
    assert opa.inputs == []


def test_postgres_fresh_app_ignores_unheaded_scenario_candidate_artifact(
    postgres_dsn: str,
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove a fresh app selects only the PostgreSQL head, never a loose CAS artifact."""
    from polisyos.runtime.http.services.scenarios import _finalize_manifest_hash
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _fixture_bearer,
        _scenario_create_body,
    )

    _configure_postgres_runtime(monkeypatch, dsn=postgres_dsn)
    suffix = uuid.uuid4().hex
    scenario_id = f"scn_ds20b_pg_unheaded_{suffix}"
    bearer = _fixture_bearer(f"postgres-unheaded-{suffix}")
    first_client = _authenticated_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        bearer=bearer,
        jti=f"jwt-postgres-unheaded-first-{suffix}",
    )
    body = _scenario_create_body(
        scenario_id=scenario_id,
        quantity=_scenario_quantity(runtime_api_env),
    )
    body["policy_question"] = "Authoritative PostgreSQL winner"
    path = f"/api/v1/runs/{runtime_api_env['core_run_id']}/scenarios"
    headers = _authorization_headers(runtime_api_env, bearer=bearer)

    with first_client:
        first_store = _scenario_head_store(first_client)
        assert first_store.backend == "postgres"
        created = first_client.post(path, headers=headers, json=body)
        assert created.status_code == 200, created.text
        winner = ScenarioManifest.model_validate(created.json()["scenario"])
        head = first_store.get_scenario_head(scenario_id)
        assert head is not None

    unheaded = _finalize_manifest_hash(
        winner.model_copy(update={"policy_question": "Unheaded PostgreSQL loser"})
    )
    artifact_store = FileSystemCAS(runtime_api_env["cas_root"])
    unheaded_ref = artifact_store.put_json(
        unheaded.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind="runtime.scenario_manifest",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.runtime.scenario_manifest", version="1"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    assert str(unheaded_ref.artifact_id) != head.artifact_ref

    second_client = _authenticated_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        bearer=bearer,
        jti=f"jwt-postgres-unheaded-second-{suffix}",
    )
    with second_client:
        second_store = _scenario_head_store(second_client)
        assert second_store.backend == "postgres"
        fetched = second_client.get(
            f"/api/v1/scenarios/{scenario_id}",
            headers=headers,
        )

    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["scenario"]["policy_question"] == "Authoritative PostgreSQL winner"
    assert fetched.json()["scenario"]["manifest_hash"] == head.manifest_hash


def test_postgres_acquisition_head_legacy_schema_migrates_without_profile_backfill(
    postgres_dsn: str,
    tmp_path: Path,
) -> None:
    """Migrate the real prior head schema and retain its unknown selected profile."""
    psycopg = importlib.import_module("psycopg")
    legacy_ref = frontier_helpers._sha("postgres-legacy-receipt")
    route = frontier_helpers._sha("postgres-legacy-route")
    with psycopg.connect(postgres_dsn) as connection:
        connection.execute(
            "CREATE TABLE runtime_acquisition_action_heads ("
            "tenant_id TEXT NOT NULL, cell_id TEXT NOT NULL, run_id TEXT NOT NULL, "
            "source_job_id TEXT NOT NULL, route_id TEXT NOT NULL, "
            "action_generation INTEGER NOT NULL, head_generation INTEGER NOT NULL, "
            "receipt_ref TEXT NOT NULL, receipt_sha256 TEXT NOT NULL, "
            "durable_event_id TEXT NOT NULL, coarse_phase TEXT NOT NULL, "
            "receipt_phase TEXT NOT NULL, recovery_state TEXT NOT NULL, job_id TEXT NOT NULL, "
            "predecessor_receipt_ref TEXT, evaluation_frontier_before_ref TEXT, "
            "evaluation_frontier_ref TEXT, created_at TIMESTAMPTZ NOT NULL, "
            "PRIMARY KEY (tenant_id, cell_id, run_id, source_job_id, route_id, "
            "action_generation, head_generation))"
        )
        connection.execute(
            "INSERT INTO runtime_acquisition_action_heads "
            "(tenant_id, cell_id, run_id, source_job_id, route_id, action_generation, "
            "head_generation, receipt_ref, receipt_sha256, durable_event_id, coarse_phase, "
            "receipt_phase, recovery_state, job_id, predecessor_receipt_ref, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                "tenant-a",
                "cell-a",
                "run-a",
                "source-nl",
                route,
                1,
                1,
                legacy_ref,
                legacy_ref,
                "legacy-event",
                "terminal",
                "terminal",
                "complete",
                "legacy-job",
                None,
                "2026-01-01T00:00:00+00:00",
            ),
        )
    store = ControlPlaneStore(
        backend="postgres",
        sqlite_path=tmp_path / "unused-legacy.sqlite3",
        postgres_dsn=postgres_dsn,
    )
    scope = frontier_helpers._oracle_action_scope(frontier_helpers._key(), "postgres-legacy-route")
    legacy = store.get_acquisition_action_head(**scope)
    assert legacy is not None
    assert legacy.receipt_ref == legacy_ref
    assert legacy.receipt_manifest_profile_sha256 is None
    assert store.get_acquisition_action_head_by_receipt(**scope, receipt_ref=legacy_ref) == legacy
    reopened = ControlPlaneStore(
        backend="postgres",
        sqlite_path=tmp_path / "unused-reopen.sqlite3",
        postgres_dsn=postgres_dsn,
    )
    assert reopened.get_acquisition_action_head(**scope) == legacy


def test_postgres_acquisition_frontier_cas_race_is_linearizable(
    postgres_dsn: str,
    tmp_path: Path,
) -> None:
    """Exercise frontier CAS through two real PostgreSQL store instances."""
    suffix = uuid.uuid4().hex
    stores = (
        ControlPlaneStore(
            backend="postgres",
            sqlite_path=tmp_path / f"unused-frontier-first-{suffix}.sqlite3",
            postgres_dsn=postgres_dsn,
        ),
        ControlPlaneStore(
            backend="postgres",
            sqlite_path=tmp_path / f"unused-frontier-second-{suffix}.sqlite3",
            postgres_dsn=postgres_dsn,
        ),
    )
    assert all(store.backend == "postgres" for store in stores)

    _, initial, _ = frontier_helpers._bootstrap(
        stores[0],
        tmp_path,
        source_job_id=f"frontier-source-{suffix}",
    )
    key = initial.key
    jobs = tuple(
        frontier_helpers._create_action_job(
            stores[0],
            job_id=f"frontier-action-{suffix}-{index}",
        )
        for index in range(2)
    )
    replacements = (
        frontier_helpers._value("compiled-frontier-a", "tuple-frontier-a"),
        frontier_helpers._value("compiled-frontier-b", "tuple-frontier-b"),
    )
    selected_receipts = tuple(
        frontier_helpers._selected_receipt_ref(tmp_path, f"pg-selected-{index}", version=str(index))
        for index in range(2)
    )
    assert all(ref.manifest_profile_sha256 is not None for ref in selected_receipts)
    barrier = threading.Barrier(2)

    def _compete(index: int) -> tuple[str, Any]:
        job, worker, attempt = jobs[index]
        barrier.wait(timeout=10)
        try:
            committed = frontier_helpers._append_action(
                stores[index],
                job=job,
                worker_id=worker,
                attempt=attempt,
                key=key,
                expected_revision=1,
                expected_ref=initial.frontier_ref,
                route_id=f"frontier-race-{suffix}-{index}",
                replacement=replacements[index],
                receipt_ref=str(selected_receipts[index].artifact_id),
                receipt_manifest_profile_sha256=selected_receipts[index].manifest_profile_sha256,
            )
        except ValueError as exc:
            return "conflict", exc
        return "committed", committed

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = tuple(pool.map(_compete, range(2)))
    winners = [result for outcome, result in outcomes if outcome == "committed"]
    conflicts = [result for outcome, result in outcomes if outcome == "conflict"]
    assert len(winners) == 1
    assert len(conflicts) == 1
    assert "acquisition_evaluation_frontier_conflict" in str(conflicts[0])

    winning_commit = winners[0]
    winning_index = next(
        index for index, (outcome, _) in enumerate(outcomes) if outcome == "committed"
    )
    losing_index = 1 - winning_index
    assert winning_commit.head.receipt_ref == str(selected_receipts[winning_index].artifact_id)
    assert (
        winning_commit.head.receipt_manifest_profile_sha256
        == selected_receipts[winning_index].manifest_profile_sha256
    )
    assert stores[0].read_acquisition_evaluation_frontier(key) == winning_commit.frontier
    assert stores[1].read_acquisition_evaluation_frontier(key) == winning_commit.frontier
    assert stores[1].get_acquisition_evaluation_frontier_by_ref(initial.frontier_ref) == initial
    reopened = ControlPlaneStore(
        backend="postgres",
        sqlite_path=tmp_path / "unused-pg-reopen.sqlite3",
        postgres_dsn=postgres_dsn,
    )
    winner_scope = {
        "tenant_id": key.tenant_id,
        "cell_id": key.cell_id,
        "run_id": "run-a",
        "source_job_id": key.source_job_id,
        "route_id": frontier_helpers._sha(f"frontier-race-{suffix}-{winning_index}"),
        "action_generation": 1,
    }
    assert reopened.get_acquisition_action_head(**winner_scope) == winning_commit.head
    assert (
        reopened.get_acquisition_action_head_by_receipt(
            **winner_scope, receipt_ref=winning_commit.head.receipt_ref
        )
        == winning_commit.head
    )
    assert (
        stores[0].get_acquisition_action_head(
            tenant_id=key.tenant_id,
            cell_id=key.cell_id,
            run_id="run-a",
            source_job_id=key.source_job_id,
            route_id=frontier_helpers._sha(f"frontier-race-{suffix}-{winning_index}"),
            action_generation=1,
        )
        is not None
    )
    assert (
        stores[0].get_acquisition_action_head(
            tenant_id=key.tenant_id,
            cell_id=key.cell_id,
            run_id="run-a",
            source_job_id=key.source_job_id,
            route_id=frontier_helpers._sha(f"frontier-race-{suffix}-{losing_index}"),
            action_generation=1,
        )
        is None
    )

    psycopg = importlib.import_module("psycopg")
    with psycopg.connect(postgres_dsn) as connection:
        rows = connection.execute(
            "SELECT revision, frontier_ref "
            "FROM runtime_acquisition_evaluation_frontier_versions "
            "WHERE tenant_id = %s AND cell_id = %s AND source_job_id = %s "
            "AND design_problem_ref = %s AND candidate_id = %s "
            "ORDER BY revision",
            (
                key.tenant_id,
                key.cell_id,
                key.source_job_id,
                key.design_problem_ref,
                key.candidate_id,
            ),
        ).fetchall()
    assert rows == [
        (1, initial.frontier_ref),
        (2, winning_commit.frontier.frontier_ref),
    ]

    for label, expected_revision, expected_ref in (
        ("stale-revision", 1, winning_commit.frontier.frontier_ref),
        ("stale-ref", 2, frontier_helpers._sha("not-current-frontier")),
    ):
        job, worker, attempt = frontier_helpers._create_action_job(
            stores[0],
            job_id=f"frontier-{label}-{suffix}",
        )
        with pytest.raises(ValueError, match="acquisition_evaluation_frontier_conflict"):
            frontier_helpers._append_action(
                stores[0],
                job=job,
                worker_id=worker,
                attempt=attempt,
                key=key,
                expected_revision=expected_revision,
                expected_ref=expected_ref,
                route_id=f"frontier-{label}-{suffix}",
                replacement=None,
            )
        assert stores[1].read_acquisition_evaluation_frontier(key) == winning_commit.frontier
        assert (
            stores[1].get_acquisition_action_head(
                tenant_id=key.tenant_id,
                cell_id=key.cell_id,
                run_id="run-a",
                source_job_id=key.source_job_id,
                route_id=frontier_helpers._sha(f"frontier-{label}-{suffix}"),
                action_generation=1,
            )
            is None
        )

    rollback_job, rollback_worker, rollback_attempt = frontier_helpers._create_action_job(
        stores[0],
        job_id=f"frontier-rollback-{suffix}",
    )
    with pytest.raises(ValueError, match="acquisition_action_predecessor_conflict"):
        frontier_helpers._append_action(
            stores[0],
            job=rollback_job,
            worker_id=rollback_worker,
            attempt=rollback_attempt,
            key=key,
            expected_revision=2,
            expected_ref=winning_commit.frontier.frontier_ref,
            route_id=f"frontier-race-{suffix}-{winning_index}",
            replacement=frontier_helpers._value("compiled-frontier-rollback", "tuple-rollback"),
        )
    assert stores[1].read_acquisition_evaluation_frontier(key) == winning_commit.frontier
    assert stores[1].get_acquisition_evaluation_frontier_by_ref(initial.frontier_ref) == initial
    with psycopg.connect(postgres_dsn) as connection:
        final_rows = connection.execute(
            "SELECT revision, frontier_ref "
            "FROM runtime_acquisition_evaluation_frontier_versions "
            "WHERE tenant_id = %s AND cell_id = %s AND source_job_id = %s "
            "AND design_problem_ref = %s AND candidate_id = %s "
            "ORDER BY revision",
            (
                key.tenant_id,
                key.cell_id,
                key.source_job_id,
                key.design_problem_ref,
                key.candidate_id,
            ),
        ).fetchall()
    assert final_rows == rows


def test_postgres_generic_model_input_frontier_roundtrips_current_use_and_legacy_family(
    postgres_dsn: str,
    tmp_path: Path,
) -> None:
    """Retain initial Generic N5, check equivalent use, then advance same subject key."""
    suffix = uuid.uuid4().hex
    store = ControlPlaneStore(
        backend="postgres",
        sqlite_path=tmp_path / f"unused-generic-roundtrip-{suffix}.sqlite3",
        postgres_dsn=postgres_dsn,
    )
    (
        source,
        key,
        initial_job,
        _,
        _,
        _,
        _,
        _,
        initial_evaluation,
        _,
        initial,
    ) = frontier_helpers._commit_generic_initial(
        store,
        tmp_path,
        source_job_id=f"generic-source-{suffix}",
        action_job_id=f"generic-initial-{suffix}",
    )
    legacy_initial = store.read_acquisition_evaluation_frontier(
        frontier_helpers._key(source.job_id)
    )
    assert legacy_initial is not None
    assert initial.selected_evaluation == initial_evaluation
    assert store.get_job(initial_job.job_id).state == "completed"
    assert (
        key.tenant_id,
        key.cell_id,
        key.source_job_id,
        key.design_problem_ref,
        key.candidate_id,
    ) == (
        legacy_initial.key.tenant_id,
        legacy_initial.key.cell_id,
        legacy_initial.key.source_job_id,
        legacy_initial.key.design_problem_ref,
        legacy_initial.key.candidate_id,
    )

    (
        equivalent_job,
        equivalent_worker,
        equivalent_attempt,
        _,
        equivalent_decision,
        equivalent_decision_ref,
        equivalent_replacement_basis,
        equivalent_cas,
    ) = frontier_helpers._prepare_generic_comparison(
        store,
        tmp_path,
        source_job_id=source.job_id,
        prior=initial,
        action_job_id=f"generic-equivalent-{suffix}",
        result="equivalent",
    )
    assert equivalent_replacement_basis is None
    with store.job_execution_fence(
        job_id=equivalent_job.job_id,
        worker_id=equivalent_worker,
        attempt=equivalent_attempt,
    ):
        store.complete_job(
            job_id=equivalent_job.job_id,
            run_id="run-a",
            progress={},
            generic_model_input_frontier_cas=equivalent_cas,
        )
    assert store.read_generic_model_input_frontier(key) == initial
    equivalent_use = store.get_generic_model_input_use(key=key, action_job_id=equivalent_job.job_id)
    assert equivalent_use is not None
    assert equivalent_use.decision_ref == equivalent_decision_ref
    assert equivalent_use.frontier_ref == initial.frontier_ref
    assert equivalent_decision.comparison_result == "equivalent"
    equivalent_event = store.get_job_terminal_source_event_record(equivalent_job.job_id)
    equivalent_outbox = store.get_job_completed_outbox_event(equivalent_job.job_id)
    assert (
        equivalent_event.payload["generic_model_input_current_use"]["frontier_ref"]
        == initial.frontier_ref
    )
    assert (
        equivalent_outbox.payload["generic_model_input_current_use"]
        == equivalent_outbox.payload["progress"]["generic_model_input_current_use"]
    )

    (
        changed_job,
        changed_worker,
        changed_attempt,
        _,
        changed_decision,
        changed_decision_ref,
        changed_replacement_basis,
        changed_cas,
    ) = frontier_helpers._prepare_generic_comparison(
        store,
        tmp_path,
        source_job_id=source.job_id,
        prior=initial,
        action_job_id=f"generic-changed-{suffix}",
        result="different",
    )
    assert changed_replacement_basis is not None
    with store.job_execution_fence(
        job_id=changed_job.job_id,
        worker_id=changed_worker,
        attempt=changed_attempt,
    ):
        store.complete_job(
            job_id=changed_job.job_id,
            run_id="run-a",
            progress={},
            generic_model_input_frontier_cas=changed_cas,
        )

    changed = store.read_generic_model_input_frontier(key)
    assert changed is not None and changed.revision == 2
    assert changed.key == initial.key
    assert changed.frontier_ref != initial.frontier_ref
    assert changed.selected_evaluation.action_job_id == changed_job.job_id
    assert store.get_generic_model_input_frontier_by_ref(initial.frontier_ref) == initial
    assert store.read_acquisition_evaluation_frontier(frontier_helpers._key(source.job_id)) == (
        legacy_initial
    )
    changed_use = store.get_generic_model_input_use(key=key, action_job_id=changed_job.job_id)
    assert changed_use is not None
    assert changed_use.decision_ref == changed_decision_ref
    assert changed_use.frontier_ref == changed.frontier_ref
    assert changed_decision.comparison_result == "different"
    changed_event = store.get_job_terminal_source_event_record(changed_job.job_id)
    changed_outbox = store.get_job_completed_outbox_event(changed_job.job_id)
    changed_projection = changed_event.payload["generic_model_input_current_use"]
    assert changed_projection["frontier_ref"] == changed.frontier_ref
    assert (
        changed_outbox.payload["generic_model_input_current_use"]
        == changed_outbox.payload["progress"]["generic_model_input_current_use"]
        == changed_projection
    )

    reopened = ControlPlaneStore(
        backend="postgres",
        sqlite_path=tmp_path / f"unused-generic-roundtrip-reopen-{suffix}.sqlite3",
        postgres_dsn=postgres_dsn,
    )
    assert reopened.read_generic_model_input_frontier(key) == changed
    assert reopened.get_generic_model_input_frontier_by_ref(initial.frontier_ref) == initial
    assert reopened.get_generic_model_input_use(key=key, action_job_id=changed_job.job_id) == (
        changed_use
    )
    assert reopened.get_job_completed_outbox_event(changed_job.job_id) == changed_outbox
    assert reopened.read_acquisition_evaluation_frontier(frontier_helpers._key(source.job_id)) == (
        legacy_initial
    )


def test_postgres_generic_model_input_frontier_cas_race_rolls_back_loser_completion(
    postgres_dsn: str,
    tmp_path: Path,
) -> None:
    """Race same-key Generic replacements and prove winner-only durable completion."""
    suffix = uuid.uuid4().hex
    stores = (
        ControlPlaneStore(
            backend="postgres",
            sqlite_path=tmp_path / f"unused-generic-race-first-{suffix}.sqlite3",
            postgres_dsn=postgres_dsn,
        ),
        ControlPlaneStore(
            backend="postgres",
            sqlite_path=tmp_path / f"unused-generic-race-second-{suffix}.sqlite3",
            postgres_dsn=postgres_dsn,
        ),
    )
    (
        source,
        key,
        _,
        _,
        _,
        _,
        _,
        _,
        _,
        _,
        initial,
    ) = frontier_helpers._commit_generic_initial(
        stores[0],
        tmp_path,
        source_job_id=f"generic-race-source-{suffix}",
        action_job_id=f"generic-race-initial-{suffix}",
    )
    legacy_initial = stores[0].read_acquisition_evaluation_frontier(
        frontier_helpers._key(source.job_id)
    )
    assert legacy_initial is not None
    assert stores[1].read_generic_model_input_frontier(key) == initial

    prepared = tuple(
        frontier_helpers._prepare_generic_comparison(
            stores[0],
            tmp_path,
            source_job_id=source.job_id,
            prior=initial,
            action_job_id=f"generic-race-action-{suffix}-{index}",
            result="different",
        )
        for index in range(2)
    )
    barrier = threading.Barrier(2)

    def _compete(index: int) -> tuple[str, Any]:
        job, worker, attempt, _, _, _, _, cas = prepared[index]
        barrier.wait(timeout=10)
        try:
            with stores[index].job_execution_fence(
                job_id=job.job_id,
                worker_id=worker,
                attempt=attempt,
            ):
                stores[index].complete_job(
                    job_id=job.job_id,
                    run_id="run-a",
                    progress={},
                    generic_model_input_frontier_cas=cas,
                )
        except ValueError as exc:
            return "conflict", exc
        return "committed", job

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = tuple(pool.map(_compete, range(2)))
    winners = [
        (index, result) for index, (kind, result) in enumerate(outcomes) if kind == "committed"
    ]
    conflicts = [
        (index, result) for index, (kind, result) in enumerate(outcomes) if kind == "conflict"
    ]
    assert len(winners) == 1
    assert len(conflicts) == 1
    assert "generic_model_input_frontier_conflict" in str(conflicts[0][1])
    winner_index, winner_job = winners[0]
    loser_index, _ = conflicts[0]
    assert loser_index == 1 - winner_index
    loser_job = prepared[loser_index][0]

    current = stores[0].read_generic_model_input_frontier(key)
    assert current is not None and current.revision == 2
    assert current.key == initial.key
    assert current.selected_evaluation.action_job_id == winner_job.job_id
    assert stores[1].read_generic_model_input_frontier(key) == current
    assert stores[1].get_generic_model_input_frontier_by_ref(initial.frontier_ref) == initial
    assert (
        stores[0].get_generic_model_input_use(key=key, action_job_id=winner_job.job_id) is not None
    )
    assert stores[0].get_generic_model_input_use(key=key, action_job_id=loser_job.job_id) is None
    assert stores[0].get_job(winner_job.job_id).state == "completed"
    assert stores[0].get_job(loser_job.job_id).state == "running"
    with pytest.raises(frontier_helpers.store_module.ControlJobLeaseLostError):
        stores[0].get_job_terminal_source_event_record(loser_job.job_id)

    winner_event = stores[0].get_job_terminal_source_event_record(winner_job.job_id)
    winner_outbox = stores[1].get_job_completed_outbox_event(winner_job.job_id)
    winner_use = stores[1].get_generic_model_input_use(key=key, action_job_id=winner_job.job_id)
    assert winner_use is not None
    assert winner_event.payload["generic_model_input_current_use"]["frontier_ref"] == (
        current.frontier_ref
    )
    assert (
        winner_outbox.payload["generic_model_input_current_use"]
        == winner_outbox.payload["progress"]["generic_model_input_current_use"]
        == winner_event.payload["generic_model_input_current_use"]
    )
    assert winner_outbox.event_key == f"{winner_job.job_id}:job_completed"

    psycopg = importlib.import_module("psycopg")
    with psycopg.connect(postgres_dsn) as connection:
        version_rows = connection.execute(
            "SELECT revision, frontier_ref "
            "FROM runtime_generic_model_input_evaluation_frontier_versions "
            "WHERE tenant_id = %s AND cell_id = %s AND source_job_id = %s "
            "AND design_problem_ref = %s AND candidate_id = %s "
            "AND family = %s ORDER BY revision",
            (
                key.tenant_id,
                key.cell_id,
                key.source_job_id,
                key.design_problem_ref,
                key.candidate_id,
                key.family,
            ),
        ).fetchall()
        outbox_counts = connection.execute(
            "SELECT job_id, COUNT(*) FROM control_outbox_events "
            "WHERE topic = %s AND job_id IN (%s, %s) GROUP BY job_id",
            ("control.job.completed", winner_job.job_id, loser_job.job_id),
        ).fetchall()
    assert version_rows == [(1, initial.frontier_ref), (2, current.frontier_ref)]
    assert outbox_counts == [(winner_job.job_id, 1)]
    assert stores[0].read_acquisition_evaluation_frontier(frontier_helpers._key(source.job_id)) == (
        legacy_initial
    )

    reopened = ControlPlaneStore(
        backend="postgres",
        sqlite_path=tmp_path / f"unused-generic-race-reopen-{suffix}.sqlite3",
        postgres_dsn=postgres_dsn,
    )
    assert reopened.read_generic_model_input_frontier(key) == current
    assert reopened.get_generic_model_input_frontier_by_ref(initial.frontier_ref) == initial
    assert (
        reopened.get_generic_model_input_use(key=key, action_job_id=winner_job.job_id) == winner_use
    )
    assert reopened.get_generic_model_input_use(key=key, action_job_id=loser_job.job_id) is None
    assert reopened.get_job_completed_outbox_event(winner_job.job_id) == winner_outbox
    assert reopened.read_acquisition_evaluation_frontier(frontier_helpers._key(source.job_id)) == (
        legacy_initial
    )
