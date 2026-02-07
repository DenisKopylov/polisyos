# Catalog — Data Contract Catalog

Metric-level система контрактов, обеспечивающая type safety и предотвращающая hallucination имен метрик в AI-driven симуляциях.

## Проблема и решение

Scientist Agent может «галлюцинировать» несуществующие метрики. Catalog решает это через цепочку:

```
Raw Query → Fuzzy Search → Disambiguation → Hash-Locked Binding → Type-Safe UDF Query
   "GDP"      candidates      human/auto       MetricBinding        DataViewRequest
```

## Структура

```
catalog/
├── contract.py      # DataContract, DataContractCollection, DataType, Granularity, PIITier
├── binding.py       # MetricBinding — frozen, hash-locked ссылка на контракт
├── registry.py      # DataContractRegistry — lazy loading, binding cache, hash validation
├── search.py        # MetricSearcher — fuzzy search с Jaccard similarity + disambiguation
└── validate.py      # load_contract_collection() — загрузка и Pydantic-валидация из JSON
```

## Ключевые типы

### DataContract

Каноническое определение метрики:

- **Identity:** `metric_id` (e.g. `us.macro.gdp_nominal`), `display_name`, `description`
- **Type info:** `dtype` (int/float/string/boolean/datetime/array/json), `unit`, `granularity` (tick → aggregate)
- **Structure:** `dimensions` (["region", "sector"]), `valid_range`
- **Provenance:** `source_system`, `source_table`, `source_column`, `jurisdiction`
- **Privacy:** `pii_tier` (none/low/medium/high/critical)
- **Search:** `aliases`, `tags`
- **Lifecycle:** `deprecated`, `superseded_by`

### MetricBinding

Immutable frozen dataclass — то, что получает Scientist:

```python
@dataclass(frozen=True, slots=True)
class MetricBinding:
    metric_id: str
    unit: str | None
    dtype: str
    dimensions: tuple[str, ...]
    pii_tier: str
    contract_hash: str  # SHA-256[:16] полного контракта
```

Hash-lock гарантирует: если контракт изменился, binding невалиден → silent drift невозможен.

### MetricSearcher

Fuzzy поиск с confidence scoring:

- **Exact match** → alias index (O(1))
- **Fuzzy match** → Jaccard similarity на токенах + substring/prefix boosts
- **Confidence thresholds:** >0.7 — auto-resolve, 0.5–0.7 — предложение опций, <0.5 — переформулировка

### DataContractRegistry

Управление контрактами с lazy loading и binding cache:

```python
registry = DataContractRegistry(Path("data/curated"))
contract = registry.get("us.macro.gdp_nominal")
binding = registry.get_binding("us.macro.gdp_nominal")
contract = registry.validate_binding(binding)  # hash check
```

## PII-классификация

| Tier | Доступ | Требования |
|------|--------|-----------|
| none | Без ограничений | — |
| low | Basic auth | Group by dimensions |
| medium | k-anonymization | k >= 5 |
| high | Audit logging | Explicit approval |
| critical | PII/PHI | Consent required |

## Связи

- **Scientist** — получает MetricBinding через search/resolve, использует для type-safe UDF-запросов
- **Claims** — валидация извлеченных claims против контрактов (dtype, unit)
- **Ingestion** — автогенерация draft-контрактов из схем датасетов
