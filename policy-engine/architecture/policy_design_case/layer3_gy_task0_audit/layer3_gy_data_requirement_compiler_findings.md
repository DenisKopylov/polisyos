# Layer 3 GY Data Requirement Compiler Audit

## Verdict

`polisyos.data_requirement` is **near_route**, not route-pinned, not out_of_route,
and not pure built_not_wired.

It is near-route because the compiler has a typed contract, deterministic
producer, audit projection, persistence writer, Fabric/source-contract
consumers, runtime-quality consumers, and tests. It is not route-pinned because
the normal `resolve_metric_bindings -> FetchPlan -> FetchExecutor._fetch` path
does not consume `DataRequirementSpec` rows or selected/rejected source-contract
binding status before connector fetch.

Capability labels for the GY plan: `bridge_missing`,
`implemented_but_not_orchestrated`, `consumer_missing`, and
`verification_missing`.

## What Is Real

- `DataRequirementSpec` and `DataRequirementCompilationReport` are strict typed
  artifacts: `src/polisyos/data_requirement/_impl/models.py:85` and
  `src/polisyos/data_requirement/_impl/models.py:165`.
- The compiler requires 16 mandatory facets, including `source_rights`,
  `field_refs`, `time_coverage_refs`, `freshness_ref`, and
  `claim_bindability_refs`: `src/polisyos/data_requirement/compiler.py:39`.
- The report declares an authority boundary for data requirements and Fabric
  source-selection preconditions, but not claim support, legal authority,
  method validity, projection authority, or closeout pass:
  `src/polisyos/data_requirement/_impl/models.py:29`.
- The compiler can persist replayable JSON and expose an audit surface:
  `src/polisyos/data_requirement/compiler.py:447` and
  `src/polisyos/data_requirement/compiler.py:476`.
- Fabric has a real strict consumer:
  `src/polisyos/fabric/catalog/data_requirement_adapter.py:15`.
- Production-data contract index and producer pipeline can consume compiled
  specs: `src/polisyos/runtime/quality/production_data_contract_index.py:356`
  and `src/polisyos/runtime/quality/producer_pipeline.py:2052`.

## No-Write Probe Results

- Current GY engine census artifact has 69 rows and 0 `data_requirement` rows.
- `compile_data_requirements_for_scenario()` on the UA MSME scenario executed
  and returned a valid `policyos.data_requirement_compilation.v1` report, but
  `spec_count=0` without an injected resolver.
- `normalize_scenario_evidence_contract()` for the public golden scenario
  exposes `data_requirement_specs=0` while preserving the legacy projected
  families `production_msme_panel`, `credit_program_registry`, and
  `regional_displacement_indicators`.
- With the G1 release-backed resolver and mapped constructs
  `firm_survival`, `regional_displacement_pressure`, and
  `credit_program_enrollment`, the compiler emitted 9 specs with all 16
  mandatory facets and 7 admissibility predicates. The embedded capability
  binding status was `blocked_construct_not_observed`, not selected.
- With G1 resolver and unmapped `credit_access`, the compiler emitted 0 specs
  while still recording `layer3-g1:substrate-grounding:l1-dcat`.

## Why This Is Not Route-Pinned

`FetchPlan` is the pinned execution artifact for connector fetch. Its contract
has connector id, dataset id, filters, dates, quality minimum, fallback list,
and generic metadata, but no typed `data_requirement_id`, no
`source_contract_binding_status`, no mandatory-facet ledger, and no authority
boundary: `src/polisyos/core/contracts/control.py:458`.

The catalog route creates fetch plans from metric bindings:
`src/polisyos/fabric/retrieval/service.py:726` and
`src/polisyos/fabric/retrieval/service.py:870`. The executor then builds a
connector `FetchRequest` from dataset id, filters, dates, schema flags, and
page size: `src/polisyos/fabric/retrieval/executor.py:204` and
`src/polisyos/fabric/retrieval/executor.py:210`.

That means a failed or missing compiled data requirement cannot currently block
or downgrade the normal connector fetch path.

## Plan Implications

- GY-0 census should add `data_requirement` as a **near_route** asset with a
  pinned-fetch bridge gap, not as green route-pinned execution.
- GY-1 must define the admission envelope joining `DataRequirementSpec`,
  SourceContract binding report, `MetricBindingMatch`, and `FetchPlan`.
- GY-2 should not govern fetch execution below this surface until missing specs
  or rejected source-contract bindings fail closed or become explicit degraded
  run status.

Validator:
`tools/quality/validation/check_layer3_gy_data_requirement_compiler_audit.py`.
