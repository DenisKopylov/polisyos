"""E2E tests for multi-tenant isolation, namespace validation, and quota enforcement.

These tests verify:
* Cross-tenant artifact isolation
* Namespace collision prevention
* Cell-level isolation within a tenant
* Hard quota enforcement (concurrent runs, daily runs, LLM spend)
* Concurrent tenant stress test
"""

from __future__ import annotations

import threading
from decimal import Decimal
from typing import Any

import pytest

from polisyos.core.security.namespace import (
    NamespacedArtifactStore,
    namespaced_artifact_id,
    namespaced_lock_key,
    namespaced_run_id,
)
from polisyos.core.security.quota_enforcer import (
    QuotaAccountingError,
    QuotaEnforcer,
    QuotaExceededError,
)
from polisyos.core.security.tenant_quota import TenantQuotaLimits, TenantQuotaState

# ---------------------------------------------------------------------------
# Minimal in-memory artifact store for isolation tests
# ---------------------------------------------------------------------------


class InMemoryArtifactStore:
    """Simple in-memory store for testing namespace isolation."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def has(self, artifact_id: str) -> bool:
        return artifact_id in self._data

    def get_bytes(self, artifact_id: str) -> bytes:
        if artifact_id not in self._data:
            raise KeyError(f"Artifact not found: {artifact_id}")
        return self._data[artifact_id]

    def put_bytes(self, data: bytes, opts: Any = None) -> str:
        # Use a simple incrementing ID
        aid = f"art-{len(self._data)}"
        self._data[aid] = data
        return aid

    def get_manifest(self, artifact_id: str) -> dict[str, Any]:
        return {"id": artifact_id}

    def put_json(self, obj: Any, opts: Any = None, canon_spec: Any = None) -> str:
        import json

        return self.put_bytes(json.dumps(obj).encode(), opts)

    def verify(self, artifact_id: str) -> dict[str, Any]:
        return {"valid": self.has(artifact_id)}

    def iter_artifact_ids(self) -> list[str]:
        return list(self._data.keys())


# ---------------------------------------------------------------------------
# TestCrossTenantArtifactIsolation
# ---------------------------------------------------------------------------


class TestCrossTenantArtifactIsolation:
    """Tenant A puts → Tenant B can't see it."""

    def test_tenant_a_invisible_to_tenant_b(self) -> None:
        base = InMemoryArtifactStore()
        store_a = NamespacedArtifactStore(base, tenant_id="tenant_a")
        store_b = NamespacedArtifactStore(base, tenant_id="tenant_b")

        # Tenant A writes
        base._data["tenant_a:my-artifact"] = b"secret"

        assert store_a.has("my-artifact") is True
        assert store_b.has("my-artifact") is False

    def test_iter_artifact_ids_filtered(self) -> None:
        base = InMemoryArtifactStore()
        base._data["tenant_a:art1"] = b"a1"
        base._data["tenant_b:art2"] = b"b1"

        store_a = NamespacedArtifactStore(base, tenant_id="tenant_a")
        store_b = NamespacedArtifactStore(base, tenant_id="tenant_b")

        assert store_a.iter_artifact_ids() == ["art1"]
        assert store_b.iter_artifact_ids() == ["art2"]

    def test_same_base_id_no_collision(self) -> None:
        base = InMemoryArtifactStore()
        base._data["tenant_a:shared-name"] = b"from_a"
        base._data["tenant_b:shared-name"] = b"from_b"

        store_a = NamespacedArtifactStore(base, tenant_id="tenant_a")
        store_b = NamespacedArtifactStore(base, tenant_id="tenant_b")

        assert store_a.get_bytes("shared-name") == b"from_a"
        assert store_b.get_bytes("shared-name") == b"from_b"

    def test_tenant_b_cannot_get_tenant_a_artifact(self) -> None:
        base = InMemoryArtifactStore()
        base._data["tenant_a:secret"] = b"sensitive"

        store_b = NamespacedArtifactStore(base, tenant_id="tenant_b")
        with pytest.raises(KeyError):
            store_b.get_bytes("secret")

    def test_put_bytes_uses_base_store(self) -> None:
        base = InMemoryArtifactStore()
        store_a = NamespacedArtifactStore(base, tenant_id="tenant_a")
        ref = store_a.put_bytes(b"data")
        # put_bytes goes through the inner store directly
        assert isinstance(ref, str)


# ---------------------------------------------------------------------------
# TestNamespaceCollisionPrevention
# ---------------------------------------------------------------------------


class TestNamespaceCollisionPrevention:
    """Validate that bad tenant/cell IDs are rejected."""

    def test_colon_in_tenant_id_raises(self) -> None:
        with pytest.raises(ValueError, match="must not contain separator"):
            namespaced_artifact_id("bad:id", None, "base")

    def test_empty_tenant_id_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            namespaced_artifact_id("", None, "base")

    def test_unicode_tenant_id_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant_id"):
            namespaced_artifact_id("тенант", None, "base")

    def test_valid_tenant_id_passes(self) -> None:
        result = namespaced_artifact_id("valid-tenant_1", None, "base")
        assert result == "valid-tenant_1:base"

    def test_colon_in_cell_id_raises(self) -> None:
        with pytest.raises(ValueError, match="must not contain separator"):
            namespaced_artifact_id("tenant", "bad:cell", "base")

    def test_run_id_validation(self) -> None:
        with pytest.raises(ValueError):
            namespaced_run_id("a:b", None, "run-1")

    def test_lock_key_validation(self) -> None:
        with pytest.raises(ValueError):
            namespaced_lock_key("a:b", None, "lock-1")

    def test_starts_with_dash_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant_id"):
            namespaced_artifact_id("-bad", None, "base")

    def test_too_long_tenant_id_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant_id"):
            namespaced_artifact_id("a" * 65, None, "base")


# ---------------------------------------------------------------------------
# TestCellLevelIsolation
# ---------------------------------------------------------------------------


class TestCellLevelIsolation:
    """Within a tenant, cells are isolated."""

    def test_different_cells_isolated(self) -> None:
        base = InMemoryArtifactStore()
        store_c1 = NamespacedArtifactStore(base, tenant_id="t1", cell_id="cell_a")
        store_c2 = NamespacedArtifactStore(base, tenant_id="t1", cell_id="cell_b")

        base._data["t1:cell_a:doc"] = b"cell_a_data"

        assert store_c1.has("doc") is True
        assert store_c2.has("doc") is False

    def test_same_cell_shared(self) -> None:
        base = InMemoryArtifactStore()
        store1 = NamespacedArtifactStore(base, tenant_id="t1", cell_id="shared")
        store2 = NamespacedArtifactStore(base, tenant_id="t1", cell_id="shared")

        base._data["t1:shared:doc"] = b"shared_data"

        assert store1.has("doc") is True
        assert store2.has("doc") is True
        assert store1.get_bytes("doc") == store2.get_bytes("doc")

    def test_cell_iter_filtered(self) -> None:
        base = InMemoryArtifactStore()
        base._data["t1:c1:x"] = b"1"
        base._data["t1:c2:y"] = b"2"

        store = NamespacedArtifactStore(base, tenant_id="t1", cell_id="c1")
        assert store.iter_artifact_ids() == ["x"]


# ---------------------------------------------------------------------------
# TestQuotaEnforcementE2E
# ---------------------------------------------------------------------------


class TestQuotaEnforcementE2E:
    """Hard quota enforcement blocks when limits exceeded."""

    def test_max_concurrent_runs_blocks(self) -> None:
        limits = TenantQuotaLimits(max_concurrent_runs=2, enforcement_mode="block")
        state = TenantQuotaState(tenant_id="t1")
        enforcer = QuotaEnforcer(limits, state)

        enforcer.record_run_start()
        enforcer.record_run_start()
        with pytest.raises(QuotaExceededError, match="concurrent_runs"):
            enforcer.check_run_start()

    def test_max_daily_runs_blocks(self) -> None:
        limits = TenantQuotaLimits(max_runs_per_day=1, enforcement_mode="block")
        state = TenantQuotaState(tenant_id="t2")
        enforcer = QuotaEnforcer(limits, state)

        enforcer.record_run_start()
        enforcer.record_run_end()
        with pytest.raises(QuotaExceededError, match="daily_runs"):
            enforcer.check_run_start()

    def test_llm_spend_block_mode(self) -> None:
        limits = TenantQuotaLimits(
            max_llm_spend_usd_per_day=Decimal("10"),
            enforcement_mode="block",
        )
        state = TenantQuotaState(tenant_id="t3")
        enforcer = QuotaEnforcer(limits, state)

        enforcer.record_llm_spend(Decimal("9"))
        with pytest.raises(QuotaExceededError, match="daily_llm_spend"):
            enforcer.record_llm_spend(Decimal("5"))

    def test_llm_spend_warn_mode_no_raise(self) -> None:
        limits = TenantQuotaLimits(
            max_llm_spend_usd_per_day=Decimal("10"),
            enforcement_mode="warn",
        )
        state = TenantQuotaState(tenant_id="t4")
        enforcer = QuotaEnforcer(limits, state)

        # Should warn, not raise
        enforcer.record_llm_spend(Decimal("15"))

    def test_storage_block_mode(self) -> None:
        limits = TenantQuotaLimits(
            max_storage_bytes=100,
            enforcement_mode="block",
        )
        state = TenantQuotaState(tenant_id="t5")
        enforcer = QuotaEnforcer(limits, state)

        enforcer.record_storage_delta(80)
        with pytest.raises(QuotaExceededError, match="storage_bytes"):
            enforcer.record_storage_delta(30)

    def test_check_llm_spend_preflight(self) -> None:
        limits = TenantQuotaLimits(
            max_llm_spend_usd_per_day=Decimal("10"),
            enforcement_mode="block",
        )
        state = TenantQuotaState(tenant_id="t6")
        enforcer = QuotaEnforcer(limits, state)

        enforcer.record_llm_spend(Decimal("8"))
        with pytest.raises(QuotaExceededError):
            enforcer.check_llm_spend(Decimal("5"))

    def test_check_storage_delta_preflight(self) -> None:
        limits = TenantQuotaLimits(
            max_storage_bytes=100,
            enforcement_mode="block",
        )
        state = TenantQuotaState(tenant_id="t7")
        enforcer = QuotaEnforcer(limits, state)

        enforcer.record_storage_delta(90)
        with pytest.raises(QuotaExceededError):
            enforcer.check_storage_delta(20)

    def test_negative_storage_delta_requires_trusted_release_path(self) -> None:
        limits = TenantQuotaLimits(max_storage_bytes=100, enforcement_mode="block")
        state = TenantQuotaState(tenant_id="t8", storage_bytes_used=50)
        enforcer = QuotaEnforcer(limits, state)

        with pytest.raises(QuotaAccountingError, match="trusted release_storage"):
            enforcer.record_storage_delta(-10)

        with pytest.raises(QuotaAccountingError, match="trusted release_storage"):
            enforcer.check_storage_delta(-10)

        enforcer.release_storage(15)
        assert state.storage_bytes_used == 35


# ---------------------------------------------------------------------------
# TestConcurrentTenantStress
# ---------------------------------------------------------------------------


class TestConcurrentTenantStress:
    """10 threads × different tenant_scope × 5 artifacts → zero cross-contamination."""

    def test_concurrent_tenant_isolation(self) -> None:
        base = InMemoryArtifactStore()
        errors: list[str] = []
        num_tenants = 10
        artifacts_per_tenant = 5

        def worker(tenant_id: str) -> None:
            store = NamespacedArtifactStore(base, tenant_id=tenant_id)
            for i in range(artifacts_per_tenant):
                key = f"{tenant_id}:art-{i}"
                base._data[key] = f"data-{tenant_id}-{i}".encode()

            # Verify own artifacts visible
            ids = store.iter_artifact_ids()
            if len(ids) != artifacts_per_tenant:
                errors.append(f"{tenant_id}: expected {artifacts_per_tenant}, got {len(ids)}")

            # Verify no other tenant's data visible
            for aid in ids:
                if not aid.startswith("art-"):
                    errors.append(f"{tenant_id}: unexpected artifact {aid}")

        threads = []
        for t_idx in range(num_tenants):
            tid = f"tenant{t_idx:02d}"
            t = threading.Thread(target=worker, args=(tid,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Cross-contamination detected: {errors}"

    def test_concurrent_quota_enforcement(self) -> None:
        """Multiple threads check quota for different tenants concurrently."""
        from polisyos.core.security.quota_registry import TenantQuotaRegistry

        registry = TenantQuotaRegistry()
        errors: list[str] = []

        def worker(tenant_id: str) -> None:
            enforcer = registry.get_enforcer(tenant_id)
            try:
                enforcer.check_run_start()
                enforcer.record_run_start()
                enforcer.record_run_end()
            except Exception as exc:
                errors.append(f"{tenant_id}: {exc}")

        threads = [threading.Thread(target=worker, args=(f"t{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Quota enforcement errors: {errors}"
