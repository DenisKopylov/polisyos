# Migrations: Система версионирования артефактов

> **Последнее обновление:** 26 января 2026 г.

Модуль `polisyos.common.migrations` предоставляет детерминированную систему версионирования артефактов Policy Engine. Система обеспечивает безопасные преобразования данных между версиями схем с обнаружением циклов миграций.

## Архитектурная роль

Система миграций является фундаментальным компонентом инфраструктуры Policy Engine, обеспечивая:

- **Версионирование схем** - отслеживание изменений в структурах данных
- **Обратную совместимость** - автоматическая миграция устаревших данных
- **Безопасность данных** - детерминированные преобразования без потери информации
- **Расширяемость** - простое добавление новых типов артефактов и миграций

## Структура модуля

```
migrations/
├── __init__.py         # Публичный API миграций
├── base.py            # Ядро системы миграций
├── manifest.py        # Миграции Dataset Manifest
├── policy_ir.py       # Миграции Policy IR
└── README.md          # Эта документация
```

## Архитектурные принципы

### Детерминированные преобразования

Все миграции должны быть:
- **Детерминированными** - один и тот же вход всегда дает один результат
- **Безопасными** - не терять данные при преобразованиях
- **Обратимыми** - поддерживать откат к предыдущим версиям

### Обнаружение циклов

Система предотвращает бесконечные циклы миграций через:
- Отслеживание посещенных версий (`visited` set)
- Проверку наличия пути миграции между версиями
- Исключения при обнаружении циклов

## Компоненты системы

### `base.py` - Ядро системы миграций

#### Глобальный реестр миграций

```python
_MIGRATIONS: Dict[str, Dict[str, Tuple[str, MigrationFn]]] = {}
```

Структура реестра:
- **Первый уровень**: тип артефакта (`"dataset_manifest"`, `"policy_ir"`)
- **Второй уровень**: версия источника → (версия назначения, функция миграции)

#### Декоратор регистрации миграций

```python
def register_migration(artifact: str, from_version: str, to_version: str):
    def decorator(fn: MigrationFn) -> MigrationFn:
        _MIGRATIONS.setdefault(artifact, {})[from_version] = (to_version, fn)
        return fn
    return decorator
```

#### Основная функция миграции

```python
def migrate_artifact(data: dict, artifact: str, target_version: str) -> dict:
    # 1. Проверка наличия schema_version
    # 2. Поиск пути миграции с обнаружением циклов
    # 3. Последовательное применение миграций
    # 4. Возврат преобразованных данных
```

### `manifest.py` - Миграции Dataset Manifest

#### Текущая версия

```python
MANIFEST_CURRENT_VERSION = "1.0"
```

#### Доступные миграции

```python
@register_migration("dataset_manifest", "0.9", "1.0")
def migrate_manifest_0_9_to_1_0(data: dict) -> dict:
    # Нормализация полей: datasetName → dataset_name, rawHash → raw_hash
    if "datasetName" in data and "dataset_name" not in data:
        data["dataset_name"] = data.pop("datasetName")
    if "rawHash" in data and "raw_hash" not in data:
        data["raw_hash"] = data.pop("rawHash")
    return data
```

### `policy_ir.py` - Миграции Policy IR и Trinity

#### Текущие версии

```python
POLICY_IR_CURRENT_VERSION = "2.0"
TRINITY_CURRENT_VERSION = "1.0"
```

#### Особенности версионирования

- **Policy IR v2.0** является стабильной основной версией для PolicySurfaceIR
- **Trinity v1.0** - новый формат артефактов с разделением на bundle компонентов
- **Двунаправленные миграции** между PolicySurfaceIR (v2.0) и Trinity форматом (v1.0)
- **Использование внешних функций** из `ir.migrations.trinity_migration` для сложных преобразований

#### Доступные миграции Trinity

```python
@register_migration("policy_surface_to_trinity", "2.0", "1.0")
def migrate_surface_to_trinity(data: dict) -> dict:
    # Преобразование PolicySurfaceIR → TrinityBundle
    # Использует ir.migrations.trinity_migration.split_to_bundle

@register_migration("trinity_to_policy_surface", "1.0", "2.0")
def migrate_trinity_to_surface(data: dict) -> dict:
    # Преобразование TrinityBundle → PolicySurfaceIR
    # Использует ir.migrations.trinity_migration.merge_to_surface_ir
```

## Публичный API (`__init__.py`)

```python
from polisyos.common.migrations.base import migrate_artifact, register_migration
from polisyos.common.migrations.manifest import MANIFEST_CURRENT_VERSION
from polisyos.common.migrations.policy_ir import POLICY_IR_CURRENT_VERSION, TRINITY_CURRENT_VERSION

__all__ = [
    "migrate_artifact",
    "register_migration",
    "POLICY_IR_CURRENT_VERSION",
    "TRINITY_CURRENT_VERSION",
    "MANIFEST_CURRENT_VERSION",
]
```

## Использование в проекте

### Базовое использование

```python
from polisyos.common.migrations import migrate_artifact

# Миграция Dataset Manifest
manifest_data = {"schema_version": "0.9", "datasetName": "test"}
migrated = migrate_artifact(manifest_data, "dataset_manifest", "1.0")
# Результат: {"schema_version": "1.0", "dataset_name": "test"}

# Trinity миграции - преобразование между форматами
# PolicySurfaceIR → TrinityBundle
trinity_bundle = migrate_artifact(policy_surface_data, "policy_surface_to_trinity", "1.0")

# TrinityBundle → PolicySurfaceIR
policy_surface_data = migrate_artifact(trinity_bundle, "trinity_to_policy_surface", "2.0")
```

### Регистрация новых миграций

```python
from polisyos.common.migrations import register_migration

@register_migration("my_artifact", "1.0", "2.0")
def migrate_my_artifact_1_0_to_2_0(data: dict) -> dict:
    # Логика миграции
    data["new_field"] = data.pop("old_field", None)
    return data
```

### Расширенная обертка в ir/migrations

Модуль `ir/migrations/__init__.py` предоставляет расширенную обертку:

```python
from polisyos.ir.migrations import migrate_policy_ir

# Дополнительная валидация версий Policy IR
migrated = migrate_policy_ir(data, target_version="2.0", allow_major=True)
```

## Безопасность и валидация

### Проверки при миграции

1. **Наличие `schema_version`** - обязательное поле в данных
2. **Существование пути миграции** - проверка зарегистрированных миграций
3. **Обнаружение циклов** - предотвращение бесконечных миграций
4. **Версионные ограничения** - валидация форматов версий

### Обработка ошибок

```python
try:
    migrated = migrate_artifact(data, "dataset_manifest", "1.0")
except ValueError as e:
    # Возможные ошибки:
    # - "Missing schema_version for artifact 'dataset_manifest'"
    # - "No migrator for 'dataset_manifest' from 0.8 to 1.0"
    # - "Migration loop detected for 'dataset_manifest': 1.0 -> 1.0"
    print(f"Migration failed: {e}")
```

## Архитектурные ограничения

### Запрещено в миграциях

- **Не детерминированные операции** - случайные значения, timestamps
- **Потеря данных** - удаление полей без сохранения
- **Зависимости от внешних систем** - только преобразования данных
- **Большие объемы данных** - миграции должны быть легковесными

### Требования к миграциям

- **Функции должны быть чистыми** - только преобразование входных данных
- **Обязательна обратная совместимость** - поддержка старых версий
- **Документированные изменения** - описание того, что меняется
- **Тестируемость** - каждая миграция должна иметь тесты

## Связанные компоненты

### Использование в других модулях

- **`ir/migrations/__init__.py`** - расширенная обертка для Policy IR с дополнительной логикой версий
- **`ir/trinity.py`** - использование миграций для преобразования между PolicySurfaceIR и Trinity форматами
- **`ir/migrations/trinity_migration.py`** - вспомогательные функции `split_to_bundle` и `merge_to_surface_ir`
- **`fabric/materializer.py`** - потенциальное использование для версионирования материализованных данных
- **`core/artifacts/store.py`** - хранение артефактов с версиями

### Архитектурные связи

- **common** - базовая инфраструктура миграций
- **ir** - расширенное использование для Policy IR и Trinity артефактов с преобразованиями форматов
- **core** - хранение артефактов с поддержкой версий
- **fabric** - материализация данных с учетом версий

## Тестирование

### Unit тесты миграций

```python
def test_migrate_manifest_0_9_to_1_0():
    data = {"schema_version": "0.9", "datasetName": "test", "rawHash": "abc"}
    migrated = migrate_artifact(data, "dataset_manifest", "1.0")

    assert migrated["schema_version"] == "1.0"
    assert "dataset_name" in migrated
    assert "raw_hash" in migrated
    assert "datasetName" not in migrated
    assert "rawHash" not in migrated
```

### Интеграционные тесты

- Проверка обратной совместимости
- Тестирование цепочек миграций
- Валидация обнаружения циклов

## Контрибьютинг

### Добавление новой миграции

1. **Определить тип артефакта** и версии
2. **Создать функцию миграции** с декоратором `@register_migration`
3. **Протестировать миграцию** на реальных данных
4. **Обновить документацию** - описать изменения в README
5. **Добавить unit тест** для новой миграции

### Добавление нового типа артефакта

1. **Создать новый файл** в `migrations/` (например, `new_artifact.py`)
2. **Определить текущую версию** (`NEW_ARTIFACT_CURRENT_VERSION`)
3. **Добавить экспорт** в `__init__.py`
4. **Создать миграции** при необходимости
5. **Обновить документацию** во всех README файлах

## Проверка актуальности

Для поддержания актуальности системы миграций:

1. **Проверка версий** - регулярная проверка соответствия версий в коде
2. **Анализ использования** - поиск всех мест использования миграций в проекте
3. **Тестирование обратной совместимости** - проверка работы со старыми данными
4. **Документация изменений** - фиксация всех изменений схем в ADR