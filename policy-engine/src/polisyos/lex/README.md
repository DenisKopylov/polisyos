# Lex (`polisyos.lex`)

`polisyos.lex` покрывает runtime-юридический контур PolicyOS: сборку
`NormPack`, compliance-оценку, what-if симуляцию, read-only legal knowledge
graph и слой `lex -> intervention`, который переводит
provision-level правила в tunable policy/runtime artifacts.

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

## Where to Start

- Public facade / supported imports: `src/polisyos/lex/__init__.py` and `docs/reference/public-surface.md`
- Offline corpus / versioning path: `src/polisyos/data_forge/domains/legal/corpus/`
- NormPack / legality path: `src/polisyos/lex/normpack/` and `src/polisyos/lex/legal_evaluation/`
- Intervention mapping: `src/polisyos/lex/interventions.py` and `src/polisyos/lex/intervention_artifacts.py`

## Current State

- Last updated: 2026-05-02
- Files: 9 top-level Python files plus 6 subpackages
- Exports: 58 lazy exports in `__init__.py`
- Notable delta: root facade is runtime-only; offline legal corpus and batch entrypoints live in Data Forge.
