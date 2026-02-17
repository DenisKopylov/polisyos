# ir.trinity

`ir.trinity` определяет канонический формат policy payload: `TrinityBundle`.

## Контракт

`TrinityBundle` объединяет:

- `ProblemFrame` (why);
- `PolicySpec` (what);
- `ModelSpec` (how).

Актуальная версия bundle: `TRINITY_BUNDLE_SCHEMA_VERSION = "1.0"`.

## Загрузчики

`loaders.py` предоставляет strict-loaders:

- `load_problem_frame()`
- `load_policy_spec()`
- `load_model_spec()`
- `load_trinity_bundle()`

Поддерживаются входы `dict`, `str`, `bytes`; форматы `json`, `yaml`, `auto`.

Все загрузчики требуют корректный `schema_version` и возвращают типизированные модели.

## Связь с другими модулями

- `ir.loaders` — высокоуровневый фасад для загрузки policy payload.
- `ir.migrations` — runtime миграции версий canonical Trinity payload.
- `ir.linker` — валидация Trinity против `RegistryBundle`.
