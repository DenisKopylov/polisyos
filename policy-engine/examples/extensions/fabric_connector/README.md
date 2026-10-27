# Fabric Connector Example

The repository gate builds and installs this example as a regular local wheel so it exercises
the installed-distribution and RECORD-backed provider-origin path. The gate uses a
source-owned native extension-example build-tools profile, an exact locked Hatchling
wheelhouse, a fresh output directory, and installs the exact wheel without resolving
dependencies. Run the focused gate with:

```bash
uv run polisyos-tools validation check-extension-examples --example fabric_connector
polisyos components list --kind fabric_connector --tag external-example
```

The component creates a deterministic in-memory connector and does not use the
network.

The checker keeps its locked build-tool cache under ignored product-root .cache/native-extension-example-build-tools. Fresh component discovery reconciles installed RECORD, entry point, provider module origin and module bytes to the exact wheel built in that run.
