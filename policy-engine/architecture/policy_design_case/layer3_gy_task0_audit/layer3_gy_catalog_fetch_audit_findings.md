# GY Catalog Binding -> Fetch -> Measurement Root Audit

Date: 2026-06-14
Scope: audit-only Task 0 pass for `resolve_metric_bindings -> FetchPlan -> preview/execute -> persisted artifact/root-chain`.

## Verdict

The route is mechanically partial:

- Real production catalog binding works: `DatasetCatalogGraph.resolve_metric_bindings` read the local production DuckDB and returned real `MetricBindingMatch` rows.
- `RetrievalService` can build a catalog `FetchPlan`, but only when a `DatasetCatalogGraph` is injected.
- A real WorldBank connector fetch ran from the catalog-derived plan and returned rows.
- `FetchExecutor.execute(..., persist_payload=True)` did not write any CAS object and did not return a digest/root ref.
- `/data/ingest` can accept `FetchPlan` and produce CAS-backed evidence/snapshot refs, but that is a separate API path. Normal NL retrieval calls `execute_fetch_plans(..., persist_payload=False)` and then materializes a derived `DataContext` snapshot.

Capability label: `partial_route_measurement_root_missing`.

## Probe Evidence

Repro artifact: `_build/.tmp/gy-catalog-fetch-audit/catalog_fetch_probe.json`
Probe hash: recorded in `layer3_gy_catalog_fetch_audit.json`.

Observed production catalog:

- `ds_datasets`: 137,176
- `ds_distributions`: 605,408
- `ds_metric_bindings`: 56,846
- `ds_schema_profiles`: 176,249

Probe metric: `poverty_rate`.

Top real binding:

- connector: `worldbank.wdi`
- profile: `worldbank_wdi`
- request dataset: `per_sa_sp.cba_q1_rur`
- execution tier: `transport_ready`
- title: `Benefit-cost ratio -  Social Pension -1st quintile (poorest) -rural`

That top binding is valuable evidence in two directions. It proves the route is real. It also shows why catalog `execution_tier` is not enough for admissibility: the selected title is only loosely related to a broad `poverty_rate` need, so semantic adequacy still needs a gate.

Real connector execute:

- status: `ok`
- row count: 143
- completeness: about `0.876`
- preview quality flag included `freshness:source_timestamp_missing`
- CAS file delta with `persist_payload=True`: `0`

Deterministic fake connector execute:

- successful preview + full fetch
- fetch calls: 2
- CAS file delta with `persist_payload=True`: `0`
- `DataContextMetric` had no payload/root/request/content-hash fields

## Findings

### GY-CATALOG-FETCH-001: Catalog binding is real but not default-wired

`DatasetCatalogGraph.resolve_metric_bindings` and `DatasetCatalogStore.resolve_metric_bindings` are real production readers over DuckDB. With an injected graph, `RetrievalService._resolve_via_catalog` builds `MetricCandidate` and `FetchPlan` rows with `source_lane="catalog"`.

Default runtime composition does not pass `dataset_catalog` into `RetrievalService`:

- `src/polisyos/runtime/http/services/control/run_lifecycle.py:223`
- `src/polisyos/runtime/http/services/control/nl_pipeline.py:4290`

Label: `implemented_but_not_orchestrated`.

### GY-CATALOG-FETCH-002: `persist_payload=True` is not a root producer

`FetchExecutor._execute_async` accepts `persist_payload`, but the branch at `src/polisyos/fabric/retrieval/executor.py:140` only touches `_cas_root`; it does not persist a canonical payload, request envelope, or root-chain manifest.

The probe confirmed this twice:

- fake connector: rows returned, CAS delta `0`
- real WorldBank connector: rows returned, CAS delta `0`

Label: `artifact_missing`.

### GY-CATALOG-FETCH-003: `DataContextMetric` drops root-critical fetch facts

`DataContextMetric` contains metric id, plan id, connector id, dataset id, row count, completeness, lane, and sample rows. It does not carry:

- payload/artifact/root ref
- request key or query key
- connector/profile/config fingerprint
- source version/content hash
- preview/full-fetch equivalence record

Label: `surface_missing`.

### GY-CATALOG-FETCH-004: Ingestion has CAS roots, but retrieval does not bridge to it

`IngestRequest` accepts `fetch_plans`, and `ControlPlaneService.run_data_ingestion` converts those plans into `DatasetFetchSpec`. The ingestion/orchestrator path can persist payload refs, evidence bundles, provenance, quality reports, and `fabric.data_snapshot`.

That is not the same as catalog retrieval root closure. Normal NL retrieval executes:

`retrieval.execute_fetch_plans(..., persist_payload=False)`

Then `_materialize_retrieval_artifacts` writes a `fabric.retrieval_payload` / `fabric.data_snapshot` derived from `DataContext`, not from raw connector payload roots.

Label: `bridge_missing`.

### GY-CATALOG-FETCH-005: Source-contract admissibility is not joined into FetchPlan admission

`MetricBindingMatch` is intentionally narrow: metric, dataset/distribution ids, connector/profile, request dataset id, confidence, default filters, execution tier, source, title.

`_resolve_via_catalog` projects catalog ids/title/tier and source policy history into `FetchPlan.metadata`, but does not carry or validate:

- `source_contract_ref`
- source rights/license/admissible use
- freshness refs/SLO/source-updated-at
- value/time/geography field refs
- claim bindability
- catalog snapshot hash/rule version
- replayable measurement root

The candidate trust/freshness values in the catalog lane are hard-coded (`0.7`, `0.6`), not derived from source-contract proof.

Labels: `verification_missing`, `semantic_test_missing`.

## Plan Implications

GY-1 should not be phrased as generic "wire catalog." It needs a concrete route closure:

1. Production runtime/NL composition either wires `DatasetCatalogGraph` or explicitly marks catalog lane out of scope.
2. Catalog FetchPlan admission joins source-contract rights, freshness, field refs, and claim-bindability before fetch.
3. `FetchExecutor.persist_payload=True` writes a canonical fetch envelope to CAS and returns root refs on the execution result/DataContext.
4. NL retrieval materialization consumes connector payload/root refs, or marks derived snapshots as `limited_summary_only`.
5. Replay/conformance compares connector output against the stored measurement root, not only fixture presence.

Until then, `resolve_metric_bindings -> FetchPlan -> connector fetch` is executable in a controlled probe, but it is not a governed measurement-root capability.

## Validation

Validator:

```bash
python3 tools/quality/validation/check_layer3_gy_catalog_fetch_audit.py --json
```

Negative tests:

```bash
uv run pytest tests/repo_quality/tools/test_layer3_gy_catalog_fetch_audit.py -q
```
