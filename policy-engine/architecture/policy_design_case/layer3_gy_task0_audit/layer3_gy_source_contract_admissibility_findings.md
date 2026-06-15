# GY Rights / Freshness / Source-Contract Admissibility Audit

Date: 2026-06-14
Scope: Task 0 audit-only pass for whether rights, freshness, field refs, time coverage, and claim bindability reach catalog-derived fetch admission.
Artifact: `architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_source_contract_admissibility_audit.json`

## Question

GY-1 treats source admissibility as load-bearing: license, freshness/watermark, field refs, time coverage, and claim bindability must shape what can be fetched. The census and earlier catalog-fetch audit proved search and a connector fetch, but they did not prove that source-contract facets pass into fetch admission.

This pass checks the admission chain:

```text
DataRequirementSpec / source contract
  -> DatasetCatalogGraph metric binding
  -> RetrievalService FetchPlan
  -> FetchExecutor preview/execute
  -> connector.fetch
```

## Result

Verdict: `rights_freshness_source_contract_admissibility_missing_at_fetch_admission`.

The strict contracts and validators exist, but the normal catalog-to-fetch path does not consume them before fetch. A catalog binding can become a `FetchPlan` and enter `FetchExecutor` with no `source_contract_ref`, `source_rights`, `field_refs`, `time_coverage_refs`, `freshness_ref`, watermark ref, or `claim_bindability_refs`.

## Mechanical Evidence

`DataRequirementSpec` requires 16 mandatory facets:

- `source_contract_ref`
- `source_rights`
- `dictionary_ref`
- `schema_ref`
- `field_refs`
- `unit_refs`
- `geography_refs`
- `time_coverage_refs`
- `freshness_ref`
- `lineage_refs`
- `transformation_refs`
- `quality_assertion_refs`
- `missingness_refs`
- `outlier_refs`
- `construct_validity_refs`
- `claim_bindability_refs`

The production catalog has partial raw source metadata:

| Check over execution-ready bindings | Count |
| --- | ---: |
| total `transport_ready` or `fetchable` bindings | 41,976 |
| license or access license present | 28,426 |
| freshness hint present via `last_updated` or `update_frequency` | 41,976 |
| schema profile present | 41,976 |
| inferred value columns present | 41,976 |
| time coverage start present | 4,894 |
| time coverage end present | 4,894 |
| inferred geography column present | 22,981 |
| inferred time column present | 46 |

That metadata does not become an admissibility envelope. In a no-write route probe, a production WorldBank row had `license=CC-BY-4.0`, `access_license=CC-BY-4.0`, `update_frequency=annual`, `inferred_geography_column=country`, and an inferred value column. After passing through `RetrievalService._resolve_via_catalog`, the resulting `FetchPlan` carried zero of the 16 mandatory facets.

## Blocking Findings

### 1. `MetricBindingMatch` cannot carry source-contract facets

The catalog binding model contains metric, dataset, connector, profile, request id, default filters, execution tier, source, and title. It does not expose rights, field refs, time coverage, freshness refs, lineage refs, or claim bindability.

Evidence:

- `src/polisyos/data_forge/domains/catalog/knowledge/types.py:227`
- `src/polisyos/data_forge/domains/catalog/knowledge/store.py:475`

Capability label: `bridge_missing`, `semantic_test_missing`.

### 2. `FetchPlan` admission drops every mandatory facet

`RetrievalService._resolve_via_catalog` converts binding rows into `FetchPlan`. The normal metadata added to the plan is catalog id, distribution id, catalog title, execution tier, source, history policy, default lookback days, manual backfill allowed, and route marker.

It does not add:

- license / source rights
- source contract ref
- field refs or schema refs
- time coverage refs
- freshness ref or watermark ref
- quality / missingness / outlier refs
- claim-bindability refs

Evidence:

- `src/polisyos/fabric/retrieval/service.py:726`
- `src/polisyos/fabric/retrieval/service.py:869`
- `src/polisyos/core/contracts/control.py:458`

Capability label: `bridge_missing`, `verification_missing`, `semantic_test_missing`.

### 3. `FetchExecutor` does not consume admissibility

`FetchExecutor._fetch` builds `FetchRequest` from `dataset_id`, `filters`, `date_start`, `date_end`, metadata/schema flags, page size, and retryability. It then calls `connector.fetch`. There is no pre-fetch consumer of source-contract binding status or source-selection trace status.

Evidence:

- `src/polisyos/fabric/retrieval/executor.py:109`
- `src/polisyos/fabric/retrieval/executor.py:204`

Capability label: `consumer_missing`, `bridge_missing`.

### 4. Strict gates exist but are off-route

This is not a missing-contract problem. Existing strict gates reject the same shape:

- `build_source_contract_requirement_bindings` rejects a catalog-plan-shaped candidate with `reason_code=source_contract_facets_missing`.
- A complete candidate with all 16 facets is selected.
- `build_fabric_source_selection_trace` fails a selected source lacking facets with 18 blocking issues.

Evidence:

- `src/polisyos/fabric/catalog/data_requirement_adapter.py:15`
- `src/polisyos/fabric/catalog/source_selection_audit.py:553`
- `src/polisyos/runtime/quality/production_data_contract_index.py:378`
- `src/polisyos/runtime/http/services/control/production_data.py:350`

Capability label: `implemented_but_not_orchestrated`, `bridge_missing`.

### 5. Freshness is a policy hint, not a replayable proof

The catalog source registry has 35 entries:

- 32 `full_snapshot`
- 3 `rolling_window`
- 3 with `default_lookback_days`
- 12 `publish_blocking`

`RetrievalService._catalog_date_window` can derive a date range from a rolling-window policy, but the plan does not carry a freshness ref, source watermark, last-updated assertion, or rule-versioned freshness proof.

Evidence:

- `src/polisyos/fabric/retrieval/service.py:198`
- `src/polisyos/fabric/retrieval/service.py:215`
- `src/polisyos/data_forge/domains/catalog/registry.py:21`

Capability label: `artifact_missing`, `semantic_test_missing`.

## GY-1 Implications

GY-1 should not be framed as "wire the real catalog" only. The real catalog is usable, but its binding path is not source-contract admissible.

Minimal acceptance for GY-1 should include:

1. Catalog binding results join to a `SourceContractAdmission` or equivalent envelope before `FetchPlan` creation.
2. The envelope carries `source_contract_ref`, `source_rights`, `field_refs`, `time_coverage_refs`, `freshness_ref` or `watermark_ref`, and `claim_bindability_refs`.
3. Missing mandatory facets produce a typed blocker before `FetchExecutor._fetch`.
4. `FetchPlan` should either carry the selected admission ref or be explicitly `candidate_only`.
5. Source-selection trace / data-requirement adapter status must be consumed by the normal `/data/resolve -> execute_fetch_plans` route, not only by later runtime-quality surfaces.

## Verification

Validator:

```bash
python3 tools/quality/validation/check_layer3_gy_source_contract_admissibility_audit.py --json
```

Negative tests:

```bash
uv run pytest tests/repo_quality/tools/test_layer3_gy_source_contract_admissibility_audit.py -q
```
