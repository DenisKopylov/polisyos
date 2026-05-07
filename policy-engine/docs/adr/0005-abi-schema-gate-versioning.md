# ADR-0005: ABI Versioning Gate via JSON Schema Snapshots

- **Дата**: 2026-02-06
- **Статус**: Accepted
- **Решение**: Ввести обязательный ABI CI gate на основе коммитимых JSON Schema snapshots, семантического diff и проверки `schema_version` major bump для breaking-изменений.

## Контекст

Контрактные модели в `polisyos.ir.*` и словари/enum world ABI (`EdgeKind`, `NodeKind`) используются как межслойный ABI для Foundry, Scientist, Lex, Scholar и Fabric.

До внедрения этого ADR:

- `tools/quality/diagnostics/gen_schema.py` был одиночным и ориентирован на устаревший `PolicySurfaceIR`.
- Отсутствовал семантический diff breaking/non-breaking.
- Не было автоматической проверки корректного version bump при breaking-изменениях.

## Решение

1. Реестр ABI-моделей хранится в `src/polisyos/schemas/abi_models.py`.
2. Snapshot-артефакты хранятся в `schemas/snapshots/{ir,fabric}` с `_manifest.json`.
3. `tools/quality/diagnostics/gen_schema.py`:

   - генерирует snapshots по ABI registry,
   - поддерживает `--check`,
   - пишет manifest с полями `priority`, `compat_mode`, `schema_version`, `sha256_full`, `sha256_semantic`.
4. `tools/quality/diagnostics/abi_diff.py`:

   - строит семантический diff,
   - классифицирует изменения,
   - проверяет major bump при breaking (`p0`),
   - формирует JSON/Markdown/GitHub report.
5. CI workflow `.github/workflows/abi.yml`:

   - генерирует current snapshots,
   - сравнивает с baseline snapshots из base SHA PR,
   - публикует sticky report,
   - блокирует merge при verdict `FAIL`.

## Compatibility Profiles

В `src/polisyos/schemas/abi_models.py` каждый ABI-entry имеет `compat_mode`:

- `strict`: добавление полей считается breaking (актуально для контрактов, где потребители могут валидировать с `additionalProperties=false`).
- `tolerant`: optional additive изменения допускаются как compatible.

## Versioning Rules

- Breaking change (`p0`) требует major bump: `X.Y -> (X+1).0` или `major` > baseline major.
- Breaking change (`p1/p2`) сигнализируется warning.
- Metadata-only изменения (`title/description/...`) не требуют bump.

## Rename Handling

`abi_diff` сначала сопоставляет модели по `abi_key`, затем `aliases`, затем по `sha256_semantic`/similarity fallback.

## Последствия

### Плюсы

- Раннее обнаружение ABI regressions до merge.
- Проверяемая история контрактных изменений.
- Явная политика strict/tolerant compatibility.

### Минусы

- Дополнительный шаг для разработчика: поддерживать snapshots в коммите.
- Увеличение объема репозитория (schema snapshots + manifests).

### Риски

- Обновления Pydantic/Python могут менять схему генерации.
- Ложные предупреждения на edge-cases классификации.

## Митигации

- Фиксировать среду CI (Python 3.11) и обновлять snapshots атомарно.
- Поддерживать unit-тесты на `abi_diff` классификацию.
- Использовать `compat_mode` per-entry для точной семантики.

## Related Decisions

- Extended by: ADR-0114 (schema registry and evolution rules), ADR-0123
  (ArtifactRef governance metadata).
