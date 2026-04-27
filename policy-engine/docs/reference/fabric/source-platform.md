# Fabric Source Platform

Related explanation: [Data Fabric](../../explanation/data-fabric.md).

Best-in-class inventory: [best-in-class-inventory.md](best-in-class-inventory.md).

Phase 5 makes production source admission contract-first. A connector is
production-visible only when SourceContract v2, profile compatibility,
quality, replay or non-replayable reason, lineage, access, owner/reviewer,
SLO, scorecard, and docs evidence are present.

## Generated Artifacts

| Artifact | Purpose |
| -------- | ------- |
| `schemas/fabric/source_contract.schema.json` | SourceContract v2 schema |
| `schemas/fabric/source_scorecard.schema.json` | Source scorecard schema |
| `schemas/snapshots/fabric/source_contracts_v2.json` | Production SourceContract snapshot |
| `schemas/snapshots/fabric/source_scorecards.json` | Generated source scorecards |
| `tools/quality/validation/fabric_source_contracts.py` | CI report/fail-closed gate |

## CI Gate

Report-only mode:

```bash
uv run python tools/quality/validation/fabric_source_contracts.py --report
```

Artifact check:

```bash
uv run python tools/quality/validation/fabric_source_contracts.py --check
```

Fail-closed mode rejects production connectors without SourceContract v2
and conformance evidence:

```bash
uv run python tools/quality/validation/fabric_source_contracts.py --fail-closed
```

## Source Scorecards

| Source contract | Window | Freshness | Reliability | Schema drift | Quality | Replay | Overall | Status |
| --------------- | ------ | --------- | ----------- | ------------ | ------- | ------ | ------- | ------ |
| `ckan.catalog.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `ckan.resource.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `eurostat.data.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `files.tabular.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `geojson.features.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `graphql.api.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `object_storage.blob.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `opendatasoft.ods.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `rest.json.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `sdmx.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `socrata.soda.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `sparql.endpoint.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `sql.query.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `stream.jsonl.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `ukons.datasets.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `unesco_uis.data.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `unpd.data.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `who.indicators.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `worldbank.wdi.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |
| `wvs.wave7.generic` | `rolling_30d` | 0.750 `unknown` | 0.750 `unknown` | 1.000 `unknown` | 0.750 `unknown` | 1.000 `unknown` | B / 0.844 | watch |

## Profile Compatibility Matrix

| Source contract | Connector | Profile | Present | Family | Schema preflight | Async fetch |
| --------------- | --------- | ------- | ------- | ------ | ---------------- | ----------- |
| `ckan.catalog.generic` | `ckan.catalog` | `data_gov_us` | True | `ckan` | False | False |
| `ckan.resource.generic` | `ckan.resource` | `data_gov_us` | True | `ckan` | False | False |
| `eurostat.data.generic` | `eurostat.data` | `eurostat_public` | True | `eurostat` | True | True |
| `files.tabular.generic` | `files.tabular` | `files_demo_tabular` | True | `files` | False | False |
| `geojson.features.generic` | `geojson.features` | `geojson_demo` | True | `geojson` | False | False |
| `graphql.api.generic` | `graphql.api` | `graphql_demo` | True | `graphql` | False | False |
| `object_storage.blob.generic` | `object_storage.blob` | `object_storage_demo` | True | `object_storage` | False | False |
| `opendatasoft.ods.generic` | `opendatasoft.ods` | `opendatasoft_public` | True | `opendatasoft` | False | False |
| `rest.json.generic` | `rest.json` | `open_meteo` | True | `rest` | False | False |
| `sdmx.generic` | `sdmx.source` | `ecb_sdmx` | True | `sdmx` | False | False |
| `socrata.soda.generic` | `socrata.soda` | `nyc_opendata` | True | `socrata` | False | False |
| `sparql.endpoint.generic` | `sparql.endpoint` | `wikidata_sparql` | True | `sparql` | False | False |
| `sql.query.generic` | `sql.query` | `sqlite_demo` | True | `sql` | False | False |
| `stream.jsonl.generic` | `stream.jsonl` | `stream_jsonl_demo` | True | `stream` | False | False |
| `ukons.datasets.generic` | `ukons.datasets` | `ukons_public` | True | `ukons` | False | False |
| `unesco_uis.data.generic` | `unesco_uis.data` | `unesco_uis_public` | True | `unesco_uis` | False | False |
| `unpd.data.generic` | `unpd.data` | `unpd_dataportal` | True | `unpd` | False | False |
| `who.indicators.generic` | `who.indicators` | `who_gho` | True | `who` | False | False |
| `worldbank.wdi.generic` | `worldbank.wdi` | `worldbank_wdi` | True | `worldbank` | False | False |
| `wvs.wave7.generic` | `wvs.wave7` | `wvs_wave7` | True | `wvs` | False | False |

## Source Contract Catalog

| Contract | Connector | Profile | Quality | Replay | Classification | Owner | Reviewer |
| -------- | --------- | ------- | ------- | ------ | -------------- | ----- | -------- |
| `ckan.catalog.generic` | `ckan.catalog` | `data_gov_us` | `fabric.quality.ckan.catalog.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `ckan.resource.generic` | `ckan.resource` | `data_gov_us` | `fabric.quality.ckan.resource.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `eurostat.data.generic` | `eurostat.data` | `eurostat_public` | `fabric.quality.eurostat.data.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `files.tabular.generic` | `files.tabular` | `files_demo_tabular` | `fabric.quality.files.tabular.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `geojson.features.generic` | `geojson.features` | `geojson_demo` | `fabric.quality.geojson.features.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `graphql.api.generic` | `graphql.api` | `graphql_demo` | `fabric.quality.graphql.api.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `object_storage.blob.generic` | `object_storage.blob` | `object_storage_demo` | `fabric.quality.object_storage.blob.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `opendatasoft.ods.generic` | `opendatasoft.ods` | `opendatasoft_public` | `fabric.quality.opendatasoft.ods.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `rest.json.generic` | `rest.json` | `open_meteo` | `fabric.quality.rest.json.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `sdmx.generic` | `sdmx.source` | `ecb_sdmx` | `fabric.quality.sdmx.source.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `socrata.soda.generic` | `socrata.soda` | `nyc_opendata` | `fabric.quality.socrata.soda.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `sparql.endpoint.generic` | `sparql.endpoint` | `wikidata_sparql` | `fabric.quality.sparql.endpoint.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `sql.query.generic` | `sql.query` | `sqlite_demo` | `fabric.quality.sql.query.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `stream.jsonl.generic` | `stream.jsonl` | `stream_jsonl_demo` | `fabric.quality.stream.jsonl.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `ukons.datasets.generic` | `ukons.datasets` | `ukons_public` | `fabric.quality.ukons.datasets.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `unesco_uis.data.generic` | `unesco_uis.data` | `unesco_uis_public` | `fabric.quality.unesco_uis.data.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `unpd.data.generic` | `unpd.data` | `unpd_dataportal` | `fabric.quality.unpd.data.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `who.indicators.generic` | `who.indicators` | `who_gho` | `fabric.quality.who.indicators.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `worldbank.wdi.generic` | `worldbank.wdi` | `worldbank_wdi` | `fabric.quality.worldbank.wdi.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |
| `wvs.wave7.generic` | `wvs.wave7` | `wvs_wave7` | `fabric.quality.wvs.wave7.default.v1` | Replay fixture has not been recorded for this migrated source yet. | `public` | `@fabric-owners` | `@fabric-reviewers` |

## Deprecation And Sunset Policy

A production source moves from `active` to `deprecated` only with an owner,
reviewer, reason, migration note, replacement contract when available,
and a sunset date. During deprecation, scorecards remain generated and
the CI gate continues to require replay, lineage, access, and SLO evidence.
A `sunset` source remains in snapshots for historical replay but must not
be selected for new production fetch plans.

## Validation Anchors

- `tests/fabric/connectors/test_source_contract_v2.py` validates the model,
  scaffold, conformance harness, scorecards, and generated snapshots.
- `tests/tools/test_fabric_source_contracts.py` validates CI report/check
  behavior and source-platform docs generation.
