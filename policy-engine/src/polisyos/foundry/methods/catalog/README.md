# Methods Catalog (`polisyos.foundry.methods.catalog`)

`methods/catalog` — каноническое дерево реализаций методов Foundry после миграции из legacy путей `methods/{causal,econometrics,optimization}`.

Актуально по коду на 2026-03-03.

## Роль

Каталог группирует предметные method-реализации, которые регистрируются в `MethodRegistry` и затем доступны:

- напрямую через `polisyos.foundry.methods` API;
- как `method`-узлы в execution graph Foundry;
- через `scientist` planning/runtime узлы.

## Подкаталоги

- `causal/`: причинные методы (discovery, estimation, transportability, sensitivity).
- `econometrics/`: panel, IV, time-series методы.
- `optimization/`: LP/MILP и input-output модели.

## Регистрация

Каждый подкаталог содержит `_registry_boot.py` с функцией `register_*_methods()`.

Интеграция в runtime выполняется через `ensure_*_methods_registered()` в соответствующих `__init__.py`.

## Совместимость

Legacy импорт-пути в `polisyos.foundry.methods.causal`, `...econometrics`, `...optimization` сохранены как facade-слой и переэкспортируют реализации из `catalog/*`.

## Смежная документация

- `../README.md` — обзор подсистемы `methods`.
- `causal/README.md` — подробная документация causal-каталога.
