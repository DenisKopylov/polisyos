# Canon (Каноническая сериализация)

## Обзор

Детерминированная JSON сериализация для reproducible вычислений и стабильных хешей. Запрет float, сортировка ключей, поддержка Decimal/datetime.

## Архитектура

```
canon/
└── canon_json.py   # CanonSpec, to_canonical_bytes, from_canonical_bytes
```

## Основные компоненты

### CanonSpec
Конфигурация параметров канонизации.

```python
from polisyos.core.canon import CanonSpec

spec = CanonSpec(
    forbid_floats=True,      # Запрет float
    sort_keys=True,          # Сортировка ключей
    ensure_ascii=False       # Unicode
)
```

### Основные функции

#### to_canonical_bytes()
Преобразование в канонические байты.

```python
from polisyos.core.canon import to_canonical_bytes
from decimal import Decimal
from datetime import datetime

data = {
    "threshold": Decimal("0.75"),
    "created_at": datetime(2024, 1, 15, 10, 30, 0)
}
canonical_bytes = to_canonical_bytes(data)
```

#### from_canonical_bytes()
Десериализация из байт.

```python
from polisyos.core.canon import from_canonical_bytes
restored = from_canonical_bytes(canonical_bytes)
```

## Правила канонизации

### Запреты
- **Float числа**: Используйте `Decimal` для точных вычислений
- **NaN/Inf**: Запрещены для предотвращения неопределенности

```python
# ✅ Правильно
from decimal import Decimal
data = {"price": Decimal("19.99")}

# ❌ Неправильно
data = {"price": 19.99}  # float
```

### Специальные типы
- **Decimal**: `{"_type": "decimal", "value": "19.99"}`
- **datetime**: `{"_type": "datetime", "iso_utc": "2024-01-15T10:30:00Z"}`
- **date**: `{"_type": "date", "iso": "2024-01-15"}`
- **bytes**: `{"_type": "bytes", "encoding": "base64", "data": "..."}`

### Детерминизм
- **Сортировка ключей**: Алфавитный порядок
- **Фиксированные разделители**: `",:"` без пробелов
- **Unicode**: Поддержка интернационализации

## Примеры использования

### Стабильные хеши

```python
from polisyos.core.canon import to_canonical_bytes
import hashlib

policy_data = {
    "rules": [{"condition": "budget > 1000", "action": "approve"}],
    "version": "2.1.0"
}

canonical = to_canonical_bytes(policy_data)
stable_hash = hashlib.sha256(canonical).hexdigest()
```

### Сравнение конфигураций

```python
config1 = {"threshold": Decimal("0.8"), "enabled": True}
config2 = {"enabled": True, "threshold": Decimal("0.8")}  # другой порядок

# Идентичны после канонизации
assert to_canonical_bytes(config1) == to_canonical_bytes(config2)
```

### Pydantic модели

```python
from pydantic import BaseModel
from polisyos.core.canon import to_canonical_bytes, from_canonical_bytes

class Config(BaseModel):
    iterations: int
    learning_rate: Decimal

config = Config(iterations=1000, learning_rate=Decimal("0.01"))
canonical_bytes = to_canonical_bytes(config)
restored = Config(**from_canonical_bytes(canonical_bytes))
```

## Использование в системе

- **Artifacts**: Стабильные хеши для CAS
- **Foundry**: Reproducible результаты симуляций
- **Scientist**: Воспроизводимость экспериментов
- **Fabric**: Сериализация evidence и фактов

## Производительность

- **Детерминизм**: Стабильные результаты для кеширования
- **Валидация**: Строгая проверка типов
- **Безопасность**: Предотвращение float/NaN проблем
- **Совместимость**: Поддержка Decimal, datetime, bytes

## Ошибки

### CanonViolation

```python
from polisyos.core.canon import to_canonical_bytes

try:
    to_canonical_bytes({"value": 3.14})  # float запрещен
except CanonViolation as e:
    print(f"Violation: {e}")
```

## Лучшие практики

- Используйте `Decimal` вместо `float`
- Проверяйте типы перед сериализацией
- Тестируйте восстановление данных
- Документируйте ожидаемые типы