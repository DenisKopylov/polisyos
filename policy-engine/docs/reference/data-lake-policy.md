# Data Lake And Committed Data Policy

Freshness: 2026-05-03
Owner: `team-data-forge`
Source of truth: `architecture/policies/data.toml`

The collapsed product-root workspace has one data surface with two policies:

- `data/academic_gold/` and `data/dataset_catalog/` are committed only by
  allowlist;
- `data/policy-engine-local/` and medallion-style local zones under `data/`
  are ignored local data.

## Local Data Lake

The ignored local lake uses medallion zones:

| Zone | Path | Retention |
| --- | --- | --- |
| Bronze | `data/bronze/` | short-lived source cache |
| Silver | `data/silver/` | intermediate transform |
| Gold | `data/gold/` | review candidate |
| Manifests | `data/manifests/` | local evidence |
| Quarantine | `data/quarantine/` | security or schema hold |

Local data can be cleaned with the commands listed in
`architecture/policies/data.toml`.

## Product Data

Committed `data/` content may contain only:

- tiny gold examples under `data/academic_gold/`;
- registry YAML under `data/dataset_catalog/`;
- reviewed fixtures, contracts, manifests, or examples registered in
  `architecture/generated_artifacts.toml`.

Bulk raw files, parquet outputs, local databases, and derived data stay ignored
under `data/policy-engine-local/raw/`, `data/policy-engine-local/curated/`,
and `data/policy-engine-local/databases/`.
