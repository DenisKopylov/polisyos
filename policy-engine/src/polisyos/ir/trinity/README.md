# IR Trinity: Канонические контракты политик

**Trinity** - канонические контракты Policy Engine, реализующие Trinity архитектуру разделения политики на три независимых артефакта: ProblemFrame ("Why"), PolicySpec ("What") и ModelSpec ("How").

**Обновлено**: документация актуализирована для отражения текущего состояния на 2026-02-05, включая полную реализацию TrinityBundle как контейнера артефактов, загрузчики с поддержкой JSON/YAML форматов, и интеграцию с линкером и Foundry.

## Архитектурная роль

Trinity представляет фундаментальный сдвиг от монолитных политик к композиционным артефактам:

```
Legacy: PolicySurfaceIR (monolithic)
Trinity: ProblemFrame + PolicySpec + ModelSpec (composable)
```

### Trinity архитектура

**Trinity** разделяет политику на три независимых измерения:

- **ProblemFrame**: Постоянные аспекты проблемы (цели, ограничения, stakeholders)
- **PolicySpec**: Изменяемые аспекты политики (интервенции, параметры)
- **ModelSpec**: Конфигурация моделирования (данные, предположения, агенты)

### Положение в системе

- **Входящие зависимости**: НИКАКИХ (чистый контракт)
- **Исходящие зависимости**: Все компоненты Policy Engine (Scientist, Linker, Foundry, Runtime)
- **Принцип**: "Trinity → все" (фундаментальный контракт системы)

## Структура модуля

```
trinity/
├── __init__.py          # TrinityBundle и базовые типы
└── loaders.py           # Загрузчики Trinity артефактов
```

## Основные компоненты

### 1. TrinityBundle (`__init__.py`)

#### TrinityBundle - контейнер артефактов

```python
from polisyos.ir.trinity import TrinityBundle, TRINITY_BUNDLE_SCHEMA_VERSION

class TrinityBundle(KernelModel):
    """Bundle containing the three canonical Trinity artifacts."""

    schema_version: str = Field(TRINITY_BUNDLE_SCHEMA_VERSION, pattern=SCHEMA_VERSION_PATTERN)
    problem_frame: ProblemFrame
    policy_spec: PolicySpec
    model_spec: ModelSpec
```

**Ключевые особенности:**
- **Immutable**: Все артефакты неизменяемы после создания
- **Versioned**: Версионирование схемы с обратной совместимостью
- **Validated**: Автоматическая валидация через Pydantic
- **Serializable**: Поддержка JSON/YAML сериализации

#### Использование TrinityBundle

```python
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.problem_frame import ProblemFrame
from polisyos.ir.policy_spec import PolicySpec
from polisyos.ir.model_spec import ModelSpec

# Создание полного Trinity Bundle
bundle = TrinityBundle(
    problem_frame=problem_frame,
    policy_spec=policy_spec,
    model_spec=model_spec,
)

# Сериализация для хранения/передачи
import json
with open('policy_bundle.json', 'w') as f:
    json.dump(bundle.model_dump(), f, indent=2, ensure_ascii=False)

# Доступ к отдельным артефактам
pf = bundle.problem_frame
ps = bundle.policy_spec
ms = bundle.model_spec
```

### 2. Загрузчики (`loaders.py`)

#### Универсальная загрузка Trinity

```python
from polisyos.ir.trinity.loaders import load_trinity_bundle, TrinityLoadError

def load_trinity_bundle(
    payload: str | Mapping[str, Any],
    *,
    fmt: str = "auto"
) -> tuple[TrinityBundle, list[str]]:
    """
    Загружает TrinityBundle из различных форматов.

    Args:
        payload: JSON/YAML строка или словарь
        fmt: Формат ('json', 'yaml', 'auto')

    Returns:
        (TrinityBundle, warnings)

    Raises:
        TrinityLoadError: При ошибках загрузки
    """
```

**Поддерживаемые форматы:**
- **JSON**: Стандартный JSON с полной валидацией
- **YAML**: YAML с безопасной загрузкой
- **Auto**: Автоматическое распознавание формата

#### Примеры использования

```python
# Загрузка из JSON файла
with open('policy_bundle.json', 'r') as f:
    bundle, warnings = load_trinity_bundle(f.read(), fmt='json')

# Загрузка из YAML строки
yaml_content = """
schema_version: "1.0"
problem_frame:
  schema_version: "1.0"
  domain: fiscal
  objectives: [...]
policy_spec: [...]
model_spec: [...]
"""

bundle, warnings = load_trinity_bundle(yaml_content, fmt='yaml')

# Автоматическое распознавание
bundle, warnings = load_trinity_bundle(content)  # fmt='auto'

# Обработка предупреждений
for warning in warnings:
    print(f"Warning: {warning}")
```

## Интеграция с другими компонентами

### С линкером

```python
from polisyos.ir.linker import link_trinity
from polisyos.ir.registry_fragments import RegistryBundle

# Линковка Trinity Bundle
linked_bundle, report = link_trinity(bundle, registries)

if report.ok:
    # Передача в Foundry для компиляции
    foundry.compile_policy(linked_bundle)
```

### С Foundry

```python
from polisyos.foundry import compile_policy

# Компиляция в исполняемые механизмы
compiled_policy = compile_policy(linked_bundle)
```

### С Runtime

```python
from polisyos.runtime import store_artifact

# Сохранение для аудита и воспроизводимости
artifact_id = store_artifact(bundle, "trinity_bundle")
```

## Архитектурные принципы

### Design Patterns

1. **Composition over Inheritance**: Trinity артефакты компонуются, а не наследуются
2. **Separation of Concerns**: Каждое измерение отвечает за отдельный аспект
3. **Immutable Contracts**: Все контракты неизменяемы после создания
4. **Versioned Schemas**: Версионирование с гарантией совместимости

### Качество и надежность

- **Type Safety**: Полная типизация через Pydantic
- **Schema Validation**: Строгая валидация всех полей
- **Immutable Models**: Защита от случайных изменений
- **Comprehensive Testing**: Полное покрытие edge cases

### Производительность

- **Efficient Serialization**: Оптимизированная JSON/YAML сериализация
- **Lazy Loading**: Загрузка только при необходимости
- **Memory Efficient**: Минимальный overhead на метаданные

## Расширяемость

### Добавление новых форматов загрузки

```python
def load_trinity_bundle_custom(payload: str) -> tuple[TrinityBundle, list[str]]:
    """Пример кастомного загрузчика."""
    # Ваша логика парсинга
    data = custom_parse(payload)

    # Создание TrinityBundle
    bundle = TrinityBundle(**data)
    return bundle, []
```

### Расширение TrinityBundle

```python
class ExtendedTrinityBundle(TrinityBundle):
    """Пример расширения с дополнительными полями."""

    custom_metadata: dict[str, Any] = Field(default_factory=dict)
    validation_reports: list[ValidationReport] = Field(default_factory=list)
```

## Тестирование

### Тестовые сценарии

```bash
# Unit-тесты Trinity
pytest tests/unit/test_ir_trinity_*.py

# Contract-тесты загрузчиков
pytest tests/contract/test_ir_trinity_loaders.py

# Интеграционные тесты
pytest tests/integration/test_trinity_linker.py
pytest tests/integration/test_trinity_foundry.py
```

**Ключевые тестовые сценарии:**
- Загрузка из всех поддерживаемых форматов
- Валидация корректных/некорректных данных
- Сериализация/десериализация без потерь
- Интеграция с линкером и Foundry
- Регрессионные тесты на изменения схем

## Миграция с Legacy

### Из PolicySurfaceIR

```python
from polisyos.ir.legacy.migrations.surface_to_trinity import migrate_surface_ir_to_trinity

# Миграция legacy политики в Trinity
surface_policy = PolicySurfaceIR(...)  # Из loaders.load_policy()
bundle, report = migrate_surface_ir_to_trinity(surface_policy)

if report.ok:
    print("Миграция успешна!")
    # Теперь bundle можно использовать в новой архитектуре
else:
    print(f"Проблемы миграции: {report.issues}")
```

### Обратная совместимость

```python
from polisyos.ir.legacy.migrations.surface_to_trinity import migrate_trinity_to_surface_ir

# Обратная миграция для совместимости
surface, report = migrate_trinity_to_surface_ir(bundle)
# surface можно использовать в legacy коде
```

## Связанные компоненты

### Зависимости

**Входящие:**
- **ProblemFrame**: Определение проблемы
- **PolicySpec**: Спецификация политики
- **ModelSpec**: Конфигурация модели

**Исходящие:**
- **Linker**: Валидация Trinity Bundle
- **Foundry**: Компиляция в исполняемые механизмы
- **Runtime**: Хранение артефактов
- **Scientist**: Генерация Trinity артефактов

### Архитектурные контракты

```
Scientist → Trinity Bundle → Linker → LinkedTrinityBundle → Foundry → Simulation
   ↑                           ↓
   Policy Generation         Registry Validation
```

**Trinity в компиляторной трубе:**
```
Input:  ProblemFrame + PolicySpec + ModelSpec
Process: Composition → Validation → Compilation
Output: Simulation Results
```

---

**См. также:**
- [IR README](../README.md) - общая архитектура IR
- [ProblemFrame](../problem_frame.py) - определение проблемы
- [PolicySpec](../policy_spec.py) - спецификация политики
- [ModelSpec](../model_spec.py) - конфигурация модели
- [Linker](../linker/) - валидация Trinity артефактов
- [Foundry](../../foundry/) - компиляция политик