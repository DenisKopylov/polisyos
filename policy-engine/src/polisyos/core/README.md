# Core — инфраструктурный слой PolisyOS

`polisyos.core` — общий слой инфраструктуры для `fabric`, `foundry`, `scientist`, `lex`,
`runtime`, `scholar` и `packs`: контракты, артефакты, run/trace lifecycle, безопасность,
наблюдаемость, governance и общие runtime-примитивы.

`ir` остается отдельным слоем схем/реестров: `core` использует `ir`, но `ir` не зависит от `core`.

## Архитектура директории

```text
core/
├── artifacts/      # CAS + манифесты + подписи + environment + dependency graph
├── audit/          # Экспорт/верификация офлайн аудит-пакетов (PROV/SLSA/checksums)
├── backends/       # Унифицированный dispatcher backend-реализаций
├── cache/          # Потокобезопасные LRU/TTL кэши
├── canon/          # Канонический JSON и хеширование
├── compiler/       # Compile/link reports в CAS
├── components/     # Component Model v1: metadata/discovery/registry/bootstrap
├── contracts/      # Typed ABI между модулями
├── discovery/      # Базовые discovery-примитивы
├── errors/         # Базовая унифицированная ошибка и категории
├── evaluation/     # Weighted scoring и threshold mapping
├── governance/     # Validation profiles + legal/safety passes
├── llm/            # Трассируемый LLM client + parsing/cost/retry facade
├── observability/  # Tracing, metrics, propagation, structured logs, pricing
├── pipeline/       # Линейные и DAG pipeline-примитивы
├── registry/       # Generic registries + registry bundle builder/loader
├── resilience/     # Общая retry-политика с backoff/jitter
├── run/            # RunContext + RunManifest lifecycle
├── security/       # Tenant isolation, authn/authz, audit chain, TEE, SBOM, SLSA
└── trace/          # TraceRecord и sink'и (JSONL/composite)
```

## Роль в системе

- ABI plane: `core.contracts` задает typed refs и DTO на межмодульных границах.
- Data/provenance plane: `artifacts`, `run`, `trace`, `audit` обеспечивают воспроизводимость.
- Plugin plane: `components`, `discovery`, `registry` связывают entry points с runtime.
- Runtime-quality plane: `security`, `observability`, `resilience`, `pipeline` дают единые NFR-гарантии.

## Публичные точки входа

`polisyos.core` (lazy facade) экспортирует:

- `artifacts`, `backends`, `cache`, `canon`, `components`, `contracts`, `discovery`
- `evaluation`, `errors`, `llm`, `observability`, `pipeline`, `resilience`, `registry`, `run`

Подсистемы, импортируемые напрямую:

- `polisyos.core.audit`
- `polisyos.core.compiler`
- `polisyos.core.governance`
- `polisyos.core.security`
- `polisyos.core.trace`

## Ключевые сценарии

1. Сборка реестров: `components` -> `registry.build_registry_bundle_from_components` -> CAS bundle.
2. Запуск пайплайнов: `run.RunContext` + `trace.TraceRecord` + `contracts.*`.
3. Governance-валидация: `governance.ValidationProfile` + `governance.passes`.
4. Проверяемая поставка: `audit` + `artifacts.signing` + `security.slsa`.

## Связь с другими директориями

| Директория | Как использует `core` |
|---|---|
| `fabric/` | CAS (`artifacts`), canonical hashing (`canon`), evidence contracts (`contracts.fabric`), component discovery |
| `foundry/` | compile/execute contracts (`contracts.foundry`), registry bundles (`registry`), tracing/metrics (`observability`) |
| `scientist/` | run lifecycle (`run`), governance passes/profiles (`governance`), LLM wrappers (`llm`), artifacts/contracts |
| `lex/` | legal contracts (`contracts.lex`), legal/safety validation passes, component providers |
| `runtime/` | runtime API contracts (`contracts.runtime`), lineage/debug, security middleware |
| `scholar/` | scholar contracts, CAS, component-based extractors, freshness metrics |
| `packs/` | декларация компонентов (`components.ComponentMetadata/Capability/ComponentKind`) |
| `ir/` | источник canonical refs/registry schemas для `contracts` и `registry` |

## Документация подсистем

- [artifacts/README.md](artifacts/README.md)
- [audit/README.md](audit/README.md)
- [cache/README.md](cache/README.md)
- [components/README.md](components/README.md)
- [contracts/README.md](contracts/README.md)
- [governance/README.md](governance/README.md)
- [llm/README.md](llm/README.md)
- [observability/README.md](observability/README.md)
- [registry/README.md](registry/README.md)
- [security/README.md](security/README.md)

## Границы ответственности

- В `core` добавляется только то, что переиспользуется минимум двумя подсистемами.
- Доменная бизнес-логика остается в `fabric`/`foundry`/`scientist`/`lex`/`scholar`.
- Новый межмодульный API сначала фиксируется в `core.contracts`, затем реализуется в доменном модуле.
