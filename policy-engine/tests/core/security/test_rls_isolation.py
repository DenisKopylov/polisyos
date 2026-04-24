from __future__ import annotations

import os

import pytest

pytest.importorskip("psycopg")

from polisyos.core.security.db_backend import PostgresBackend

PG_DSN = os.environ.get("POLISYOS_TEST_PG_DSN", "")
pytestmark = pytest.mark.skipif(not PG_DSN, reason="POLISYOS_TEST_PG_DSN is not set")

TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


@pytest.fixture
def backend() -> PostgresBackend:
    be = PostgresBackend(PG_DSN)
    be.connect()
    yield be
    be.close()


def _prepare_schema(backend: PostgresBackend) -> None:
    backend.execute(
        "CREATE TABLE IF NOT EXISTS public.rls_test_records (id TEXT PRIMARY KEY, tenant_id UUID NOT NULL, payload TEXT NOT NULL)"
    )
    backend.execute("ALTER TABLE public.rls_test_records ENABLE ROW LEVEL SECURITY")
    backend.execute("ALTER TABLE public.rls_test_records FORCE ROW LEVEL SECURITY")
    backend.execute(
        "DROP POLICY IF EXISTS tenant_access_rls_test_records ON public.rls_test_records"
    )
    backend.execute(
        "CREATE POLICY tenant_access_rls_test_records ON public.rls_test_records "
        "USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
    )
    backend.execute("DELETE FROM public.rls_test_records")


def test_tenant_cannot_read_other_tenant_rows(backend: PostgresBackend) -> None:
    with backend.transaction():
        _prepare_schema(backend)

    with backend.transaction(), backend.tenant_scope(TENANT_A):
        backend.execute(
            "INSERT INTO public.rls_test_records (id, tenant_id, payload) VALUES (%s, %s, %s)",
            ["a1", TENANT_A, "row-a"],
        )

    with backend.transaction(), backend.tenant_scope(TENANT_B):
        backend.execute(
            "INSERT INTO public.rls_test_records (id, tenant_id, payload) VALUES (%s, %s, %s)",
            ["b1", TENANT_B, "row-b"],
        )

    with backend.transaction(), backend.tenant_scope(TENANT_A):
        rows = backend.fetchall("SELECT id FROM public.rls_test_records ORDER BY id")
        assert rows == [("a1",)]


def test_without_tenant_context_returns_no_rows(backend: PostgresBackend) -> None:
    with backend.transaction():
        _prepare_schema(backend)

    with backend.transaction(), backend.tenant_scope(TENANT_A):
        backend.execute(
            "INSERT INTO public.rls_test_records (id, tenant_id, payload) VALUES (%s, %s, %s)",
            ["a1", TENANT_A, "row-a"],
        )

    with backend.transaction():
        rows = backend.fetchall("SELECT id FROM public.rls_test_records")
        assert rows == []
