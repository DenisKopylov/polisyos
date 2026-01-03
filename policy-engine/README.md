# Policy Engine

AI-driven Policy Simulation System using JAX and Unified Data Fabric

## Технологический стек

### Model Foundry (Математическое ядро)
- **Python 3.11**: Золотая середина между скоростью 3.12 и поддержкой JAX
- **JAX/JAXlib**: Основа вычислений
- **Equinox**: OOP wrapper для JAX моделей
- **Diffrax**: Решение дифференциальных уравнений (ODE/SDE)
- **Optax**: Оптимизаторы и лосс-функции
- **Jaxtyping**: Проверка размерностей тензоров

### Unified Data Fabric (Данные)
- **Kuzu**: Встраиваемая графовая БД
- **DuckDB**: Встраиваемая аналитическая SQL БД
- **PyArrow**: Zero-copy передача данных между БД и JAX
- **Pydantic v2**: Валидация данных и схем IR

### Orchestrator & Agents (Мозг)
- **LangGraph**: Управление стейтом агентов и циклами
- **LangChain**: Доступ к LLM (OpenAI/Anthropic)
- **PyMOO**: Многокритериальная оптимизация (NSGA-II)

### Dev Tools (Качество кода)
- **Ruff**: Быстрый линтер и форматер (замена Black + Flake8 + Isort)
- **MyPy**: Статическая типизация
- **Pytest**: Тесты

## Установка

### Вариант A: Рекомендуемый (uv - быстрый менеджер пакетов)

```bash
# Установка uv (если не установлен)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Синхронизация зависимостей (создает виртуальное окружение автоматически)
uv sync --extra dev

# Активация виртуального окружения
source .venv/bin/activate  # Linux/Mac
# или .venv\Scripts\activate на Windows
```

### Вариант B: Стандартный pip (если uv недоступен)

```bash
# Создаем виртуальное окружение
python3.11 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или .venv\Scripts\activate на Windows

# Устанавливаем зависимости
pip install -e .[dev]
```

### 2. Специфика JAX

**Mac M1/M2/M3:**
```bash
pip install jax-metal
# или uv add jax-metal
```

**Linux с NVIDIA:**
```bash
pip install -U "jax[cuda12_pip]" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
# или uv add "jax[cuda12_pip]" --extra-index-url https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
```

### 3. Решение проблем с установкой

**Если возникают ошибки permissions на macOS:**
```bash
# Для pip - используйте флаг user
pip install --user -e .[dev]

# Или настройте pip для игнорирования external management
pip config set global.break-system-packages true
```

**Если Python 3.11 недоступен:**
```bash
# Используйте python3 (работает с 3.11+)
python3 -m venv .venv
```

### 3. Настройка окружения

Скопируйте пример файла окружения и настройте API ключи:

```bash
cp env_example.txt .env
# Отредактируйте .env файл с вашими ключами
```

### 4. Автоматическая установка

Для удобства создан скрипт автоматической установки:

```bash
# Сделать исполняемым и запустить
chmod +x install.sh
./install.sh
```

## Структура проекта

```
policy-engine/
├── .env                  # API ключи (не в Git!)
├── .gitignore            # Стандартный gitignore
├── pyproject.toml        # Единый конфиг для зависимостей, линтера и тестов
├── README.md
├── data/                 # Локальное хранилище (DuckDB, Kuzu, Parquet)
│   ├── raw/
│   └── curated/
├── notebooks/            # Jupyter ноутбуки для тестов и EDA
├── src/                  # Весь исходный код
│   ├── fabric/           # Unified Data Fabric (DB adapters, Ingestion)
│   ├── foundry/          # JAX Simulation Core (Diffrax, Mechanisms)
│   ├── policy_ir/        # Pydantic Schemas (Contracts)
│   ├── orchestrator/     # LangGraph workflows
│   └── utils/            # Logging, tracing
└── tests/                # Pytest тесты
```

## Проверка установки

Запустите smoke test:

```bash
python check_setup.py
```

## Качество кода

Проект использует строгие правила линтинга:

- **Запрещены print statements** в продакшн коде (src/)
- Строгая статическая типизация
- Автоматическое форматирование кода

```bash
# Проверка линтера
ruff check .

# Форматирование
ruff format .

# Типизация
mypy src/
```
