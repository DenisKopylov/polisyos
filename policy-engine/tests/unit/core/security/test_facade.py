from __future__ import annotations

from importlib import import_module
from types import MappingProxyType

import pytest

EXPECTED_EXPORTS = {
    "AuditLog": "polisyos.core.security.audit_protocol",
    "InTotoStatement": "polisyos.core.security.slsa.models",
    "NamespacedArtifactStore": "polisyos.core.security.namespace",
    "SECURITY_ASSURANCE_REPORT_REF_KEY": "polisyos.core.security.quality_gates",
    "SECURITY_ASSURANCE_ARTIFACT_KIND": "polisyos.core.security.quality_gates",
    "SECURITY_ASSURANCE_ARTIFACT_MEDIA_TYPE": "polisyos.core.security.quality_gates",
    "SECURITY_ASSURANCE_ARTIFACT_SCHEMA_NAME": "polisyos.core.security.quality_gates",
    "SECURITY_ASSURANCE_ARTIFACT_SCHEMA_VERSION": "polisyos.core.security.quality_gates",
    "SECURITY_REPORT_FILE": "polisyos.core.security.quality_gates",
    "QuotaAccountingError": "polisyos.core.security.quota_enforcer",
    "QuotaEnforcer": "polisyos.core.security.quota_enforcer",
    "QuotaExceededError": "polisyos.core.security.quota_enforcer",
    "TenantQuotaLimits": "polisyos.core.security.tenant_quota",
    "TenantQuotaRegistry": "polisyos.core.security.quota_registry",
    "build_security_assurance_report": "polisyos.core.security.quality_gates",
    "security_gates_from_report": "polisyos.core.security.quality_gates",
    "tenant_scope": "polisyos.core.security.tenant_context",
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


def test_security_facade_export_map_is_immutable_and_covers_public_exports() -> None:
    facade = import_module("polisyos.core.security")

    assert isinstance(facade._EXPORTS, MappingProxyType)
    assert set(facade._EXPORTS) == set(facade.__all__)
    with pytest.raises(TypeError):
        facade._EXPORTS["tenant_scope"] = (
            "importlib",
            "import_module",
        )
