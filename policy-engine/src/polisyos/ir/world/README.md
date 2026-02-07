# ir.world — Семантическая модель мира

World определяет типизированную семантическую сеть знаний Policy Engine: документы, утверждения (claims), конфликты, события с provenance, оценки качества и доверия. Все объекты идентифицируются детерминированными content-addressed ID.

9 Python-файлов, ~50 экспортируемых символов.

## Архитектурная роль

```
Raw Data → Documents → Claims → Conflicts → Resolution → Knowledge Graph
               ↓           ↓         ↓           ↓              ↓
          Provenance     Trust    Validation   Consensus     Queryable
```

World — **граф знаний** с типизированными узлами (`NodeKind`) и рёбрами (`EdgeKind`). Fabric и Core используют эти типы для построения и запроса семантической сети; Scientist анализирует world state для формулировки политик.

## Структура

```
world/
├── __init__.py       # Реэкспорт всех публичных символов
├── abi.py            # NodeKind, EdgeKind, RESERVED_WORLD_PREFIXES_V1
├── claim.py          # Claim, ClaimSourceKind
├── event.py          # WorldEvent, ProvAgent, ProvActivity, EventKind
├── conflict.py       # ConflictSet, ConflictResolution, ConflictKind
├── doc.py            # DocFragment, DocMeta
├── quality.py        # QualityReport, QualityIssue
├── trust.py          # TrustAssessment, TrustTier
├── predicates.py     # World-константы: WORLD_KIND, WORLD_LABEL, rel()
└── ids.py            # Детерминированная генерация ID
```

## ABI: типы графа (`abi.py`)

**NodeKind** — типы узлов: `ARTIFACT`, `DOC_SOURCE`, `DOC_VERSION`, `DOC_FRAGMENT`, `CLAIM`, `CONFLICT_SET`, `TRUST_ASSESSMENT`, `QUALITY_REPORT`, `WORLD_EVENT`, `PROV_AGENT`, `PROV_ACTIVITY`.

**EdgeKind** — типы рёбер: `DOC_HAS_VERSION`, `DOC_HAS_FRAGMENT`, `CLAIM_CITES`, `CLAIM_DERIVED_FROM`, `CLAIM_IN_CONFLICT_SET`, `CONFLICT_RESOLVES_TO`, `CLAIM_SUPPORTS`, `CLAIM_CONTRADICTS`, `REPORT_ABOUT`, `PROV_USED`, `PROV_WAS_GENERATED_BY`, `PROV_WAS_DERIVED_FROM`, `PROV_WAS_ASSOCIATED_WITH`, `PROV_WAS_ATTRIBUTED_TO`.

`RESERVED_WORLD_PREFIXES_V1` — зарезервированные префиксы для ID: `artifact`, `doc`, `docv`, `frag`, `claim`, `cset`, `trust`, `quality`, `event`, `prov`.

## Основные модели

### Claim (`claim.py`)

Утверждение о факте: `predicate_id`, `subject_id`/`subject_text`, `value_text`/`value_decimal`, `unit_id`, `confidence` (0-1), `source_kind` (`ClaimSourceKind`: DOC / DATASET / SIMULATION / EXPERT / DERIVED), `citations`, `jurisdiction`, `valid_from`/`valid_to`.

### WorldEvent (`event.py`)

Событие с W3C PROV-совместимым provenance:
- `event_kind` (`EventKind`: FETCH_DOC, NORMALIZE_DOC, EXTRACT_CLAIMS, DETECT_CONFLICTS, RESOLVE_CONFLICTS, SIMULATE, VALIDATE)
- `activity` (`ProvActivity` + `ProvActivityType`)
- `agent` (`ProvAgent` + `ProvAgentType`: HUMAN, MODEL, SYSTEM, PIPELINE)
- `target_objects`, `generated_objects`, `invalidated_objects` (списки `WorldObjectRef`)

### ConflictSet (`conflict.py`)

Набор конфликтующих claims: `conflict_kind` (`ConflictKind`: VALUE_MISMATCH, UNIT_MISMATCH, DEFINITION_MISMATCH, TEMPORAL_MISMATCH, DUPLICATE), `claim_ids`, `key`.

`ConflictResolution`: `resolved_claim_ids`, `rejected_claim_ids`, `consensus_claim`, `resolution_method`, `confidence`, `resolver_agent`.

`ConflictSetResolution` / `ConflictResolutionInputs` / `ConflictResolutionCandidate` — контракты для pipeline разрешения.

### DocFragment, DocMeta (`doc.py`)

`DocFragment`: `fragment_id`, `doc_source_id`, `doc_version_id`, `content`, `content_type`, `locator` (→ `FragmentLocator` из `ir.citations`), `quality_score`.

`DocMeta`: `title`, `authors`, `publication_date`, `jurisdiction`, `doc_type`, `language`, `source_url`.

### QualityReport (`quality.py`)

`QualityReport`: `scope` (`QualityScope`), `target_object_id`, `issues: list[QualityIssue]`, `overall_score`, `assessor_agent`.

`QualityIssue`: `severity` (`QualityIssueSeverity`), `category`, `description`, `suggested_fix`.

### TrustAssessment (`trust.py`)

`TrustAssessment`: `target_id`, `tier` (`TrustTier`: VERIFIED / HIGH / MEDIUM / LOW / UNTRUSTED), `score` (0-1), `factors`, `assessed_by`, `valid_until`.

## Детерминированные ID (`ids.py`)

Все world-объекты получают стабильные ID через каноническую сериализацию + SHA256:

```python
stable_world_id_from_canon(prefix="claim", payload={...})  # → "claim.sha256_<64hex>"
```

Специализированные генераторы:

| Функция | Результат | Ключевые поля payload |
|---|---|---|
| `doc_source_id()` | `doc.sha256_...` | `canonical_url` xor `official_id` |
| `doc_version_id_from_raw_artifact()` | `docv.sha256_...` | `raw_artifact_id` |
| `doc_fragment_id()` | `frag.sha256_...` | `doc_version_id`, `locator`, `text_artifact_id` |
| `claim_id_from_payload()` | `claim.sha256_...` | `predicate_id`, `subject_id`, `value_*`, `citations`/`source_artifacts` |
| `world_event_id_from_payload()` | `event.sha256_...` | `event_kind`, `agent`, `activity`, `inputs`, `outputs` |
| `conflict_set_id_from_key()` | `cset.sha256_...` | `conflict_key` (64-char hex) |
| `trust_assessment_id_from_payload()` | `trust.sha256_...` | `policy_id`, `target_world_id`, `score`, `tier` |
| `quality_report_id_from_payload()` | `quality.sha256_...` | `scope`, `policy_id`, `metrics`, `issues` |

Свойства: один и тот же payload всегда даёт один и тот же ID; Enum-значения нормализуются; None-поля отбрасываются; Pydantic-модели сериализуются через `model_dump()`.

## Предикаты (`predicates.py`)

Константы для world-графа: `WORLD_KIND`, `WORLD_LABEL`, `WORLD_ARTIFACT_ID`, `WORLD_PROPS_REF`, `WORLD_REL_PREFIX`. Утилита `rel(edge_kind)` — создание имени ребра.

## Зависимости

**Входящие:**
- `ir.kernel.base` — `KernelModel`, `ARTIFACT_ID_PATTERN`
- `ir.canon` — `to_canonical_bytes()` для генерации ID
- `ir.citations` — `CitationRef`, `FragmentLocator`

**Исходящие (кто использует world):**
- `fabric/claims/`, `fabric/world/`, `fabric/docs/` — CRUD и запросы к world-данным
- `core/` — построение семантической сети
- `scientist/` — анализ world state

## Тестирование

```bash
pytest tests/unit/test_ir_world_*.py
pytest tests/contract/test_ir_world_semantics.py
```
