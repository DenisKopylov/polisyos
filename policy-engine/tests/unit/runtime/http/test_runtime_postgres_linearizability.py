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
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _BarrierOPA,
    _build_secure_client,
    _CaptureOPA,
    _claims,
    _fixture_bearer,
    _scenario_create_body,
)

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
