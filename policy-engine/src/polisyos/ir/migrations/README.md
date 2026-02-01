# IR Migrations: Система версионирования схем

**Migrations** - система детерминированных миграций между версиями схем Policy IR, обеспечивающая обратную совместимость и воспроизводимость артефактов.

**Обновлено**: документация актуализирована для отражения текущего состояния на 2026-02-01, включая полную реализацию Trinity миграции (trinity_migration.py) для преобразования PolicySurfaceIR в Trinity артефакты.

## Архитектурная роль

Migrations обеспечивает:

- **Версионирование схем**: Детерминированные изменения форматов данных
- **Обратная совместимость**: Автоматическая конвертация между версиями
- **Воспроизводимость**: Гарантия идентичных результатов при одинаковых входных данных
- **Безопасность**: Защита от несовместимых изменений через major/minor версионирование

## Структура модуля

```
migrations/
├── __init__.py              # API миграций для Policy IR
└── trinity_migration.py     # Миграция PolicySurfaceIR → Trinity артефактов
```

## Основные компоненты

### 1. API миграций (`__init__.py`)

#### Основные функции

```python
from polisyos.ir.migrations import (
    migrate_policy_ir,           # Миграция данных политики
    parse_version,               # Парсинг версии MAJOR.MINOR
    is_major_bump,               # Проверка major изменения
    register_migration,          # Регистрация новой миграции
    IR_CURRENT_VERSION,          # Текущая версия IR
    IR_ARTIFACT                  # Идентификатор артефакта
)
```

#### Константы

```python
IR_ARTIFACT = "policy_ir"                    # Идентификатор типа артефакта
IR_CURRENT_VERSION = POLICY_IR_CURRENT_VERSION  # Текущая версия (из common.migrations)
```

### 2. Парсинг версий

#### parse_version()

```python
def parse_version(version: str) -> tuple[int, int]:
    """
    Парсит версию формата MAJOR.MINOR в кортеж (major, minor).

    Args:
        version: Строка версии, например "2.1"

    Returns:
        Кортеж (major, minor) как integers

    Raises:
        ValueError: Если версия не соответствует формату MAJOR.MINOR
    """
```

**Примеры:**
```python
major, minor = parse_version("2.1")  # (2, 1)
major, minor = parse_version("1.0")  # (1, 0)
```

#### is_major_bump()

```python
def is_major_bump(from_version: str, to_version: str) -> bool:
    """
    Определяет, является ли изменение major (ломающим совместимость).

    Особенность: переход 0.x -> 1.x считается совместимым (стабилизация API).
    """
```

**Примеры:**
```python
is_major_bump("1.0", "1.1")  # False (minor изменение)
is_major_bump("1.0", "2.0")  # True (major изменение)
is_major_bump("0.5", "1.0")  # False (специальный случай стабилизации)
```

### 3. Миграция данных

#### migrate_policy_ir()

```python
def migrate_policy_ir(
    data: dict,
    target_version: str | None = None,
    *,
    allow_major: bool = False
) -> dict:
    """
    Миграция policy IR данных между версиями.

    Args:
        data: Словарь с данными политики (должен содержать schema_version)
        target_version: Целевая версия (по умолчанию IR_CURRENT_VERSION)
        allow_major: Разрешить major изменения (по умолчанию False)

    Returns:
        Миграированные данные с обновленной schema_version

    Raises:
        ValueError: Если версия не указана или миграция невозможна
    """
```

**Примеры использования:**

```python
# Миграция на текущую версию
migrated = migrate_policy_ir(old_policy_data)

# Миграция на конкретную версию
migrated = migrate_policy_ir(data, target_version="2.1")

# Разрешить major изменения
migrated = migrate_policy_ir(data, target_version="3.0", allow_major=True)
```

### 4. Trinity миграция (`trinity_migration.py`)

#### Миграция PolicySurfaceIR → Trinity артефактов

Система миграции для преобразования устаревшего PolicySurfaceIR в новые Trinity артефакты (ProblemFrame, PolicySpec, ModelSpec). Реализует структурное разделение с автоматическим распределением данных по артефактам:

```python
from polisyos.ir.migrations.trinity_migration import (
    migrate_surface_to_trinity, TrinityBundle,
    split_surface_ir, merge_to_surface_ir, split_to_bundle,
    _partition_labels, _compute_source_ref
)

# Основные функции миграции
surface_policy = PolicySurfaceIR(...)  # Загруженная политика v2.x

# Полная миграция в bundle
trinity_bundle = migrate_surface_to_trinity(surface_policy)
# Или split_to_bundle для альтернативного API
bundle = split_to_bundle(surface_policy)

# Разделение на отдельные артефакты
problem_frame, policy_spec, model_spec = split_surface_ir(surface_policy)

# Обратное слияние для совместимости
reconstructed = merge_to_surface_ir(problem_frame, policy_spec, model_spec)

# Получение отдельных артефактов
problem_frame = trinity_bundle.problem_frame
policy_spec = trinity_bundle.policy_spec
model_spec = trinity_bundle.model_spec

# Сохранение для дальнейшего использования
for artifact_name, artifact in trinity_bundle.as_dict().items():
    with open(f"{artifact_name}.json", 'w') as f:
        json.dump(artifact.model_dump(), f, indent=2)
```

#### Логика разделения

Миграция автоматически разделяет содержимое PolicySurfaceIR по Trinity артефактам на основе семантического анализа:

**ProblemFrame (постоянные аспекты):**
- Цели и KPI (из semantic.objectives)
- Ограничения политики (из semantic.constraints)
- Заинтересованные стороны (из advisory.entities)
- Критерии успеха (из metadata.success_criteria)

**PolicySpec (изменяемые аспекты политики):**
- Интервенции и их параметры (из semantic.interventions)
- Механизмы привязки (из semantic.mechanism_bindings)
- Метки политики (из advisory.labels с префиксом "policy:")
- Заметки по реализации (из semantic.implementation_notes)

**ModelSpec (конфигурация моделирования):**
- Ссылка на данные (из semantic.context_snapshot_ref)
- Ссылка на реестры (из semantic.registry_bundle_ref)
- Предположения модели (из metadata.assumptions)
- Метки модели (из advisory.labels с префиксом "model:")
- Настройки времени (восстанавливаются из интервенций)

#### Разделение меток и заметок

Автоматическое распределение меток по артефактам на основе префиксов:

```python
# Префиксы для распределения
PROBLEM_FRAME_PREFIXES = frozenset(["goal:", "success:", "actor:", "kpi:"])
POLICY_SPEC_PREFIXES = frozenset(["policy:", "intervention:", "mechanism:"])
MODEL_SPEC_PREFIXES = frozenset(["model:", "data:", "assumption:", "fidelity:"])

# Пример разделения
labels = [
    "goal:gdp_growth", "policy:budget_cut", "model:inflation_rate",
    "actor:government", "intervention:tax_reform", "data:official_stats",
    "assumption:rational_agents", "kpi:unemployment_reduction"
]
partitioned = _partition_labels(labels)

# Результат распределения:
# {
#   "problem_frame": ["goal:gdp_growth", "actor:government", "kpi:unemployment_reduction"],
#   "policy_spec": ["policy:budget_cut", "intervention:tax_reform"],
#   "model_spec": ["model:inflation_rate", "data:official_stats", "assumption:rational_agents"]
# }
```

**Обработка заметок:**
- Заметки с префиксом "[policy]" → PolicySpec
- Заметки с префиксом "[model]" → ModelSpec
- Остальные заметки → ProblemFrame

### 5. Регистрация миграций

#### register_migration()

```python
def register_migration(from_version: str, to_version: str):
    """
    Декоратор для регистрации функции миграции.

    Используется для добавления новых миграций в систему.
    Миграции регистрируются в общем реестре common.migrations.
    """
```

**Пример регистрации миграции:**

```python
from polisyos.ir.migrations import register_migration

@register_migration("2.0", "2.1")
def migrate_2_0_to_2_1(data: dict) -> dict:
    """Миграция с 2.0 на 2.1"""
    # Логика миграции...
    data["new_field"] = "default_value"
    return data
```

## Поддерживаемые версии

### Текущая версия: Trinity (1.0) + PolicySurfaceIR (2.x)

- **Trinity 1.0**: ProblemFrame, PolicySpec, ModelSpec (новая архитектура)
- **PolicySurfaceIR 2.x**: Унаследованный интерфейс с миграцией в Trinity
- **2.0**: PolicySurfaceIR (текущая стабильная версия)
- **2.x**: Minor изменения в рамках 2.x - обратная совместимость гарантирована

### Устаревшие версии

- **1.x**: PolicyIR (унаследованный формат, конвертация через loaders)
- **0.x**: Устаревшие форматы (требуют ручной миграции)

### Особенности версионирования

1. **Major версии (X.0)**: Ломающие изменения, требуют `allow_major=True`
2. **Minor версии (x.Y)**: Совместимые изменения, применяются автоматически
3. **Специальный случай**: `0.x -> 1.x` считается minor (стабилизация API)

## Архитектура миграций

### Общая система миграций

IR migrations использует общую систему миграций из `common.migrations`:

```
common.migrations.base
├── _MIGRATIONS: Dict[str, Dict[str, Tuple[str, MigrationFn]]]
├── register_migration()
└── migrate_artifact()
```

### Регистр миграций

```python
_MIGRATIONS = {
    "policy_ir": {
        "1.0": ("2.0", migrate_1_0_to_2_0),
        "2.0": ("2.1", migrate_2_0_to_2_1),
        # ...
    }
}
```

### Алгоритм миграции

1. **Проверка версии**: В данных должен быть ключ `schema_version`
2. **Поиск пути**: Поиск последовательности миграций до целевой версии
3. **Применение**: Последовательное применение функций миграции
4. **Обновление**: Обновление `schema_version` после каждой миграции
5. **Валидация**: Проверка отсутствия циклов в графе миграций

### Trinity миграция

**Миграция PolicySurfaceIR → Trinity** является специальным случаем, так как представляет собой структурное разделение, а не последовательную эволюцию. Использует детерминированные алгоритмы для обеспечения воспроизводимости:

1. **Семантический анализ**: Автоматическое определение принадлежности компонентов к артефактам
2. **Разделение по ответственности**: Распределение данных по трем артефактам Trinity
3. **Генерация ссылок**: Создание детерминированных ссылок через SHA256 хеши
4. **Создание связей**: Установление связей между артефактами через shared metadata
5. **Валидация целостности**: Проверка полноты и корректности распределения данных
6. **Обратная совместимость**: Возможность обратного слияния для совместимости с legacy кодом

## Использование в коде

### Базовая миграция

```python
from polisyos.ir.migrations import migrate_policy_ir

# Данные старой политики
old_policy = {
    "schema_version": "1.0",
    "project_name": "Legacy Policy",
    "entities": [...],
    "interventions": [...]
}

# Автоматическая миграция на текущую версию
current_policy = migrate_policy_ir(old_policy)
print(f"Миграция: {old_policy['schema_version']} -> {current_policy['schema_version']}")
```

### Работа с версиями

```python
from polisyos.ir.migrations import parse_version, is_major_bump, IR_CURRENT_VERSION

# Парсинг версии
major, minor = parse_version("2.1")
print(f"Major: {major}, Minor: {minor}")

# Проверка совместимости
if is_major_bump("2.0", "3.0"):
    print("Major изменение - требуется ручное подтверждение")
else:
    print("Minor изменение - безопасно мигрировать автоматически")

# Текущая версия
print(f"Текущая версия IR: {IR_CURRENT_VERSION}")
```

### Trinity миграция

```python
from polisyos.ir.migrations.trinity_migration import migrate_surface_to_trinity
from polisyos.ir.surface import PolicySurfaceIR

# Загрузка существующей политики
surface_policy = PolicySurfaceIR.model_validate(json_data)

# Миграция в Trinity артефакты
trinity_bundle = migrate_surface_to_trinity(surface_policy)

# Использование отдельных артефактов
problem_frame = trinity_bundle.problem_frame
policy_spec = trinity_bundle.policy_spec
model_spec = trinity_bundle.model_spec
```

### Интеграция с loaders

```python
from polisyos.ir.loaders import load_policy

# load_policy автоматически использует миграции для конвертации версий
policy = load_policy(legacy_data)  # Автоматически конвертирует 1.x -> 2.x

# Для Trinity миграции используйте отдельную функцию
from polisyos.ir.migrations.trinity_migration import migrate_surface_to_trinity
trinity_bundle = migrate_surface_to_trinity(policy)
```

## Безопасность и ограничения

### Защита от ошибок

- **Обязательная schema_version**: Все данные должны содержать версию
- **Валидация версий**: Строгие паттерны для номеров версий
- **Защита major изменений**: Требуется явное разрешение для major миграций
- **Предотвращение циклов**: Детекция циклических зависимостей в миграциях

### Ограничения

- **Только 2.x**: Поддерживаются только версии 2.x (PolicySurfaceIR)
- **Последовательные миграции**: Миграции должны применяться последовательно
- **Immutable данные**: Функции миграции не должны модифицировать входные данные

## Тестирование

### Тестовые сценарии

```bash
# Тесты миграций
pytest tests/unit/test_ir_migrations.py

# Интеграционные тесты с loaders
pytest tests/integration/test_loaders_migration.py
```

**Ключевые тесты:**
- Миграция между всеми поддерживаемыми версиями
- Валидация результатов миграции
- Обработка ошибок (отсутствующая версия, неизвестная миграция)
- Циклические зависимости в миграциях
- Совместимость с load_policy()
- **Trinity миграция**: Разделение и слияние артефактов, распределение меток, детерминированные ссылки
- **Валидация целостности**: Проверка полноты данных при разделении

## Связанные компоненты

### Интеграция с другими модулями

- **Loaders**: Автоматическая миграция при загрузке политик с поддержкой Trinity
- **Common**: Использование общей инфраструктуры миграций и async_tools
- **Surface**: Миграция PolicySurfaceIR между версиями с обратной совместимостью
- **Trinity**: Основное использование - преобразование в Trinity артефакты для новой архитектуры
- **Validation**: Проверка корректности после миграции и разделения данных
- **Scientist**: Генерация и использование Trinity артефактов с миграцией из legacy форматов
- **Linker**: Валидация Trinity артефактов после миграции
- **Foundry**: Компиляция PolicySpec из Trinity артефактов

### Архитектурные контракты

```
Legacy Data → Loaders → Migrations → PolicySurfaceIR v2.x → Trinity Migration → Trinity Bundle
         ↓              ↑                              ↓                    ↓
   Common Migrations    Common Migrations Registry      Scientist → Linker → Foundry → Runtime
         ↓
   async_tools (для асинхронных операций)
```

---

**См. также:**
- [IR Loaders](../loaders.py) - автоматическая миграция при загрузке
- [Common Migrations](../../../../common/migrations/) - общая инфраструктура
- [PolicySurfaceIR](../surface.py) - целевой формат миграций