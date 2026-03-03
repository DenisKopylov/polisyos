# Security — zero-trust и multi-tenant primitives

`core.security` — общий security/runtime слой для multi-tenant исполнения: tenant routing, identity/authz, delegation, chained audit, TEE, SBOM и SLSA.

## Архитектура

```text
security/
├── cell.py, registry.py, router.py, tenant_context.py
├── identity.py, access_scope.py, delegation.py, authz.py
├── db_backend.py
├── audit_models.py, audit_sink.py, audit_verifier.py
├── tee.py, tee_middleware.py
├── sbom.py
├── slsa/
├── settings.py, exceptions.py
└── __init__.py  # lazy exports
```

## Подсистемы

| Подсистема | Что делает |
|---|---|
| Tenant/cell routing | `CellRegistry`, `resolve_routing`, `tenant_scope` |
| Identity | JWT/OIDC claims normalization + SPIFFE service identity |
| AccessScope | неизменяемый security-контекст запроса |
| Authorization | async OPA client (`OPAClient`) с TTL-cache и deny-by-default |
| Delegation | подписанные hop-to-hop delegation tokens |
| DB isolation | `PostgresBackend` (RLS) + `DuckDBLegacyBackend` |
| Audit chain | append-only chained log + hot/cold backends + tamper verify |
| TEE | attestation verification + gatekeeper middleware |
| SBOM gate | CycloneDX генерация/проверка + vulnerability threshold |
| SLSA | attestation/signing/transparency clients и config |

## Поведение по умолчанию

- fail-closed для критичных путей (routing/authz/attestation).
- часть переключателей автоматически ужесточается в `POLISYOS_ENV=prod`.
- все runtime-переключатели централизованы в `settings.py` (`get_security_settings()`).

## Ключевые env-группы

Tenant/AuthN/AuthZ:
- `POLISYOS_MULTI_TENANT_ENABLED`, `POLISYOS_CELL_REGISTRY_PATH`, `POLISYOS_MULTI_TENANT_FAIL_CLOSED`
- `POLISYOS_AUTHN_ENABLED`, `POLISYOS_AUTHZ_MODE`, `POLISYOS_OPA_URL`, `POLISYOS_OPA_POLICY_PATH`

Delegation/identity:
- `POLISYOS_DELEGATION_REQUIRED`, `POLISYOS_DELEGATION_HEADER`, `POLISYOS_DELEGATION_SECRET`
- `POLISYOS_MTLS_SPIFFE_HEADER`, `POLISYOS_SERVICE_SPIFFE_ID`

TEE/SBOM:
- `POLISYOS_TEE_ENABLED`, `POLISYOS_TEE_REQUIRED`, `POLISYOS_TEE_REPORT_PATH`, `POLISYOS_TEE_EXPECTED_MEASUREMENTS`
- `POLISYOS_SBOM_ENABLED`, `POLISYOS_SBOM_PATH`, `POLISYOS_SBOM_CVSS_THRESHOLD`, `POLISYOS_SBOM_ALLOWED_CVES`

SLSA:
- `POLISYOS_SLSA_MODE`, `POLISYOS_SLSA_POLICY`
- `POLISYOS_SLSA_FULCIO_URL`, `POLISYOS_SLSA_REKOR_URL`, `POLISYOS_SLSA_OIDC_*`

Audit backends:
- `POLISYOS_AUDIT_HOT_TIER_URL`
- `POLISYOS_AUDIT_COLD_TIER_BUCKET`, `POLISYOS_AUDIT_COLD_TIER_PREFIX`, `POLISYOS_AUDIT_COLD_TIER_REGION`

## Связи

- `runtime/http`: routing, tenant context, authz, delegation, tee middleware
- `core.run`: опционально fan-out trace в chained audit sink
- `core.audit`: может включать SLSA/SBOM материалы при экспорте
- `core.observability`: security telemetry (authz/audit/tee/sbom)
