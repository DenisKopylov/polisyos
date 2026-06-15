# GY Connector Family Truth Audit

Date: 2026-06-14
Scope: Task 0 audit-only pass for the 12 connector families represented in the production catalog.
Artifact: `architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_connector_family_truth_audit.json`

## Method

This pass checks whether catalog binding shape matches the concrete fetch contract for each connector family. It deliberately does not claim network replay coverage for every external API. The question here is lower-level and load-bearing: before fetch, does the binding even carry the request/profile/filter shape that the connector implementation consumes?

Inputs:

- Production catalog: `production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb`
- Table: `ds_metric_bindings`
- Rows covered: `56,846` bindings across the 12 route-relevant connector ids
- Selection rule: one representative binding per connector id, ordered by `transport_ready > fetchable > catalog`, then `metric_id`
- Helper checks exercised: WorldBank indicator normalization, SDMX profile parsing, Generic REST profile parsing, safe path segment checks, and family-specific filter grammar checks

## Result

The connector rows are not uniform:

| Status | Count | Connector ids |
| --- | ---: | --- |
| `shape_pass` | 8 | `ckan.resource`, `eurostat.data`, `opendatasoft.ods`, `socrata.soda`, `unesco_uis.data`, `who.indicators`, `worldbank.wdi`, `wvs.wave7` |
| `shape_warn` | 1 | `sdmx.source` |
| `contract_mismatch` | 2 | `rest.json`, `unpd.data` |
| `not_execution_ready` | 1 | `ukons.datasets` |

This rejects the previous weak reading of "connector exists, therefore family works." A connector-family row is only meaningful when the catalog binding shape matches that family's request id, profile, filter, and execution-tier contract.

## Blocking Findings

### 1. `rest.json` is a contract mismatch

Representative binding:

- profile: `data_gov_pl`
- request id: `https://api.dane.gov.pl/1.4/datasets/2913,dane-pomiarowe-esa-edukacyjna-siec-antysmogowa/resources`
- execution tier: `fetchable`

The Generic REST connector parses endpoint behavior from the source profile and calls `handle.config.url`; it does not use `request.dataset_id` to build the fetch endpoint. The `data_gov_pl` profile base URL is `https://api.dane.gov.pl/1.4/datasets`, while the binding carries a deeper resources URL as `request_dataset_id`.

Evidence:

- `src/polisyos/fabric/connectors/reference/rest_json.py:193`
- `src/polisyos/fabric/connectors/reference/rest_json.py:321`
- `src/polisyos/fabric/connectors/reference/rest_json.py:378`
- `src/polisyos/fabric/connectors/reference/rest_json.py:464`
- `src/polisyos/fabric/connectors/profiles/builtin_profiles.py:456`

Capability label: `producer_missing`, `bridge_missing`, `semantic_test_missing`.

Implication: `data_gov_pl` fetchable rows can launder a catalog URL through a generic REST profile unless a family adapter promotes the request id into the actual endpoint contract or those bindings are downgraded/remapped.

### 2. `unpd.data` is transport-ready but lacks mandatory filters

Representative binding:

- profile: `unpd_dataportal`
- request id: `86`
- execution tier: `transport_ready`
- default filters: `{}`

The UNPD connector explicitly raises unless the request carries a `country` or `location_id` filter and a date/year bound. The representative binding, and the family default shape, do not carry those fields.

Evidence:

- `src/polisyos/fabric/connectors/sources/unpd.py:153`
- `src/polisyos/fabric/connectors/sources/unpd.py:159`
- `src/polisyos/fabric/connectors/sources/unpd.py:166`
- `src/polisyos/fabric/connectors/sources/unpd.py:241`
- `src/polisyos/fabric/connectors/sources/unpd.py:255`

Capability label: `bridge_missing`, `semantic_test_missing`.

Implication: UNPD must not count as `runs_e2e_on_real` from tier label alone. The binding generator needs to attach location and time filters, or the rows need a lower execution status.

### 3. `ukons.datasets` has a connector but only catalog-tier bindings

Representative binding:

- profile: `ukons_public`
- request id: `ashe-table-5`
- execution tier: `catalog`

The connector can form an observations URL, but all `50` production bindings for `ukons.datasets` are still catalog tier. That makes this family structurally present, not execution-ready.

Evidence:

- `src/polisyos/fabric/connectors/sources/ukons.py:138`
- `src/polisyos/fabric/connectors/sources/ukons.py:185`

Capability label: `producer_missing`, `bridge_missing`, `semantic_test_missing`.

Implication: GY should keep UKONS out of execution-ready counts until a replay fixture or bounded real fetch promotes specific bindings.

## Warning Finding

### 4. `sdmx.source` is structurally valid but unbounded

Representative binding:

- profile: `oecd_sdmx`
- request id: `DSD_SDG@DF_SDG_G_16`
- execution tier: `transport_ready`
- default filters: `{}`

The SDMX connector builds its URL from profile agency/data path, dataflow key, and an optional filter path. Empty filters produce an empty key path. That can be valid protocol-wise, but it is not yet a metric adequacy proof: no dimension key, codelist constraint, or time bound is demonstrated.

Evidence:

- `src/polisyos/fabric/connectors/sources/sdmx_source.py:492`
- `src/polisyos/fabric/connectors/sources/sdmx_source.py:498`
- `src/polisyos/fabric/connectors/sources/sdmx_source.py:725`
- `src/polisyos/fabric/connectors/sources/sdmx_source.py:748`

Capability label: `semantic_test_missing`.

Implication: SDMX should get a dimension-key adequacy probe before being treated as fully governed execution. This is not the same severity as REST/UNPD because the request can be constructed, but it is still too broad for claim-grade measurement.

## Shape-Pass Families

Eight families match their connector request grammar structurally:

- `worldbank.wdi`: indicator id batch, optional country/date and `mrv`/`mrnev`/`frequency`
- `ckan.resource`: direct URL or exact `package_id/resource_id`
- `eurostat.data`: safe Eurostat dataset code
- `unesco_uis.data`: UIS indicator code query parameter
- `socrata.soda`: safe 4x4 Socrata id, raw `$where` blocked
- `opendatasoft.ods`: safe ODS slug, raw `where` blocked
- `who.indicators`: WHO indicator id appended to the API base
- `wvs.wave7`: WVS variable id with optional country/year fallback

These are not end-to-end greens. They prove only family-shape compatibility. They still need bounded replay, field-level metric adequacy, source-contract admissibility, and persisted measurement-root proof.

## Plan Implications

1. Add a GY-0.5 connector-family gate before any connector row can be called `runs_e2e_on_real`.
2. Split connector status into at least: `class_exists`, `binding_shape_matches_fetch_contract`, `bounded_replay_runs`, `payload_root_persisted`, `metric_semantic_binding_verified`.
3. Treat `rest.json`, `unpd.data`, and `ukons.datasets` as blockers for execution-ready accounting.
4. Treat `sdmx.source` as `shape_warn` until dimension-key/codelist adequacy is proven.
5. Keep the network replay suite separate from this audit so shape failures cannot be hidden behind skipped outward calls.

## Verification

Validator:

```bash
python3 tools/quality/validation/check_layer3_gy_connector_family_truth_audit.py --json
```

Negative tests:

```bash
uv run pytest tests/repo_quality/tools/test_layer3_gy_connector_family_truth_audit.py -q
```
