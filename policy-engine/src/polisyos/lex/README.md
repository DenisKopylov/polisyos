# Lex (`polisyos.lex`)

`polisyos.lex` покрывает юридический контур PolicyOS: ingest и versioning
нормативных документов, сборку `NormPack`, compliance-оценку, what-if симуляцию,
offline knowledge graph и новый слой `lex -> intervention`, который переводит
provision-level правила в tunable policy/runtime artifacts.

## Роль в системе

- **Зависит от:** `polisyos.ir`, `polisyos.core`, `polisyos.fabric`, `polisyos.foundry`
- **Используется в:** `polisyos.scientist`, `polisyos.runtime`, governance and policy-design flows
- Модуль связывает legal corpus, factual world state и policy execution surface через CAS, fact log и typed contracts.

## Ключевые концепции

- **Compliance path** — `corpus -> normpack -> legal_evaluation -> simulator` формирует юридическую проверку и change proposals.
- **Knowledge path** — `batch -> knowledge` превращает XML-корпус в DuckDB/HNSW legal graph для search и downstream reasoning.
- **Intervention mapping** — `interventions.py` и `intervention_artifacts.py` компилируют provision directives в intervention knobs, temporal sequences и strategic-response specs.
- **Version-aware corpus** — `build_version_index()` и `resolve_active_version()` выбирают активную редакцию по temporal envelope, а не по случайному document id.
- **Component-driven extensibility** — providers, evaluators и extractors поднимаются через registry/entry points, а не хардкодятся в orchestration.
- **Artifact-first execution** — ключевые выходы сохраняются как `lex.*` artifacts и world events с provenance.

## Public API

| Type/Function | Description |
|---|---|
| `ingest_legal_doc_bytes()` | Ingest raw legal bytes and persist normalized corpus metadata |
| `build_legal_structure()` | Extract provision hierarchy and emit `lex.corpus.provision_index` |
| `build_version_index()`, `resolve_active_version()` | Build and query active-version indexes for legal docs |
| `assemble_norm_pack()` | Assemble a `NormPack` through provider or pipeline path |
| `evaluate_legality()` | Produce `lex.legal_report` and optional change proposals |
| `NormPackMutator`, `diff_norm_packs()`, `NormImpactAnalyzer` | What-if diff and impact analysis for norm changes |
| `LegalKnowledgeGraph` | Read-only search API over the offline legal graph |
| `LexInterventionCompiler`, `TemporalInterventionSequencer` | Compile legal provisions into intervention/runtime artifacts |

Full reference: [docs/reference/lex/](../../../docs/reference/lex/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 9 top-level Python files plus 6 subpackages
- Exports: 58 lazy exports in `__init__.py`
- Notable delta: root facade now includes intervention mapping artifacts in addition to corpus, normpack, simulator and knowledge flows
