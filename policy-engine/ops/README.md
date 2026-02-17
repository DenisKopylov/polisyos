# ops — эксплуатационный слой PolicyOS

`ops/` хранит инфраструктурные и security-артефакты, которые описывают окружение вокруг приложения: Kubernetes baseline, policy-as-code (OPA), наблюдаемость, SQL-миграции и IaC.

## Роль в системе

- фиксирует baseline Zero Trust и tenant isolation;
- задает observability-контур (Prometheus alerting/SLO + Grafana dashboards);
- хранит шаги rollout/rollback для инфраструктуры и БД.

## Состав директории

| Путь | Роль | Примечание |
|---|---|---|
| `helm/` | baseline Helm-чарты | cell isolation, SPIRE, Keycloak |
| `opa/` | runtime/deploy Rego-политики | 7 policy-модулей + 7 тестов |
| `prometheus/` | scrape/rules/alerts/SLO | 2 scrape jobs, 27 alerts, 15 recording rules |
| `grafana/` | prebuilt dashboards | 6 дашбордов, file provisioning |
| `migrations/` | tenant + RLS SQL миграции | forward-цепочка + rollback |
| `terraform/` | IaC-модуль confidential node pool | AKS + KataCcIsolation + SEV-SNP |
| `scripts/` | вспомогательные ops-скрипты | `install-linkerd.sh` |
| `docker-compose.observability.yml` | локальный стек метрик | Prometheus + Grafana |

## Архитектурные связи

```text
src/polisyos/core/observability/* -> /metrics -> ops/prometheus -> ops/grafana

src/polisyos/runtime/http/authz_middleware.py
  + src/polisyos/core/security/authz.py
  -> OPA /v1/data/polisyos/authz/decision
  <- ops/opa/policies/*.rego

src/polisyos/core/security/db_backend.py
  -> SET LOCAL app.current_tenant
  -> PostgreSQL RLS enforcement
  <- ops/migrations/*.sql

Cluster baseline:
ops/helm/spire + ops/helm/keycloak + ops/helm/polisyos-cell
```

## Важные особенности

- `ops/helm/polisyos-cell` ожидает обязательный `cell.id`; имя namespace/chart ресурсов строится из первых 8 символов `cell.id`.
- `ops/helm/polisyos-cell/templates/runtimeclass-confidential.yaml` рендерится только при `confidentialCompute.enabled=true` и `cell.tier=dedicated`.
- `ops/prometheus/prometheus.yml` подключает `/etc/prometheus/rules/audit_chain_alerts.yml`, но в `docker-compose.observability.yml` не смонтирована директория `./prometheus/rules` (для локального запуска нужен дополнительный mount).
- `ops/grafana/provisioning/dashboards.yml` провиженит только dashboards; datasource Prometheus нужно настроить отдельно.

## Локальный запуск observability

```bash
cd policy-engine/ops
docker compose -f docker-compose.observability.yml up -d
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
```

## Быстрые проверки

```bash
# OPA unit tests
opa test policy-engine/ops/opa/policies -v

# Проверка правил Prometheus (если установлен promtool)
promtool check rules policy-engine/ops/prometheus/alerts.yml
promtool check rules policy-engine/ops/prometheus/slo_alerts.yml
promtool check rules policy-engine/ops/prometheus/rules/audit_chain_alerts.yml

# Рендер Helm chart'а cell
helm template demo policy-engine/ops/helm/polisyos-cell --set cell.id=cell-00112233
```

## Подробная документация

- Helm: [helm/README.md](helm/README.md)
- OPA: [opa/README.md](opa/README.md)
- Prometheus: [prometheus/README.md](prometheus/README.md)
- Grafana: [grafana/README.md](grafana/README.md)
- Migrations: [migrations/README.md](migrations/README.md)
- Terraform: [terraform/README.md](terraform/README.md)
