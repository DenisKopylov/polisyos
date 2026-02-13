# Core — инфраструктурный слой PolisyOS

`polisyos.core` — это общий инфраструктурный слой для `fabric`, `foundry`, `scientist`, `lex`, `runtime`, `scholar` и `packs`.
Здесь находится стабильный ABI (контракты), CAS-хранилище артефактов, provenance/audit, компонентная модель, безопасность и наблюдаемость.

`ir` остается независимым: он может использоваться без `core` как самостоятельный слой схем/реестров.

## Архитектура директории

```text
core/
├── artifacts/      # CAS + манифесты + подписи + environment fingerprinting + dependency graph
├── audit/          # Экспорт и офлайн-верификация аудит-пакетов (PROV + checksums + SLSA)
├── backends/       # Унифицированный dispatcher backend-реализаций
├── cache/          # Потокобезопасные LRU/TTL кэши
├── canon/          # Канонический JSON + хеширование
├── compiler/       # Отчеты компиляции/линковки в CAS
├── components/     # Component Model v1 (metadata/discovery/registry/bootstrap)
├── contracts/      # Typed ABI между модулями
├── discovery/      # Базовые примитивы discovery (entry points + file modules)
├── errors/         # Унифицированная ошибка PolicyOSError + категории
├── evaluation/     # Взвешенный scoring + threshold mapping
├── governance/     # Validation profiles + legal/safety passes
├── llm/            # Трассируемый LLM client + provider/model-variant telemetry + cost/latency + retry facade
├── observability/  # Tracing, metrics, context propagation, structured logs
├── pipeline/       # Линейные и DAG pipeline-примитивы
├── registry/       # Сборка/загрузка registry bundles из IR и fragment-компонентов
├── resilience/     # Общая retry-политика с backoff/jitter
├── run/            # RunContext + RunManifest lifecycle
├── security/       # Tenant isolation, authn/authz, audit chain, TEE, SBOM, SLSA helpers
└── trace/          # TraceRecord и sink'и (JSONL/composite)
```

## Роль в системе

- Единый ABI: `core.contracts` задает типизированные ссылки и модели на межмодульных границах.
- Единый data/provenance plane: `artifacts`, `run`, `trace`, `audit` держат воспроизводимость и аудируемость.
- Единый plugin plane: `components` + `discovery` + `registry` связывают entry-points, packs и runtime-реестры.
- Единый runtime-quality plane: `security`, `observability`, `resilience`, `pipeline` дают общие нефункциональные гарантии.

## Публичные точки входа

`polisyos.core` (lazy facade) экспортирует:

- `artifacts`, `backends`, `cache`, `canon`, `components`, `contracts`, `discovery`
- `evaluation`, `errors`, `llm`, `observability`, `pipeline`, `resilience`, `registry`, `run`

Подсистемы, которые импортируются напрямую (не через facade `core.__all__`):

- `polisyos.core.audit`
- `polisyos.core.compiler`
- `polisyos.core.governance`
- `polisyos.core.security`
- `polisyos.core.trace`

## Связь с другими директориями

| Директория | Как использует `core` |
|---|---|
| `fabric/` | CAS (`artifacts`), canonical hashing (`canon`), evidence contracts (`contracts.fabric`), plugin discovery (`components`) |
| `foundry/` | compile/execute contracts (`contracts.foundry`), registry bundles (`registry`), determinism/metrics (`observability`) |
| `scientist/` | run lifecycle (`run`), governance passes/profiles (`governance`), LLM wrappers (`llm`), artifacts/contracts |
| `lex/` | legal contracts (`contracts.lex`), governance passes, artifact persistence, component providers |
| `runtime/` | runtime API contracts (`contracts.runtime`), artifact lineage/debug endpoints, security middleware |
| `scholar/` | scholar contracts, CAS, component-based extractors, freshness metrics |
| `packs/` | декларация компонентов (`components.ComponentMetadata/Capability/ComponentKind`) |
| `ir/` | source of registries/refs для `core.registry` и facade-контрактов; прямой зависимости `ir -> core` нет |

## Ключевые сценарии

- Компиляция/исполнение: `ir` + `core.registry` + `core.contracts.foundry`.
- Runtime replay/debug: `core.run` + `core.trace` + `core.contracts.runtime`.
- Проверяемая поставка: `core.audit` + `core.security.slsa` + `core.artifacts.signing`.
- Мультитенантность: `core.security` + `runtime/http/*` + `fabric` DB adapters.

## Документация подсистем

- [artifacts/README.md](artifacts/README.md)
- [audit/README.md](audit/README.md)
- [components/README.md](components/README.md)
- [contracts/README.md](contracts/README.md)
- [observability/README.md](observability/README.md)
- [security/README.md](security/README.md)
- [cache/README.md](cache/README.md)

## Границы ответственности

- В `core` добавляем только то, что переиспользуется минимум двумя подсистемами.
- Доменно-специфичную бизнес-логику оставляем в `fabric`/`foundry`/`scientist`/`lex`/`scholar`.
- Если новый API нужен между модулями, сначала фиксируется контракт в `core.contracts`, затем реализация в доменном модуле.
