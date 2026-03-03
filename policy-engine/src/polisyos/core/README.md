# Core — инфраструктурный слой PolisyOS

`polisyos.core` — общий инфраструктурный слой для доменных подсистем (`fabric`, `foundry`, `scientist`, `lex`, `runtime`, `scholar`, `packs`).

Он концентрирует:
- типизированные межмодульные контракты;
- CAS/lineage/run lifecycle;
- component discovery/bootstrap;
- наблюдаемость, безопасность и устойчивость исполнения.

`polisyos.ir` остается отдельным слоем схем и canonical refs: `core` зависит от `ir`, но не наоборот.

## Архитектурная карта

```text
core/
├── artifacts/      # CAS, manifests, signatures, environment, dependency graph
├── audit/          # экспорт и офлайн-верификация audit package
├── backends/       # generic backend dispatcher
├── cache/          # in-memory LRU/TTL cache primitives
├── canon/          # canonical JSON и хеширование
├── compiler/       # compile/link report artifacts
├── components/     # component model, discovery, bootstrap, CLI wiring
├── contracts/      # typed ABI: refs + DTO между подсистемами
├── discovery/      # generic discovery orchestration primitives
├── errors/         # базовая ошибка и категории
├── evaluation/     # weighted scoring + threshold mapping
├── governance/     # validation profiles + legal/safety passes
├── llm/            # traced LLM facade (response/cost/retry)
├── observability/  # tracing, metrics, logs, propagation, pricing
├── pipeline/       # linear + DAG pipeline primitives
├── registry/       # registry bundle build/load + generic registries
├── resilience/     # retry policy с backoff/jitter
├── run/            # RunContext и RunManifest lifecycle
├── security/       # tenant isolation, authz, audit chain, TEE, SBOM, SLSA
└── trace/          # TraceRecord + sinks (jsonl/composite)
```

## Роль в системе

- `ABI plane`: `core.contracts` фиксирует стабильные границы между модулями.
- `Data/provenance plane`: `artifacts`, `run`, `trace`, `audit` обеспечивают воспроизводимость.
- `Plugin plane`: `components`, `discovery`, `registry` соединяют плагины с runtime.
- `NFR plane`: `security`, `observability`, `resilience`, `pipeline` дают единые runtime-гарантии.

## Ключевые потоки

1. Discovery и bootstrap компонентов:
   `components.discover_components` -> `build_components_index` -> `bootstrap_plugin_registries`.
2. Run lifecycle:
   `run.RunContext.start` -> trace события (`trace.jsonl`) -> `RunManifest` в CAS.
3. Governance validation:
   `governance.ValidationProfile` + набор pass'ов (`safety`, `legal`, ...).
4. Проверяемая поставка:
   `audit.AuditPackageAssembler` / `audit.AuditPackageVerifier` + `artifacts.signing` + `security.slsa`.

## Публичные точки входа

Через lazy-facade `polisyos.core` экспортируются:
- `artifacts`, `backends`, `cache`, `canon`, `components`, `contracts`, `discovery`
- `evaluation`, `errors`, `llm`, `observability`, `pipeline`, `resilience`, `registry`, `run`

Импортируются напрямую (вне lazy facade):
- `polisyos.core.audit`
- `polisyos.core.compiler`
- `polisyos.core.governance`
- `polisyos.core.security`
- `polisyos.core.trace`

## Связь с соседними директориями

| Директория | Как использует `core` |
|---|---|
| `fabric/` | `contracts.fabric`, CAS (`artifacts`), component discovery, provenance |
| `foundry/` | compile/execute contracts, registry bundles, tracing/metrics |
| `scientist/` | run lifecycle, governance passes, LLM facade, execution contracts |
| `lex/` | legal contracts, legal/safety passes, norm pack/provider bootstrap |
| `runtime/` | runtime API contracts, security routing/authz, observability hooks |
| `scholar/` | scholar contracts, CAS bundles, freshness and enrichment telemetry |
| `packs/` | component metadata/capabilities и IR fragments |
| `ir/` | canonical refs/schemas для контрактов и registry payloads |

## README подсистем

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

- В `core` попадает только функциональность, которую используют минимум две подсистемы.
- Доменная логика остается в `fabric`/`foundry`/`scientist`/`lex`/`scholar`.
- Новый межмодульный интерфейс сначала фиксируется в `core.contracts`, затем внедряется в доменный модуль.
