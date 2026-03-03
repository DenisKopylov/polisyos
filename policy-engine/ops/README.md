# ops — эксплуатационный слой PolicyOS

`ops/` описывает инфраструктурный периметр PolicyOS: как обеспечиваются isolation/identity/policy enforcement, как собирается observability, и как накатываются инфраструктурные и SQL-изменения.

## Роль в системе

- задает Kubernetes baseline для cell isolation и Zero Trust;
- хранит policy-as-code (OPA) для runtime authz и deploy gate;
- определяет контур observability (Prometheus rules + Grafana dashboards);
- фиксирует SQL-цепочку tenant/RLS миграций и IaC-модуль confidential node pool.

## Карта директории

| Путь | Роль | Связь с кодом |
|---|---|---|
| `helm/` | инфраструктурные chart'ы (`polisyos-cell`, `spire`, `keycloak`) | `src/polisyos/core/security/identity.py`, `src/polisyos/runtime/http/authz_middleware.py` |
| `opa/` | Rego-политики + unit tests | `src/polisyos/core/security/authz.py` |
| `prometheus/` | scrape config, recording rules, alerts, SLO | `src/polisyos/core/observability/*`, `src/polisyos/core/security/*` |
| `grafana/` | prebuilt dashboards + provisioning | использует метрики из `ops/prometheus` |
| `migrations/` | tenant/RLS SQL-миграции | `src/polisyos/core/security/db_backend.py` |
| `terraform/` | AKS confidential node pool модуль | `ops/helm/polisyos-cell/templates/runtimeclass-confidential.yaml` |
| `scripts/` | вспомогательные ops-скрипты (Linkerd install) | используется с `helm/polisyos-cell` strict mTLS |
| `docker-compose.observability.yml` | локальный Prometheus + Grafana | для быстрой валидации rules/dashboards |

## Архитектурные связи

```text
runtime /metrics endpoint (port 9464)
  -> ops/prometheus/prometheus.yml (scrape + rule_files)
  -> ops/grafana/dashboards/*.json

runtime authz middleware
  -> OPA /v1/data/polisyos/authz/decision
  <- ops/opa/policies/*.rego

deploy SBOM gate
  -> OPA /v1/data/polisyos/deploy/decision
  <- ops/opa/policies/vulnerability.rego + deploy.rego

db tenant context (SET LOCAL app.current_tenant)
  -> PostgreSQL RLS
  <- ops/migrations/001..004

confidential workload scheduling
  <- ops/terraform/modules/confidential_nodepool
  <- ops/helm/polisyos-cell RuntimeClass (условный рендер)
```

## Важные операционные инварианты

- `helm/polisyos-cell` требует `cell.id`; namespace и имена ресурсов строятся из первых 8 символов.
- `prometheus/prometheus.yml` подключает `rules/audit_chain_alerts.yml`, но в `docker-compose.observability.yml` нет mount для `./prometheus/rules`.
- `migrations/003_rls_disable_rollback.sql` — emergency rollback только для шага `003_rls_enable.sql`, не часть forward-цепочки.
- `ops/opa/policies/*.rego` и `helm/polisyos-cell/policies/*.rego` должны оставаться синхронными (chart пакует копию политик).

## Базовый локальный smoke-check

```bash
cd policy-engine/ops

docker compose -f docker-compose.observability.yml up -d
opa test ./opa/policies -v
helm template cell-a ./helm/polisyos-cell --set cell.id=cell-00112233
```

## Документация по модулям

- [helm/README.md](helm/README.md)
- [opa/README.md](opa/README.md)
- [prometheus/README.md](prometheus/README.md)
- [grafana/README.md](grafana/README.md)
- [migrations/README.md](migrations/README.md)
- [terraform/README.md](terraform/README.md)
