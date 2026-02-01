# Demos - Демонстрационные скрипты Policy Engine

Коллекция демонстрационных скриптов, показывающих ключевые возможности Policy Engine. Демонстрации охватывают полный спектр функциональности: от ingestion данных до оптимизации политик и экспорта результатов.

## Структура папки

```
demos/
├── run_export_demo.py      # Экспорт симуляционных данных в разные форматы
│   # - Экспорт в Parquet, JSON, CSV, HDF5
│   # - Поддержка downstream анализа
│   # - Сохранение в DuckDB и Kuzu
├── run_ingest_demo.py      # Полный ingestion пайплайн (CSV → DuckDB + Kuzu)
│   # - Генерация тестовых данных (agents, interactions, macro)
│   # - Pydantic валидация и Parquet конвертация
│   # - Загрузка в DuckDB (аналитическое хранилище)
│   # - Загрузка в Kuzu (графовая БД взаимодействий)
│   # - Генерация manifests для reproducible runs
├── run_laffer_demo.py      # Демонстрация кривой Лаффера
│   # - Классическая кривая Лаффера (налоговые доходы)
│   # - Поиск оптимальной налоговой ставки
│   # - Экономическая теория в действии
├── run_optimizer_demo.py   # Многокритериальная оптимизация политик (NSGA-II)
│   # - Настройка целевых функций (GDP, inequality, unemployment)
│   # - PyMOO NSGA-II оптимизация
│   # - Pareto front анализ и визуализация
├── run_udf_hybrid_demo.py  # Гибридные запросы (SQL + Python UDF)
│   # - Комплексные агрегации с Python функциями
│   # - Машинное обучение в SQL запросах
│   # - Статистические и временные ряды функции
└── run_udf_query_demo.py   # UDF запросы к Unified Data Fabric
    # - Регистрация Python функций в DuckDB
    # - Гибридные SQL + Python запросы
    # - Kuzu графовые запросы с UDF
```

## Быстрый старт

Все демонстрации запускаются из корня проекта:

```bash
cd policy-engine/

# Полный ingestion пайплайн (начать с этого)
python tools/demos/run_ingest_demo.py

# UDF запросы к подготовленным данным
python tools/demos/run_udf_query_demo.py

# Оптимизация политик
python tools/demos/run_optimizer_demo.py

# Экспорт результатов
python tools/demos/run_export_demo.py
```

## Детальные описания демонстраций

### run_ingest_demo.py - Полный ingestion пайплайн

Полная демонстрация Unified Data Fabric ingestion: от сырых CSV до готовых баз данных с полной трассировкой данных.

#### Этапы пайплайна

1. **Генерация тестовых данных**
   - CSV файлы: `agents.csv`, `interactions.csv`, `macro.csv`
   - Реалистичные экономические данные (доходы, безработица, инфляция)
   - Агентские взаимодействия и транзакции

2. **Pydantic валидация**
   - Схема-ориентированная валидация данных
   - Преобразование в типизированные структуры
   - Обработка ошибок и неконсистентностей

3. **Parquet конвертация**
   - Columnar storage для эффективной аналитики
   - Сжатие и оптимизация для чтения
   - Поддержка сложных типов данных

4. **Загрузка в DuckDB**
   - Аналитическое хранилище временных рядов
   - SQL запросы для экономических показателей
   - Агрегации и статистика по популяции

5. **Загрузка в Kuzu**
   - Графовая БД для агентских взаимодействий
   - Социальные сети и транзакционные графы
   - Cypher запросы для сетевого анализа

6. **Генерация manifests**
   - JSON метаданные для reproducible runs
   - Хеши данных и версий
   - Полная трассировка происхождения данных

#### Создаваемые файлы

```
data/
├── raw/
│   ├── agents.csv          # Исходные данные агентов
│   ├── interactions.csv    # Транзакции между агентами
│   └── macro.csv           # Макроэкономические показатели
├── staging/
│   └── *.parquet           # Обработанные данные
├── curated/
│   └── manifests/          # Метаданные и хеши
demo_udf.duckdb              # Аналитическая БД
demo_udf.kuzu               # Графовая БД
```

#### Интеграция с модулями

- **`polisyos.fabric.ingestion.run_ingestion`** - основной пайплайн
- **`polisyos.fabric.io.db.SimulationDB`** - DuckDB интеграция
- **`polisyos.fabric.io.graph_store.GraphStore`** - Kuzu интеграция
- **`polisyos.ir.data_views.*`** - UDF запросы

### run_udf_query_demo.py - UDF запросы к данным

Демонстрация гибридных запросов с пользовательскими функциями (SQL + Python UDF) к Unified Data Fabric.

#### Типы запросов

**Panel запросы:**
- Временные ряды макроэкономических показателей
- GDP, unemployment rate, inflation по шагам симуляции

**Snapshot запросы:**
- Агрегации по состоянию агентов на конкретном шаге
- Средний доход безработных, распределение по доходам

**Network запросы:**
- Графовые запросы в Kuzu
- Социальные связи и взаимодействия агентов
- Достижимость и центральность в сети

#### Интеграция с модулями

- **`polisyos.fabric.udf.engine.UDFEngine`** - движок гибридных запросов
- **`polisyos.ir.data_views.DataViewRequest`** - спецификации запросов
- **`polisyos.fabric.io.db.SimulationDB`** - SQL база данных
- **`polisyos.fabric.io.graph_store.GraphStore`** - графовая БД

### run_optimizer_demo.py - Оптимизация политик

Демонстрация многокритериальной оптимизации политик с PyMOO (NSGA-II) для поиска оптимальных параметров.

#### Целевые функции

- **GDP максимизация** - экономический рост
- **Снижение неравенства** - равномерное распределение доходов
- **Минимизация безработицы** - социальная стабильность

#### Алгоритм оптимизации

- **NSGA-II** - элитный генетический алгоритм
- **Pareto front** - множество оптимальных решений
- **Многокритериальный анализ** - trade-offs между целями

#### Интеграция с модулями

- **`polisyos.scientist.orchestrator.workflow`** - оркестрация оптимизации
- **`polisyos.ir.surface.PolicySurfaceIR`** - спецификация политик
- **PyMOO** - библиотека многокритериальной оптимизации

### run_udf_hybrid_demo.py - Продвинутые UDF запросы

Расширенная демонстрация комбинации SQL запросов и Python функций для комплексного анализа данных.

#### Возможности

- **Комплексные агрегации** - статистические функции на Python
- **Машинное обучение** - ML модели в SQL запросах
- **Временные ряды** - анализ трендов и сезонности
- **Статистические функции** - распределения, корреляции

#### Интеграция с модулями

- **`polisyos.fabric.udf.engine.UDFEngine`** - гибридный движок
- **DuckDB UDF API** - регистрация Python функций
- **Pandas/NumPy** - численные вычисления

### run_laffer_demo.py - Кривая Лаффера

Классическая экономическая демонстрация кривой Лаффера - зависимости налоговых доходов от ставки налога.

#### Экономическая теория

- **Лафферова кривая** - нелинейная зависимость доходов от ставки
- **Оптимальная ставка** - баланс между доходами и disincentives
- **Поведенческая экономика** - реакция агентов на налоги

#### Интеграция с модулями

- **`polisyos.foundry.domain`** - экономическая модель
- **`polisyos.foundry.engine`** - симуляционное ядро

### run_export_demo.py - Экспорт симуляционных данных

Демонстрация экспорта результатов симуляции в различные форматы для downstream анализа.

#### Поддерживаемые форматы

- **Parquet** - columnar storage для аналитики (рекомендуемый)
- **JSON** - метаданные и конфигурация
- **CSV** - совместимость с legacy инструментами
- **HDF5** - большие числовые массивы и массивы

#### Интеграция с модулями

- **`polisyos.foundry.domain.state.GlobalState`** - симуляционное состояние
- **`polisyos.foundry.engine.kernel.SimulationKernel`** - симуляционное ядро
- **`polisyos.fabric.io.db.SimulationDB`** - сохранение в БД

## Архитектурная интеграция

Демонстрации показывают возможности всех основных модулей Policy Engine:

### Связи с модулями

| Демонстрация | Основные модули | Архитектурный аспект |
|-------------|----------------|---------------------|
| `run_ingest_demo.py` | `fabric.*`, `ir.*` | Unified Data Fabric ingestion |
| `run_udf_*_demo.py` | `fabric.udf.*`, `ir.data_views` | Гибридные SQL + Python запросы |
| `run_optimizer_demo.py` | `scientist.*` | Многокритериальная оптимизация |
| `run_export_demo.py` | `foundry.*`, `core.*` | Симуляция и экспорт данных |
| `run_laffer_demo.py` | `foundry.*` | Экономическое моделирование |

### Архитектурные принципы

- **Закон A**: Все демонстрации уважают направленный граф зависимостей
- **Закон B**: Foundry остается чистым математическим ядром
- **Закон C**: Контракты используются как источник истины
- **Закон D**: Все прогоны воспроизводимы с seed и run_id

## CI/CD интеграция

Демонстрации используются для smoke testing в CI:

```yaml
# .github/workflows/smoke-tests.yml
jobs:
  integration-smoke:
    steps:
    - name: Data ingestion test
      run: python tools/demos/run_ingest_demo.py

    - name: UDF functionality test
      run: python tools/demos/run_udf_query_demo.py

    - name: Export pipeline test
      run: python tools/demos/run_export_demo.py
```

## Troubleshooting

### Данные не найдены
```bash
# Сначала запустить ingestion
python tools/demos/run_ingest_demo.py

# Проверить созданные файлы
ls -la data/ demo_udf.*
```

### JAX проблемы
```bash
# Принудительно CPU для стабильности
export POLICY_ENGINE_ALLOW_JAX_METAL=0
python tools/demos/run_export_demo.py
```

### Kuzu установка
```bash
# Проверить установку
python -c "import kuzu; print('Kuzu OK')"

# Переустановить если нужно
pip install kuzu --force-reinstall
```

## Разработка новых демонстраций

### Принципы дизайна

1. **Образовательная ценность** - демонстрировать ключевые концепции
2. **Самодостаточность** - каждая demo работает независимо
3. **Реалистичные данные** - использовать правдоподобные сценарии
4. **Четкий вывод** - понятные результаты и интерпретация

### Шаблон новой демонстрации

```python
#!/usr/bin/env python3
"""
Название демонстрации - краткое описание.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

def main():
    print("🎬 Starting demonstration...")

    # Демонстрационная логика...

    print("✅ Demonstration complete!")

if __name__ == "__main__":
    main()
```

---

*Демонстрации протестированы на Python 3.11+ с полным стеком Policy Engine. Документация актуальна на 2026-02-01.*