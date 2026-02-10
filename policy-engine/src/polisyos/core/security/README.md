# core.security — Zero Trust и tenant isolation primitives

`core.security` — общий security/runtime слой для multi-tenant deployments.
Модуль покрывает маршрутизацию tenant→cell, authn/authz, делегацию контекста, audit chain, TEE attestation, SBOM и SLSA-вспомогательные компоненты.

## Архитектура

```text
security/
├── cell.py, registry.py, router.py, tenant_context.py, db_backend.py
├── identity.py, access_scope.py, delegation.py, authz.py
├── audit_models.py, audit_sink.py, audit_verifier.py
├── tee.py, tee_middleware.py
├── sbom.py
├── slsa/
├── settings.py, exceptions.py
└── __init__.py  # lazy facade exports
```

## Подсистемы

| Подсистема | Что делает |
|---|---|
| Tenant routing | `CellRegistry`, `resolve_routing`, `tenant_scope` для tenant-aware execution |
| DB isolation | `DatabaseBackend` protocol + `PostgresBackend` (RLS) + `DuckDBLegacyBackend` |
| Identity | SPIFFE service identity + OIDC/JWT user claims normalization |
| Access scope | `AccessScope` как неизменяемый per-request security контекст |
| Delegation | Подписанные hop-to-hop delegation tokens (`DelegationTokenManager`) |
| Authorization | Async OPA client с TTL cache и fail-closed семантикой |
| Audit chain | append-only chained audit log + hot/cold реплика + tamper verification |
| TEE | attestation policy/verifier + gatekeeper middleware |
| SBOM | генерация/слияние/проверка CycloneDX + vulnerability gate |
| SLSA | модели, attestation builder, Fulcio/Rekor клиенты |

## Поведение по умолчанию

- Fail-closed для критичных multi-tenant путей (`authz`, tenant routing, RLS scope).
- Безопасная деградация на dev-сценариях через `SecuritySettings`.
- Все runtime-переключатели централизованы в `settings.py` и читаются через `get_security_settings()`.

## Ключевые интеграции

- `runtime/http/*` использует `registry`, `router`, `tenant_context`, `authz`, `delegation`.
- `core.run.RunContext` может писать trace события и в chained audit sink (`audit_sink`).
- `core.audit` может подтягивать SLSA-материалы из `core.security.slsa` при сборке audit package.
- `core.observability` получает security-метрики (authz, cell-router, audit, tee, sbom).

## Важные env-переключатели

| Переменная | Назначение |
|---|---|
| `POLISYOS_MULTI_TENANT_ENABLED` | включает multi-tenant режим |
| `POLISYOS_AUTHN_ENABLED` | включает user/service authentication |
| `POLISYOS_AUTHZ_MODE` | `off` / `shadow` / `enforce` |
| `POLISYOS_OPA_URL` | адрес OPA sidecar |
| `POLISYOS_DELEGATION_REQUIRED` | требовать delegation token на межсервисных вызовах |
| `POLISYOS_TEE_ENABLED` | включить TEE checks |
| `POLISYOS_TEE_REQUIRED` | fail-closed при отсутствии валидной attestation |
| `POLISYOS_SBOM_ENABLED` | включить SBOM gate |
| `POLISYOS_CELL_REGISTRY_PATH` | путь к snapshot tenant/cell registry |
| `POLISYOS_DB_BACKEND` | `postgres`/`duckdb` override |

## Публичный API

`core.security.__init__` экспортирует lazy facade для основных моделей, исключений и сервисов.
Для low-level интеграций можно импортировать напрямую из конкретных модулей (`authz.py`, `tee.py`, `sbom.py`, `audit_sink.py`).
