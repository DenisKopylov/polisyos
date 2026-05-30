from __future__ import annotations

import os

import pytest

from _helpers.runtime_http import build_runtime_api_env
from polisyos.common.config import build_process_bootstrap_config
from polisyos.core.security import (
    AccessScope,
    get_security_settings,
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.fabric.security.adapters import get_fabric_security_adapter

pytestmark = pytest.mark.integration


def test_core_security_config_reaches_runtime_startup_and_fabric_context(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_MULTI_TENANT_ENABLED", "true")
    monkeypatch.setenv("POLISYOS_DEFAULT_CELL_TIER", "dedicated")
    monkeypatch.setenv("POLISYOS_AUTHZ_MODE", "shadow")
    monkeypatch.setenv("POLISYOS_ENABLE_DEV_FIXTURE_IDENTITY", "true")
    get_security_settings.cache_clear()

    env = build_runtime_api_env(tmp_path, include_test_client=True)
    try:
        bootstrap = build_process_bootstrap_config(env=os.environ, total_cores=8)
        security_settings = get_security_settings()
        assert bootstrap.multi_tenant_enabled is True
        assert bootstrap.default_cell_tier == "dedicated"
        assert security_settings.POLISYOS_MULTI_TENANT_ENABLED is True
        assert security_settings.POLISYOS_DEFAULT_CELL_TIER == "dedicated"
        assert security_settings.authz_shadow is True

        app = env["app"]
        container = app.state.runtime_container
        assert app.state.allow_fixture_identity is True
        assert container.runtime_security.allow_fixture_identity is True
        assert container.deployment_policy.effective_profile == "dev"

        capabilities = env["client"].get("/api/v1/control/capabilities")
        assert capabilities.status_code == 200
        feature_keys = {item["key"] for item in capabilities.json()["features"]}
        assert "security_admin_layer" in feature_keys

        auth_me = env["client"].get("/api/v1/auth/me")
        assert auth_me.status_code == 200
        assert auth_me.json()["tenant_id"] == env["tenant_a"]

        scope = AccessScope.for_service(
            tenant_id=env["tenant_a"],
            cell_id=env["cell_a"],
            spiffe_id=f"spiffe://polisyos.local/cell/{env['cell_a']}/svc/runtime",
        )
        with tenant_scope(None, tenant_id=env["tenant_a"], cell_id=env["cell_a"]):
            token = set_current_access_scope(scope)
            try:
                fabric_context = get_fabric_security_adapter().current_context()
            finally:
                reset_current_access_scope(token)

        assert fabric_context.is_tenant_scoped is True
        assert fabric_context.tenant_id == env["tenant_a"]
        assert fabric_context.cell_id == env["cell_a"]
        assert fabric_context.access_scope is scope
    finally:
        get_security_settings.cache_clear()
        client_close = getattr(env.get("client"), "close", None)
        if callable(client_close):
            client_close()
        service_close = getattr(getattr(app.state, "_control_service", None), "close", None)
        if callable(service_close):
            service_close()
