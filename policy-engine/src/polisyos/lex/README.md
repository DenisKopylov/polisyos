# Lex (`polisyos.lex`)

`polisyos.lex` covers PolicyOS's runtime legal domain: building
`NormPack`, compliance evaluation, what-if simulation, a read-only legal knowledge
graph, and the `lex -> intervention` layer that translates
provision-level rules into tunable policy/runtime artifacts.

## Purpose

Use `polisyos.lex` for runtime legal evaluation and NormPack-backed policy
reasoning. Offline legal corpus extraction and batch graph construction live in
Data Forge; Lex reads those published artifacts and turns legal provisions into
typed runtime/evaluation contracts.

## Role in the system

- **Depends on:** `polisyos.ir`, `polisyos.core`, `polisyos.fabric`
- **Used by:** `polisyos.scientist`, `polisyos.runtime`, governance and policy-design flows
- The module connects published legal artifacts, factual world state, and the policy execution surface through CAS, the fact log, and typed contracts.

## Key concepts

- **Compliance path** — `read_api.legal -> normpack -> legal_evaluation -> simulator` produces legal evaluations and change proposals.
- **Knowledge path** — the Data Forge legal batch publishes the DuckDB/HNSW graph, and `lex.knowledge` reads it without write-side logic.
- **Intervention mapping** — `interventions/compiler.py`, `interventions/sequencing.py`, and `interventions/artifacts.py` compile provision directives into neutral IR intervention contracts, temporal sequences, and strategic-response specs; Scientist owns policy-search and DTR execution bridges.
- **Version-aware reads** — `resolve_active_version()` reads Data Forge version-index artifacts through `polisyos.data_forge.read_api.legal`.
- **Component-driven extensibility** — providers, evaluators, and extractors are loaded through registries/entry points rather than hard-coded into orchestration.
- **Artifact-first execution** — key outputs are persisted as `lex.*` artifacts and world events with provenance.

## Public API

| Type/Function                                                | Description                                                             |
| ------------------------------------------------------------ | ----------------------------------------------------------------------- |
| `resolve_active_version()`                                   | Query active-version indexes for legal docs through Data Forge read API |
| `assemble_norm_pack()`                                       | Assemble a `NormPack` through provider or pipeline path                 |
| `evaluate_legality()`                                        | Produce `lex.legal_report` and optional change proposals                |
| `NormPackMutator`, `diff_norm_packs()`, `NormImpactAnalyzer` | What-if diff and impact analysis for norm changes                       |
| `LegalKnowledgeGraph`                                        | Read-only search API over the offline legal graph                       |
| `run_legal_benchmark()`, `LexBenchmarkOutcome`               | Execute Lex-owned semantic readiness over published Data Forge fixtures |
| `LexInterventionCompiler`, `TemporalInterventionSequencer`   | Compile legal provisions into intervention/runtime artifacts            |

Full reference: [docs/reference/lex/](../../../docs/reference/lex/index.md)

## Internal Layout

- `__init__.py` owns the runtime-only public facade.
- `normpack/` owns NormPack assembly and provider contracts.
- `legal_evaluation/` owns legality report generation and compliance checks.
- `knowledge/` owns read-only access to Data Forge legal graph artifacts.
- `knowledge/benchmark.py` owns NormPack, transport, graph, and legal-quality readiness;
  Scientist retrieval diagnostics cannot override this receipt.
- `interventions/compiler.py`, `interventions/sequencing.py`, and `interventions/artifacts.py` own provision-to-policy
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
- Intervention mapping: `src/polisyos/lex/interventions/compiler.py`, `src/polisyos/lex/interventions/sequencing.py`, and `src/polisyos/lex/interventions/artifacts.py`

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

- `polisyos.lex.factlog` has been removed; NormPack imports `load_world_facts` from
  `polisyos.fabric.world` directly.
- The legacy `polisyos.norm_pack_providers` extension group is compatibility
  support for `polisyos.lex_normpacks`; new providers should use the Lex group.
- Offline legal preprocessing imports must stay in Data Forge; do not
  reintroduce Lex-owned batch write paths.

## Current State

- Last updated: 2026-10-17
- Files: 2 top-level Python facade modules plus 8 implementation packages
- Exports: 61 total names in the current lazy facade `__all__`.
- Notable delta: Lex owns the semantic legal benchmark; Data Forge publishes
  query fixtures through its read API and no longer imports Lex benchmark
  consumers.

`knowledge/multilingual_assurance.py` owns the candidate MAEP instrument. Its persisted finite
comparison remains distinct from `normpack/legal_authority.py` competence and from legal benchmark
readiness: W5-K06 scope, vacant holder and unsigned trust checks prevent equivalence issuance.

### Legal transport and source-refusal facade

The stable `polisyos.lex` root facade lazily re-exports `LegalConstraintBridge`,
`LegalConstraintSet`, `is_transport_blocked`, and
`evaluate_transport_constraints` from their canonical Lex owners. It also exposes
`LegalSourceRelationRefusal` and
`LegalSourceRelationVerificationMissingError` from the existing Data Forge legal
source-relation contract. These are aliases to the canonical objects, not parallel
contracts.

`evaluate_transport_constraints()` currently propagates the typed
`verification_missing` refusal before reading the legal graph. Callers must retain
that status rather than interpreting it as an empty constraint set, a permission,
or a positive legal finding. The facade does not establish a legal conclusion.


## Internal module identity

The supported import surface remains polisyos.lex and polisyos.lex.knowledge.
Implementation owners now live under normpack, interventions, provenance, and
exception_taxonomy; direct former module paths such as polisyos.lex.types,
polisyos.lex.errors, and polisyos.lex.intervention_artifacts are internal migration
paths and are not compatibility shims. Root-facade exports preserve object identity.
The natural Python module names of moved implementation classes change, so new pickle
globals use their new owner path. Historical external pickle populations were not
established by the repository census.
