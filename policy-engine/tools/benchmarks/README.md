# Benchmarks - Бенчмарки производительности Policy Engine

Набор инструментов для измерения и анализа производительности ключевых компонентов Policy Engine. Бенчмарки обеспечивают регрессионное тестирование производительности и помогают оптимизировать системные bottlenecks.

## Структура папки

```
benchmarks/
├── bench_domain.py         # Бенчмарк доменной модели (JAX + Equinox + GlobalState)
│   # - Тестирование масштабируемости GlobalState аллокации
│   # - JAX JIT компиляция функциональных обновлений
│   # - Векторизованные операции (grants, taxes)
│   # - Память эффективность Equinox структур
│   #   └── bench_simulation.py     # Бенчмарк полного симуляционного пайплайна
    # - Экономический цикл (производство → потребление → рынок)
    # - Механизмы политик (TaxSubsidy, IncomeTax, Queue)
    # - JAX JIT оптимизации для больших состояний
    # - Полная интеграция foundry модуля
```

## Быстрый старт

Все бенчмарки запускаются из корня проекта с корректным PYTHONPATH:

```bash
cd policy-engine/

# Бенчмарк доменной модели (рекомендуемый для начала)
python tools/benchmarks/bench_domain.py

# Полный симуляционный бенчмарк
python tools/benchmarks/bench_simulation.py
```

## bench_domain.py - Бенчмарк доменной модели

Тестирует производительность и масштабируемость JAX доменной модели foundry - ключевого компонента для работы с большими состояниями симуляции.

### Что тестируется

**Масштабируемость аллокации:**
- `GlobalState` аллокация для миллионов агентов
- Память эффективность Equinox структур данных
- JAX ленивая инициализация и управление памятью

**JIT компиляция:**
- JAX JIT компиляция функциональных обновлений
- Оптимизация векторизованных операций
- Компиляция сложных экономических механизмов

**Векторизованные операции:**
- Массовые гранты (grants) для всех агентов
- Налоговые вычеты (tax subsidies)
- Агрегации по популяции

### Интеграция с модулями

- **`polisyos.foundry.domain.state.GlobalState`** - основная структура состояния
- **`polisyos.common.logger`** - логирование результатов
- **JAX JIT и векторизация** - компиляция и оптимизация

### Примеры использования

```bash
# Тест на 1M агентов (рекомендуемый размер)
python tools/benchmarks/bench_domain.py

# Кастомный размер популяции
python tools/benchmarks/bench_domain.py --n-agents 500000

# С детальным логированием
POLICY_ENGINE_LOG_LEVEL=DEBUG python tools/benchmarks/bench_domain.py
```

### Типичный вывод

```
🚀 Starting Domain Model Check...
Allocating state for 1,000,000 agents...
✅ Memory allocation: 2.3GB
✅ JIT compilation: 1.2s
✅ Vectorized operations: 45ms per step
✅ Domain Layer is JAX-compatible!
```

### Метрики производительности

- **Память:** Общий объем RAM для аллокации состояния
- **JIT время:** Время компиляции JAX функций
- **Время шага:** Производительность векторизованных операций
- **Совместимость:** Проверка JAX совместимости структур

## bench_simulation.py - Бенчмарк симуляционного ядра

Полносистемный бенчмарк симуляционного пайплайна foundry - тестирование полного цикла от доменной модели до экономической логики.

### Что тестируется

**Экономический цикл:**
- Производство → Потребление → Рынок
- Рыночные механизмы ценообразования
- Агентские взаимодействия

**Механизмы политик:**
- `TaxSubsidy` - субсидии и налоговые льготы
- `IncomeTax` - прогрессивное налогообложение
- `Queue` - механизмы очередей и аллокации

**JAX оптимизации:**
- JIT компиляция сложных симуляций
- Векторизация для больших состояний
- Оптимизация памяти и вычислений

### Интеграция с модулями

- **`polisyos.foundry.engine.kernel.SimulationKernel`** - ядро симуляции
- **`polisyos.foundry.domain.*`** - экономическая логика и механизмы
- **Полный foundry стек** - все компоненты математического ядра

### Примеры использования

```bash
# Полный симуляционный бенчмарк (рекомендуемый)
python tools/benchmarks/bench_simulation.py

# Кастомные параметры
python tools/benchmarks/bench_simulation.py --n-steps 100 --n-agents 10000

# С детальным логированием прогресса
POLICY_ENGINE_LOG_LEVEL=DEBUG python tools/benchmarks/bench_simulation.py
```

### Типичный вывод

```
🚀 Starting Simulation Loop Check...
Populated world with 1,000,000 agents.
Starting time loop...

Step 001 | GDP: 850.2M | Unempl: 4.8%
Step 002 | GDP: 892.1M | Unempl: 4.2%
...
Step 012 | GDP: 945.6M | Unempl: 3.9%

✅ Simulation finished in 3.47s
Speed: 3.5 steps/sec (3.5M agents-steps/sec)
```

### Метрики производительности

- **Время выполнения:** Общее время симуляции
- **Производительность:** Шаги в секунду, агенты-шаги в секунду
- **Экономические показатели:** GDP, unemployment rate по шагам
- **Стабильность:** Проверка на численные ошибки и сходимость

## Архитектурная интеграция

Бенчмарки обеспечивают качество foundry модуля согласно **Закону B** (компиляторная архитектура) и помогают поддерживать высокую производительность математического ядра.

### Закон B: Компиляторная архитектура
- Бенчмарки подтверждают чистоту математического ядра
- Тестируют JAX совместимость без side effects
- Обеспечивают производительность для масштабируемых симуляций

### CI/CD интеграция

Рекомендуется включать бенчмарки в nightly pipeline:

```yaml
# .github/workflows/nightly-benchmarks.yml
jobs:
  performance-regression:
    runs-on: ubuntu-latest
    schedule:
      - cron: '0 2 * * *'  # Каждый день в 2:00 UTC
    steps:
    - name: Domain scalability test
      run: python tools/benchmarks/bench_domain.py --n-agents 1000000

    - name: Full simulation benchmark
      run: python tools/benchmarks/bench_simulation.py --n-steps 1000 --n-agents 10000
```

## Troubleshooting

### Память переполнена (OOM)
```bash
# Уменьшить размер теста
python tools/benchmarks/bench_domain.py --n-agents 100000

# Проверить JAX backend
python -c "import jax; print(jax.default_backend())"
```

### JAX Metal проблемы (macOS)
```bash
# Принудительно CPU
export POLICY_ENGINE_ALLOW_JAX_METAL=0
python tools/benchmarks/bench_domain.py
```

### Медленная компиляция
```bash
# Первый запуск всегда медленный из-за JIT компиляции
# Повторные запуски будут быстрее
time python tools/benchmarks/bench_domain.py
```

## Разработка новых бенчмарков

### Принципы дизайна

1. **Фокус на bottlenecks:** Тестировать критические пути производительности
2. **Реалистичные сценарии:** Использовать типичные размеры данных
3. **Метрики качества:** Измерять latency, throughput, memory usage
4. **Регрессионное тестирование:** Предотвращать degradation производительности

### Добавление нового бенчмарка

```python
# tools/benchmarks/bench_new_feature.py
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# Импорты и бенчмарк логика...
```

---

*Бенчмарки протестированы на Python 3.11+ с JAX 0.4.x. Документация актуальна на 2026-01-24.*