# Core — Фундаментальная инфраструктура PolisyOS

Модуль `core` — фундамент системы: CAS-хранилище, типизированные контракты, компонентная модель, observability, аудит. Все верхнеуровневые модули (Fabric, Foundry, Scientist, Lex, Runtime, Scholar) зависят от core. Модуль IR не зависит от core (определяет схемы данных самостоятельно).

## Архитектура

```
core/
├── artifacts/      # CAS хранилище, подписи Ed25519, environment manifests, dependency graph
├── audit/          # Сборка и верификация портативных аудит-пакетов (W3C PROV-JSON)
├── canon/          # Детерминированная JSON-сериализация (Decimal, datetime, запрет float)
├── compiler/       # Структуры отчетов компиляции/линковки политик
├── components/     # Component Model v1: identity, discovery, registry, compliance
├── contracts/      # Типизированные контракты между модулями (14 доменов)
├── observability/  # OTel трассировка, Prometheus метрики, determinism tiers, LLM pricing
├── registry/       # Сборка и загрузка registry bundles из IR
├── run/            # Контексты выполнения с lifecycle и трассировкой
└── trace/          # TraceRecord / TraceSink для span-based JSONL логирования
```

## Принципы

- **Content-addressable storage**: ID = SHA256(содержимое), неизменяемость, дедупликация
- **Строгая типизация**: Pydantic-модели с `extra="forbid"`, Literal-типы для kind/media_type
- **Детерминизм**: Каноническая сериализация (запрет float), DeterminismTier для симуляций
- **Provenance**: Полный трекинг зависимостей от входных данных до финальных решений
- **Distributed tracing**: OTel spans + JSONL trace records для воспроизводимости

## Зависимости от Core по модулям

| Модуль | Что использует из Core |
|--------|----------------------|
| **Fabric** | `artifacts.store`, `artifacts.ids`, `canon`, `contracts.fabric`, `audit.prov_json` |
| **Foundry** | `contracts.foundry`, `artifacts`, `run`, `observability.determinism` |
| **Scientist** | `run.context`, `artifacts.store/manifest`, `contracts.scientist/trinity` |
| **Lex** | `artifacts.store/ids`, `canon`, `contracts.lex`, `components` |
| **Runtime** | `contracts.foundry`, `artifacts.environment/graph`, `canon` |
| **Scholar** | `artifacts.store/ids`, `contracts.scholar`, `components` |
| **Packs** | `components` (ComponentId, ComponentKind, ComponentMetadata, Capability) |

## Подсистемы с собственными README

Каждая из следующих директорий — самостоятельная подсистема с публичным API (>= 5 файлов):

- **[artifacts/](artifacts/README.md)** — CAS хранилище с SHA256, подписи Ed25519, EnvironmentManifest, dependency graph
- **[audit/](audit/README.md)** — Сборка портативных `.polisyos-audit.tar.gz` пакетов, офлайн-верификация, W3C PROV-JSON
- **[components/](components/README.md)** — Component Model v1: ComponentId, discovery через entry points, registry с conflict resolution
- **[contracts/](contracts/README.md)** — Типизированные контракты: Fabric, Foundry, Trinity, Lex, Scientist, Scholar, Causal, HTE, Backtest, Uncertainty, Distributional
- **[observability/](observability/README.md)** — OTel трассировка, Prometheus метрики, determinism tiers, LLM cost estimation

---

## Canon — Детерминированная сериализация

> `core/canon/` — 2 файла: `canon_json.py`, `__init__.py`

Каноническая JSON-сериализация для reproducible вычислений и стабильных CAS-хешей.

**Публичный API:**
- `CanonSpec` — конфигурация параметров канонизации
- `to_canonical_bytes(data)` → `bytes` — сериализация в канонические байты
- `from_canonical_bytes(data)` / `from_canonical_obj(data)` — десериализация
- `CanonViolation` — исключение при нарушении правил

**Правила:**
- Запрет `float` и `NaN/Inf` — использовать `Decimal`
- Сортировка ключей, фиксированные разделители `",:"` без пробелов
- Специальные типы: `Decimal` → `{"_type": "decimal", "value": "..."}`, `datetime` → `{"_type": "datetime", "iso_utc": "..."}`, `bytes` → base64
- Поддержка Pydantic-моделей и dataclasses

```python
from polisyos.core.canon import to_canonical_bytes, from_canonical_bytes
from decimal import Decimal

data = {"threshold": Decimal("0.75"), "constraints": ["budget"]}
canonical = to_canonical_bytes(data)       # стабильный хеш
restored = from_canonical_bytes(canonical) # round-trip
```

**Используется:** artifacts (хеширование), Fabric (сериализация evidence), Lex (corpus), Runtime (replay).

---

## Compiler — Отчеты компиляции

> `core/compiler/` — 2 файла: `report.py`, `__init__.py`

Структуры данных для результатов компиляции и линковки политик.

**Публичный API:**
- `CompileReport` (Pydantic) — отчет компиляции: `ok`, `policy_ref`, `program_graph_ref`, `exec_plan_ref`, `link_report_ref`, `notes`
- `put_compile_report(store, report, inputs)` → `CompileReportRef` — сохранение в CAS
- `put_link_report(store, report, inputs)` → `LinkReportRef` — сохранение отчета линковки

```python
from polisyos.core.compiler import CompileReport, put_compile_report

report = CompileReport(ok=True, policy_ref=ref, program_graph_ref=graph_ref, exec_plan_ref=plan_ref)
compile_ref = put_compile_report(store, report, inputs=[policy_input])
```

**Рабочий процесс:** IR компилирует политику → CompileReport → Foundry читает program_graph/exec_plan → Scientist оркестрирует и хранит отчеты.

---

## Registry — Сборка и загрузка реестров

> `core/registry/` — 4 файла: `builder.py`, `builder_from_fragments.py`, `loader.py`, `__init__.py`

Инфраструктура для сборки и загрузки пакетов реестров (SlotRegistry, MechanismTypeRegistry, MetricRegistry, ConstraintRegistry, MergeRuleRegistry и др.) как CAS-артефактов.

**Публичный API:**
- `build_default_registry_bundle(store)` — стандартный пакет из IR
- `build_registry_bundle(store, ...)` — кастомный пакет
- `build_registry_bundle_from_components(store, components)` — из IR-фрагментов компонентов
- `load_registry_bundle(store, ref)` → `RegistryBundle` — загрузка ссылок
- `load_registry_bundle_content(store, ref)` → `RegistryBundleContent` — загрузка полных объектов
- `FragmentPrecedencePolicy` — политика приоритетов при слиянии фрагментов

**Структуры:**
- `RegistryBundlePayload` — ссылки на реестры (обязательные: slot, merge, constraint, mechanism)
- `RegistryBundleContent` — загруженные объекты реестров для компиляции

```python
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content

bundle = build_default_registry_bundle(store)
bundle_ref = bundle.save(store)
content = load_registry_bundle_content(store, bundle_ref)
```

**Используется:** Foundry (валидация и исполнение), Scientist (управление версиями), Compiler (ссылки в CompileReport).

---

## Run — Контексты выполнения

> `core/run/` — 3 файла: `context.py`, `manifest.py`, `__init__.py`

Управление жизненным циклом запусков с автоматической трассировкой и provenance tracking.

**Публичный API:**
- `RunContext` (dataclass) — контекст выполнения с интегрированной трассировкой
  - `RunContext.start(store, registry_bundle)` — создание контекста с генерацией `R_<16hex>` run_id
  - `emit(phase, event, metrics, inputs, outputs)` — запись события в trace
  - `add_input(ref)` / `add_output(ref)` — регистрация артефактов для provenance
  - `finalize(success)` — завершение с сохранением трассировки
- `RunManifest` (Pydantic) — метаданные запуска: run_id, timestamps, producer, inputs/outputs, status, trace_ref, seed, parent_run_id, environment_manifest_ref

```python
from polisyos.core.run import RunContext

ctx = RunContext.start(store=store, registry_bundle=bundle_ref)
ctx.emit("simulation", "STARTED", inputs=[data_ref])
result_ref = run_simulation(ctx, data_ref)
ctx.add_output(result_ref)
ctx.finalize(success=True)
```

**Файловая структура:** `/artifacts/runs/R_{run_id}/trace.jsonl` + `manifest.json`

**Используется:** Foundry (SimulationEngine), Scientist (gate_protocol), Fabric (DataProcessor), audit (assembler читает run metadata).

---

## Trace — Span-based логирование

> `core/trace/` — 3 файла: `record.py`, `sink.py`, `__init__.py`

Низкоуровневые примитивы для записи трассировки: записи событий и sink-адаптеры.

**Публичный API:**
- `TraceRecord` (Pydantic) — запись события: `ts`, `run_id`, `phase`, `event`, `span_id`, `parent_span_id`, `refs` (TraceRefs с inputs/outputs), `metrics`, `warnings`, `errors`
- `TraceSink` (Protocol) — интерфейс для вывода записей (расширяемый)
- `JsonlTraceSink` — реализация для JSONL-файлов

```python
from polisyos.core.trace import TraceRecord, JsonlTraceSink

sink = JsonlTraceSink(Path("/tmp/trace.jsonl"))
record = TraceRecord(run_id="R_abc123", phase="init", event="STARTED")
sink.write(record)
```

**Формат JSONL:**
```jsonl
{"ts":"2024-01-15T10:30:00Z","run_id":"R_123","phase":"data_load","event":"batch_loaded","metrics":{"batch_size":1000}}
```

**Используется:** `run.context` (RunContext.emit записывает через TraceSink), `audit.assembler` (парсит trace.jsonl для provenance).
