# roads pack

`roads` это полный встроенный доменный пакет для демонстрации end-to-end потока:
IR-фрагменты -> Foundry method -> Scholar extraction -> Lex extraction/evaluation -> NormPack provider.

Экспорт: `__polisyos_components__` в `components.py` (6 компонентов).

## Роль в системе

- дает рабочий baseline для дорожного домена;
- покрывает сразу несколько kind-компонентов;
- используется как эталонный набор для discovery и интеграционных тестов.

## Архитектура потока

```
ir_fragments.py
  -> roads.kmh unit (priority=100)

foundry_methods.py
  -> speed_cap method (vector clamp)

scholar_extractors.py
  -> roads.scholar.speed_limit (text -> ClaimCandidate)
  -> lex.norm_extractor.regex_v1 (legacy backend wrapper)

lex_evaluators.py
  -> lex.eval.simple_v1 (evaluate_legality_impl wrapper)

norms_provider.py
  -> roads.normpack.static_provider (UA static NormPack)
```

## Файлы и ответственность

| Файл | Что делает |
|---|---|
| `components.py` | Собирает и экспортирует `__polisyos_components__` |
| `ir_fragments.py` | Регистрирует `roads.kmh` через `UnitsFragment` |
| `foundry_methods.py` | Определяет метод `speed_cap` (`np.minimum`, O(N)) |
| `scholar_extractors.py` | Дает domain extractor для speed limit и обертку `lex_norm_regex_v1` |
| `lex_evaluators.py` | Дает обертку `evaluate_legality_impl` |
| `norms_provider.py` | Возвращает статический `NormPack` с 2 правилами для `ua` |

## Каталог компонентов

| Component ID | Kind | Кратко |
|---|---|---|
| `roads.ir.registry_fragment@1.0.0` | IR_FRAGMENT | `roads.kmh`, namespace `roads`, priority `100` |
| `roads.method.speed_cap@1.0.0` | FOUNDRY_METHOD | Ограничение скорости по параметру `cap` (default `50.0`) |
| `roads.scholar.speed_limit@1.0.0` | SCHOLAR_EXTRACTOR | Regex извлекает лимит скорости из plain text (en/uk) |
| `lex.norm_extractor.regex_v1@1.0.0` | LEX_EXTRACTOR | Обертка legacy regex backend из `fabric` |
| `lex.eval.simple_v1@1.0.0` | LEX_EVALUATOR | Обертка функции legal evaluation из `lex` |
| `roads.normpack.static_provider@1.0.0` | NORM_PACK_PROVIDER | Статический провайдер норм для `ua` |

## Связь с другими директориями

- `src/polisyos/core/components`: `ComponentMetadata`, `Capability`, discovery model.
- `src/polisyos/ir/*`: `UnitsFragment`, `NormPack`, `NormRule`.
- `src/polisyos/foundry/methods/base`: сигнатуры/типы метода `speed_cap`.
- `src/polisyos/fabric/claims/types`: `ClaimCandidate` для scholar extractor.
- `src/polisyos/fabric/claims/backends`: `lex_norm_regex_v1.extract` (lazy import).
- `src/polisyos/lex/legal_evaluation/evaluate.py`: `evaluate_legality_impl` (lazy import).

Регистрация в entry points: `policy-engine/pyproject.toml`.

## Особенности и ограничения

- IR фрагмент roads (`priority=100`) выигрывает конфликт у `econ` (`priority=90`) при merge.
- `RoadsStaticNormPackProvider` хранит данные в коде; это demo-режим, не source of truth.
- Regex extractor покрывает простые случаи (`speed limit 50`, `max speed 80`, `максимальна швидкість 60`).
- Тяжелые зависимости импортируются лениво внутри `create()`/factory.

## Тесты

- `policy-engine/tests/test_packs_discovery.py`
