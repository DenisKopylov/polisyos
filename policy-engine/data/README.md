# Committed Product Data

`policy-engine/data/` is an allowlisted committed-data surface. It contains only
small fixtures, contracts, manifests, registries, and gold examples that are safe
to version and review.

Allowed committed homes:

- `academic_gold/`: tiny gold examples and review guidelines.
- `dataset_catalog/`: YAML registries used by catalog and Data Forge tests.

Bulk raw data, derived parquet/CSV outputs, local databases, run products, and
temporary audit bundles must stay ignored under product-root local data
locations such as `data/policy-engine-local/` or medallion zones declared in
`architecture/policies/data.toml`.

Source of truth: `architecture/policies/data.toml`.
