from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import pandas as pd
import pytest

from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.identity import PIIAccessLevel, PolicyOSRole
from polisyos.fabric.security import (
    DataClassification,
    JsonlAccessAuditLog,
    RowAccessPolicy,
)
from polisyos.fabric.world_query import WorldQueryError, WorldQueryRequest, execute_world_query


class _MaskingBackend:
    backend_kind = "postgres"
    placeholder = "%s"
    tenant_scope_enforced = True

    def __init__(self) -> None:
        self.last_sql = ""

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        del sql, params
        return None

    def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[tuple[Any, ...]]:
        del sql, params
        return []

    def fetchdf(self, sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
        del params
        self.last_sql = sql
        # Simulate backend returning extra columns regardless of projection.
        return pd.DataFrame([{"claim_id": "c1", "confidence": 0.9, "ssn": "123-45-6789"}])

    @contextmanager
    def transaction(self) -> Iterator[None]:
        yield

    @contextmanager
    def tenant_scope(self, tenant_id: str) -> Iterator[None]:
        del tenant_id
        yield

    def close(self) -> None:
        return None


class _NonTenantScopedBackend:
    backend_kind = "duckdb"
    placeholder = "?"
    tenant_scope_enforced = False

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        del sql, params
        return None

    def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[tuple[Any, ...]]:
        del sql, params
        return []

    def fetchdf(self, sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
        del sql, params
        return pd.DataFrame([{"claim_id": "c1"}])

    @contextmanager
    def transaction(self) -> Iterator[None]:
        yield

    def close(self) -> None:
        return None


def test_world_query_expands_star_to_allowed_columns() -> None:
    backend = _MaskingBackend()
    request = WorldQueryRequest(
        table="claims",
        columns=("*",),
        allowed_columns=("claim_id", "confidence"),
        limit=10,
    )

    frame = execute_world_query(backend, request)

    assert "SELECT claim_id, confidence" in backend.last_sql
    assert list(frame.columns) == ["claim_id", "confidence"]


def test_world_query_rejects_disallowed_column() -> None:
    backend = _MaskingBackend()
    request = WorldQueryRequest(
        table="claims",
        columns=("claim_id", "ssn"),
        allowed_columns=("claim_id",),
        limit=10,
    )

    with pytest.raises(WorldQueryError, match="Unauthorized columns"):
        execute_world_query(backend, request)


def test_world_query_treats_allowed_columns_case_insensitively() -> None:
    backend = _MaskingBackend()
    request = WorldQueryRequest(
        table="claims",
        columns=("CLAIM_ID", "confidence"),
        allowed_columns=("claim_id", "CONFIDENCE"),
        limit=10,
    )

    frame = execute_world_query(backend, request)

    assert list(frame.columns) == ["claim_id", "confidence"]


def test_world_query_rejects_classified_column_without_scope() -> None:
    backend = _MaskingBackend()
    request = WorldQueryRequest(
        table="claims",
        columns=("ssn",),
        allowed_columns=("claim_id", "ssn"),
        column_classification={"ssn": DataClassification.REGULATED_PII},
        limit=10,
    )

    with pytest.raises(WorldQueryError, match="Unauthorized classified columns"):
        execute_world_query(backend, request)


def test_world_query_emits_access_audit_log(tmp_path) -> None:
    backend = _MaskingBackend()
    audit_path = tmp_path / "world-access.jsonl"
    request = WorldQueryRequest(
        table="claims",
        columns=("*",),
        allowed_columns=("claim_id", "confidence"),
        access_scope=AccessScope(
            tenant_id="tenant-a",
            cell_id=None,
            principal_type="user",
            user_sub="alice",
            roles=frozenset({PolicyOSRole.ANALYST}),
            max_pii_tier=PIIAccessLevel.HIGH,
            mfa_verified=True,
        ),
        classification=DataClassification.INTERNAL,
        purpose_of_use="investigation",
        row_policy=RowAccessPolicy(tenant_id="tenant-a"),
        tenant_column="tenant_id",
        audit_log=JsonlAccessAuditLog(audit_path),
        limit=10,
    )

    frame = execute_world_query(backend, request)

    assert not frame.empty
    payload = json.loads(audit_path.read_text(encoding="utf-8").strip())
    assert payload["decision"] == "allow"
    assert payload["actor"] == "alice"
    assert payload["classification"] == "internal"
    assert payload["metadata"]["tenant_filter"] == "tenant-a"


def test_world_query_rejects_conflicting_row_policy_filter() -> None:
    backend = _MaskingBackend()
    request = WorldQueryRequest(
        table="claims",
        columns=("claim_id",),
        where={"tenant_id": "tenant-a"},
        row_policy=RowAccessPolicy(tenant_id="tenant-b"),
        tenant_column="tenant_id",
        limit=10,
    )

    with pytest.raises(WorldQueryError, match="Conflicting row-level filter"):
        execute_world_query(backend, request)


def test_world_query_requires_enforced_tenant_scope_for_tenant_policy() -> None:
    backend = _NonTenantScopedBackend()
    request = WorldQueryRequest(
        table="claims",
        columns=("claim_id",),
        row_policy=RowAccessPolicy(tenant_id="tenant-a"),
        tenant_column="tenant_id",
        limit=10,
    )

    with pytest.raises(WorldQueryError, match="does not support enforced tenant_scope"):
        execute_world_query(backend, request)
