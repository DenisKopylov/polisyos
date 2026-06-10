# Policy Design Case Layer 3 Substrate Grounding

Layer 3 G1 is the substrate grounding and acquisition-gap audit slice for the
Policy Design Case. It turns existing Layer 3 G0 discovery/search discipline
into a runtime bundle that can say whether a pinned construct has a validated
Fabric SourceContract v2 binding, an observed-but-uncertain binding, or a
fail-closed acquisition/search ceiling.

This page documents the `layer3_g1_substrate_grounding_audit_surface`.

## Contract

- Schema version: `policyos.policy_design_case.layer3_g1_substrate_grounding.v1`
- Rule version: `policyos.layer3.g1.substrate_grounding_search.v1`
- Producer: `src/polisyos/runtime/quality/layer3_substrate_grounding.py`
- Validator: `tools/quality/validation/check_policy_design_case_layer3_g1_readiness.py`

## Validator

```bash
uv run python tools/quality/validation/check_policy_design_case_layer3_g1_readiness.py \
  --repo-root . \
  --output-format json
```

Write mode is reserved for the persistence task:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer3_g1_readiness.py \
  --repo-root . \
  --write \
  --output-format json
```

## Authority Posture

G1 artifacts are authoritative only for:

- `layer3_g1_construct_grounding_audit`
- `layer3_g1_lineage_contamination_audit`

They may not be used for:

- `claim_authority`
- `causal_effect`
- `policy_recommendation`
- `publishability`
- `adapter_promotion`
- `useful_design_credit`
- `production_authority`
- `search_hit_as_authority`

Search ledgers, search hits, no-hit routes, hardcode-strangle records, and
readiness summaries are replay/control-plane evidence. They are not claim,
publication, promotion, or useful-design authority.

## Surfaces

The active audit surface is for:

- `EXPERT`
- `MACHINE`

Out of scope until later promotion slices:

- `PUBLIC`: waits for G4/G5 public projection.
- `REVIEWER`: waits for G4/G5 reviewer projection.

## G0 Dependency Gate

G1 must load and validate these G0 v2 artifacts before a pass result:

- `architecture/policy_design_case/layer3_g0_readiness_manifest.json`
- `architecture/policy_design_case/layer3_discovery_search_discipline.json`
- `architecture/policy_design_case/layer3_hardcode_enumeration_backlog.json`
- `architecture/policy_design_case/layer3_engineering_quality_check.json`
- `architecture/policy_design_case/layer3_health_metric_ledgers.toml`

## Runtime Artifacts

- `architecture/policy_design_case/layer3_g1_adapter_admission_registry.json`
- `architecture/policy_design_case/layer3_g1_substrate_search_ledgers.json`
- `architecture/policy_design_case/layer3_g1_l1_l5_l6_index_coverage.json`
- `architecture/policy_design_case/layer3_g1_search_recall_freshness.json`
- `architecture/policy_design_case/layer3_g1_hardcode_strangle_delta.json`
- `architecture/policy_design_case/layer3_g1_free_growth_report.json`
- `architecture/policy_design_case/layer3_g1_search_engineering_quality_report.json`
- `architecture/policy_design_case/layer3_g1_grounded_source_contracts.json`
- `architecture/policy_design_case/layer3_g1_lineage_contamination_ledger.json`
- `architecture/policy_design_case/layer3_g1_conformance_report.json`
- `architecture/policy_design_case/layer3_g1_coverage_lineage_abstention_surface.json`
- `architecture/policy_design_case/layer3_g1_health_metric_delta.toml`
- `architecture/policy_design_case/layer3_g1_adapter_contract_registry.toml`
- `architecture/policy_design_case/layer3_g1_readiness_manifest.json`

## Search-Health Gates

- Direct L1 coverage must cite
  `production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb::ds_metric_bindings`.
- Capability-index refs do not satisfy L1 coverage.
- L5 calibration refs and L6 routing refs must be present.
- Every selected/no-hit/abstention/ceiling route must have a replayable search ledger.
- Known-groundable recall must pass before domain ceiling.
- Index freshness must pass before domain ceiling.
- Free-growth fixture count must be at least one.
- Mechanism generality must cover at least two request shapes.
- No-hardcode lint must pass.
- Hardcoded fallback status must be `deleted_or_disabled_no_fallback`.
- Search-engineering quality and scaling status must pass.
- All five G0 health metric deltas must be represented.

## Negative Controls

The validator and runtime contract block:

- raw Fabric/data_forge output without adapter envelope
- active-flag-only SourceContract echoes
- missing rights
- contaminated or workstation-local lineage
- search-ledger authority leakage
- missing replayable search frontier
- stale index or recall miss before domain ceiling
- hardcoded fallback closure
- capability-index-as-L1 overclaim
- unjustified L1 surrogate when production DCAT exists
- search-engineering full-scan/unindexed behavior
