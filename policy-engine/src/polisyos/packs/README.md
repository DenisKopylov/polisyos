# polisyos.packs

`polisyos.packs` содержит встроенные доменные наборы компонентов (component packs), которые
подключаются в единый discovery pipeline.

Сейчас в директории 2 пакета и 7 компонентов:
- `roads` (6 компонентов)
- `econ` (1 компонент, конфликтный demo)

## Роль в системе

Паки не задают новые интерфейсы. Их задача: собрать готовые реализации поверх существующих
контрактов из `core`, `ir`, `foundry`, `scholar`, `fabric`, `lex`.

```
core/components + ir + foundry + fabric + lex
                  |
                  v
        polisyos/packs/* (готовые реализации)
```

Это reference-слой для:
- быстрого старта локальных сценариев;
- проверки discovery и conflict resolution;
- интеграционных тестов компонентной системы.

## Структура

```
packs/
├── __init__.py
├── README.md
├── roads/
│   ├── README.md
│   ├── components.py
│   ├── ir_fragments.py
│   ├── foundry_methods.py
│   ├── scholar_extractors.py
│   ├── lex_evaluators.py
│   └── norms_provider.py
└── econ/
    ├── README.md
    ├── components.py
    └── ir_fragments.py
```

`packs/__init__.py` использует lazy import через `__getattr__`, экспортируя `roads` и `econ`.

## Как компоненты обнаруживаются

Каждый пакет экспортирует `__polisyos_components__` (список компонентов с метаданными).

1. Entry points (`policy-engine/pyproject.toml`):
- `polisyos.ir_fragments`
- `polisyos.foundry_methods`
- `polisyos.scholar_extractors`
- `polisyos.lex_extractors`
- `polisyos.lex_evaluators`
- `polisyos.norm_pack_providers`

2. Dev scan:
- `discover_components(include_dev_scan=True, dev_scan_paths=[...])`
- скан `components.py` в указанных путях и их непосредственных подпапках

По умолчанию `DiscoveryPrecedencePolicy` задает `dev_scan_wins_over_entry_points=True`.

## Каталог компонентов

| Component ID | Kind | Пак | Назначение |
|---|---|---|---|
| `roads.ir.registry_fragment@1.0.0` | IR_FRAGMENT | roads | Регистрирует `roads.kmh` |
| `roads.method.speed_cap@1.0.0` | FOUNDRY_METHOD | roads | Ограничение скорости в симуляции |
| `roads.scholar.speed_limit@1.0.0` | SCHOLAR_EXTRACTOR | roads | Regex-извлечение лимита скорости |
| `lex.norm_extractor.regex_v1@1.0.0` | LEX_EXTRACTOR | roads | Обертка legacy norm regex extractor |
| `lex.eval.simple_v1@1.0.0` | LEX_EVALUATOR | roads | Обертка `evaluate_legality_impl` |
| `roads.normpack.static_provider@1.0.0` | NORM_PACK_PROVIDER | roads | Статический NormPack для UA |
| `econ.ir.registry_fragment@1.0.0` | IR_FRAGMENT | econ | Конфликтный demo-фрагмент `roads.kmh` |

## Связь с другими директориями

- `src/polisyos/core/components`: типы метаданных, capability flags, discovery.
- `src/polisyos/ir/*`: единицы и `NormPack` модели.
- `src/polisyos/foundry/methods/*`: сигнатуры/контракты методов.
- `src/polisyos/fabric/claims/*`: тип `ClaimCandidate` и regex backend.
- `src/polisyos/lex/legal_evaluation/*`: функция оценки легальности.

Проверка пака как целого: `policy-engine/tests/test_packs_discovery.py`.

## Поддиректории

- `roads`: полный доменный пакет, см. `roads/README.md`.
- `econ`: минимальный конфликтный пакет, см. `econ/README.md`.
