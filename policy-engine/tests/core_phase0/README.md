# Core Phase 0 Tests

Тесты фундаментальных компонентов core layer - базовые примитивы для всей системы Policy Engine.

**Последнее обновление:** Январь 2026
**Уровень:** Core Phase 0 (фундаментальные примитивы)
**Зависимости:** Только стандартная библиотека Python, pathlib, hashlib

## Архитектурный контекст

Core Phase 0 представляет собой фундаментальную инфраструктуру, на которой строятся все остальные компоненты системы. Эти тесты обеспечивают корректность базовых примитивов хранения, сериализации и управления метаданными.

## Структура тестов

```
core_phase0/
├── conftest.py                    # Специфичные fixtures для core тестов
├── test_artifact_store.py         # FileSystemCAS, дедупликация, верификация integrity
├── test_canon_json.py             # Каноническая JSON сериализация, детерминированные хэши
├── test_environment_manifest.py   # Захват и сравнение environment манифестов
├── test_registry_bundle.py        # Сборка и загрузка registry bundles
└── test_run_context.py            # Контекст выполнения и артефакты producer'а
```

## Категории тестов

### Artifact Store (`test_artifact_store.py`)

**Цель:** Валидация content-addressable storage с дедупликацией и integrity checks.

**Ключевые тесты:**
- **Roundtrip Operations**: `put_bytes` → `get_bytes` с верификацией SHA256
- **Content Deduplication**: Идентичный контент производит одинаковые artifact ID
- **Canonical JSON Deduplication**: Нормализованная сериализация предотвращает дубликаты
- **Manifest Persistence**: Сохранение и загрузка метаданных артефактов

**Принципы:**
- **SHA256 Addressing**: Content-addressable storage с криптографической integrity
- **Immutable Artifacts**: Артефакты неизменяемы после создания
- **Deduplication**: Автоматическое обнаружение и переиспользование идентичного контента
- **Metadata Tracking**: Полная provenance информация для каждого артефакта

### Canonical JSON (`test_canon_json.py`)

**Цель:** Детерминированная сериализация с математическими гарантиями стабильности.

**Ключевые тесты:**
- **Key Order Independence**: Порядок ключей не влияет на сериализацию
- **Float Prohibition**: Запрет на float значения (только Decimal для денег)
- **NaN/Inf Rejection**: Отклонение нечисловых значений даже в permissive mode
- **Datetime Normalization**: UTC timestamps с Z-сuffixed format
- **Golden Hash Stability**: Детерминированные SHA256 для валидных структур

**Принципы:**
- **Mathematical Stability**: Хэши независимы от порядка ключей/элементов
- **Type Safety**: Строгая типизация, запрет на неопределенные значения
- **Decimal Money**: Принудительное использование Decimal для финансовых расчетов
- **UTC Timestamps**: Нормализованное представление времени

### Registry Bundle (`test_registry_bundle.py`)

**Цель:** Централизованное управление метаданными и конфигурациями системы.

**Ключевые тесты:**
- **Bundle Construction**: Сборка полного registry bundle из компонентов
- **Artifact Persistence**: Все registry компоненты сохраняются как артефакты
- **Reference Integrity**: Корректные ссылки между компонентами bundle

**Принципы:**
- **Centralized Metadata**: Единое место для всех системных конфигураций
- **Version Tracking**: Полная traceability версий registry компонентов
- **Artifact-based Storage**: Registry данные immutable и versioned

### Environment Manifest (`test_environment_manifest.py`)

**Цель:** Захват и сравнение вычислительных окружений для обеспечения reproducibility.

**Ключевые тесты:**
- **Environment Capture**: Захват CPU/GPU/OS/Python/JAX информации без приватных данных
- **Manifest Fingerprinting**: Детерминированные SHA256 fingerprints для environment comparison
- **Compatibility Scoring**: Автоматическое определение compatibility между окружениями с risk levels
- **Component Validation**: Валидация отдельных компонентов (CPU info, GPU info, OS info, etc.)

**Принципы:**
- **Deterministic Fingerprinting**: Стабильные хэши независимо от порядка компонентов
- **Privacy Protection**: Исключение hostname, username и других приватных данных
- **Risk-based Comparison**: Классификация различий по уровням риска (CRITICAL/HIGH/MEDIUM/LOW/INFO)
- **Performance Bounds**: Быстрый capture (< 2 сек) для CI/CD интеграции

### Run Context (`test_run_context.py`)

**Цель:** Управление жизненным циклом выполнения и метаданными producer'ов.

**Ключевые тесты:**
- **Context Initialization**: Создание run context с producer метаданными
- **Trace Emission**: Запись операций в audit trail
- **Manifest Writing**: Сохранение run manifest с детерминированными seed'ами
- **Path Resolution**: Корректное разрешение относительных путей артефактов

**Принципы:**
- **Producer Tracking**: Полная информация о создателе и окружении
- **Audit Trail**: JSON Lines логирование всех операций с timestamps
- **Reproducible Execution**: Детерминированные seed'ы для воспроизводимости
- **Portable Paths**: Относительные пути для переносимости между окружениями

## Конфигурация окружения (conftest.py)

### Специфичные Fixtures

```python
@pytest.fixture()
def cas_root(tmp_path: Path) -> Path:
    return tmp_path / ".polisyos"

@pytest.fixture()
def store(cas_root: Path) -> FileSystemCAS:
    return FileSystemCAS(cas_root)

@pytest.fixture()
def producer() -> ProducerInfo:
    return ProducerInfo(
        component="tests.phase0",
        version="0.0.0",
        git=GitInfo(commit="0000000", dirty=False),
    )

@pytest.fixture()
def env_info() -> EnvInfo:
    return EnvInfo(
        python=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        platform=platform.platform(),
        deps_lock_hash="sha256:" + "0" * 64,
    )
```

## Запуск тестов

```bash
# Все core phase 0 тесты
pytest tests/core_phase0/ -v

# Конкретный компонент
pytest tests/core_phase0/test_artifact_store.py -v
pytest tests/core_phase0/test_canon_json.py -v
pytest tests/core_phase0/test_registry_bundle.py -v
pytest tests/core_phase0/test_run_context.py -v
```

## Связи с другими модулями

### Зависимости от Core Phase 0

**Все модули системы** используют компоненты Core Phase 0:
- **Artifact Store**: Фундаментальное хранилище для всех immutable артефактов
- **Canonical JSON**: Стандартизированная сериализация для детерминированных хэшей
- **Environment Manifest**: Захват и сравнение окружений для reproducibility и debugging
- **Registry System**: Централизованное управление метаданными и конфигурациями
- **Run Context**: Базовая инфраструктура для execution tracking и audit trails

### Архитектурные инварианты

- **Закон D**: Core layer как фундамент (core → runtime → ir → fabric → foundry → scientist)
- **Content Addressing**: Все артефакты адресуются по SHA256 хэшу контента
- **Immutability**: Артефакты неизменяемы после создания
- **Provenance Tracking**: Полная traceability для всех операций

## Разработка и расширение

### Добавление новых тестов

1. Используйте стандартные fixtures: `store`, `producer`, `env_info`
2. Тестируйте roundtrip операции для всех CRUD-like функций
3. Проверяйте integrity через SHA256 верификацию
4. Валидируйте immutable constraints (артефакты нельзя изменять)
5. Тестируйте дедупликацию для идентичного контента

### Отладка

```bash
# С подробным выводом для конкретного теста
pytest tests/core_phase0/test_canon_json.py::test_golden_hash_is_stable -v -s

# С остановкой на первой ошибке
pytest tests/core_phase0/ --tb=short -x
```

## Troubleshooting

### Распространенные проблемы

**Artifact store integrity failures:**
```bash
# Проверьте что SHA256 хэши совпадают
pytest tests/core_phase0/test_artifact_store.py::test_put_get_roundtrip_and_verify -v
```

**Canonical JSON serialization issues:**
```bash
# Проверьте запрет на float значения
pytest tests/core_phase0/test_canon_json.py::test_float_forbidden -v
```

**Registry bundle construction failures:**
```bash
# Проверьте persistence всех компонентов
pytest tests/core_phase0/test_registry_bundle.py -v
```

**Environment manifest capture issues:**
```bash
# Проверьте capture без приватных данных
pytest tests/core_phase0/test_environment_manifest.py::TestCaptureEnvironment::test_capture_no_private_data -v
# Проверьте fingerprint determinism
pytest tests/core_phase0/test_environment_manifest.py::TestEnvironmentManifest::test_manifest_fingerprint_deterministic -v
```

**Run context path resolution issues:**
```bash
# Проверьте относительные пути
pytest tests/core_phase0/test_run_context.py -v
```