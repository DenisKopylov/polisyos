# Canon Module (Каноническая сериализация)

## Обзор

Модуль `canon` предоставляет детерминированную сериализацию данных в JSON формат для обеспечения воспроизводимости вычислений и создания стабильных хешей артефактов. Каноническая сериализация гарантирует, что одинаковые данные всегда сериализуются в одинаковые байты, независимо от порядка ключей, форматирования или платформы.

## Архитектура

```
canon/
└── canon_json.py   # Основная реализация канонической сериализации
```

## Основные компоненты

### CanonSpec

Спецификация параметров канонизации с настраиваемыми правилами.

```python
from polisyos.core.canon import CanonSpec

# Стандартная спецификация (рекомендуется)
spec = CanonSpec()

# Кастомная спецификация
spec = CanonSpec(
    forbid_floats=True,      # Запрет float чисел
    forbid_nan_inf=True,     # Запрет NaN/Inf
    sort_keys=True,          # Сортировка ключей
    separators=(",", ":"),   # Разделители JSON
    ensure_ascii=False       # Кодировка Unicode
)
```

### Основные функции

#### to_canonical_bytes()

Преобразование объектов в канонические байты.

```python
from polisyos.core.canon import to_canonical_bytes
from decimal import Decimal
from datetime import datetime

# Сериализация сложных данных
data = {
    "policy": {
        "threshold": Decimal("0.75"),
        "created_at": datetime(2024, 1, 15, 10, 30, 0),
        "parameters": ["budget", "fairness"]
    },
    "version": "1.0.0"
}

canonical_bytes = to_canonical_bytes(data)
print(canonical_bytes.decode('utf-8'))
```

#### from_canonical_bytes()

Десериализация из канонических байт.

```python
from polisyos.core.canon import from_canonical_bytes

# Десериализация
restored_data = from_canonical_bytes(canonical_bytes)
assert restored_data["policy"]["threshold"] == Decimal("0.75")
```

#### from_canonical_obj()

Десериализация из канонического объекта.

```python
from polisyos.core.canon import from_canonical_obj, to_canonical_bytes

# Частичная десериализация
canonical_obj = to_canonical_bytes(data, return_obj=True)
restored = from_canonical_obj(canonical_obj)
```

## Правила канонизации

### Запрет float (forbid_floats=True)

Float числа запрещены для обеспечения точных вычислений. Используйте Decimal для денежных значений и точных расчетов.

```python
# ❌ Неправильно
data = {"price": 19.99}  # float

# ✅ Правильно
from decimal import Decimal
data = {"price": Decimal("19.99")}
```

### Запрет NaN/Inf (forbid_nan_inf=True)

NaN и бесконечные значения запрещены для предотвращения неопределенного поведения.

```python
# Эти значения вызовут CanonViolation
invalid_data = {"value": float('nan')}
invalid_data = {"value": float('inf')}
```

### Специальные типы

#### Decimal
```json
{"_type": "decimal", "value": "19.99"}
```

#### datetime
```json
{"_type": "datetime", "iso_utc": "2024-01-15T10:30:00Z"}
```

#### date
```json
{"_type": "date", "iso": "2024-01-15"}
```

#### bytes
```json
{"_type": "bytes", "encoding": "base64", "data": "SGVsbG8gV29ybGQ="}
```

#### float (если разрешено)
```json
{"_type": "float", "repr": "19.99"}
```

### Автоматическая конвертация

Модуль автоматически конвертирует Pydantic модели и датаклассы:

```python
from pydantic import BaseModel
from polisyos.core.canon import to_canonical_bytes

class PolicyConfig(BaseModel):
    threshold: Decimal
    max_iterations: int

config = PolicyConfig(threshold=Decimal("0.8"), max_iterations=100)
canonical_bytes = to_canonical_bytes(config)
```

## Детерминированная сериализация

### Сортировка ключей (sort_keys=True)
Ключи объектов всегда сортируются в алфавитном порядке.

### Фиксированные разделители (separators=",:")
Используются минимальные разделители без пробелов.

### Кодировка Unicode (ensure_ascii=False)
Поддерживается Unicode для интернационализации.

## Примеры использования

### Создание стабильных хешей

```python
import hashlib
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.artifacts.ids import ArtifactID

# Данные политики
policy_data = {
    "rules": [
        {"condition": "budget > 1000", "action": "approve"},
        {"condition": "budget <= 1000", "action": "review"}
    ],
    "metadata": {
        "version": "2.1.0",
        "author": "policy_team"
    }
}

# Каноническая сериализация для стабильного хеша
canonical = to_canonical_bytes(policy_data)
artifact_id = ArtifactID.from_sha256_hex(hashlib.sha256(canonical).hexdigest())
```

### Сравнение конфигураций

```python
from polisyos.core.canon import to_canonical_bytes

config1 = {"threshold": Decimal("0.8"), "enabled": True}
config2 = {"enabled": True, "threshold": Decimal("0.8")}  # другой порядок ключей

# Будут идентичны после канонизации
assert to_canonical_bytes(config1) == to_canonical_bytes(config2)
```

### Работа с Pydantic моделями

```python
from pydantic import BaseModel, Field
from polisyos.core.canon import to_canonical_bytes, from_canonical_bytes

class SimulationConfig(BaseModel):
    model_config = {"extra": "forbid"}

    iterations: int = Field(ge=1, le=10000)
    learning_rate: Decimal = Field(ge=0, le=1)
    features: list[str]

config = SimulationConfig(
    iterations=1000,
    learning_rate=Decimal("0.01"),
    features=["age", "income", "score"]
)

# Сериализация
canonical_bytes = to_canonical_bytes(config)

# Десериализация обратно в модель
restored_config = SimulationConfig(**from_canonical_bytes(canonical_bytes))
```

## Использование в системе

### В artifacts
Обеспечивает стабильные хеши для Content-Addressable Storage.

### В Foundry
Гарантирует reproducible результаты симуляций.

### В Scientist
Обеспечивает воспроизводимость экспериментов.

### В Fabric
Каноническая сериализация evidence и фактов данных.

## Производительность

- **Сериализация**: Детерминированные результаты для кеширования
- **Валидация**: Строгая проверка типов на этапе сериализации
- **Безопасность**: Предотвращение неопределенного поведения с float/NaN
- **Совместимость**: Поддержка сложных типов данных (Decimal, datetime, bytes)

## Ошибки и исключения

### CanonViolation
Вызывается при нарушении правил канонизации:

```python
from polisyos.core.canon import CanonViolation, to_canonical_bytes

try:
    # Попытка сериализовать float (запрещено по умолчанию)
    to_canonical_bytes({"value": 3.14})
except CanonViolation as e:
    print(f"Canon violation: {e}")
```

## Лучшие практики

1. **Всегда используйте Decimal для чисел**: Избегайте float для финансовых и точных расчетов
2. **Проверяйте типы заранее**: Валидируйте данные перед канонизацией
3. **Используйте стандартную спецификацию**: Не меняйте параметры без необходимости
4. **Тестируйте сериализацию**: Проверяйте, что данные корректно восстанавливаются
5. **Документируйте схемы**: Указывайте ожидаемые типы данных в документации