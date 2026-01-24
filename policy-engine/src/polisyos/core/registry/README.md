# Registry Module (Реестры компонентов)

## Обзор

Модуль `registry` предоставляет инфраструктуру для сборки, хранения и загрузки реестров компонентов системы PolisyOS. Реестры содержат определения механизмов, метрик, ограничений и других компонентов, необходимых для работы политик. Модуль обеспечивает централизованное управление компонентами и их версионирование.

## Архитектура

```
registry/
├── builder.py     # Сборка реестров из IR модуля
├── loader.py      # Загрузка и десериализация реестров
└── __init__.py    # Экспорт основных функций
```

## Типы реестров

Система поддерживает следующие типы реестров компонентов:

### SlotRegistry
Определения слотов данных и их типов.

### MechanismTypeRegistry
Типы и конфигурации механизмов политики.

### MetricRegistry
Метрики для оценки и мониторинга.

### ConstraintRegistry
Ограничения и правила валидации.

### MergeRuleRegistry
Правила объединения состояний.

### SelectorFieldRegistry
Поля для селекции и фильтрации данных.

### UnitsRegistry
Единицы измерения и конвертации.

### TrustRegistry (опционально)
Политики доверия к источникам данных.

### PredicateRegistry (опционально)
Предикаты для условной логики.

### PrivacyRegistry (опционально)
Политики приватности данных.

## Основные функции

### build_default_registry_bundle()

Сборка стандартного пакета реестров из IR модуля.

```python
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.artifacts.store import FileSystemCAS
from pathlib import Path

store = FileSystemCAS(Path("/tmp/artifacts"))

# Сборка стандартных реестров
registry_bundle = build_default_registry_bundle(store)

# Сохранение пакета как артефакта
bundle_ref = registry_bundle.save(store)

print(f"Registry bundle saved: {bundle_ref.artifact_id}")
print(f"Slot registry: {registry_bundle.slot_registry_ref}")
print(f"Mechanism registry: {registry_bundle.mechanism_registry_ref}")
```

### build_registry_bundle()

Сборка кастомного пакета реестров.

```python
from polisyos.core.registry import build_registry_bundle
from polisyos.ir.kernel import SlotRegistry, MechanismTypeRegistry

# Создание кастомных реестров
custom_slot_registry = SlotRegistry(...)
custom_mechanism_registry = MechanismTypeRegistry(...)

# Сборка пакета
custom_bundle = build_registry_bundle(
    store=store,
    slot_registry=custom_slot_registry,
    mechanism_registry=custom_mechanism_registry,
    # Другие реестры...
)

custom_bundle_ref = custom_bundle.save(store)
```

### load_registry_bundle()

Загрузка пакета реестров из артефакта.

```python
from polisyos.core.registry import load_registry_bundle

# Загрузка пакета реестров
loaded_bundle = load_registry_bundle(store, bundle_ref)

# Доступ к реестрам
slots = loaded_bundle.slots
mechanisms = loaded_bundle.mechanisms
metrics = loaded_bundle.metrics
constraints = loaded_bundle.constraints
```

### load_registry_bundle_content()

Загрузка полного содержимого реестров с десериализацией.

```python
from polisyos.core.registry import load_registry_bundle_content

# Загрузка с полным содержимым
content = load_registry_bundle_content(store, bundle_ref)

# Доступ к загруженным объектам реестров
slot_registry_obj = content.slot_registry
mechanism_registry_obj = content.mechanism_registry
merge_registry_obj = content.merge_registry
# ... и т.д.
```

## Структура RegistryBundle

### RegistryBundlePayload

Базовая структура ссылок на реестры:

```python
class RegistryBundlePayload(BaseModel):
    slot_registry: ArtifactRef
    merge_registry: ArtifactRef
    constraint_registry: ArtifactRef
    selector_field_registry: ArtifactRef | None = None
    metric_registry: ArtifactRef | None = None
    mechanism_registry: ArtifactRef
    trust_registry: ArtifactRef | None = None
    units_registry: ArtifactRef | None = None
    predicate_registry: ArtifactRef | None = None
    privacy_registry: ArtifactRef | None = None
```

### RegistryBundle

Расширенная версия с ссылкой на сам пакет:

```python
class RegistryBundle(RegistryBundlePayload):
    bundle_ref: ArtifactRef
```

### RegistryBundleContent

Загруженное содержимое всех реестров:

```python
@dataclass(frozen=True)
class RegistryBundleContent:
    bundle_ref: ArtifactRef
    slot_registry: SlotRegistry
    merge_registry: MergeRuleRegistry
    mechanism_registry: MechanismTypeRegistry
    constraint_registry: ConstraintRegistry
    # ... остальные реестры
```

## Рабочий процесс

### 1. Сборка стандартных реестров

```python
from polisyos.core.registry import build_default_registry_bundle

# Автоматическая сборка из IR модуля
registry_bundle = build_default_registry_bundle(store)

# Сохранение для повторного использования
bundle_ref = registry_bundle.save(store)
```

### 2. Кастомизация реестров

```python
# Загрузка существующего пакета
base_bundle = load_registry_bundle(store, bundle_ref)

# Модификация конкретного реестра
custom_mechanisms = modify_mechanism_registry(base_bundle.mechanism_registry)

# Сборка нового пакета
custom_bundle = build_registry_bundle(
    store=store,
    slot_registry=base_bundle.slot_registry,
    mechanism_registry=custom_mechanisms,
    # ... остальные реестры из базового пакета
)
```

### 3. Использование в политиках

```python
# Загрузка реестров для компиляции политики
content = load_registry_bundle_content(store, bundle_ref)

# Передача в компилятор
from polisyos.ir.compiler import compile_policy

result = compile_policy(
    store=store,
    policy_ref=policy_ref,
    registry_bundle=content
)
```

## Интеграция с другими модулями

### IR (Intermediate Representation)
- Предоставляет определения реестров (SlotRegistry, MechanismRegistry, etc.)
- Используется builder.py для сборки стандартных реестров

### Foundry
- Загружает реестры для валидации и исполнения политик
- Использует RegistryBundleContent для доступа к определениям компонентов

### Scientist
- Управляет версиями реестров в экспериментах
- Хранит provenance реестров в decision packets

### Compiler
- Включает ссылку на registry_bundle в CompileReport
- Обеспечивает воспроизводимость компиляции

## Хранение и версионирование

### Структура артефактов

```
artifacts/
├── sha256/ab/cd/<hash1>.blob    # SlotRegistry JSON
├── sha256/ab/cd/<hash1>.manifest.json
├── sha256/ef/gh/<hash2>.blob    # MechanismRegistry JSON
├── sha256/ef/gh/<hash2>.manifest.json
├── ...
└── sha256/xy/zl/<bundle_hash>.blob  # RegistryBundle JSON
```

### Метаданные реестров

Каждый реестр сохраняется с полными метаданными:

```python
PutOptions(
    kind="registry.slot_registry",
    media_type="application/json",
    schema=SchemaInfo(name="polisyos.ir.SlotRegistry", version="1.0"),
    producer=ProducerInfo(component="registry_builder", version="1.0.0")
)
```

### Версионирование

- **Schema versioning**: Каждая версия реестра имеет schema_version
- **Artifact versioning**: Новые версии реестров = новые артефакты
- **Bundle versioning**: RegistryBundle ссылается на конкретные версии реестров

## Примеры использования

### Создание кастомного реестра механизмов

```python
from polisyos.ir.kernel import MechanismTypeRegistry, MechanismType
from polisyos.core.registry import build_registry_bundle

# Создание кастомного механизма
custom_mechanism = MechanismType(
    name="advanced_risk_model",
    schema_version="1.0",
    parameters={
        "model_type": "neural_network",
        "features": ["amount", "frequency", "history"],
        "threshold": 0.8
    }
)

# Добавление в реестр
custom_registry = MechanismTypeRegistry(
    schema_version="1.0",
    mechanisms=[custom_mechanism]
)

# Сборка пакета с кастомным реестром
bundle = build_registry_bundle(
    store=store,
    mechanism_registry=custom_registry,
    # Использование стандартных для остальных
    slot_registry=DEFAULT_SLOT_REGISTRY,
    constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
    # ...
)
```

### Валидация реестров

```python
def validate_registry_bundle(store: FileSystemCAS, bundle_ref: ArtifactRef) -> bool:
    """Валидация целостности пакета реестров"""

    try:
        # Попытка загрузки
        content = load_registry_bundle_content(store, bundle_ref)

        # Проверка наличия обязательных реестров
        required_registries = [
            content.slot_registry,
            content.mechanism_registry,
            content.constraint_registry,
            content.merge_registry
        ]

        if any(reg is None for reg in required_registries):
            return False

        # Проверка версий схем
        if content.slot_registry.schema_version != "1.0":
            return False

        return True

    except Exception:
        return False
```

### Управление версиями реестров

```python
def create_registry_version(store: FileSystemCAS, base_bundle_ref: ArtifactRef) -> ArtifactRef:
    """Создание новой версии реестров"""

    # Загрузка базовой версии
    base_content = load_registry_bundle_content(store, base_bundle_ref)

    # Модификация (пример: добавление нового механизма)
    updated_mechanisms = MechanismTypeRegistry(
        schema_version="1.1",  # Новая версия
        mechanisms=base_content.mechanism_registry.mechanisms + [new_mechanism]
    )

    # Сборка новой версии пакета
    new_bundle = build_registry_bundle(
        store=store,
        slot_registry=base_content.slot_registry,
        mechanism_registry=updated_mechanisms,
        # ... остальные реестры без изменений
    )

    return new_bundle.save(store)
```

## Производительность

- **Ленивая загрузка**: Реестры загружаются только при необходимости
- **Кеширование**: Артефакты кешируются CAS для быстрого доступа
- **Дедупликация**: Одинаковые реестры имеют одинаковые артефакты
- **Оптимизация**: RegistryBundleContent использует dataclasses для эффективности

## Лучшие практики

1. **Используйте стандартные реестры**: Начинайте с build_default_registry_bundle()
2. **Версионируйте изменения**: Новые версии реестров = новые артефакты
3. **Валидируйте реестры**: Проверяйте целостность перед использованием
4. **Документируйте кастомизации**: Комментируйте причины изменений реестров
5. **Тестируйте совместимость**: Проверяйте работу политик с новыми реестрами

## Отладка и мониторинг

### Проверка содержимого реестра

```python
def inspect_registry(store: FileSystemCAS, bundle_ref: ArtifactRef) -> dict:
    """Инспекция содержимого пакета реестров"""

    bundle = load_registry_bundle(store, bundle_ref)
    content = load_registry_bundle_content(store, bundle_ref)

    return {
        "bundle_id": str(bundle.bundle_ref.artifact_id),
        "slot_count": len(content.slot_registry.slots),
        "mechanism_count": len(content.mechanism_registry.mechanisms),
        "constraint_count": len(content.constraint_registry.constraints),
        "schema_versions": {
            "slots": content.slot_registry.schema_version,
            "mechanisms": content.mechanism_registry.schema_version,
            "constraints": content.constraint_registry.schema_version,
        }
    }
```