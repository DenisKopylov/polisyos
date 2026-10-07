# Curated catalog defaults

The four authored defaults in `data/dataset_catalog` are seed variable alignments,
proxy metric penalties, the WVS indicator registry, and the metrics map. They are
curated configuration, not observed production data or a causal validation result.

One internal catalog resolver selects their filesystem profile. In a source
checkout, the exact `src/polisyos/data_forge/domains/catalog` anchor and project
manifest select the original YAML files. In an unpacked wheel installation, the
resolver returns durable `Path` objects within the package-private catalog
`_resources/` directory. Hatch projects the original bytes there and includes
the same four original files in the source distribution, so a rebuilt wheel has
the same resource content. There is no search of the working directory or a
neighbouring checkout, and no temporary extraction context behind a returned path.

Variable alignment, proxy penalties, core source ingestion, the catalog harvester,
batch metrics configuration and Fabric WVS all use this owner. Fabric reaches it
through the existing Data Forge runtime read facade.

`polisyos.data_forge.read_api.catalog.catalog_default_resource_path(name)` is an
additive `public_experimental` runtime function within the existing Data Forge
supported window. The catalog resolver module remains an internal provider. The
lazy facade exposes the same canonical function object, whose FQN is
`polisyos.data_forge.domains.catalog._resources.catalog_default_resource_path`;
it accepts exactly the four filenames above, returns a durable `Path`, and raises
`ValueError` for names outside that profile. It adds no root package export or
resource registry. Existing loader path arguments and the batch configuration's
explicit `metrics_map_path` continue to override defaults through their existing
caller contracts.

Explicit caller paths keep their original behavior. `repo_root`, raw WVS CSV/XLSX paths and mutable output
directories retain their existing ownership; those inputs are not bundled.

Missing seed files and metrics maps still fail their required reads. Proxy and
WVS loaders retain their existing optional absence and parse fallbacks. A successful
fallback call is not evidence that packaged defaults were read. Packaging admission
therefore checks all four projected files against their exact original bytes;
removing one projection or changing a still-valid YAML value fails that check.

The supported packaged profile is an unpacked filesystem installation. This
change does not add zip-import resource extraction, replace source-law validation,
alter curated values, or grant statistical or policy authority.
