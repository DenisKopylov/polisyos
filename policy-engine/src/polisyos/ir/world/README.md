# ir.world

`ir.world` — канонические контракты семантического world-graph слоя: документы, claims, конфликты, provenance-события, trust и quality отчёты.

Это контрактный слой; хранение и запросы реализуются в `fabric`.

## Роль в архитектуре

```text
fabric claims/world pipelines
            │
            ▼
      ir.world contracts
            │
            ├─► lex (norm pipelines)
            ├─► scholar (knowledge artifacts)
            └─► scientist (analysis/trust consumers)
```

Контекст IR: [`../README.md`](../README.md)

## Состав

| Файл | Что содержит |
|---|---|
| `abi.py` | `NodeKind`, `EdgeKind`, `RESERVED_WORLD_PREFIXES_V1` |
| `doc.py` | `DocMeta`, `DocFragment` |
| `claim.py` | `Claim`, `ClaimSourceKind` |
| `conflict.py` | `ConflictSet`, `ConflictResolution*` |
| `event.py` | `WorldEvent`, provenance agent/activity |
| `trust.py` | `TrustAssessment`, `TrustTier` |
| `quality.py` | `QualityReport`, issue severity/scope |
| `ids.py` | deterministic ID builders через canonical hash |
| `predicates.py` | world predicate constants + `rel()` |

## Ключевые инварианты

- Deterministic world IDs: `<prefix>.sha256_<hex64>`.
- `DocMeta`: ровно одно из `canonical_url` или `official_id`.
- `Claim`:
  - нужен `subject_id` или `subject_text`;
  - для `source_kind=doc` обязательны `citations`;
  - для остальных источников обязательны `source_artifacts`.
- `ConflictSet.member_claim_ids` должен быть отсортирован и уникален.
- `ConflictResolution.candidates` должен быть отсортирован по `score_total desc`, затем `claim_id asc`; winner — первый.
- `TrustAssessment` и `QualityReport` верифицируют ID по canonical payload.
- `QualityReport.issues` должен быть детерминированно отсортирован.

## Детерминированные ID-функции

- `doc_source_id()`
- `doc_version_id_from_raw_artifact()`
- `doc_fragment_id()`
- `claim_id_from_payload()`
- `world_event_id_from_payload()`
- `conflict_set_id_from_key()`
- `trust_assessment_id_from_payload()`
- `quality_report_id_from_payload()`

## Связи с другими директориями

| Директория | Использование |
|---|---|
| `fabric/claims` | extraction/normalize/conflicts/persist/world-events |
| `fabric/world` | materialization/query/storage |
| `lex/` | document structuring + world predicates/ids |
| `scholar/` | trust/event контракты в orchestration |
| `core/contracts` | shared schema compatibility |

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

## Проверки

```bash
pytest /Users/deniskopylov/polisyos/policy-engine/tests/contract/test_world_abi_contract.py
pytest /Users/deniskopylov/polisyos/policy-engine/tests/fabric/test_world_store.py
pytest /Users/deniskopylov/polisyos/policy-engine/tests/fabric/test_world_materialization.py
```
