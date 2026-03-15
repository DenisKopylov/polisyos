# Runtime HTTP API (`polisyos.runtime.http`)

`polisyos.runtime.http` — FastAPI слой runtime API v1: health/read/debug/artifact endpoints, decision feedback loop surfaces и control-plane операции.

Документ отражает текущее состояние кода на **2026-03-11**.

## Роль и границы

- Даёт HTTP-контур для introspection/debug над `core_run`, decision packets и CAS-артефактами.
- Проксирует control-plane операции: запуск workflow/NL runs, fabric retrieval/ingestion, Lex batch.
- Открывает operator surface для feedback loop v1: post-deployment monitoring, run-vs-run compare и human-gated reissue.
- Не хранит доменные данные: работает поверх `FileSystemCAS`, `core_runs_root` и сервисов `scientist/fabric/lex`.

## Архитектура директории

```text
http/
├── app.py                  # create_runtime_api_app + middleware wiring + OpenAPI install
├── dependencies.py         # RuntimeApiContext + meta/authz/tenant helpers
├── errors.py               # application/problem+json error model
├── openapi_contract.py     # OpenAPI enrichment (examples + problem responses)
├── jwt_auth_middleware.py  # JWT -> AccessScope projection
├── cell_router_middleware.py
├── authz_middleware.py
├── routes/                 # тонкий HTTP слой (см. routes/README.md)
└── services/               # прикладная логика (см. services/README.md)
```

## Request pipeline

```text
HTTP request
  -> app.py (FastAPI app + exception handlers)
  -> telemetry middleware (request_id + metrics/tracing)
  -> optional security chain (JWT -> CellRouter -> Authz)
  -> routes/*
  -> services/*
  -> FileSystemCAS + core_runs_root
```

Важно:

- Security middleware выключены по умолчанию и включаются только через `enable_security_middlewares=True`.
- В Starlette middleware исполняются в обратном порядке регистрации; в `app.py` это учтено, чтобы порядок проверок был `JWT -> CellRouter -> Authz`.

## Группы маршрутов

| Модуль | Prefix | Назначение |
|---|---|---|
| `routes/health.py` | `/`, `/api/v1/health` | liveness/readiness/runtime health |
| `routes/runs.py` | `/api/v1/runs` | список run, details, timeline, nodes, lineage, agents, workflow |
| `routes/debug.py` | `/api/v1/debug/runs` | node/governance/errors debug + decision feedback/compare |
| `routes/artifacts.py` | `/api/v1/artifacts` | artifact manifest/content/lineage/schema |
| `routes/control.py` | `/api/v1/control` | запуск run, feedback evaluate/reissue и data/lex control-plane API |

Полная карта endpoint'ов: [routes/README.md](routes/README.md).

## Security и tenant isolation

- `JWTAuthMiddleware` валидирует Bearer token, строит `AccessScope`, сверяет header tenant с token tenant.
- `CellRouterMiddleware` резолвит tenant -> cell routing, задаёт `request.state.tenant_id/cell_id` и блокирует cell/tenant mismatch.
- `AuthzMiddleware` собирает `AuthzInput` и проверяет OPA policy; поддерживает `enforce` и `shadow_mode`, а также delegation token flow.
- Routes выставляют ресурсный контекст через `set_authz_resource(...)`, чтобы authz policy видела тип ресурса и tenant/artifact id.
- Дополнительная проверка доступа к данным:
  - `enforce_run_tenant_access(...)`
  - `enforce_artifact_tenant_access(...)`

## Observability и error model

- Каждому запросу присваивается/прокидывается `X-Request-ID`.
- Telemetry middleware пишет tracing span `runtime.http.request` и latency/status метрики.
- Исключения нормализуются в `application/problem+json` (`RuntimeApiProblem`) через `errors.py`.
- `openapi_contract.py` добавляет единообразные problem responses и примеры payload.

## Diagnostic labels в debug/decision surfaces

| Label | Где появляется | Интерпретация |
|---|---|---|
| `transport:<status>` | `DecisionCard`, `DecisionPacket.diagnostics_summary` | Статус transportability из causal report; `not_run` означает отсутствие transport pass |
| `legal:checked` / `legal:not_run` | `DecisionCard`, governance debug | Была ли зафиксирована `lex.legal_report` в run artifacts |
| `replay:<level>` | `DecisionCard`, `DecisionPacket.replay`, agent debug reproducibility | Уровень replay completeness: `complete`, `partial`, `incomplete` |
| `human-review:required` | `DecisionCard`, gate context | Есть явный human gate / strict review / expert review signal |
| `uncertainty:available` / `uncertainty:not_available` | `DecisionCard`, `DecisionPacket.diagnostics_summary` | Есть ли uncertainty envelope или вычисленные bounds в packet |

## Feedback Loop Surface

- `GET /api/v1/debug/runs/{run_id}/feedback` возвращает `feedback_loop` из `DecisionPacket` вместе с `DecisionMonitoringContract`, последним `DecisionMonitoringReport`, `DecisionCompareReport`, `DecisionReissuePlan` и summary из `DecisionValidityService`.
- `GET /api/v1/debug/runs/{left_run_id}/compare/{right_run_id}` строит packet-level deltas по `law/data/evidence/model/governance/outcome`, а `root_cause` остаётся synthesized summary.
- `POST /api/v1/control/runs/{run_id}/feedback/evaluate` запускает ex-post evaluation без отдельного scheduler/queue и materialize-ит monitoring/compare/reissue artifacts при refutation.
- `POST /api/v1/control/runs/{run_id}/reissue` клонирует исходный `ExperimentState.inputs`, подставляет feedback artifacts и создаёт новый run, но publication остаётся human-gated.

## Ключевые настройки `create_runtime_api_app(...)`

- Хранилища и лимиты: `cas_root`, `core_runs_root`, `max_preview_bytes`, `lineage_max_depth`, `lineage_max_nodes`.
- Tenant-policy behavior: `allow_unscoped_artifacts`.
- Runtime behavior: `enable_response_compression`, `artifact_redaction_hooks`.
- Security wiring: `enable_security_middlewares`, `identity_provider`, `cell_registry`, `opa_client`, `authz_enforce`, `authz_shadow_mode`, `delegation_manager`, `trusted_delegators`, `service_spiffe_id`.

## Важные ENV-флаги

- `POLISYOS_CELL_ID` — expected cell binding для JWT-проверки.
- `POLISYOS_SERVICE_SPIFFE_ID` — audience binding для delegation tokens.
- `POLISYOS_LLM_MULTIMODEL_ENABLED`
- `POLISYOS_REQUIRED_PREFLIGHT_ENABLED`
- `POLISYOS_AUTO_MATERIALIZATION_ENABLED`
- `POLISYOS_UNIFIED_DAG_ENABLED`

## Связанные подсистемы

- `polisyos/core/contracts/runtime.py` и `polisyos/core/contracts/control.py` — request/response DTO.
- `polisyos/runtime/http/services/control.py` — bridge к `scientist`, `fabric`, `lex`.
- `polisyos/core/security/*` — identity/routing/authz primitives.

## Поддиректории с отдельной документацией

- [routes/README.md](routes/README.md)
- [services/README.md](services/README.md)
