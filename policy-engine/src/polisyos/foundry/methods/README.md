# Methods Module (Система методов Foundry)

Модуль `methods` предоставляет декларативную систему для определения, композиции и исполнения экономических методов в Foundry. Модуль реализует type-safe протоколы для создания переиспользуемых компонентов симуляции с автоматической валидацией, версионированием и linking'ом.

## Архитектура

### Core Components (Основные компоненты)

- **`base.py`** - Базовые типы, протоколы и декораторы методов
- **`registry.py`** - Реестр методов с версионированием
- **`discovery.py`** - Автообнаружение и загрузка методов
- **`linker.py`** - Связывание слотов между методами
- **`composer.py`** - Композиция цепочек методов
- **`compiler.py`** - Компиляция методов в исполняемые формы
- **`specialization.py`** - Специализация методов для конкретных форм данных
- **`artifacts.py`** - Artifact система для методов
- **`types/`** - Система типов и проверки совместимости
- **`testing/`** - Фреймворк тестирования методов

### Protocol Hierarchy (Иерархия протоколов)

```
FoundryMethod (Protocol)
├── MethodSignature (типизация)
├── MethodMetadata (метаданные)
├── SlotSpec (спецификация слотов)
├── ParameterSpec (параметры)
└── pure_step (чистая функция исполнения)
```

## Основные концепции

### FoundryMethod Protocol (Протокол метода Foundry)

```python
from polisyos.foundry.methods.base import FoundryMethod

class EconomicMechanism(FoundryMethod):
    """Экономический механизм с полным протоколом Foundry."""

    @property
    def signature(self) -> MethodSignature:
        """Сигнатура метода для type checking."""
        return MethodSignature(...)

    @property
    def metadata(self) -> MethodMetadata:
        """Метаданные метода."""
        return MethodMetadata(...)

    def pure_step(
        self,
        state_arrays: dict[str, np.ndarray],
        static_params: dict[str, Any],
        rng_key: np.ndarray,
    ) -> dict[str, np.ndarray]:
        """Чистая функция одного шага симуляции."""
        # Реализация логики
        return updated_arrays
```

### MethodSignature (Сигнатура метода)

```python
@dataclass(frozen=True)
class MethodSignature:
    """Полная сигнатура метода для type checking и linking."""

    name: str                           # Имя метода
    namespace: str                      # Пространство имён
    version: str                        # Версия (SemVer)
    description: str                    # Описание

    # Слоты ввода/вывода
    input_slots: Mapping[str, SlotSpec]     # Читаемые слоты
    output_slots: Mapping[str, SlotSpec]    # Записываемые слоты

    # Параметры
    static_params: Mapping[str, ParameterSpec]  # Статические параметры
    dynamic_params: Mapping[str, ParameterSpec] # Динамические параметры

    # Метаданные
    fidelity: FidelityLevel             # Уровень точности
    complexity: ComplexityClass         # Сложность алгоритма
    units: Mapping[str, Unit]           # Единицы измерения
```

### SlotSpec (Спецификация слота)

```python
@dataclass(frozen=True)
class SlotSpec:
    """Спецификация слота данных."""

    slot_type: SlotType                 # Тип слота (SCALAR/VECTOR/MATRIX/TENSOR)
    dtype: np.dtype                     # Тип данных NumPy
    shape: tuple[int, ...]              # Форма массива
    unit: Unit                          # Единица измерения
    description: str                    # Описание

    # Валидация
    constraints: list[Callable]         # Функции валидации
    range: tuple[float, float] | None   # Диапазон значений
```

### ParameterSpec (Спецификация параметра)

```python
@dataclass(frozen=True)
class ParameterSpec:
    """Спецификация параметра метода."""

    param_type: type                   # Python тип
    default: Any                       # Значение по умолчанию
    description: str                   # Описание
    constraints: list[Callable]        # Валидация
    unit: Unit | None                  # Единица измерения
```

### Method Decorator (Декоратор метода)

```python
from polisyos.foundry.methods import foundry_method

@foundry_method(
    name="income_tax",
    namespace="economy.fiscal",
    version="1.0.0",
    description="Подоходный налог на агентов"
)
class IncomeTaxMechanism:
    """Механизм подоходного налога."""

    def __init__(self, tax_rate: float = 0.2):
        self.tax_rate = tax_rate

    @property
    def signature(self) -> MethodSignature:
        return MethodSignature(
            name="income_tax",
            namespace="economy.fiscal",
            version="1.0.0",
            description="Подоходный налог",
            input_slots={
                "income": SlotSpec(
                    slot_type=SlotType.VECTOR,
                    dtype=np.float32,
                    shape=(None,),  # n_agents
                    unit=Unit.CURRENCY,
                    description="Доходы агентов"
                )
            },
            output_slots={
                "tax_paid": SlotSpec(
                    slot_type=SlotType.VECTOR,
                    dtype=np.float32,
                    shape=(None,),
                    unit=Unit.CURRENCY,
                    description="Уплаченный налог"
                ),
                "net_income": SlotSpec(
                    slot_type=SlotType.VECTOR,
                    dtype=np.float32,
                    shape=(None,),
                    unit=Unit.CURRENCY,
                    description="Доход после налога"
                )
            },
            static_params={
                "tax_rate": ParameterSpec(
                    param_type=float,
                    default=0.2,
                    constraints=[lambda x: 0 <= x <= 1],
                    unit=Unit.RATIO,
                    description="Ставка налога"
                )
            },
            fidelity=FidelityLevel.HIGH,
            complexity=ComplexityClass.O_N,
        )

    def pure_step(self, state_arrays, static_params, rng_key):
        income = state_arrays["income"]
        tax_rate = static_params["tax_rate"]

        tax_paid = income * tax_rate
        net_income = income - tax_paid

        return {
            "tax_paid": tax_paid,
            "net_income": net_income,
        }
```

## Registry System (Система реестра)

### MethodRegistry (Реестр методов)

```python
from polisyos.foundry.methods import get_registry, MethodRegistry

registry = get_registry()

# Регистрация метода
registry.register(tax_mechanism)

# Поиск метода
method = registry.get("economy.fiscal.income_tax@1.0.0")

# Поиск совместимых версий
compatible = registry.find_compatible("economy.fiscal.income_tax", "^1.0.0")
```

### Version Resolution (Разрешение версий)

```python
from polisyos.foundry.methods.resolution import resolve_version, VersionConstraint

# Разрешение версии по constraint
version = resolve_version(
    available_versions=["1.0.0", "1.1.0", "2.0.0"],
    constraint=VersionConstraint("^1.0.0")  # >=1.0.0, <2.0.0
)
# Результат: "1.1.0"
```

## Discovery System (Система обнаружения)

### Method Discovery (Обнаружение методов)

```python
from polisyos.foundry.methods.discovery import bootstrap_registry

# Автоматическая загрузка всех методов
report = bootstrap_registry()

if report.errors:
    for error in report.errors:
        print(f"Discovery error: {error}")
```

### Entry Points (Точки входа)

```python
# setup.py или pyproject.toml
[project.entry-points.polisys_methods]
economy.fiscal.income_tax = "my_package.mechanisms:IncomeTaxMechanism"
economy.labor.market = "my_package.mechanisms:LaborMarketMechanism"
```

## Type System (Система типов)

### Slot Compatibility (Совместимость слотов)

```python
from polisyos.foundry.methods.types.checker import check_slot_compatibility

compatibility = check_slot_compatibility(
    source_slot=producer.output_slots["income"],
    target_slot=consumer.input_slots["wages"]
)

if not compatibility.compatible:
    for reason in compatibility.incompatibilities:
        print(f"Incompatible: {reason}")
```

### Type Adapters (Адаптеры типов)

```python
from polisyos.foundry.methods.types.checker import find_compatible_slots

# Поиск совместимых слотов с адаптацией
adapters = find_compatible_slots(
    source_slots=producer.output_slots,
    target_slots=consumer.input_slots
)

for adapter in adapters:
    print(f"Adapter needed: {adapter}")
```

## Linking System (Система связывания)

### Slot Linker (Связыватель слотов)

```python
from polisyos.foundry.methods.linker import link_methods

# Связывание цепочки методов
link_result = link_methods(
    methods=[tax_method, consumption_method, savings_method],
    config=LinkerConfig(
        allow_type_adaptation=True,
        strict_unit_matching=True,
    )
)

if link_result.success:
    bindings = link_result.bindings
    print(f"Successfully linked {len(bindings)} slots")
else:
    for error in link_result.errors:
        print(f"Linking error: {error}")
```

## Composition System (Система композиции)

### Method Composer (Композитор методов)

```python
from polisyos.foundry.methods.composer import MethodComposer

composer = MethodComposer()

# Добавление методов в композицию
composer.add_method("tax", tax_method)
composer.add_method("labor", labor_method)
composer.add_method("consumption", consumption_method)

# Определение связей
composer.connect("labor", "tax", slot_mapping={"wages": "income"})
composer.connect("tax", "consumption", slot_mapping={"net_income": "disposable_income"})

# Компиляция цепочки
compiled_chain = composer.compile()
```

### Composition DAG (Граф композиции)

```python
from polisyos.foundry.methods.composer import CompositionDAG

dag = CompositionDAG()
dag.add_node("producer", producer_method)
dag.add_node("consumer", consumer_method)
dag.add_edge("producer", "consumer", slot_bindings={"output": "input"})

# Топологическая сортировка
execution_order = dag.topological_sort()
```

## Compilation System (Система компиляции)

### Method Compiler (Компилятор методов)

```python
from polisyos.foundry.methods.compiler import MethodCompiler

compiler = MethodCompiler()

# Компиляция метода
compiled_method = compiler.compile(method)

# Компиляция цепочки
compiled_chain = compiler.compile_chain(composition_dag)

# Исполнение скомпилированной цепочки
result = compiled_chain.execute(input_arrays, static_params, rng_key)
```

### Compilation Cache (Кэш компиляции)

```python
from polisyos.foundry.methods.compiler import get_global_cache

cache = get_global_cache()

# Статистика кэша
stats = cache.get_stats()
print(f"Cache hits: {stats.hits}, misses: {stats.misses}")
```

## Specialization System (Система специализации)

### Method Specialization (Специализация методов)

```python
from polisyos.foundry.methods.specialization import build_specialization

# Создание специализации для конкретной формы данных
specialization = build_specialization(
    method=method,
    shape_spec=ShapeSpec(n_agents=1000, n_firms=100),
    backend_spec=BackendSpec(device="gpu", precision="float32")
)

# Компиляция специализированной версии
compiled_specialized = compiler.compile(specialization)
```

## Artifacts System (Система артефактов)

### Method Artifacts (Артефакты методов)

```python
from polisyos.foundry.methods.artifacts import store_method_artifact

# Сохранение артефакта метода
artifact_ref = store_method_artifact(
    store=store,
    method=method,
    execution_evidence=evidence,
    source_fingerprint=fingerprint
)
```

### Execution Evidence (Доказательства исполнения)

```python
from polisyos.foundry.methods.artifacts import ExecutionEvidence

evidence = ExecutionEvidence(
    method_fqn="economy.fiscal.income_tax@1.0.0",
    input_hashes={"income": hash_income_array},
    output_hashes={"tax_paid": hash_tax_array},
    timing=MethodTiming(start_time=..., end_time=...),
    device_info=DeviceInfo(device="gpu", memory_used=1024),
    source_fingerprint=source_fingerprint
)
```

## Testing Framework (Фреймворк тестирования)

### Method Testing (Тестирование методов)

```python
from polisyos.foundry.methods.testing import MethodTestSuite

suite = MethodTestSuite()

# Добавление тестов
@suite.add_test
def test_income_tax_basic():
    method = IncomeTaxMechanism(tax_rate=0.2)
    input_arrays = {"income": np.array([1000.0, 2000.0, 3000.0])}

    result = method.pure_step(input_arrays, {"tax_rate": 0.2}, rng_key)

    expected_tax = np.array([200.0, 400.0, 600.0])
    np.testing.assert_array_equal(result["tax_paid"], expected_tax)

# Запуск тестов
report = suite.run()
print(f"Passed: {report.passed}, Failed: {report.failed}")
```

## Components Bridge (Мост с компонентами)

### Bootstrap from Components (Загрузка из компонентов)

```python
from polisyos.foundry.methods.components_bridge import bootstrap_method_registry_from_components

# Конвертация legacy компонентов в методы Foundry
report = bootstrap_method_registry_from_components()

if report.errors:
    for error in report.errors:
        print(f"Bridge error: {error}")
```

## Exception Hierarchy (Иерархия исключений)

```python
FoundryMethodError
├── MethodDefinitionError      # Ошибки определения метода
├── MethodNotFoundError        # Метод не найден
├── MethodAlreadyRegisteredError # Метод уже зарегистрирован
├── ResolutionError            # Ошибки разрешения версий
├── SlotConnectionError        # Ошибки связывания слотов
├── UnitMismatchError          # Несоответствие единиц
├── ShapeMismatchError         # Несоответствие форм
├── CyclicDependencyError      # Циклические зависимости
├── CompilationError           # Ошибки компиляции
├── ParameterValidationError   # Ошибки валидации параметров
├── ArtifactError              # Ошибки артефактов
└── LawViolationError          # Нарушение архитектурных законов
```

## Примеры использования

### Создание простого метода

```python
from polisyos.foundry.methods import foundry_method, SlotSpec, SlotType, Unit
import numpy as np

@foundry_method(
    name="simple_tax",
    namespace="example.economy",
    version="1.0.0",
    description="Простой механизм налогообложения"
)
class SimpleTaxMechanism:
    def __init__(self, rate: float = 0.1):
        self.rate = rate

    def pure_step(self, state_arrays, static_params, rng_key):
        income = state_arrays["income"]
        rate = static_params.get("rate", self.rate)

        tax = income * rate
        after_tax = income - tax

        return {
            "tax_collected": tax,
            "disposable_income": after_tax,
        }
```

### Композиция методов

```python
from polisyos.foundry.methods import MethodComposer

# Создание композитора
composer = MethodComposer()

# Добавление методов
composer.add_method("production", ProductionMechanism())
composer.add_method("taxation", TaxationMechanism())
composer.add_method("consumption", ConsumptionMechanism())

# Связывание
composer.connect("production", "taxation", {"output": "income"})
composer.connect("taxation", "consumption", {"disposable_income": "income"})

# Компиляция и исполнение
chain = composer.compile()
result = chain.execute(initial_state, static_params, rng_key)
```

## Архитектурные принципы

### Architecture Laws (Архитектурные законы)

1. **F: Units & Metadata in Python**: Единицы измерения и метаданные только в Python, pure_step получает только массивы
2. **H: Deterministic Cache Keys**: Стабильные ключи кэша через digest, не __hash__
3. **I: Static vs Dynamic Parameters**: Явное объявление статических/динамических параметров
4. **L: Multi-fidelity Support**: Поддержка многоуровневой точности
5. **M: Semantic Versioning**: Строгое версионирование по SemVer

### Performance Characteristics

- **Type Safety**: Полная типизация с compile-time проверками
- **Caching**: Глобальный кэш компиляции для избежания повторных компиляций
- **Vectorization**: Автоматическая векторизация для массивов агентов
- **Specialization**: Специализация для конкретных форм данных и устройств

## Связь с другими модулями

- **`foundry.base`**: Использует базовые механизмы
- **`foundry.compiler`**: Компилирует методы в ProgramGraph
- **`foundry.runtime`**: Исполняет скомпилированные методы
- **`core.artifacts`**: Хранит артефакты методов
- **`scientist`**: Использует методы в экспериментах

---

Модуль `methods` - декларативная система для создания переиспользуемых, типобезопасных и композитных экономических методов с полной поддержкой версионирования, валидации и artifact tracking.