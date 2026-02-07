# roads — Дорожный компонентный пакет

Reference implementation полного доменного пакета PolicyOS: от определения единиц измерения до оценки легальности. 6 компонентов, покрывающих все слои стека.

## Архитектура

Компоненты образуют функциональную цепочку — выход одного слоя питает следующий:

```
ir_fragments.py          roads.kmh (единица измерения)
       │
       ├──► foundry_methods.py     speed_cap: clamp скорости по порогу
       ├──► scholar_extractors.py  regex → ClaimCandidate (speed limit)
       └──► norms_provider.py      статический NormPack (UA)
                   │
                   ├──► lex_evaluators.py   evaluate_legality_impl
                   └──► scholar_extractors.py (lex_norm_regex_v1 extractor)
```

Все компоненты агрегируются в `components.py` → `__polisyos_components__` (6 штук).

## Компоненты

### IR Fragment — `roads.ir.registry_fragment@1.0.0`

Определяет единицу `roads.kmh` через `UnitsFragment` с priority=100. Все остальные компоненты roads опираются на эту единицу. Побеждает конфликтный фрагмент из econ (priority=90).

- **ABI:** `ir_abi:1.x` | **Capabilities:** `IR_FRAGMENT` | **Provides:** `ir.registry.units`

### Foundry Method — `roads.method.speed_cap@1.0.0`

Симуляционный метод: поэлементный clamp массива скоростей по configurable cap (дефолт 50 km/h). Использует `np.minimum` — чистая функция без побочных эффектов.

- **Сигнатура:** `speed_input (VECTOR, kmh)` → `speed_output (VECTOR, kmh)`
- **Fidelity:** LOW | **Complexity:** O(N) | **ABI:** `foundry_methods_api:>=3.5.0,<4.0.0`
- **Capabilities:** `FOUNDRY_METHOD | FOUNDRY_COMPILE`
- numpy импортируется лениво внутри factory

### Scholar Extractor — `roads.scholar.speed_limit@1.0.0`

Regex-экстрактор ограничений скорости из плоского текста. Поддерживает английский и украинский:

```
speed limit 50 → 50    max speed: 80 → 80    максимальна швидкість 60 → 60
```

Паттерн: `(?:speed\s*limit|max\s*speed|максимальн\w*\s+швидк\w*)[^\d]*(\d{2,3})`

Возвращает `ClaimCandidate` с `predicate_id="roads.speed_limit_kmh"`, `unit_id="roads.kmh"`, `qualifiers={"op": "<="}`.

- **Languages:** en, uk | **Capabilities:** `SCHOLAR_EXTRACTOR | SCHOLAR_ENRICH`

### Lex Extractor — `lex.norm_extractor.regex_v1@1.0.0`

Обёртка над legacy backend `fabric.claims.backends.lex_norm_regex_v1.extract`. Domain-agnostic — используется norms_provider для декларации extractor_id в NormRule.

- **Capabilities:** `LEX_EXTRACTOR` | Deferred import

### Lex Evaluator — `lex.eval.simple_v1@1.0.0`

Обёртка над `lex.legal_evaluation.evaluate.evaluate_legality_impl`. Сравнивает извлечённые claims с нормами и возвращает оценку легальности.

- **Capabilities:** `LEX_EVALUATOR | LEX_EVALUATE` | Deferred import

### Norm Pack Provider — `roads.normpack.static_provider@1.0.0`

`RoadsStaticNormPackProvider` — frozen dataclass, возвращающий hardcoded `NormPack` для UA юрисдикции. Содержит 2 нормы:

| norm_id | Тип | Описание | Оператор | Значение |
|---|---|---|---|---|
| `roads.static.speed_limit` | OBLIGATION | Макс. скорость в городе | <= | 50 km/h |
| `roads.static.lane_width` | OBLIGATION | Мин. ширина полосы | >= | 3.5 m |

Обе нормы ссылаются на `lex.norm_extractor.regex_v1@1.0.0` как extractor backend.

- **Jurisdictions:** ua | **Capabilities:** `NORM_PACK_PROVIDER | CAS_WRITE`
- `_StaticComponent` хранит **инстанс** провайдера (не factory) — провайдер stateless

## Зависимости

```
roads/
├─► core/components           ComponentMetadata, Capability, ComponentId, ComponentKind
├─► ir/kernel/units           GenericUnit, UnitsRegistry
├─► ir/registry_fragments     RegistryFragmentMeta, UnitsFragment
├─► ir/norm_pack              NormPack, NormRule, NormRef, RuleType
├─► foundry/methods/base      MethodSignature, SlotSpec, SlotType, Unit, FidelityLevel, ComplexityClass
├─► fabric/claims/types       ClaimCandidate
├─► fabric/claims/backends    lex_norm_regex_v1.extract  (deferred)
└─► lex/legal_evaluation      evaluate_legality_impl     (deferred)
```

## Особенности реализации

- **Lazy imports:** numpy, evaluate_legality_impl, lex_norm_regex_v1 импортируются только при вызове `create()` — метаданные компонентов доступны без тяжёлых зависимостей
- **Priority=100** для IR-фрагмента гарантирует победу над econ (priority=90) при conflict resolution
- **Статические данные:** нормы и regex hardcoded для упрощения демонстраций; для production потребуется динамическая загрузка из базы и temporal validity
- **Regex ограничения:** извлекает только числа 2-3 цифр; не обрабатывает диапазоны ("50-70 km/h"), условия ("в дождь: 40") и контекстные ограничения ("для грузовых")
- **Нет кэширования:** каждый вызов `get_static_norm_pack()` создаёт новый объект NormPack
