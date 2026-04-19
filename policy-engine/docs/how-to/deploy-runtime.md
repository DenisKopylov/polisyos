# Развёртывание Runtime

> Разберитесь в текущем Runtime HTTP app factory, поверхности конфигурации, dashboard и production-аспектах.

!!! info "Bootstrap проверен"
    На 2026-04-17 на текущем дереве реально проверены импорт
    `from polisyos.runtime.http.app import create_runtime_api_app`,
    вызов `create_runtime_api_app()`,
    а также наличие runtime paths
    `/api/v1/control/jobs/{job_id}`
    и `/api/v1/runs/{run_id}/live`.

## Вход

- Python-окружение с runtime extras
- выбранный execution profile и control-plane state store
- решение по auth/authz, OPA и observability path

## Выход

- локально стартующий Runtime API на `:8000`
- список ключевых env vars для execution, security и telemetry
- понятный путь к dashboard, control-plane и runtime runs surface

## Команды

```bash
pip install -e ".[runtime]"
uvicorn 'polisyos.runtime.http.app:create_runtime_api_app' --factory --reload
uv run polisyos-tools runtime check-runtime-api-contract
```

## 1. Локальная разработка

Установите runtime-зависимости из исходников:

```bash
pip install -e ".[runtime]"
```

Если вам нужен минимальный HTTP-only path без observability umbrella:

```bash
pip install -e ".[runtime-http]"
```

Если в том же окружении нужны и tutorial/causal страницы:

```bash
pip install -e ".[all]"
```

Текущий app factory:

```text
polisyos.runtime.http.app:create_runtime_api_app
```

Проверенный локальный bootstrap:

```bash
uvicorn 'polisyos.runtime.http.app:create_runtime_api_app' --factory --reload
```

Локальные URL по умолчанию:

- `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## 2. Конфигурация

### Переменные окружения для execution и control plane

| Variable | Назначение |
|----------|------------|
| `POLISYOS_EXECUTION_PROFILE` | Выбор runtime deployment profile (`dev`, `research`, `governed`, `production`) |
| `POLISYOS_CONTROL_WORKER_BACKEND` | Backend для control-plane worker |
| `POLISYOS_CONTROL_STATE_STORE_BACKEND` | Backend для control-plane state store |
| `POLISYOS_CONTROL_SQLITE_PATH` | Путь к SQLite для control-plane state |
| `POLISYOS_CONTROL_POSTGRES_DSN` | Postgres DSN для control-plane state |
| `POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE` | Разрешить локальный control plane в research mode |
| `POLISYOS_LLM_GATEWAY_BASE_URL` | Base URL внешнего LLM gateway |
| `POLISYOS_LLM_GATEWAY_PROVIDER` | Идентификатор провайдера LLM gateway |
| `POLISYOS_CONTROL_MAX_WORKERS` | Размер пула воркеров `TaskRunner` |

### Переменные окружения для security, auth, tenancy, OPA и attestation

| Variable | Назначение |
|----------|------------|
| `POLISYOS_ENV` | Глобальное имя runtime environment |
| `POLISYOS_DB_BACKEND` | Выбор database backend |
| `POLISYOS_MULTI_TENANT_ENABLED` | Включить cell/tenant routing |
| `POLISYOS_CELL_REGISTRY_PATH` | Путь к cell registry |
| `POLISYOS_DEFAULT_CELL_TIER` | Cell tier по умолчанию |
| `POLISYOS_ALLOWED_REGIONS` | Allowlist регионов |
| `POLISYOS_MULTI_TENANT_FAIL_CLOSED` | Падать fail-closed при tenancy errors |
| `POLISYOS_AUTHN_ENABLED` | Включить authentication |
| `POLISYOS_AUTHZ_MODE` | Режим authorization |
| `POLISYOS_EXTERNAL_TENANT_HEADER_FALLBACK` | Fallback на внешний tenant header |
| `POLISYOS_KEYCLOAK_ISSUER_URL` | Keycloak issuer |
| `POLISYOS_KEYCLOAK_JWKS_URI` | Keycloak JWKS URI |
| `POLISYOS_KEYCLOAK_CLIENT_ID` | Keycloak client id |
| `POLISYOS_KEYCLOAK_AUDIENCE` | JWT audience |
| `POLISYOS_JWT_REQUIRED_MFA_ROLES` | Роли, требующие MFA |
| `POLISYOS_OPA_URL` | Base URL для OPA |
| `POLISYOS_OPA_POLICY_PATH` | Путь к OPA policy |
| `POLISYOS_OPA_TIMEOUT` | Таймаут OPA |
| `POLISYOS_OPA_CACHE_TTL` | TTL кэша OPA |
| `POLISYOS_OPA_CACHE_SIZE` | Размер кэша OPA |
| `POLISYOS_MTLS_SPIFFE_HEADER` | Заголовок SPIFFE identity |
| `POLISYOS_DELEGATION_REQUIRED` | Требовать delegated requests |
| `POLISYOS_DELEGATION_HEADER` | Имя delegation header |
| `POLISYOS_DELEGATION_SECRET` | Секрет для подписи delegation |
| `POLISYOS_DELEGATION_ALGORITHM` | Алгоритм подписи delegation |
| `POLISYOS_DELEGATION_TTL_SECONDS` | TTL delegation |
| `POLISYOS_TRUSTED_DELEGATORS` | Список trusted delegators |
| `POLISYOS_PII_ENABLED` | Включить PII controls |
| `POLISYOS_TEE_ENABLED` | Включить TEE checks |
| `POLISYOS_TEE_REQUIRED` | Требовать TEE attestation |
| `POLISYOS_TEE_PLATFORM` | Имя TEE platform |
| `POLISYOS_TEE_REPORT_PATH` | Путь к attestation report |
| `POLISYOS_TEE_MAX_REPORT_AGE_SECONDS` | Максимальный возраст отчёта |
| `POLISYOS_TEE_MIN_TCB_VERSION` | Минимальный TCB |
| `POLISYOS_TEE_MIN_GUEST_SVN` | Минимальный guest SVN |
| `POLISYOS_TEE_EXPECTED_MEASUREMENTS` | Ожидаемые measurements |
| `POLISYOS_TEE_EXPECTED_HOST_DATA` | Ожидаемые host data |
| `POLISYOS_TEE_REQUIRE_SIGNATURE_VALIDATION` | Обязательная проверка подписи отчёта |
| `POLISYOS_TEE_CACHE_TTL_SECONDS` | TTL кэша TEE |
| `POLISYOS_TEE_ENFORCE_TIERS` | Включить tiered TEE policy |
| `POLISYOS_SBOM_ENABLED` | Включить SBOM checks |
| `POLISYOS_SBOM_PATH` | Путь к SBOM |
| `POLISYOS_SBOM_CVSS_THRESHOLD` | Порог CVSS для SBOM |
| `POLISYOS_SBOM_GRYPE_DB_PATH` | Путь к Grype DB |
| `POLISYOS_SBOM_ALLOWED_CVES` | Allowlist CVE |

### Переменные окружения для observability

| Variable | Назначение |
|----------|------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Endpoint для OTLP collector |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Транспортный протокол OTLP |
| `OTEL_SERVICE_NAME` | Имя сервиса |
| `POLISYOS_OTEL_ENABLED` | Включить OpenTelemetry |
| `POLISYOS_HPC_OBSERVABILITY_ENABLED` | Включить HPC-specific observability hooks |
| `POLISYOS_OTEL_CONSOLE_EXPORT` | Включить console exporter |
| `POLISYOS_METRICS_PORT` | Порт Prometheus metrics |
| `POLISYOS_TRACE_SAMPLING_RATIO` | Коэффициент trace sampling |
| `POLISYOS_ALWAYS_SAMPLE_ERRORS` | Всегда сэмплировать error paths |

## 3. Обзор endpoints

Проверенное приложение сейчас поднимает 57 routes из:

- `routes/health.py`
- `routes/auth.py`
- `routes/runs.py`
- `routes/debug.py`
- `routes/artifacts.py`
- `routes/control.py`
- `routes/review.py`

Репрезентативные группы endpoints:

- health:
  - `/health`
  - `/ready`
- runs:
  - `GET /api/v1/runs`
  - `GET /api/v1/runs/{run_id}`
  - `GET /api/v1/runs/{run_id}/timeline`
  - `GET /api/v1/runs/{run_id}/nodes`
  - `GET /api/v1/runs/{run_id}/lineage`
  - `GET /api/v1/runs/{run_id}/workflow`
- control plane:
  - `POST /api/v1/control/runs`
  - `POST /api/v1/control/runs/nl`
  - `POST /api/v1/control/runs/{run_id}/feedback/evaluate`
  - `POST /api/v1/control/runs/{run_id}/reissue`
  - `GET /api/v1/control/jobs/{job_id}`
  - `GET /api/v1/control/workers`
  - `GET /api/v1/control/outbox`
  - несколько `/api/v1/control/data/...` endpoints

Полезные implementation notes:

- app factory — это `create_runtime_api_app(...)`
- тяжёлые модули импортируются достаточно лениво для быстрого bootstrap
- runtime security middleware включается только если этого требует deployment profile
- `ControlPlaneService` использует `TaskRunner`, а `TaskRunner` использует `ThreadPoolExecutor`
- NL endpoint control plane переключается на mock agents, когда `llm_model=None`

## 4. Frontend dashboard

Пакет dashboard:

```text
frontend/runtime-dashboard
```

Локальный запуск:

```bash
cd frontend/runtime-dashboard
npm install
npm run dev
```

Локальный frontend URL по умолчанию:

```text
http://localhost:5173
```

Текущие маршруты workspace:

- `/` -> command center
- `/compose` с alias `/launch` -> scenario composer
- `/runs` -> workspace для запусков и решений
- `/evidence` с alias `/sources` и `/data` -> evidence fabric
- `/knowledge` с alias `/lex` -> lex knowledge
- `/platform` с alias `/health` -> platform health

## 5. Production considerations

- Используйте нормальную ASGI-схему, например `gunicorn` плюс `uvicorn` workers.
- Если включаете policy-based authorization, держите OPA рядом с runtime как sidecar или соседний сервис.
- Если включаете service identity path, используйте SPIFFE или эквивалентный mTLS identity layer.
- Завершайте TLS на ingress или upstream proxy.
- Для серьёзной production-нагрузки замените локальный `TaskRunner` на queue-backed execution backend.

## 6. Мониторинг и телеметрия

Runtime уже импортирует observability helpers:

- `get_tracer()`
- `get_metrics()`

Что приложение делает сейчас:

- telemetry middleware пишет route, method, status и duration
- routers для health и readiness уже подключены
- OpenAPI enrichment устанавливается через `openapi_contract.py`

Операционные рекомендации:

- подключите OTLP к collector
- собирайте Prometheus metrics, если включён exporter
- коррелируйте structured logs через `X-Request-ID`

## Откат

Для локального rollback достаточно:

1. остановить `uvicorn`;
2. удалить scratch state store, если вы использовали локальный SQLite path, например `POLISYOS_CONTROL_SQLITE_PATH`;
3. очистить временные CAS/runtime outputs, если экспериментировали в локальном каталоге и не хотите сохранять их как baseline.

Если правка затрагивала runtime contract surface, откатите ещё и OpenAPI/client
артефакты до committed версии.

## Troubleshooting

- Если `create_runtime_api_app()` не импортируется, проверьте, что установлены `.[runtime]` или минимум `.[runtime-http]`.
- Если control-plane job остаётся `pending`, проверьте state store backend, `POLISYOS_CONTROL_MAX_WORKERS` и worker/outbox endpoints из [Use Control Plane](use-control-plane.md).
- Если auth включён и `curl` получает `401/403`, перепроверьте OIDC/JWT/OPA env vars до отладки бизнес-логики.

## 7. Связанные файлы

- `src/polisyos/runtime/http/app.py`
- `src/polisyos/runtime/http/execution_policy.py`
- `src/polisyos/runtime/http/routes/runs.py`
- `src/polisyos/runtime/http/routes/control.py`
- `src/polisyos/runtime/http/services/control.py`
- `src/polisyos/runtime/http/services/task_runner.py`
- `frontend/runtime-dashboard/src/app/workspaces.ts`
