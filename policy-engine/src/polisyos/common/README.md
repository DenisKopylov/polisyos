# `polisyos.common` — базовый инфраструктурный слой

`polisyos.common` хранит общие технические примитивы без доменной логики: bootstrap окружения, логирование, сериализацию, работу со временем, sync↔async bridge и локальные миграции схем.

## Роль в системе

```text
polisyos.common
  ├─ bootstrap среды          (config, jax_env)
  ├─ observability            (logger)
  ├─ utility primitives       (async_tools, serialization, timestamps)
  └─ local schema migrations  (common/migrations)
```

Инварианты:
- пакет находится внизу графа зависимостей и должен оставаться стабильным;
- `common` не должен импортировать верхние слои (`core`, `fabric`, `foundry`, `scientist`, `runtime`, `lex`, `scholar`, `ir`);
- в этом слое нет бизнес-правил.

## Состав и API

| Модуль | Публичные точки | Назначение | Особенности |
|---|---|---|---|
| `__init__.py` | lazy facade через `__getattr__` | Ленивая загрузка `common.<module>` | Явный `__all__` |
| `config.py` | import-time конфигурация | Bootstrap env + конфиг `loguru` | Глобальные side-effects (`os.environ`, sinks логов) |
| `jax_env.py` | `apply_jax_env_defaults()` | Безопасные дефолты JAX на macOS | CPU по умолчанию, `metal` только через opt-in |
| `logger.py` | `logger`, `get_logger()` | Единый logging API | OTel trace enrichment + fallback на stdlib logging |
| `async_tools.py` | `run_coro_sync()` | Запуск coroutine из sync-кода | При активном loop уходит в отдельный поток |
| `serialization.py` | `to_python_data`, `stable_json_dumps`, `fast_json_*`, `strip_none` | Канонизация/JSON сериализация | Поддержка dataclass/Enum/`model_dump`/`tolist`/`item`; `orjson` опционально |
| `timestamps.py` | `utc_now`, `ensure_utc`, `to_iso_utc`, `parse_iso_datetime`, `to_epoch_seconds`, `from_epoch_seconds` | Единая UTC-нормализация времени | Поддержка ISO (`Z`) и epoch |
| `migrations/*` | `register_migration`, `migrate_artifact`, `MANIFEST_CURRENT_VERSION` | Локальные миграции схем `common` | Сейчас покрыт только `dataset_manifest` |

Отдельная документация по миграциям: [`migrations/README.md`](./migrations/README.md).

## Связи с другими директориями (фактическое использование)

- `fabric/*` — основной потребитель (`logger/get_logger`, `run_coro_sync`) ;
- `core/*` — `logger`, `serialization` (`fast_json_dumps*`);
- `runtime/*` — `serialization` (`runtime/api.py`) и точечный `run_coro_sync` (`runtime/http/services/control.py`);
- `scientist/*` — `serialization` и `timestamps`;
- `foundry/*` — `logger` и `serialization`;
- `scholar/freshness_store.py` — `timestamps`;
- entrypoints/tools: `jax_bootstrap.py` (`jax_env`), `tools/diagnostics/check_setup.py` (`config` side-effects), migration CLI (`common.migrations`).

## Ключевые особенности

1. `config.py` исполняется при импорте и сразу применяет runtime safeguards (JAX/threads/log sinks).
2. `logger.py` продолжает работать без optional зависимостей (`loguru`, `opentelemetry`) через мягкий fallback.
3. `serialization.py` обеспечивает детерминированный JSON (`stable_json_dumps`) и быстрый путь (`fast_json_*`).
4. `common.migrations` отделён от `polisyos.ir.migrations`: это разные владельцы схем.

## Известный интеграционный нюанс

`policy-engine/migrate.py` и `policy-engine/tools/migrations/migrate.py` импортируют `POLICY_IR_CURRENT_VERSION` из `polisyos.common.migrations`, но этот символ в `common.migrations` не экспортируется.  
Актуальный источник версии для IR: `polisyos.ir.migrations`.

## Правила изменений

- не добавлять зависимости из `common` на верхние подсистемы;
- `config` импортировать только в bootstrap/entrypoint коде;
- для модульных логов использовать `get_logger(__name__)`;
- новые миграции добавлять только для артефактов, которыми владеет слой `common`.

## Быстрые проверки

```bash
# Кто использует common
rg -n "from polisyos\\.common|import polisyos\\.common|polisyos\\.common\\." policy-engine/src policy-engine/tools policy-engine/*.py

# Проверка, что common не импортирует верхние слои
rg -n "from polisyos\\.(core|fabric|foundry|scientist|ir|runtime|lex|scholar)" policy-engine/src/polisyos/common
```
