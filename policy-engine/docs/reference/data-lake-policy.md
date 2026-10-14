# Data Lake And Committed Data Policy

Last updated: 2026-10-14
Owner: `team-data-forge`
Source pin: `8dd933600dd7a5a8a5b48432c6089d63b81ca641`
Source of truth: `architecture/policies/data.toml`, `.gitignore`,
`architecture/generated_artifacts.toml`, and `data/policy-engine-local/README.md`
Evidence status: the data policy, ignore rules, and tracked data paths were
inspected at the source pin; tests were not run and local data contents were not
measured.

The collapsed product-root workspace has one data surface with two policies:

- `data/academic_gold/` and `data/dataset_catalog/` are committed only by
  allowlist;
- `data/policy-engine-local/` contains ignored local data apart from its tracked
  explanatory `README.md`; medallion-style local zones under `data/` are ignored.

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
- the explanatory `data/policy-engine-local/README.md`, the documented
  exception for the legacy local-state directory name;
- reviewed fixtures, contracts, manifests, or examples registered in
  `architecture/generated_artifacts.toml`.

Bulk raw files, parquet outputs, local databases, and derived data stay ignored
under `data/policy-engine-local/raw/`, `data/policy-engine-local/curated/`,
and `data/policy-engine-local/databases/`.
