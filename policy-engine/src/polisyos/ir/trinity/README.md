# ir.trinity

`ir.trinity` определяет канонический policy payload: `TrinityBundle`.

## Контракт

`TrinityBundle` объединяет:

- `ProblemFrame` (why);
- `PolicySpec` (what);
- `ModelSpec` (how).

Актуальная версия bundle: `TRINITY_BUNDLE_SCHEMA_VERSION = "1.0"`.

## Загрузчики

`trinity/loaders.py` предоставляет strict loaders:

- `load_problem_frame()`
- `load_policy_spec()`
- `load_model_spec()`
- `load_trinity_bundle()`

Поддерживаются входы `dict`, `str`, `bytes`; форматы `json`, `yaml`, `auto`.
Все loaders требуют валидный `schema_version` (можно переопределить `target_schema_version`/`target_version`) и возвращают типизированные модели.

## Высокоуровневый фасад

`ir/loaders.py` добавляет удобные входы:

- `load_policy()`
- `load_trinity_bundle()` (возвращает `(TrinityBundle, None)`)
- `load_trinity()`

Важно: на текущем коде `auto_migrate` не выполняет legacy runtime migration. Невалидный non-Trinity payload будет отклонён.

## Связь с другими модулями

- `ir.migrations` — runtime миграции canonical Trinity payload версий.
- `ir.linker` — валидация Trinity против `RegistryBundle`.
- `ir.registry_fragments` — источник registry для линковки.
