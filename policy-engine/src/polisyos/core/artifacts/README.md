# Artifacts (CAS хранилище)

## Обзор

Content-Addressable Storage для неизменяемых артефактов. SHA256 хеширование, дедупликация, provenance tracking, reproducible симуляции через EnvironmentManifest.

## Архитектура

```
artifacts/
├── ids.py          # ArtifactID - SHA256 идентификаторы
├── manifest.py     # ArtifactManifest, ArtifactRef
├── environment.py  # EnvironmentManifest с fingerprinting
├── registry.py     # RegistryBundle
└── store.py        # FileSystemCAS, PutOptions, VerificationReport
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

## Environment Manifest (Манифест окружения)

### EnvironmentManifest

Полный манифест окружения для обеспечения воспроизводимости симуляций.

```python
from polisyos.core.artifacts.environment import EnvironmentManifest, capture_environment
from pathlib import Path

# Захват текущего окружения
env_manifest = capture_environment(
    project_root=Path("/path/to/project"),
    include_git=True,
    include_dependencies=True,
    include_system_libraries=True
)

# Доступ к компонентам
print(f"CPU: {env_manifest.cpu.architecture} with {env_manifest.cpu.core_count} cores")
print(f"GPU: {env_manifest.gpu.available}, {env_manifest.gpu.device_count} devices")
print(f"JAX: {env_manifest.jax.jax_version}, backend: {env_manifest.jax.default_backend}")
print(f"Git: {env_manifest.git.commit_short if env_manifest.git else 'no git info'}")

# Fingerprint для быстрого сравнения
fingerprint = env_manifest.fingerprint
print(f"Environment fingerprint: {fingerprint}")
```

### CPUInfo

Информация о процессоре и его возможностях.

```python
cpu_info = env_manifest.cpu
print(f"Architecture: {cpu_info.architecture}")
print(f"Model: {cpu_info.model_name}")
print(f"Cores: {cpu_info.core_count}, Threads: {cpu_info.thread_count}")
print(f"AVX support: {cpu_info.has_avx}, AVX2: {cpu_info.has_avx2}, AVX512: {cpu_info.has_avx512}")
```

### GPUInfo

Информация о графическом процессоре.

```python
gpu_info = env_manifest.gpu
if gpu_info.available:
    print(f"GPU devices: {gpu_info.device_count}")
    print(f"CUDA version: {gpu_info.cuda_version}")
    print(f"Driver version: {gpu_info.cuda_driver_version}")
    print(f"Memory: {gpu_info.memory_gb} GB")
else:
    print("No GPU available")
```

### JAXInfo

Информация о JAX/XLA рантайме.

```python
jax_info = env_manifest.jax
print(f"JAX version: {jax_info.jax_version}")
print(f"XLA version: {jax_info.xla_version}")
print(f"Default backend: {jax_info.default_backend}")
print(f"Available backends: {jax_info.available_backends}")
print(f"X64 enabled: {jax_info.x64_enabled}")
print(f"Deterministic ops: {jax_info.deterministic_ops_enabled}")
```

### Сравнение окружений

```python
from polisyos.core.artifacts.environment import compare_environments

# Сравнение двух манифестов
diffs = compare_environments(env1, env2)

for diff in diffs:
    print(f"{diff.field_name}: {diff.value_a} -> {diff.value_b}")
    print(f"  Risk: {diff.risk_level}, Explanation: {diff.explanation}")
```

### EnvironmentManifestRef

Типизированная ссылка на манифест окружения.

```python
from polisyos.core.artifacts.environment import EnvironmentManifestRef

env_ref = EnvironmentManifestRef(
    artifact_id=env_artifact_id,
    kind="foundry.environment_manifest",  # literal type
    media_type="application/json"         # literal type
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

### В Environment Capture
Захват и хранение манифестов окружения для reproducible симуляций.

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
- **Environment capture**: <2s для полного захвата окружения с hardware detection
- **Fingerprinting**: <1ms для быстрого сравнения окружений
- **Compatibility scoring**: Автоматическая оценка совместимости окружений
- **HPC Observability**: Интеграция с трассировкой и метриками для Phase 3 операций

## Связи с другими модулями

### Core (Observability)
Интеграция с модулем observability для трассировки операций CAS и метрик производительности:

```python
# Автоматическая трассировка операций чтения/записи
store = FileSystemCAS(Path("/tmp/artifacts"))
data = store.get_json(artifact_id)  # Создает span "cas.get_bytes"
```

### Fabric (Обработка данных)
Хранение всех результатов обработки данных с provenance tracking:

```python
# Fabric сохраняет результаты как артефакты
fabric_result_ref = store.put_json(
    fabric_result_data,
    PutOptions(
        kind="fabric.result_bundle",
        producer=ProducerInfo(component="fabric_processor")
    )
)
```

### Foundry (Симуляция и исполнение)
Хранение состояний симуляций, конфигураций и результатов:

```python
# Сохранение состояния симуляции
state_ref = store.put_json(
    state_snapshot.model_dump(),
    PutOptions(
        kind="foundry.state_snapshot",
        producer=ProducerInfo(component="simulation_engine")
    )
)

# Environment manifest для reproducible симуляций
env_ref = store.put_json(
    environment_manifest.model_dump(),
    PutOptions(
        kind="foundry.environment_manifest",
        producer=ProducerInfo(component="environment_capture")
    )
)
```

### Scientist (Оркестрация экспериментов)
Хранение всех артефактов экспериментов для reproducible research:

```python
# Сохранение результатов эксперимента
experiment_ref = store.put_json(
    experiment_results,
    PutOptions(
        kind="scientist.experiment_results",
        producer=ProducerInfo(component="experiment_runner")
    )
)
```

### Runtime (Production исполнение)
Доступ к развернутым артефактам политик:

```python
# Загрузка обученной политики для production
policy_data = store.get_json(policy_ref.artifact_id)
trained_policy = Policy.from_dict(policy_data)
```

### Trinity (Базовые спецификации)
Хранение Trinity артефактов (ProblemFrame, PolicySpec, ModelSpec):

```python
# Сохранение Trinity bundle
trinity_ref = store.put_json(
    trinity_bundle.model_dump(),
    PutOptions(
        kind="scientist.trinity_bundle",
        producer=ProducerInfo(component="experiment_setup")
    )
)
```

## Интеграция с HPC Observability

### Автоматическая трассировка
При включенной `POLISYOS_HPC_OBSERVABILITY_ENABLED=true` все операции CAS автоматически трассируются:

- **get_bytes/get_json**: span "cas.get_bytes" с атрибутами размера и ID
- **put_bytes/put_json**: span "cas.put_bytes" с атрибутами размера и типа
- **verify**: span "cas.verify" с результатом верификации

### Метрики производительности
Автоматический сбор метрик для мониторинга:

- `polisyos_artifact_operations_total`: Счетчик операций по типу
- `polisyos_artifact_io_bytes`: Гистограмма размеров передаваемых данных
- `polisyos_artifact_io_duration_seconds`: Время выполнения операций
- `polisyos_artifact_cache_hits_total`: Попадания в кеш
- `polisyos_artifact_cache_misses_total`: Промахи кеша

### Настройка интеграции
```python
from polisyos.core.artifacts.store import FileSystemCAS

# HPC observability включается автоматически через переменные окружения
store = FileSystemCAS(Path("/tmp/artifacts"))

# Все операции теперь трассируются и метрикуются
data = store.get_json(artifact_id)
```