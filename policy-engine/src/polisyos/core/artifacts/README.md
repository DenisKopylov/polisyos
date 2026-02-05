# Artifacts (CAS хранилище)

## Обзор

Content-Addressable Storage с SHA256 хешированием для неизменяемых артефактов. Обеспечивает дедупликацию, provenance tracking и reproducible симуляции через EnvironmentManifest.

## Архитектура

```
artifacts/
├── ids.py          # ArtifactID (SHA256 идентификаторы)
├── manifest.py     # ArtifactManifest, ArtifactRef, типизированные ссылки
├── environment.py  # EnvironmentManifest с fingerprinting
├── registry.py     # RegistryBundle
└── store.py        # FileSystemCAS, PutOptions, верификация
```

## Основные компоненты

### ArtifactID
Уникальный SHA256-based идентификатор артефакта.

```python
from polisyos.core.artifacts.ids import ArtifactID
artifact_id = ArtifactID.from_sha256_hex("a665a459...")
```

### ArtifactManifest
Метаданные артефакта (производитель, схема, зависимости, provenance).

### ArtifactRef
Типизированная ссылка с проверкой kind/media_type.

```python
from polisyos.core.artifacts.manifest import ArtifactRef

ref = ArtifactRef(
    artifact_id=artifact_id,
    kind="fabric.result_bundle",
    media_type="application/json"
)
```

### FileSystemCAS
CAS реализация на файловой системе.

```python
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions

store = FileSystemCAS(Path("/tmp/artifacts"))
ref = store.put_json(data, PutOptions(kind="result", producer=info))
retrieved = store.get_json(ref.artifact_id)
```

### RegistryBundle
Пакет реестров компонентов системы.

## Environment Manifest

### EnvironmentManifest
Манифест окружения для reproducible симуляций с fingerprinting и compatibility scoring.

```python
from polisyos.core.artifacts.environment import capture_environment

env_manifest = capture_environment(
    project_root=Path("/path/to/project"),
    include_git=True,
    include_dependencies=True
)

# Компоненты: CPU, GPU, JAX, Git, Python, dependencies
fingerprint = env_manifest.fingerprint  # Для быстрого сравнения
compatibility = env_manifest.compatibility_score(other_env)
```

### Сравнение окружений

```python
from polisyos.core.artifacts.environment import compare_environments
diffs = compare_environments(env1, env2)  # Анализ различий и рисков
```

### EnvironmentManifestRef
Типизированная ссылка на манифест окружения.

## Структуры метаданных

- **ProducerInfo**: Компонент-производитель
- **SchemaInfo**: Схема данных артефакта
- **InputRef**: Ссылки на входные артефакты с ролями
- **WarningRecord**: Предупреждения о проблемах

## Layout хранилища

Иерархическая структура: `/artifacts/sha256/ab/cd/abcdef.blob` и `.manifest.json`

## Верификация

```python
report = store.verify(artifact_id)
if not report.ok:
    print(f"Verification failed: {report.error}")
```

## Использование в системе

- **Fabric**: Хранение результатов обработки с provenance tracking
- **Foundry**: Состояния симуляций, environment manifests, результаты калибровки
- **Scientist**: Артефакты экспериментов для reproducible research
- **Runtime**: Доступ к развернутым политикам
- **Environment**: Захват окружения для reproducible симуляций

## Принципы

- **Неизменяемость**: Артефакты неизменны после создания
- **Адресация по содержимому**: ID = SHA256(содержимое)
- **Дедупликация**: Одинаковые данные = одинаковый ID
- **Верификация**: Криптографическая проверка целостности
- **Provenance**: Полный трекинг зависимостей

## Производительность

- **Доступ**: <1ms на операцию чтения/записи
- **Верификация**: Криптографическая проверка
- **Масштабируемость**: Миллионы артефактов с дедупликацией
- **Environment capture**: <2s с hardware detection
- **Fingerprinting**: <1ms для сравнения окружений

## Связи с модулями

- **Core**: Интеграция с observability для трассировки CAS операций
- **Fabric**: Хранение результатов обработки с provenance
- **Foundry**: Состояния симуляций, environment manifests, результаты
- **Scientist**: Артефакты экспериментов
- **Runtime**: Доступ к развернутым политикам
- **Trinity**: Хранение спецификаций (ProblemFrame, PolicySpec, ModelSpec)

## HPC Observability

Автоматическая трассировка всех CAS операций при `POLISYOS_HPC_OBSERVABILITY_ENABLED=true`. Метрики: операции, I/O размеры, продолжительность, кеш-хиты.