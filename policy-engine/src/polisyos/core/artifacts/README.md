# Artifacts Module

## Обзор

Модуль `artifacts` предоставляет инфраструктуру для управления артефактами системы PolisyOS - неизменяемыми объектами с метаданными, хранящимися в Content-Addressable Storage (CAS). Модуль обеспечивает надежное хранение, верификацию и provenance tracking всех результатов вычислений в системе.

## Архитектура

Модуль состоит из следующих компонентов:

```
artifacts/
├── ids.py          # Уникальные идентификаторы артефактов
├── manifest.py     # Метаданные и манифесты артефактов
├── registry.py     # Пакеты реестров компонентов
└── store.py        # Реализация хранилища артефактов
```

## Основные компоненты

### ArtifactID

Уникальный идентификатор артефакта на основе SHA256 хеша содержимого.

```python
from polisyos.core.artifacts.ids import ArtifactID

# Создание из hex строки
artifact_id = ArtifactID.from_sha256_hex("a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3")

# Получение hex представления
hex_value = artifact_id.hex  # "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
```

### ArtifactManifest

Полные метаданные артефакта, включая информацию о производителе, схеме, окружении и зависимостях.

```python
from polisyos.core.artifacts.manifest import ArtifactManifest, ProducerInfo, SchemaInfo

manifest = ArtifactManifest(
    artifact_id=artifact_id,
    kind="fabric.result_bundle",
    media_type="application/json",
    byte_size=1024,
    created_at=datetime.now(),
    producer=ProducerInfo(
        component="fabric_processor",
        version="1.0.0",
        git=GitInfo(commit="abc123", dirty=False)
    ),
    schema=SchemaInfo(name="fabric.result.schema", version="1.0.0"),
    inputs=[InputRef(artifact_id=input_id, role="source_data")]
)
```

### ArtifactRef

Типизированная ссылка на артефакт с проверкой kind и media_type.

```python
from polisyos.core.artifacts.manifest import ArtifactRef

# Общая ссылка
ref = ArtifactRef(
    artifact_id=artifact_id,
    kind="fabric.result_bundle",
    media_type="application/json"
)

# Типизированная ссылка (наследование)
class FabricResultRef(ArtifactRef):
    kind: Literal["fabric.result_bundle"] = "fabric.result_bundle"
    media_type: Literal["application/json"] = "application/json"
```

### FileSystemCAS

Реализация Content-Addressable Storage на файловой системе.

```python
from pathlib import Path
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions

# Инициализация хранилища
store = FileSystemCAS(Path("/tmp/artifacts"))

# Сохранение данных как артефакта
data = {"result": "example", "value": 42}
artifact_ref = store.put_json(
    data,
    PutOptions(
        kind="example.result",
        media_type="application/json",
        producer=ProducerInfo(component="example_component", version="1.0.0")
    )
)

# Получение данных
retrieved_data = store.get_json(artifact_ref.artifact_id)
```

### RegistryBundle

Пакет реестров компонентов системы, содержащий ссылки на все необходимые реестры.

```python
from polisyos.core.artifacts.registry import RegistryBundle

bundle = RegistryBundle(
    bundle_ref=registry_bundle_ref,
    slot_registry=slot_registry_ref,
    mechanism_registry=mechanism_registry_ref,
    constraint_registry=constraint_registry_ref,
    # ... другие реестры
)
```

## Структуры метаданных

### ProducerInfo
Информация о компоненте, создавшем артефакт.

### SchemaInfo
Информация о схеме данных артефакта.

### EnvInfo
Информация об окружении выполнения.

### GitInfo
Информация о Git коммите.

### InputRef
Ссылка на входной артефакт с указанием роли.

### IntegrityInfo
Информация о целостности (SHA256 хеш).

### WarningRecord
Записи предупреждений о потенциальных проблемах.

## Layout хранилища

Артефакты хранятся в иерархической структуре:

```
/root/artifacts/sha256/
├── ab/
│   └── cd/
│       ├── abcdef1234567890abcdef1234567890abcdef.blob
│       └── abcdef1234567890abcdef1234567890abcdef.manifest.json
```

- `.blob` - бинарные данные артефакта
- `.manifest.json` - метаданные в формате JSON

## Верификация целостности

```python
from polisyos.core.artifacts.store import VerificationReport

# Верификация артефакта
report = store.verify(artifact_id)
if not report.ok:
    print(f"Verification failed: {report.error}")
```

## Использование в системе

### В Fabric
Хранение всех результатов обработки данных с полным provenance tracking.

### В Foundry
Хранение состояний симуляций, конфигураций исполнения и результатов калибровки.

### В Scientist
Хранение всех артефактов экспериментов для reproducible research.

### В Runtime
Доступ к развернутым артефактам политик в production.

## Принципы работы

1. **Неизменяемость**: Артефакты никогда не изменяются после создания
2. **Адресация по содержимому**: ID артефакта = SHA256(содержимое)
3. **Дедупликация**: Одинаковые данные имеют одинаковый ID
4. **Верификация**: Целостность проверяется при каждом доступе
5. **Provenance**: Полный трекинг зависимостей между артефактами

## Производительность

- **Хранение**: Эффективная дедупликация экономит дисковое пространство
- **Доступ**: <1ms на операцию чтения/записи
- **Верификация**: Криптографическая проверка целостности
- **Масштабируемость**: Поддержка миллионов артефактов