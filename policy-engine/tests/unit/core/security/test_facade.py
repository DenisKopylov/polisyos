from __future__ import annotations

from importlib import import_module

import pytest

EXPECTED_EXPORTS = {
    "AuditLog": "polisyos.core.security.audit_protocol",
    "InTotoStatement": "polisyos.core.security.slsa.models",
    "NamespacedArtifactStore": "polisyos.core.security.namespace",
    "SECURITY_ASSURANCE_REPORT_REF_KEY": "polisyos.core.security.quality_gates",
    "SECURITY_REPORT_FILE": "polisyos.core.security.quality_gates",
    "TenantQuotaLimits": "polisyos.core.security.tenant_quota",
    "TenantQuotaRegistry": "polisyos.core.security.quota_registry",
    "build_security_assurance_report": "polisyos.core.security.quality_gates",
    "security_gates_from_report": "polisyos.core.security.quality_gates",
    "validate_tenant_id": "polisyos.core.security.db_backend",
}


@pytest.mark.parametrize(("name", "module_name"), EXPECTED_EXPORTS.items())
def test_security_facade_resolves_canonical_export(name: str, module_name: str) -> None:
    facade = import_module("polisyos.core.security")
    defining_module = import_module(module_name)

    assert name in facade.__all__
    assert getattr(facade, name) is getattr(defining_module, name)


def test_security_facade_does_not_export_private_tenant_validator() -> None:
    facade = import_module("polisyos.core.security")

    assert "_validate_tenant_id" not in facade.__all__
    assert not hasattr(facade, "_validate_tenant_id")
