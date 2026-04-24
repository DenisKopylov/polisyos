# World (`polisyos.ir.world`)

`polisyos.ir.world` описывает канонические world-graph contracts: документы,
claims, provenance events, conflict sets, trust assessments и quality reports.
Это IR boundary для knowledge/world pipelines; хранение и querying остаются в
`fabric`, а `world` фиксирует типы и deterministic identifiers.

## Роль в системе

- **Зависит от:** `polisyos.ir.artifacts`, canonical ID helpers внутри `polisyos.ir`
- **Используется в:** `polisyos.fabric.claims`, `polisyos.fabric.world`, `polisyos.lex`, `polisyos.scholar`, `polisyos.scientist`
- World contracts стандартизируют evidence graph, который затем потребляют trust/conflict and analysis pipelines.

## Ключевые концепции

- **World ABI** — `NodeKind`, `EdgeKind` и reserved prefixes задают графовую совместимость.
- **Document and claim contracts** — `DocMeta`, `DocFragment`, `Claim` формируют базовые evidence units.
- **Conflict resolution** — `ConflictSet` и related resolution models нормализуют competing claims.
- **Provenance events** — `WorldEvent`, `ProvAgent`, `ProvActivity` описывают lineage изменений.
- **Trust and quality** — отдельные contracts фиксируют scored assessments и issue ordering.
- **Deterministic IDs** — `ids.py` вычисляет stable identifiers из canonical payload.

## Public API

| Type/Function                                              | Description                                       |
| ---------------------------------------------------------- | ------------------------------------------------- |
| `DocMeta`, `DocFragment`                                   | Контракты документа и его canonical fragments     |
| `Claim`, `ClaimSourceKind`                                 | Evidence claim и тип источника                    |
| `ConflictSet`, `ConflictSetResolution`                     | Canonical representation claim conflicts          |
| `WorldEvent`, `WorldObjectRef`                             | Provenance events и ссылки на world objects       |
| `TrustAssessment`, `QualityReport`                         | Trust/quality evaluation contracts                |
| `claim_id_from_payload()`, `world_event_id_from_payload()` | Deterministic ID builders для core world entities |

Full reference: [docs/reference/ir/](../../../../docs/reference/ir/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Files: 11 Python files
- Exports: 43 public names in `__init__.py`
- Delta status: кодовая поверхность стабильна; README обновлен, чтобы точнее зафиксировать current world ABI and deterministic ID surface
