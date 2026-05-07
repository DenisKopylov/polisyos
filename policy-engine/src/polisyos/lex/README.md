# Lex (`polisyos.lex`)

`polisyos.lex` покрывает runtime-юридический контур PolicyOS: сборку
`NormPack`, compliance-оценку, what-if симуляцию, read-only legal knowledge
graph и слой `lex -> intervention`, который переводит
provision-level правила в tunable policy/runtime artifacts.

## Purpose

Use `polisyos.lex` for runtime legal evaluation and NormPack-backed policy
reasoning. Offline legal corpus extraction and batch graph construction live in
Data Forge; Lex reads those published artifacts and turns legal provisions into
typed runtime/evaluation contracts.

## Роль в системе

- **Зависит от:** `polisyos.ir`, `polisyos.core`, `polisyos.fabric`, `polisyos.foundry`
- **Используется в:** `polisyos.scientist`, `polisyos.runtime`, governance and policy-design flows
- Модуль связывает опубликованные legal artifacts, factual world state и policy execution surface через CAS, fact log и typed contracts.

## Ключевые концепции

- **Compliance path** — `read_api.legal -> normpack -> legal_evaluation -> simulator` формирует юридическую проверку и change proposals.
- **Knowledge path** — Data Forge legal batch публикует DuckDB/HNSW graph, а `lex.knowledge` читает его без write-side логики.
- **Intervention mapping** — `interventions.py` и `intervention_artifacts.py` компилируют provision directives в intervention knobs, temporal sequences и strategic-response specs.
- **Version-aware reads** — `resolve_active_version()` читает Data Forge version-index artifacts через `polisyos.data_forge.read_api.legal`.
- **Component-driven extensibility** — providers, evaluators и extractors поднимаются через registry/entry points, а не хардкодятся в orchestration.
- **Artifact-first execution** — ключевые выходы сохраняются как `lex.*` artifacts и world events с provenance.

## Public API

| Type/Function                                                | Description                                                       |
| ------------------------------------------------------------ | ----------------------------------------------------------------- |
| `resolve_active_version()`                                   | Query active-version indexes for legal docs through Data Forge read API |
| `assemble_norm_pack()`                                       | Assemble a `NormPack` through provider or pipeline path           |
| `evaluate_legality()`                                        | Produce `lex.legal_report` and optional change proposals          |
| `NormPackMutator`, `diff_norm_packs()`, `NormImpactAnalyzer` | What-if diff and impact analysis for norm changes                 |
| `LegalKnowledgeGraph`                                        | Read-only search API over the offline legal graph                 |
| `LexInterventionCompiler`, `TemporalInterventionSequencer`   | Compile legal provisions into intervention/runtime artifacts      |

Full reference: [docs/reference/lex/](../../../docs/reference/lex/index.md)

## Internal Layout

- `__init__.py` owns the runtime-only public facade.
- `normpack/` owns NormPack assembly and provider contracts.
- `legal_evaluation/` owns legality report generation and compliance checks.
- `knowledge/` owns read-only access to Data Forge legal graph artifacts.
- `interventions.py` and `intervention_artifacts.py` own provision-to-policy
  intervention mapping.
- Offline legal batch and corpus write paths belong to
  `polisyos.data_forge.domains.legal`, not this package.

## Extension Points

- NormPack providers use the `polisyos.lex_normpacks` entry-point group in
  [architecture/extension_points.toml](../../../architecture/extension_points.toml).
- The legacy `polisyos.norm_pack_providers` group remains compatibility-only
  under the same extension contract.
- Use [normpack/AUTHORING.md](normpack/AUTHORING.md) before adding provider or
  assembly surfaces.

## Where to Start

- Public facade / supported imports: `src/polisyos/lex/__init__.py` and `docs/reference/public-surface.md`
- Offline corpus / versioning path: `src/polisyos/data_forge/domains/legal/corpus/`
- NormPack / legality path: `src/polisyos/lex/normpack/` and `src/polisyos/lex/legal_evaluation/`
- Intervention mapping: `src/polisyos/lex/interventions.py` and `src/polisyos/lex/intervention_artifacts.py`

## Tests

Run from the repository root:

```bash
uv run pytest tests/unit/lex -q
uv run pytest tests/unit/data_forge/legal_batch -q
```

Run Data Forge legal batch tests when a Lex change consumes newly published
legal corpus or graph artifacts.

## Operability Links

- [Lex component SLO](../../../ops/components/lex/slo.yaml)
- [Lex component runbooks](../../../ops/components/lex/runbooks.md)
- [Lex pipeline explanation](../../../docs/explanation/lex-pipeline.md)
- [Lex production runbook](../../../docs/runbooks/lex-production-140k.md)
- [Configure Lex pipeline how-to](../../../docs/how-to/configure-lex-pipeline.md)

## Known Shims/Deprecations

- No active package-local Lex import shims are registered in
  [architecture/shims.toml](../../../architecture/shims.toml) as of 2026-05-06.
- The legacy `polisyos.norm_pack_providers` extension group is compatibility
  support for `polisyos.lex_normpacks`; new providers should use the Lex group.
- Offline legal preprocessing imports must stay in Data Forge; do not
  reintroduce Lex-owned batch write paths.

## Current State

- Last updated: 2026-05-06
- Files: 9 top-level Python files plus 6 subpackages
- Exports: 58 lazy exports in `__init__.py`
- Notable delta: root facade is runtime-only; offline legal corpus and batch entrypoints live in Data Forge.
