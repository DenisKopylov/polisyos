# IR Linker: Валидация и линковка политик

**Linker** - система валидации и линковки политик Policy Engine. Обеспечивает корректность Trinity артефактов (ProblemFrame, PolicySpec, ModelSpec) относительно kernel-реестров, проверяя все ссылки на механизмы, слоты, метрики, ограничения и другие компоненты.

**Обновлено**: документация актуализирована для отражения текущего состояния на 2026-02-05, включая канонический `link_trinity()` для Trinity артефактов, расширенную систему кодов ошибок LinkIssueCode, и типизированные отчеты LinkReport.

## Архитектурная роль

Linker является критическим компонентом валидации политик в компиляторной трубе Policy Engine:

```
Trinity Bundle → Linker Validation → LinkedTrinityBundle
                    ↓
            Registry Bundle (Kernel)
                    ↓
            LinkReport (issues/codes)
```

### Положение в системе

- **Входящие зависимости**: TrinityBundle, RegistryBundle (из kernel)
- **Исходящие зависимости**: Foundry (использует LinkedTrinityBundle)
- **Принцип**: "Валидация перед компиляцией" - линкер гарантирует, что политики могут быть safely скомпилированы Foundry

## Структура модуля

```
linker/
├── __init__.py          # API линкера и экспорт основных типов
├── link_trinity.py      # Канонический линкер Trinity артефактов
├── reports.py           # Типы отчетов линковки и коды ошибок
└── types.py             # Вспомогательные типы и утилиты
```

## Основные компоненты

### 1. Канонический линкер (`link_trinity.py`)

#### link_trinity() - основная функция линковки

```python
from polisyos.ir.linker import link_trinity
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.registry_fragments import RegistryBundle

def link_trinity(
    bundle: TrinityBundle,
    registries: RegistryBundle,
    *,
    strict: bool = True
) -> tuple[LinkedTrinityBundle | None, LinkReport]:
    """
    Валидирует TrinityBundle относительно kernel-реестров.

    Args:
        bundle: Trinity артефакты для валидации
        registries: Kernel реестры для линковки
        strict: Если True, возвращает None при ошибках

    Returns:
        (LinkedTrinityBundle, LinkReport) при успехе
        (None, LinkReport) при ошибках (если strict=True)
    """
```

**Процесс линковки:**
1. **Валидация ProblemFrame**: Проверка ограничений и KPI относительно реестров
2. **Линковка PolicySpec**: Валидация интервенций, параметров и селекторов
3. **Проверка ModelSpec**: Валидация ссылок на данные и реестры
4. **Создание LinkedTrinityBundle**: Результат успешной линковки с привязанными реестрами

#### LinkedTrinityBundle - результат линковки

```python
class LinkedTrinityBundle(KernelModel):
    """Результат успешной линковки Trinity артефактов."""

    schema_version: str
    problem_frame: ProblemFrame
    policy_spec: PolicySpec
    model_spec: ModelSpec
    registries: RegistryBundle  # Привязанные реестры
    bindings: TrinityBindings   # Вычисленные связи
```

#### TrinityBindings - вычисленные связи

```python
class TrinityBindings(KernelModel):
    """Вычисленные связи между компонентами Trinity."""

    interventions: dict[str, LinkedIntervention]
    constraints: dict[str, LinkedConstraint]
    metrics: dict[str, LinkedMetric]
    selectors: dict[str, LinkedSelector]
```

### 2. Отчеты линковки (`reports.py`)

#### LinkReport - структурированный отчет

```python
class LinkReport(KernelModel):
    """Отчет о результатах линковки."""

    ok: bool                    # Успех линковки
    issues: list[LinkIssue]     # Список проблем
    summary: str               # Краткое описание
    schema_version: str
```

#### LinkIssue - отдельная проблема

```python
class LinkIssue(KernelModel):
    """Отдельная проблема линковки."""

    code: LinkIssueCode         # Стабильный код ошибки
    severity: LinkSeverity      # Критичность (ERROR/WARNING/INFO)
    path: tuple[str, ...]       # Путь к проблемному элементу
    ids: tuple[str, ...]        # Связанные ID компонентов
    message: str               # Человекочитаемое описание
    details: dict[str, Any]     # Дополнительные детали
```

#### LinkIssueCode - стабильные коды ошибок

```python
class LinkIssueCode(str, Enum):
    # Механизмы и параметры
    UNKNOWN_MECHANISM = "unknown_mechanism"
    MISSING_PARAM = "missing_param"
    UNKNOWN_PARAM = "unknown_param"
    PARAM_TYPE = "param_type"
    PARAM_ENUM = "param_enum"
    PARAM_RANGE = "param_range"

    # Слоты и состояния
    MISSING_SLOT = "missing_slot"
    UNKNOWN_SLOT = "unknown_slot"

    # Единицы измерения
    UNKNOWN_UNIT = "unknown_unit"
    UNIT_MISMATCH = "unit_mismatch"

    # Селекторы
    UNKNOWN_SELECTOR_FIELD = "unknown_selector_field"
    SELECTOR_SCOPE_MISMATCH = "selector_scope_mismatch"

    # Правила слияния
    UNKNOWN_MERGE_RULE = "unknown_merge_rule"
    MERGE_RULE_CONFLICT = "merge_rule_conflict"

    # Ограничения
    UNKNOWN_CONSTRAINT = "unknown_constraint"
    INCOMPATIBLE_CONSTRAINT = "incompatible_constraint"

    # Нормы и compliance
    UNKNOWN_ACTOR = "unknown_actor"
    UNKNOWN_JURISDICTION = "unknown_jurisdiction"

    # Системные ошибки
    MISSING_REGISTRY = "missing_registry"
```

### 3. Вспомогательные типы (`types.py`)

#### Валидация ссылок на нормы

```python
def validate_norm_applicability_refs(
    applicability: NormApplicability,
    registries: RegistryBundle
) -> list[LinkIssue]:
    """Валидирует ссылки в применимости норм."""
```

## Использование в коде

### Базовая линковка Trinity

```python
from polisyos.ir.linker import link_trinity
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.registry_fragments import RegistryBundle
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
    # ... другие реестры
)

# Создание RegistryBundle
registries = RegistryBundle(
    mechanisms=DEFAULT_MECHANISM_REGISTRY,
    slots=DEFAULT_SLOT_REGISTRY,
    units=DEFAULT_UNITS_REGISTRY,
    # ... остальные реестры
)

# Линковка Trinity Bundle
trinity_bundle = TrinityBundle(...)  # Ваши Trinity артефакты
linked_bundle, report = link_trinity(trinity_bundle, registries)

if not report.ok:
    print(f"Линковка не удалась: {report.summary}")
    for issue in report.issues:
        print(f"  {issue.severity}: {issue.code} - {issue.message}")
        print(f"    Path: {'.'.join(issue.path)}")
else:
    print("Линковка успешна!")
    # Использование linked_bundle в Foundry
    foundry.compile_policy(linked_bundle)
```

### Обработка ошибок линковки

```python
linked, report = link_trinity(bundle, registries, strict=False)

# Анализ проблем по типам
errors = [i for i in report.issues if i.severity == "error"]
warnings = [i for i in report.issues if i.severity == "warning"]

# Группировка по кодам ошибок
from collections import Counter
error_codes = Counter(i.code for i in errors)

print(f"Ошибки: {dict(error_codes)}")
print(f"Предупреждения: {len(warnings)}")

# Детальный анализ конкретного типа ошибок
mechanism_errors = [i for i in errors if i.code == "unknown_mechanism"]
for err in mechanism_errors:
    print(f"Неизвестный механизм: {err.ids[0]} в {'.'.join(err.path)}")
```

### Расширенная конфигурация линковки

```python
# Нестрогая линковка (возвращает результат даже при ошибках)
linked, report = link_trinity(bundle, registries, strict=False)

# Проверка только определенных аспектов
if linked:
    # Проверка корректности вычисленных связей
    for intervention_id, linked_int in linked.bindings.interventions.items():
        print(f"Интервенция {intervention_id}:")
        print(f"  Читает слоты: {linked_int.reads_slots}")
        print(f"  Пишем слоты: {linked_int.writes_slots}")
        print(f"  Активна с {linked_int.schedule_start} по {linked_int.schedule_end}")
```

## Архитектурные принципы

### Design Patterns

1. **Validation Pattern**: Разделение на валидацию (link_trinity) и отчеты (LinkReport)
2. **Stable Error Codes**: Стабильные коды ошибок для автоматизированной обработки
3. **Immutable Results**: Результаты линковки неизменяемы после создания
4. **Dependency Injection**: Реестры передаются явно для тестируемости

### Качество и надежность

- **Type Safety**: Полная типизация через Pydantic модели
- **Immutable Models**: Все модели неизменяемы (`frozen=True`)
- **Comprehensive Validation**: Проверка всех ссылок и зависимостей
- **Detailed Reporting**: Структурированные отчеты с полным контекстом ошибок

### Производительность

- **Lazy Evaluation**: Валидация останавливается при первой критической ошибке в strict режиме
- **Efficient Lookups**: Реестры оптимизированы для быстрого поиска
- **Memory Efficient**: Минимальный overhead на структурированные отчеты

## Расширяемость

### Добавление новых проверок линковки

```python
def validate_custom_constraint(
    constraint: ConstraintSpec,
    registries: RegistryBundle
) -> list[LinkIssue]:
    """Пример кастомной валидации ограничений."""
    issues = []

    # Ваша логика валидации
    if constraint.constraint_type == "custom":
        if not hasattr(registries, 'custom_registry'):
            issues.append(LinkIssue(
                code="missing_custom_registry",
                severity="error",
                path=("constraints", constraint.constraint_id),
                message="Custom registry required for custom constraints"
            ))

    return issues
```

### Добавление новых кодов ошибок

```python
class LinkIssueCode(str, Enum):
    # Существующие коды...
    CUSTOM_VALIDATION_ERROR = "custom_validation_error"
```

## Тестирование

### Тестовые сценарии

```bash
# Unit-тесты линкера
pytest tests/unit/test_ir_linker_*.py

# Contract-тесты валидации
pytest tests/contract/test_ir_linker.py

# Интеграционные тесты с Foundry
pytest tests/integration/test_linker_foundry.py
```

**Ключевые тестовые сценарии:**
- Валидация корректных Trinity Bundle
- Обработка всех типов ошибок LinkIssueCode
- Регрессионные тесты на edge cases
- Производительность при больших наборах данных
- Совместимость с изменениями kernel-реестров

## Связанные компоненты

### Зависимости

**Входящие:**
- **Trinity**: ProblemFrame, PolicySpec, ModelSpec для валидации
- **Kernel**: Все реестры для проверки ссылок
- **Registry Fragments**: RegistryBundle как контейнер реестров

**Исходящие:**
- **Foundry**: Использует LinkedTrinityBundle для компиляции
- **Scientist**: Получает LinkReport для обратной связи
- **Runtime**: Сохраняет результаты линковки для аудита

### Архитектурные контракты

```
Scientist → Trinity Bundle → Linker → LinkedTrinityBundle → Foundry → Simulation
   ↑                           ↓
   LinkReport                 Registry Bundle
                              (Kernel Registries)
```

**Линковка в компиляторной трубе:**
```
Input:  TrinityBundle + RegistryBundle
Process: Validation + Binding Resolution
Output: LinkedTrinityBundle + LinkReport
Next:   Foundry Compilation
```

---

**См. также:**
- [IR README](../README.md) - общая архитектура IR
- [Trinity артефакты](../trinity/) - входные данные для линковки
- [Kernel реестры](../kernel/) - реестры для валидации
- [Foundry](../../foundry/) - использование результатов линковки