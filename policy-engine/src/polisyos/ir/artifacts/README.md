# ir.artifacts

`ir.artifacts` — единый контрактный слой для CAS I/O в `ir`.

## Что здесь

| Файл | Назначение |
|---|---|
| `contracts.py` | `ArtifactID`, `InputRef`, `SchemaInfo`, `PutOptions`, `ArtifactStore` protocol |
| `io.py` | `put_json_artifact()`, `get_json_artifact()`, normalize helpers |
| `__init__.py` | публичный экспорт контрактов и I/O функций |

## Ключевые детали

- `ArtifactID` строго валидируется как `sha256:<64 lowercase hex>`.
- `ArtifactStore` ожидает методы `put_json(obj, opts, canon_spec)` и `get_bytes(artifact_id)`.
- `put_json_artifact()`:
  - нормализует input refs;
  - прикладывает schema/canon metadata;
  - возвращает стандартизированный artifact ref (`artifact_id`, `kind`, `media_type`).
- `get_json_artifact()` восстанавливает объект через canonical decode (`from_canonical_bytes`).

## Где используется

- `ir.analytics.*` persist/load функции.
- `ir.refs` typed references к артефактам.
- `fabric` и `core` компоненты, работающие с CAS-артефактами.
