# Core Module (Фундаментальная инфраструктура)

## Обзор

Модуль `core` - фундамент PolisyOS, предоставляющий базовую инфраструктуру для всей системы. Обеспечивает управление артефактами, каноническую сериализацию, типизированные контракты, observability и трассировку.

## Архитектура

```
core/
├── artifacts/     # CAS хранилище с environment manifests
├── canon/         # Детерминированная JSON сериализация
├── compiler/      # Отчеты компиляции и линковки
├── components/    # Component model v1 (discovery/registry)
├── contracts/     # Типизированные контракты (Fabric/Foundry/Trinity/Lex)
├── observability/ # Production телеметрия (OTel/Prometheus)
├── registry/      # Управление реестрами компонентов
├── run/           # Контексты выполнения с трассировкой
└── trace/         # Span-based логирование и трассировка
```

**Принципы**: Неизменяемость, строгая типизация, reproducible симуляции, distributed tracing.

## Компоненты

- **Artifacts**: CAS хранилище с SHA256, EnvironmentManifest для reproducible симуляций
- **Canon**: Детерминированная сериализация (запрет float, поддержка Decimal/datetime)
- **Contracts**: Типизированные контракты между модулями (Fabric/Foundry/Trinity/Lex/Scientist)
- **Observability**: OTel трассировка, Prometheus метрики, структурированное логирование
- **Registry**: Управление реестрами компонентов с версионированием
- **Components**: Component model v1 с discovery и registry механизмами
- **Run**: Контексты выполнения с автоматической трассировкой
- **Trace**: Span-based логирование с provenance tracking
- **Compiler**: Отчеты компиляции и линковки как артефакты

## Связи с модулями

**Архитектура**: Core - фундамент, все верхние модули зависят от core (IR не зависит от core).

### Зависимости от Core:
- **IR**: Не зависит (определяет схемы данных)
- **Fabric**: artifacts.store, contracts.fabric, trace, canon
- **Foundry**: contracts.foundry, artifacts, run, trace, canon, environment manifests
- **Scientist**: run, artifacts, contracts.trinity/scientist, registry
- **Runtime**: artifacts, contracts, run, observability
- **Lex**: contracts.lex, artifacts, trace

### Обратные зависимости:
Артефакты, трассировка, контракты, канонизация, observability интегрируются во все модули.

## Примеры использования

### Контекст выполнения с трассировкой:

```python
from polisyos.core.run import RunContext
from polisyos.core.artifacts.store import FileSystemCAS

store = FileSystemCAS(Path("/tmp/artifacts"))
ctx = RunContext.start(store=store, registry_bundle=registry_ref)
ctx.emit("processing", "started", inputs=[data_ref])
# ... операции ...
ctx.finish(success=True)
```

### Работа с артефактами:

```python
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.contracts.fabric import FabricResultRef

result_ref = store.put_json(
    result_data,
    PutOptions(kind="fabric.result_bundle", producer=producer_info)
)
typed_ref = FabricResultRef.from_artifact_ref(result_ref)
```

### Каноническая сериализация:

```python
from polisyos.core.canon import to_canonical_bytes
from decimal import Decimal

data = {"threshold": Decimal("0.75"), "constraints": ["budget"]}
canonical = to_canonical_bytes(data)  # Стабильный хеш
```

## Принципы и статус

**Архитектурные принципы**: CAS с SHA256, типобезопасные контракты, детерминированная сериализация, distributed tracing, reproducible симуляции.

**Текущее состояние**: Production-ready, активно используется всеми модулями PolisyOS. Стабильные API с версионированием, обратная совместимость, автоматические миграции.

**Производительность**: <1ms CAS операции, <0.1ms трассировка, поддержка миллионов артефактов с дедупликацией и криптографической верификацией.
