# ops — Platform Operations for PolicyOS

`ops/` хранит operational-артефакты (инфраструктура, security policy, мониторинг, миграции), которые применяются рядом с runtime, но не входят в Python-код приложения.

## Роль в системе

- задает baseline для Zero Trust и multi-tenant изоляции (Kubernetes + OPA + RLS);
- задает правила наблюдаемости (Prometheus rules + Grafana dashboards);
- хранит инфраструктурные шаги для rollout (Helm/Terraform/SQL migrations/scripts).

## Состав директории

| Модуль | Назначение | Ключевые артефакты |
|---|---|---|
| `helm/` | Kubernetes baseline-чарты | `polisyos-cell/`, `spire/`, `keycloak/` |
| `opa/` | Rego-политики авторизации и deploy-gate | `opa/policies/*.rego`, `opa/policies/*_test.rego` |
| `prometheus/` | Scrape, alerting, recording rules, SLO | `prometheus.yml`, `alerts.yml`, `slo_*.yml`, `rules/*.yml` |
| `grafana/` | Визуализация метрик | `dashboards/*.json`, `provisioning/dashboards.yml` |
| `migrations/` | SQL-миграции tenant isolation / RLS / grants | `001..004_*.sql` |
| `terraform/` | IaC для confidential node pool | `modules/confidential_nodepool/main.tf` |
| `scripts/` | Операционные скрипты кластера | `scripts/install-linkerd.sh` |
| `docker-compose.observability.yml` | Локальный стек observability | Prometheus + Grafana |

## Архитектура (упрощенно)

```text
src/polisyos/core/observability/*  ->  /metrics (9464)
                                     |
                                     v
                           ops/prometheus/*  ->  ops/grafana/*

src/polisyos/runtime/http/authz_middleware.py
  + src/polisyos/core/security/authz.py     ->  OPA /v1/data/polisyos/authz/decision
                                                  ^
                                                  |
                                            ops/opa/policies/*.rego

src/polisyos/core/security/db_backend.py     ->  SET LOCAL app.current_tenant
                                                  + PostgreSQL RLS policies
                                                  ^
                                                  |
                                            ops/migrations/*.sql

Kubernetes deployment baseline:
ops/helm/spire + ops/helm/keycloak + ops/helm/polisyos-cell
```

## Модули и особенности

### Helm (`helm/`)

- `polisyos-cell`: namespace isolation, deny-by-default NetworkPolicy, ResourceQuota, RBAC, optional RuntimeClass (`kata-cc`), Linkerd Server/AuthorizationPolicy, OPA policy ConfigMap.
- `spire`: SPIRE server + agent (PSAT attestation baseline).
- `keycloak`: минимальный baseline chart для OIDC/FIDO2-capable identity.

### OPA (`opa/`)

- 7 policy-модулей: tenant boundary, RBAC, data classification, delegation guard, composite decision, vulnerability gate, deploy decision.
- 7 unit-тестов (`opa test ...`).
- policy path для runtime по умолчанию: `polisyos/authz/decision`.

### Prometheus + Grafana (`prometheus/`, `grafana/`)

- Prometheus: 2 scrape job (`prometheus`, `polisyos`), 18 operational alerts, 5 SLO alerts, 4 audit-chain alerts, 15 recording rules.
- Grafana: 6 дашбордов (`executive`, `scientist`, `foundry`, `slo`, `security-phase4`, `knowledge-freshness`).

### Migrations (`migrations/`)

- `001` добавляет `tenant_id` как nullable.
- `002` описывает backfill-подход.
- `003_rls_enable` включает NOT NULL + индексы + RLS policies.
- `003_rls_disable_rollback` — emergency rollback.
- `004_roles_grants` — least-privilege role `polisyos_app`.

### Terraform (`terraform/`)

- модуль AKS node pool для confidential compute (`KataCcIsolation`, `sev-snp` labels/taints).

## Связь с другими директориями

- `src/polisyos/core/observability/` — источник метрик для Prometheus/Grafana.
- `src/polisyos/core/security/authz.py` и `src/polisyos/runtime/http/authz_middleware.py` — потребляют OPA policy decision.
- `src/polisyos/core/security/identity.py` — интеграция с Keycloak и SPIFFE/SPIRE.
- `src/polisyos/core/security/db_backend.py` — runtime RLS-контекст (`app.current_tenant`) для миграций из `ops/migrations`.
- `tests/core/security/*`, `tests/runtime/http/*` — проверка authz/RLS/tenant isolation контрактов.

## Локальный запуск observability

```bash
cd policy-engine/ops
docker compose -f docker-compose.observability.yml up -d

# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3000 (admin/admin)
```

Текущая конфигурация Grafana в репозитории провиженит только дашборды. Data source Prometheus нужно создать в UI (обычно `http://prometheus:9090`, как default).

## Важно про rule-файлы Prometheus

`prometheus/prometheus.yml` ссылается на `/etc/prometheus/rules/audit_chain_alerts.yml`, но `docker-compose.observability.yml` сейчас монтирует только файлы из корня `prometheus/`.

Для локального запуска audit-chain правил добавьте volume-mount для `./prometheus/rules`.

## Детализация

- OPA: [opa/README.md](opa/README.md)
- Prometheus: [prometheus/README.md](prometheus/README.md)
- Grafana: [grafana/README.md](grafana/README.md)
