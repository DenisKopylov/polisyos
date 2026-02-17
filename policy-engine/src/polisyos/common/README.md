# `polisyos.common` — базовый инфраструктурный слой

`polisyos.common` содержит низкоуровневые утилиты без доменной логики: bootstrap окружения, логирование, сериализацию, работу со временем, async-мост и простые миграции артефактов.

## Роль в архитектуре

```text
polisyos.common
  ├─ bootstrap среды (config, jax_env)
  ├─ observability (logger)
  ├─ универсальные утилиты (async_tools, serialization, timestamps)
  └─ миграции локальных схем (common/migrations)
```

Инварианты слоя:
- `common` не должен зависеть от верхних пакетов (`core`, `fabric`, `foundry`, `scientist`, `runtime`, `lex`, `scholar`, `ir`).
- здесь нет бизнес-правил и продуктовых решений, только инфраструктурные примитивы;
- API должен быть компактным и стабильным, потому что это нижняя часть графа зависимостей.

## Состав директории

```text
common/
├── __init__.py         # Lazy facade: common.<module> через __getattr__
├── async_tools.py      # run_coro_sync(coro)
├── config.py           # import-time bootstrap env + настройка loguru
├── jax_env.py          # apply_jax_env_defaults() для macOS/JAX
├── logger.py           # get_logger() + trace enrichment (OTel, optional)
├── serialization.py    # to_python_data(), stable_json_dumps(), strip_none()
├── timestamps.py       # UTC helpers (iso/epoch/parse)
├── migrations/
│   ├── __init__.py
│   ├── base.py
│   └── manifest.py
└── README.md
```

## Модули и текущее поведение

| Модуль | Ответственность | Важные особенности |
|---|---|---|
| `__init__.py` | Ленивая загрузка подмодулей через `__getattr__` | Экспортирует только фиксированный `__all__` |
| `config.py` | Bootstrap среды и логирования при импорте | Меняет `os.environ` и конфигурацию `loguru` глобально |
| `jax_env.py` | Защита от автовыбора `metal` на macOS | CPU по умолчанию, `metal` только через opt-in |
| `logger.py` | Унифицированный логгер для модулей | `get_logger()` добавляет `module`, плюс `trace_id/span_id` при активном OTel span |
| `async_tools.py` | Запуск coroutine из sync-кода | При активном event loop запускает `asyncio.run` в отдельном потоке |
| `serialization.py` | Приведение структур к JSON-friendly Python данным | Поддержка dataclass/Enum/Pydantic-like (`model_dump`) + `.tolist()`/`.item()` |
| `timestamps.py` | Единая UTC-нормализация времени | Поддержка ISO `Z`, epoch ↔ datetime |
| `migrations/*` | Реестр и исполнение цепочек миграций | В этом пакете сейчас только `dataset_manifest: 0.9 -> 1.0` |

## Связи с другими директориями

Фактическое использование в репозитории:
- `fabric/*` активно использует `logger` и `run_coro_sync`;
- `runtime/http/services/control.py` точечно использует `run_coro_sync` (ленивый импорт внутри метода);
- `scientist/*` использует `serialization` и `timestamps`;
- `foundry/*` использует `logger` и `serialization`;
- `scholar/freshness_store.py` использует `timestamps`;
- `tools/diagnostics/check_setup.py` импортирует `polisyos.common.config` для bootstrap side-effects;
- `jax_bootstrap.py` использует `apply_jax_env_defaults()`.

## Важные особенности и ограничения

### 1) `config.py` работает через side-effects
- импорт модуля сразу настраивает окружение и логирование;
- `JAX_PLATFORM_NAME`, `JAX_ENABLE_X64`, `JAX_DISABLE_MOST_OPTIMIZATIONS`, `JAX_CHECK_TRACER_LEAKS` выставляются до `load_dotenv()`;
- затем применяются safeguard-настройки потоков (`XLA_FLAGS`, `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `SCIENTIST_TORCH_*`, `DUCKDB_THREADS` и др.);
- `loguru` перенастраивается на 2 sink-а: stderr и `logs/system.log` (JSON, rotation/retention).

### 2) `logger.py` поддерживает мягкую деградацию
- при отсутствии `loguru` используется stdlib `logging`;
- при отсутствии OpenTelemetry логирование продолжает работать без trace-обогащения.

### 3) `common.migrations` и `ir.migrations` разделены
- `polisyos.common.migrations` отвечает только за общие артефакты уровня `common` (сейчас `dataset_manifest`);
- `policy_ir` мигрируется через `polisyos.ir.migrations`.

Практический нюанс текущего состояния:
- скрипты `migrate.py` и `tools/migrations/migrate.py` ожидают `POLICY_IR_CURRENT_VERSION` в `polisyos.common.migrations`, но этот символ там не экспортируется;
- актуальный источник версии IR: `polisyos.ir.migrations`.

## Правила для дальнейших изменений

- не добавлять в `common` зависимости на доменные слои;
- импорт `config` держать только в entrypoint/bootstrap-коде;
- для модульного контекста логов использовать `get_logger(__name__)`;
- новые миграции добавлять только для схем, владельцем которых является `common`.

## Быстрые проверки

```bash
# Кто использует common
rg -n "from polisyos\\.common|import polisyos\\.common|polisyos\\.common\\." src tools *.py

# Проверка, что common не импортирует верхние слои
rg -n "from polisyos\\.(core|fabric|foundry|scientist|ir|runtime|lex|scholar)" src/polisyos/common
```
