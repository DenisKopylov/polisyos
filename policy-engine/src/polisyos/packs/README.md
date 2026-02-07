# polisyos.packs — Component Packs

Встроенные доменные пакеты PolicyOS — готовые коллекции компонентов для быстрого старта, демонстраций и тестирования компонентной системы.

2 пакета, 7 компонентов, 11 Python-файлов.

## Роль в системе

Packs — **листовой** модуль в графе зависимостей. Он не экспортирует интерфейсов, а только реализует их: каждый пакет собирает компоненты из разных слоёв системы (IR, Foundry, Scholar, Lex, Fabric) в единую доменную коллекцию.

```
core/components   ir/   foundry/   fabric/   lex/
  │  интерфейсы    │  типы   │  методы   │  claims  │  evaluators
  └────────────────┴─────────┴──────────┴─────────┴──────────┐
                                                              ▼
                                                    packs/ (реализации)
                                                    ├── roads/  (6 компонентов)
                                                    └── econ/   (1 компонент)
```

**Назначение:**
- Reference implementation всех типов компонентов PolicyOS
- Демонстрация end-to-end цикла: IR-фрагменты → моделирование → экстракция → нормы → легальность
- Тестирование discovery, приоритетов и conflict resolution
- Базовый набор для прототипирования новых доменов

## Структура

```
packs/
├── __init__.py              # __all__ = ["roads", "econ"]
├── roads/                   # Полнофункциональный дорожный пакет (6 компонентов)
│   ├── components.py        # Агрегация и экспорт __polisyos_components__
│   ├── ir_fragments.py      # Единица roads.kmh (UnitsFragment, priority=100)
│   ├── foundry_methods.py   # Метод speed_cap (numpy, O(N))
│   ├── scholar_extractors.py# Regex-экстрактор speed limit (en/uk)
│   ├── lex_evaluators.py    # Обёртка над evaluate_legality_impl
│   └── norms_provider.py    # Статический NormPack для UA юрисдикции
└── econ/                    # Демо-пакет для тестирования конфликтов
    ├── components.py        # Экспорт __polisyos_components__
    └── ir_fragments.py      # Конфликтный roads.kmh (priority=90)
```

## Обнаружение компонентов

Каждый пакет экспортирует `__polisyos_components__` — список объектов `_StaticComponent`. Два механизма discovery:

| Механизм | Среда | Как работает |
|---|---|---|
| Entry Points | Production | Регистрация в `pyproject.toml` секции `[project.entry-points."polisyos.*"]` |
| Dev Scan | Разработка | `discover_components(include_dev_scan=True, dev_scan_paths=[...])` рекурсивно ищет `__polisyos_components__` |

При одновременном использовании обоих механизмов, dev scan компоненты имеют приоритет (настраивается через `DiscoveryPrecedencePolicy`).

## Каталог компонентов

| ID | Kind | Пакет | Домен | Описание |
|---|---|---|---|---|
| `roads.ir.registry_fragment@1.0.0` | IR_FRAGMENT | roads | roads | Единица измерения `roads.kmh` |
| `roads.method.speed_cap@1.0.0` | FOUNDRY_METHOD | roads | roads | Ограничение скорости агентов |
| `roads.scholar.speed_limit@1.0.0` | SCHOLAR_EXTRACTOR | roads | roads | Извлечение speed limit из текста (en/uk) |
| `lex.norm_extractor.regex_v1@1.0.0` | LEX_EXTRACTOR | roads | — | Обёртка legacy regex-экстрактора норм |
| `lex.eval.simple_v1@1.0.0` | LEX_EVALUATOR | roads | — | Обёртка evaluate_legality_impl |
| `roads.normpack.static_provider@1.0.0` | NORM_PACK_PROVIDER | roads | roads | Статические нормы для UA |
| `econ.ir.registry_fragment@1.0.0` | IR_FRAGMENT | econ | roads | Конфликтный `roads.kmh` (demo) |

Подробнее о roads: [roads/README.md](roads/README.md)

## econ — Демонстрационный пакет

Минималистичный пакет из одного IR-фрагмента. Определяет альтернативную единицу `roads.kmh` с priority=90 (ниже roads priority=100). Используется исключительно для тестирования conflict resolution:

- Проверка, что компонент с большим приоритетом побеждает
- Тестирование `DiscoveryPrecedencePolicy` при merge фрагментов
- Демонстрация изоляции: конфликт в IR не ломает остальные компоненты

Теги: `pack:econ`, `ir`, `conflict_demo`.

## Паттерн _StaticComponent

Все компоненты обёрнуты в `_StaticComponent(metadata, factory)` — frozen dataclass с ленивой инициализацией. Метаданные доступны сразу (для discovery), а factory вызывается только при `create()`. Тяжёлые зависимости (numpy, evaluate_legality_impl) импортируются внутри factory.

## Зависимости

```
packs/
├─► core/components          ComponentMetadata, Capability, discover_components
├─► ir/kernel/units          GenericUnit, UnitsRegistry
├─► ir/registry_fragments    RegistryFragmentMeta, UnitsFragment
├─► ir/norm_pack             NormPack, NormRule, RuleType
├─► foundry/methods/base     MethodSignature, SlotSpec, FidelityLevel, ComplexityClass
├─► fabric/claims/types      ClaimCandidate
├─► fabric/claims/backends   lex_norm_regex_v1.extract
└─► lex/legal_evaluation     evaluate_legality_impl
```

Внешние: `numpy` (lazy), `re`, `decimal` (stdlib).

## Тесты

`tests/test_packs_discovery_phase19.py` — dev scan обнаружение всех компонентов и эквивалентность entry points / dev scan.
