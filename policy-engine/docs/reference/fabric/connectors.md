# Fabric Connectors
Related explanation: [Data Fabric](../../explanation/data-fabric.md).

Fabric ships 14 concrete connector classes in `polisyos.fabric.connectors.sources`. They share `HTTPConnectorBase` for authentication, retries, rate limiting, and normalized `FetchResult` construction.

## Connector Catalog

| Connector | Source | Protocol | Auth | Example profile |
|-----------|--------|----------|------|-----------------|
| `WorldBankConnector` | World Bank WDI | REST JSON | None | `worldbank_wdi` |
| `EurostatConnector` | Eurostat | REST JSON, SDMX, bulk export | None | `eurostat_public` |
| `SDMXSourceConnector` | ECB, OECD, IMF, BIS, ILO, FAO, UNSD | SDMX REST | Profile-driven | `oecd_sdmx` |
| `WHOConnector` | WHO GHO | REST JSON | None | `who_gho` |
| `UNPDConnector` | UN Population Division | REST JSON | None | `unpd_dataportal` |
| `UNESCOUISConnector` | UNESCO UIS | REST JSON | None | `unesco_uis_public` |
| `WVSConnector` | World Values Survey | REST JSON plus bulk-file profile support | None | `wvs_wave7` |
| `UKONSConnector` | UK ONS | REST JSON | None | `ukons_public` |
| `CKANCatalogConnector` | CKAN package discovery | CKAN Action API | Profile-driven | `data_gov_uk` |
| `CKANResourceConnector` | CKAN resource download | CKAN metadata + resource fetch | Profile-driven | `data_gov_us` |
| `SocrataConnector` | Socrata portals | SODA / REST JSON | App token or none | `nyc_opendata` |
| `OpendatasoftConnector` | Opendatasoft hubs | Explore API v2.1 | API key or none | `paris_opendata` |
| `SPARQLConnector` | Wikidata, DBpedia, similar KG endpoints | SPARQL over HTTP | Usually none | `wikidata_sparql` |
| `RestJsonConnector` | Generic REST APIs | REST JSON | Configurable | `open_meteo` |

## Registration Status

| Surface | Count | Detail |
|---------|-------|--------|
| Concrete connector classes | 14 | Exported from `polisyos.fabric.connectors.sources` |
| `pyproject` entry points | 11 | `worldbank`, `wvs`, `eurostat`, `ukons`, `sdmx`, `ckan.catalog`, `ckan.resource`, `socrata`, `opendatasoft`, `sparql`, `rest.json` |
| Class-only connectors today | 3 | `WHOConnector`, `UNPDConnector`, `UNESCOUISConnector` |

## Shared HTTP Base

| API | Role |
|-----|------|
| `HTTPResilienceProfile` | Source-specific retry, backoff, and circuit-breaker defaults |
| `HTTPConnectorBase` | Shared authenticated HTTP runtime and `FetchResult` normalization |

## API Reference

::: polisyos.fabric.connectors.sources.http_base

::: polisyos.fabric.connectors.sources.world_bank

::: polisyos.fabric.connectors.sources.eurostat

::: polisyos.fabric.connectors.sources.sdmx_source

::: polisyos.fabric.connectors.sources.who

::: polisyos.fabric.connectors.sources.unpd

::: polisyos.fabric.connectors.sources.unesco_uis

::: polisyos.fabric.connectors.sources.wvs

::: polisyos.fabric.connectors.sources.ukons

::: polisyos.fabric.connectors.sources.ckan_catalog

::: polisyos.fabric.connectors.sources.ckan_resource

::: polisyos.fabric.connectors.sources.socrata

::: polisyos.fabric.connectors.sources.opendatasoft

::: polisyos.fabric.connectors.sources.sparql

::: polisyos.fabric.connectors.sources.rest_json

