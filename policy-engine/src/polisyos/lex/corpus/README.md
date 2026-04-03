# Corpus (`polisyos.lex.corpus`)

`polisyos.lex.corpus` подготавливает юридический корпус для downstream legal
pipelines: ingest документов, extraction структуры и version-aware индексы,
через которые `normpack` и `legal_evaluation` получают активную редакцию
документа вместо ad-hoc выбора по дате или id.

## Роль в системе

- **Зависит от:** `polisyos.fabric.docs`, `polisyos.fabric.world`, `polisyos.core.artifacts`, `polisyos.ir.world`
- **Используется в:** `polisyos.lex.normpack`, `polisyos.lex.legal_evaluation`, intervention and provenance flows
- Пакет формирует canonical corpus artifacts: provision index, version index и document source props.

## Ключевые концепции

- **Ingest wrapper** — `ingest_legal_doc_bytes()` обогащает `DocMeta.props.lex`, фиксирует pipeline metadata и пишет world events.
- **Structure extraction** — `build_legal_structure()` строит hierarchy `article -> part -> point -> subpoint` и публикует `ProvisionIndexV1`.
- **Temporal versioning** — `build_version_index()` и `resolve_active_version()` используют `effective window`, а не fallback на произвольную опубликованную версию.
- **Index artifacts** — `ProvisionIndexV1`, `VersionIndexV1` и `DocSourcePropsV1` остаются CAS-friendly surface между ingest и normpack.
- **Quality issues** — duplicate articles, non-monotonic numbering и missing structure остаются явными quality markers, а не скрытыми heuristic rewrites.

## Public API

| Type/Function | Description |
|---|---|
| `ingest_legal_doc_bytes()` | Ingest legal document bytes and enrich Lex corpus metadata |
| `build_legal_structure()` | Extract legal structure and persist `ProvisionIndexV1` |
| `build_version_index()` | Build `VersionIndexV1` and `DocSourcePropsV1` from fact-log evidence |
| `resolve_active_version()` | Resolve the active document version using temporal envelopes |
| `ProvisionIndexV1`, `VersionIndexV1`, `DocSourcePropsV1` | Persistent corpus index artifacts |
| `load_*()` / `persist_*()` helpers | CAS persistence helpers for corpus indexes |

Full reference: [docs/reference/lex/](../../../../docs/reference/lex/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 5 Python files
- Exports: 15 symbols in `__init__.py`
- Notable delta: `versioning.py` now requires resolved temporal envelopes and no longer silently falls back to `published_at`
