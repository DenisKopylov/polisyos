# ir.world — Контракты семантической world-модели

`ir.world` описывает типизированные объекты графа знаний в Policy Engine: документы, claims, конфликты, provenance-события, trust/quality оценки и deterministic world IDs.

Это **контрактный слой**, а не хранилище и не execution-движок.

## Роль в архитектуре

```text
Fabric pipelines (docs/claims/conflicts/materialization)
            │
            ▼
      ir.world contracts
            │
            ├─► world persistence/query (DuckDB/Kuzu через fabric)
            ├─► Lex (norm/legal pipelines)
            └─► Scholar/Scientist (knowledge artifacts)
```

Подробнее про общий контекст IR: [`../README.md`](../README.md)

## Состав директории

```text
world/
├── abi.py         # NodeKind / EdgeKind / reserved prefixes
├── doc.py         # DocMeta / DocFragment
├── claim.py       # Claim + source-kind rules
├── conflict.py    # ConflictSet + ConflictResolution contracts
├── event.py       # WorldEvent + provenance agent/activity
├── trust.py       # TrustAssessment + tier/score contracts
├── quality.py     # QualityReport + deterministic issue ordering
├── ids.py         # stable world ID builders (sha256 over canonical payload)
├── predicates.py  # world predicate constants and rel()
└── __init__.py    # публичные re-exports
```

## Ключевые модели

### ABI графа (`abi.py`)

- `NodeKind`: `artifact`, `doc.source`, `doc.version`, `doc.fragment`, `claim`, `conflict_set`, `trust.assessment`, `quality.report`, `world.event`, `prov.*`.
- `EdgeKind`: связи документов, claims, конфликтов и provenance.
- `RESERVED_WORLD_PREFIXES_V1`: зарезервированные ID-префиксы (`doc`, `docv`, `frag`, `claim`, `cset`, `trust`, `quality`, `event`, ...).

### Документы (`doc.py`)

- `DocMeta`: метаданные версии документа; строгое правило:
  ровно одно из `canonical_url` или `official_id`.
- `DocFragment`: фрагмент документа + `FragmentLocator` + `text_hash`.

### Claims (`claim.py`)

- `Claim` хранит `predicate_id`, субъект (`subject_id` или `subject_text`), значение, confidence, source-kind и provenance refs.
- Правила валидации:
  - должен быть `subject_id` или `subject_text`;
  - для `source_kind=doc` обязательны `citations`;
  - для остальных источников обязательны `source_artifacts`;
  - `valid_to >= valid_from`.

### Конфликты (`conflict.py`)

- `ConflictSet` с `conflict_key` (sha256 hex), `member_claim_ids`, optional resolution.
- `conflict_set_id` обязан совпадать с вычисленным `conflict_set_id_from_key()`.
- `ConflictResolution`:
  - кандидаты должны быть отсортированы по `score_total desc`, затем `claim_id asc`;
  - `winner_claim_id` должен совпадать с первым кандидатом.

### Provenance-события (`event.py`)

- `WorldEvent`: `event_kind`, `agent`, `activity`, `inputs`, `outputs`.
- `ProvActivity` валидирует временную согласованность (`ended_at >= started_at`).
- `WorldObjectRef` требует хотя бы `world_id` или `artifact_id`.

### Trust и Quality

- `TrustAssessment` (`trust.py`): `score` в `[0,1]`, `tier` (`high|medium|low`), ID верифицируется по canonical payload.
- `QualityReport` (`quality.py`): issue list должен быть детерминированно отсортирован; ID также верифицируется по canonical payload.

## Детерминированные ID (`ids.py`)

`ids.py` строит стабильные world IDs через canonical serialization + `sha256`:

- `doc_source_id()`
- `doc_version_id_from_raw_artifact()`
- `doc_fragment_id()`
- `claim_id_from_payload()`
- `world_event_id_from_payload()`
- `conflict_set_id_from_key()`
- `trust_assessment_id_from_payload()`
- `quality_report_id_from_payload()`

Формат world ID: `<prefix>.sha256_<hex64>`.

## Инварианты и особенности

- Deep float-guard:
  большинство моделей запрещают `float` в произвольных payload/props через `reject_floats_deep`.
- Deterministic payload discipline:
  ID-поля в `TrustAssessment`, `QualityReport`, `ConflictSet` проверяются как функция содержимого.
- Deterministic ordering:
  сортировка/уникальность требуется для `member_claim_ids`, ranking-кандидатов и `quality.issues`.
- Чёткая граница ответственности:
  `ir.world` определяет контракты и правила, а materialization/query реализованы в `fabric/world`.

## Связи с другими директориями

| Директория | Как использует `ir.world` |
|---|---|
| `fabric/` | основной потребитель (`claims/*`, `world/store/*`, materialization/query) |
| `lex/` | legal/norm pipelines используют world entities |
| `scholar/` | сборка knowledge artifacts и событий |
| `scientist/` | точечные trust/world контракты |
| `core/` | отдельные shared contracts и валидации |

## Минимальный пример

```python
from polisyos.ir.world.ids import claim_id_from_payload

claim_id = claim_id_from_payload(
    claim_payload={
        "predicate_id": "inflation_rate",
        "subject_text": "ua",
        "value_text": "12.5",
        "source_kind": "dataset",
        "source_artifacts": ["sha256:" + "a" * 64],
    }
)
```

## Рекомендуемые проверки

```bash
pytest /Users/deniskopylov/polisyos/policy-engine/tests/contract/test_world_abi_contract.py
pytest /Users/deniskopylov/polisyos/policy-engine/tests/fabric/test_world_store.py
pytest /Users/deniskopylov/polisyos/policy-engine/tests/fabric/test_world_materialization.py
```
