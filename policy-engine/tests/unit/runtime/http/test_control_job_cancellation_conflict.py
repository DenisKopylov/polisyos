"""Cheap real-store HTTP cancellation conflict semantics without numerical work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


def test_current_and_stale_cancellation_use_real_store_and_typed_conflict(
    runtime_api_env: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse stale identities unchanged, cancel/retry the current lease, retain internal errors."""
    import hashlib
    import sqlite3
    import struct

    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
    from polisyos.runtime.http import deployment_security
    from polisyos.runtime.http.services.control_plane_store import (
        ControlJobLeaseLostError,
    )
    from tests._helpers.control_worker import stop_embedded_control_worker
    from tests._helpers.runtime_http import deployment_security_config_mapping
    from tests.unit.runtime.http.test_control_plane_store import (
        _job_creation_event,
        _job_execution_scope,
    )
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _fixture_bearer,
    )

    seed_config = runtime_api_env["app"].state.runtime_container.config
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
        repo_root=seed_config.repo_root,
        catalog_source_selection=seed_config.catalog_source_selection,
    )
    tenant = runtime_api_env["tenant_a"]
    bearer = _fixture_bearer("cheap-cancellation-conflict")
    provider.put_claim(
        bearer,
        UserIdentityClaims(
            sub="runtime-canary",
            tenant_id=tenant,
            cell_id=cell.cell_id,
            roles=frozenset({PolicyOSRole.ADMIN}),
            mfa_verified=True,
            iss="https://idp.example",
            aud="polisyos-runtime",
            exp=9_999_999_999,
            iat=1,
            jti="cheap-cancellation-conflict-jwt",
        ),
    )
    config = deployment_security_config_mapping(tmp_path)
    registry_path = tmp_path / "cancellation-cells.json"
    registry_path.write_text(
        json.dumps(
            {
                "cells": [cell.model_dump(mode="json")],
                "tenants": [
                    {
                        "tenant_id": tenant,
                        "name": "Cancellation test tenant",
                        "tier": cell.tier.value,
                        "region": cell.region,
                        "cell_id": cell.cell_id,
                    }
                ],
            }
        )
    )
    config["cell_registry_path"] = str(registry_path)
    principals = config["service_principals"]
    assert isinstance(principals, list)
    principals[0].update(
        {
            "tenant_id": tenant,
            "cell_id": cell.cell_id,
            "permissions": ["runs.view", "jobs.cancel"],
        }
    )
    security = deployment_security.build_deployment_security(
        deployment_security.DeploymentSecurityConfig.from_mapping(config)
    )
    client.app.state.runtime_deployment_principal_grants = security.principal_grants
    headers = {"Authorization": f"Bearer {bearer}", "X-Tenant-ID": tenant}
    with client:
        service = client.app.state.runtime_container.control_service
        assert service is not None
        stop_embedded_control_worker(service)
        store = service._control_store
        scope = _job_execution_scope()
        scope.update({"tenant_id": tenant, "cell_id": cell.cell_id})
        cas = FileSystemCAS(runtime_api_env["cas_root"])
        manifest = cas.put_json(
            {"fixture": "cheap-cancellation-conflict"},
            ArtifactWriteOptions(
                kind="runtime.capability_manifest",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.test.CancellationManifest", version="1.0"),
            ),
        )
        manifest_id = str(manifest.artifact_id)
        creation = _job_creation_event(execution_scope=scope)
        creation["capability_manifest_ref"] = manifest_id
        job = store.create_job(
            job_id="job_execution_admission",
            kind="workflow_run",
            run_id="run_execution_admission",
            pipeline_id=None,
            requested_execution_profile=None,
            effective_execution_profile="dev",
            policy_flags={"candidate": True},
            capability_manifest_ref=manifest_id,
            payload_ref="sha256:payload-b",
            submitted_by="denis",
            creation_event_payload=creation,
        )
        leased = store.lease_next_job(worker_id="cheap-cancel-worker", lease_seconds=300)
        assert leased is not None and leased.job_id == job.job_id and leased.state == "running"
        client.app.state.control_job_cancellation_rollout_enabled = True
        url = f"/api/v1/control/jobs/{job.job_id}/cancel"

        assert store.backend == "sqlite"
        database_path = Path(store._sqlite_path).resolve(strict=True)
        assert database_path.is_relative_to(tmp_path.resolve(strict=True))

        def quote_identifier(name: str) -> str:
            return '"' + name.replace('"', '""') + '"'

        def protected() -> tuple[Any, ...]:
            # Snapshot the complete small test-owned control DB, not parsed job,
            # state-transition or JSON projections. Schema-derived tables and
            # columns include every duplicate event and all related outbox rows.
            # text_factory preserves raw text/blob bytes; typeof preserves their
            # storage class, and real values retain all IEEE754 bits.
            connection = sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True)
            connection.text_factory = bytes
            try:
                connection.execute("PRAGMA query_only = ON")
                connection.execute("BEGIN")
                schema = connection.execute("SELECT * FROM sqlite_schema ORDER BY type, name")
                schema_columns = tuple(column[0] for column in schema.description)
                schema_rows = tuple(tuple(row) for row in schema.fetchall())
                tables = [(row[1], row[4]) for row in schema_rows if row[0] == b"table"]
                assert {
                    b"control_jobs",
                    b"control_job_progress",
                    b"control_job_events",
                    b"control_outbox_events",
                } <= {name for name, _ in tables}
                snapshots = []
                for table_name, table_sql in tables:
                    table = quote_identifier(table_name.decode("utf-8"))
                    columns = tuple(connection.execute(f"PRAGMA table_xinfo({table})").fetchall())
                    assert columns
                    names = [column[1].decode("utf-8") for column in columns]
                    has_rowid = table_sql is None or b"WITHOUT ROWID" not in b" ".join(
                        table_sql.upper().split()
                    )
                    selected = ["_rowid_", *names] if has_rowid else names
                    expressions = [
                        item
                        for name in selected
                        for item in (
                            f"typeof({quote_identifier(name)})",
                            quote_identifier(name),
                        )
                    ]
                    ordering = (
                        "_rowid_"
                        if has_rowid
                        else ", ".join(quote_identifier(name) for name in names)
                    )
                    query = f"SELECT {', '.join(expressions)} FROM {table} ORDER BY {ordering}"  # noqa: S608
                    raw_rows = connection.execute(query).fetchall()
                    rows = []
                    for row in raw_rows:
                        cells = []
                        for offset in range(0, len(row), 2):
                            storage, value = row[offset : offset + 2]
                            assert type(value) in (type(None), int, float, bytes)
                            if type(value) is float:
                                value = struct.pack("!d", value)
                            cells.append((storage, value))
                        rows.append(tuple(cells))
                    snapshots.append((table_name, columns, tuple(selected), tuple(rows)))
                return schema_columns, schema_rows, tuple(snapshots)
            finally:
                connection.close()

        active_corruption: str | None = None

        def assert_raw_equal(
            expected: tuple[Any, ...],
            actual: tuple[Any, ...],
            *,
            phase: str,
            operation: str,
        ) -> None:
            if expected == actual:
                return
            # Diagnose only changed quantities. The equality predicate and full
            # snapshot denominator remain intact; this is not a table allowlist.
            missing = object()
            changes: list[dict[str, Any]] = []
            total_changes = 0
            changed_tables: set[str] = set()

            def describe(value: Any) -> dict[str, Any]:
                if value is missing:
                    return {"presence": "absent"}
                storage, native = value
                raw = native if isinstance(native, bytes) else repr(native).encode("utf-8")
                result: dict[str, Any] = {
                    "sqlite_storage": storage.decode("utf-8", errors="backslashreplace"),
                    "native_type": type(native).__name__,
                    "bytes": len(raw),
                    "value_sha256": hashlib.sha256(
                        storage + b"\0" + type(native).__name__.encode() + b"\0" + raw
                    ).hexdigest(),
                    "complete_value_retained": len(raw) <= 4096,
                }
                if len(raw) <= 4096:
                    if storage == b"real" and isinstance(native, bytes):
                        result["float64_hex"] = native.hex()
                    elif isinstance(native, bytes):
                        try:
                            result["utf8"] = native.decode("utf-8")
                        except UnicodeDecodeError:
                            result["hex"] = native.hex()
                    else:
                        result["value_repr"] = repr(native)
                return result

            def record(table: str, row: str, column: str, left: Any, right: Any) -> None:
                nonlocal total_changes
                if left == right:
                    return
                total_changes += 1
                changed_tables.add(table)
                if len(changes) < 128:
                    changes.append(
                        {
                            "table": table,
                            "row": row,
                            "column": column,
                            "before": describe(left),
                            "after": describe(right),
                        }
                    )

            def row_map(
                rows: tuple[Any, ...],
                selected: tuple[str, ...],
                columns: tuple[Any, ...],
                *,
                schema: bool = False,
            ) -> dict[str, Any]:
                result = {}
                primary = [
                    item[1].decode("utf-8")
                    for item in sorted(columns, key=lambda item: item[5])
                    if item[5] > 0
                ]
                for ordinal, row in enumerate(rows):
                    if schema:
                        identity = (
                            row[selected.index("type")],
                            row[selected.index("name")],
                        )
                    elif selected and selected[0] == "_rowid_":
                        identity = (row[0],)
                    elif primary:
                        identity = tuple(row[selected.index(name)] for name in primary)
                    else:
                        identity = ("ordered-row", ordinal)
                    key = repr(identity)
                    if len(key) > 1024:
                        key = "identity-sha256:" + hashlib.sha256(key.encode()).hexdigest()
                    assert key not in result
                    result[key] = dict(zip(selected, row, strict=True))
                return result

            def compare_rows(table: str, left: dict[str, Any], right: dict[str, Any]) -> None:
                for key in sorted(left.keys() | right.keys()):
                    lrow, rrow = left.get(key, {}), right.get(key, {})
                    for column in sorted(lrow.keys() | rrow.keys()):
                        record(
                            table,
                            key,
                            column,
                            lrow.get(column, missing),
                            rrow.get(column, missing),
                        )

            if expected[0] != actual[0]:
                record(
                    "sqlite_schema",
                    "metadata",
                    "column_names",
                    (b"metadata", repr(expected[0]).encode()),
                    (b"metadata", repr(actual[0]).encode()),
                )
            schema_left = tuple(tuple((b"schema", value) for value in row) for row in expected[1])
            schema_right = tuple(tuple((b"schema", value) for value in row) for row in actual[1])
            compare_rows(
                "sqlite_schema",
                row_map(schema_left, expected[0], (), schema=True),
                row_map(schema_right, actual[0], (), schema=True),
            )
            left_tables = {item[0]: item for item in expected[2]}
            right_tables = {item[0]: item for item in actual[2]}
            if tuple(left_tables) != tuple(right_tables):
                record(
                    "sqlite_schema",
                    "metadata",
                    "table_order",
                    (b"metadata", repr(tuple(left_tables)).encode()),
                    (b"metadata", repr(tuple(right_tables)).encode()),
                )
            for name in sorted(left_tables.keys() | right_tables.keys()):
                table = name.decode("utf-8", errors="backslashreplace")
                left, right = left_tables.get(name), right_tables.get(name)
                if left is None or right is None:
                    record(
                        table,
                        "metadata",
                        "table_presence",
                        missing if left is None else (b"metadata", b"present"),
                        missing if right is None else (b"metadata", b"present"),
                    )
                if left is not None and right is not None:
                    if left[1] != right[1]:
                        record(
                            table,
                            "metadata",
                            "table_xinfo",
                            (b"metadata", repr(left[1]).encode()),
                            (b"metadata", repr(right[1]).encode()),
                        )
                    if left[2] != right[2]:
                        record(
                            table,
                            "metadata",
                            "selected_columns",
                            (b"metadata", repr(left[2]).encode()),
                            (b"metadata", repr(right[2]).encode()),
                        )
                left_rows = {} if left is None else row_map(left[3], left[2], left[1])
                right_rows = {} if right is None else row_map(right[3], right[2], right[1])
                if tuple(left_rows) != tuple(right_rows):
                    record(
                        table,
                        "metadata",
                        "row_order_or_membership",
                        (b"metadata", repr(tuple(left_rows)).encode()),
                        (b"metadata", repr(tuple(right_rows)).encode()),
                    )
                compare_rows(table, left_rows, right_rows)
            report = {
                "schema": "policyos.test.raw_cancellation_mismatch.v1",
                "phase": phase,
                "operation_id": operation,
                "corruption": active_corruption,
                "database": str(database_path),
                "owner_classification": "not_established",
                "expected_snapshot_repr_sha256": hashlib.sha256(
                    repr(expected).encode()
                ).hexdigest(),
                "actual_snapshot_repr_sha256": hashlib.sha256(repr(actual).encode()).hexdigest(),
                "changed_tables": sorted(changed_tables),
                "total_changed_cells": total_changes,
                "reported_changed_cells": len(changes),
                "unreported_changed_cells": total_changes - len(changes),
                "value_byte_limit": 4096,
                "changed_cell_limit": 128,
                "differences": changes,
                "unlocalized_shape_difference": total_changes == 0,
                "limitations": "Only changed cells are retained; larger values have hashes/lengths. This does not classify protected versus independent effects or excuse any difference.",
            }
            path = tmp_path / "cancellation-raw-mismatch.json"
            with path.open("x", encoding="utf-8") as handle:
                json.dump(report, handle, indent=2, sort_keys=True)
                handle.write("\n")
            raise AssertionError(
                f"Raw cancellation mismatch phase={phase} corruption={active_corruption}; "
                f"changed_tables={sorted(changed_tables)} cells={total_changes}; diagnostic={path}"
            )

        def post(
            body: dict[str, Any],
            *,
            authorized: bool = True,
            baseline: tuple[Any, ...] | None = None,
            expect_unchanged: bool = True,
        ) -> tuple[Any, Any, Any]:
            # This is the only POST call site: every request is bracketed by
            # independent consistent read-only snapshots of all raw rows.
            prior = protected()
            if baseline is not None:
                assert_raw_equal(
                    baseline, prior, phase="before_post", operation=body["operation_id"]
                )
            response = client.post(url, headers=headers if authorized else {}, json=body)
            after = protected()
            if expect_unchanged:
                assert_raw_equal(prior, after, phase="post", operation=body["operation_id"])
            return response, prior, after

        before = protected()
        for name, owner, attempt in (
            ("stale-attempt", leased.lease_owner, leased.attempt + 1),
            ("stale-owner", "different-worker", leased.attempt),
        ):
            response, prior, after = post(
                {
                    "operation_id": name,
                    "expected_lease_owner": owner,
                    "expected_attempt": attempt,
                },
                baseline=before,
            )
            assert prior == before
            assert response.status_code == 409, response.text
            assert response.headers["content-type"].startswith("application/problem+json")
            assert response.json()["code"] == "control_job_cancellation_conflict"
            assert after == before
        # Authentication remains mandatory and does not become a conflict response.
        denied, prior, after = post(
            {"operation_id": "anonymous"}, authorized=False, baseline=before
        )
        assert denied.status_code == 401, denied.text
        assert prior == after == before
        body = {
            "operation_id": "cancel-current",
            "expected_lease_owner": leased.lease_owner,
            "expected_attempt": leased.attempt,
        }
        current, prior, cancelled = post(body, baseline=before, expect_unchanged=False)
        assert prior == before
        assert cancelled != before
        assert current.status_code == 200, current.text
        assert current.json()["state"] == "cancelled"
        assert (
            store.get_job(job.job_id).progress["cancellation"]["physical_stop_status"]
            == "not_established"
        )
        repeated, prior, after = post(body, baseline=cancelled)
        assert repeated.status_code == 200, repeated.text
        assert prior == after == cancelled
        changed, prior, after = post(
            {**body, "operation_id": "different-operation"}, baseline=cancelled
        )
        assert changed.status_code == 409, changed.text
        assert changed.json()["code"] == "control_job_cancellation_conflict"
        assert prior == after == cancelled

        # Corrupt real persisted test-owned receipts, not a mocked exception.
        # A different request must not hide integrity failures behind409.
        raw_progress = store._fetchone(
            "SELECT progress_json FROM control_job_progress WHERE job_id = ?",
            (job.job_id,),
        )[0]
        raw_event = store._fetchone(
            "SELECT payload_json FROM control_job_events WHERE job_id = ? AND event_type = ?",
            (job.job_id, "job_cancelled"),
        )[0]
        raw_outbox = store._fetchone(
            "SELECT payload_json FROM control_outbox_events WHERE job_id = ? AND topic = ?",
            (job.job_id, "control.job.cancelled"),
        )[0]

        def restore_persisted_receipt() -> None:
            store._execute(
                "UPDATE control_job_progress SET progress_json = ? WHERE job_id = ?",
                (raw_progress, job.job_id),
            )
            store._execute(
                "UPDATE control_job_events SET payload_json = ? WHERE job_id = ? AND event_type = ?",
                (raw_event, job.job_id, "job_cancelled"),
            )
            store._execute(
                "UPDATE control_outbox_events SET payload_json = ? WHERE job_id = ? AND topic = ?",
                (raw_outbox, job.job_id, "control.job.cancelled"),
            )
            assert_raw_equal(cancelled, protected(), phase="restore", operation="restore-receipt")
            assert protected() == cancelled

        # Keep the old state-transition projection identical while changing a
        # genuine persisted event byte sequence. The complete snapshot must
        # distinguish it without removing any product integrity guard.
        transition_projection = store.list_job_state_transitions(job.job_id)
        probe = json.loads(raw_event)
        probe["raw_snapshot_discriminator"] = "first"
        store._execute(
            "UPDATE control_job_events SET payload_json = ? WHERE job_id = ? AND event_type = ?",
            (json.dumps(probe), job.job_id, "job_cancelled"),
        )
        first_raw = protected()
        assert store.list_job_state_transitions(job.job_id) == transition_projection
        probe["raw_snapshot_discriminator"] = "second"
        store._execute(
            "UPDATE control_job_events SET payload_json = ? WHERE job_id = ? AND event_type = ?",
            (json.dumps(probe), job.job_id, "job_cancelled"),
        )
        second_raw = protected()
        assert store.list_job_state_transitions(job.job_id) == transition_projection
        assert first_raw != second_raw
        restore_persisted_receipt()

        for corrupt in (
            "missing_cancellation",
            "non_dict_cancellation",
            "missing_identity",
            "plausible_progress_conflict",
            "source_event",
            "outbox",
        ):
            active_corruption = corrupt
            restore_persisted_receipt()
            progress = json.loads(raw_progress)
            if corrupt == "missing_cancellation":
                progress.pop("cancellation")
            elif corrupt == "non_dict_cancellation":
                progress["cancellation"] = "malformed"
            elif corrupt == "missing_identity":
                progress["cancellation"].pop("authorized_actor")
            elif corrupt == "plausible_progress_conflict":
                progress["cancellation"]["operation_id"] = "plausible-corrupt-identity"
            if corrupt == "source_event":
                store._execute(
                    "UPDATE control_job_events SET payload_json = ? WHERE job_id = ? AND event_type = ?",
                    ("{}", job.job_id, "job_cancelled"),
                )
            elif corrupt == "outbox":
                store._execute(
                    "UPDATE control_outbox_events SET payload_json = ? WHERE job_id = ? AND topic = ?",
                    ("{}", job.job_id, "control.job.cancelled"),
                )
            else:
                store._execute(
                    "UPDATE control_job_progress SET progress_json = ? WHERE job_id = ?",
                    (json.dumps(progress), job.job_id),
                )
            corrupted = protected()
            assert corrupted != cancelled
            with pytest.raises(ControlJobLeaseLostError):
                store.get_cancelled_job_verified_record(job.job_id)
            assert_raw_equal(
                corrupted,
                protected(),
                phase="explicit_verifier",
                operation="verify-corrupt-receipt",
            )
            refused, prior, after = post(
                {**body, "operation_id": "different-valid-request"}, baseline=corrupted
            )
            assert refused.status_code == 500, (corrupt, refused.text)
            assert prior == after == corrupted
        restore_persisted_receipt()
        assert store.get_cancelled_job_verified_record(job.job_id).state == "cancelled"
        assert protected() == cancelled
        active_corruption = None
        restored, prior, after = post(body, baseline=cancelled)
        assert restored.status_code == 200, restored.text
        assert prior == after == cancelled

        # The new mapping must not hide an unrelated worker/publication lease error.
        def internal_lease_failure(**kwargs: Any) -> Any:
            raise ControlJobLeaseLostError("unrelated internal publication failure")

        with monkeypatch.context() as internal:
            internal.setattr(store, "cancel_job", internal_lease_failure)
            unexpected, prior, after = post(body, baseline=cancelled)
        assert unexpected.status_code == 500, unexpected.text
        assert prior == after == cancelled
        operation = client.app.openapi()["paths"]["/api/v1/control/jobs/{job_id}/cancel"]["post"]
        assert "409" in operation["responses"]
