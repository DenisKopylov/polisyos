# Fabric Schema Compatibility

Related explanation: [Data Fabric](../../explanation/data-fabric.md).

Freshness: 2026-10-14
Owner: `@fabric-owners`
Source pin: `c35222b3dcf103338175cf300c5fe9487e6416f3`
Source plan: `docs/plans/active/FABRIC_AUDIT_REMEDIATION_PLAN.md`, D1-L2 section in `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/fabric/connectors/contracts/**`, `src/polisyos/fabric/connectors/sources/_contracts/**`, `tools/quality/validation/fabric_schema_governance.py`, `schemas/snapshots/connectors/contracts.json`, and `schemas/snapshots/fabric/connector_contract_registry.json`
Evidence level: schema, registry, snapshot, and named test behavior inspected at the source pin. Tests were not run in this documentation pass; snapshot presence does not establish a connector-to-world consumer chain.
Test status: cited tests were inspected but not run in this documentation pass.
Best-in-class inventory: [best-in-class-inventory.md](best-in-class-inventory.md)
Inventory scope: code counts reflect statically resolved source declarations;
they do not prove runtime or deployment readiness. Dynamic or unresolved
declarations remain partial/unknown rather than being silently treated as absent.

Fabric schema compatibility is currently enforced at three layers:

| Layer                          | Current source of truth                                                                                       | What it decides                                                                                                        |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Runtime schema model           | `DataSchema`, `FieldSpec`, `SchemaVersion` in `fabric.connectors.contracts.schema`                            | Field names/types, units, semantic types, primary keys, time/geo dimensions, completeness rules                        |
| Compatibility engine           | `SchemaEvolution`, `MigrationPlan`, `ConnectorSchemaContract`, `ContractRegistry`, `ContractValidatingProxy`  | Whether one schema change is compatible, which version bump it requires, and whether a safe migration can be generated |
| Committed governance snapshots | `schemas/snapshots/connectors/contracts.json` and `schemas/snapshots/fabric/connector_contract_registry.json` | CI drift detection and documented downstream impact for connector contract changes                                     |

## Current Snapshot Surface

The `contracts` object in each of the two committed JSON snapshot files listed
above has 5 curated source-contract entries:

`eurostat.data.generic`, `sdmx.generic`, `ukons.datasets.generic`,
`worldbank.wdi.generic`, and `wvs.wave7.generic`.

| Artifact                                                    | Role                                                                   | Check command                                                                                                             | Refresh command                                                               |
| ----------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `schemas/snapshots/connectors/contracts.json`               | Baseline connector contract snapshot built from `ALL_SOURCE_CONTRACTS` | `uv run polisyos-tools connectors check-contracts --check`                                                                | `uv run polisyos-tools connectors check-contracts --update`                   |
| `schemas/snapshots/fabric/connector_contract_registry.json` | Fabric governance snapshot with impact and migration evidence          | `uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out _build/.tmp/fabric-schema-governance.json` | `uv run python tools/quality/validation/fabric_schema_governance.py --update` |

## Change Classification

`SchemaEvolution.compare()` classifies schema changes into version-bump
categories:

| Change family                       | Examples in code                                                                                                                                    | Expected bump |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- |
| Compatible additions or relaxations | `FIELD_ADDED`, `FIELD_MADE_NULLABLE`, `TYPE_WIDENED`, `BOUNDS_RELAXED`, `ALLOWED_VALUES_EXPANDED`                                                   | `minor`       |
| Breaking changes                    | `FIELD_REMOVED`, `FIELD_MADE_REQUIRED`, `TYPE_NARROWED`, `PRIMARY_KEY_CHANGED`, `UNIT_CHANGED`, `SEMANTIC_TYPE_CHANGED`, time/geo dimension changes | `major`       |
| Metadata-only updates               | `DESCRIPTION_UPDATED`, `SOURCE_UPDATED`, `TAGS_UPDATED`                                                                                             | `patch`       |

`tests/unit/fabric/connectors/test_schema_system.py` is the executable reference for
type widening/narrowing, semantic typing, schema version semantics, dataframe
validation, and coercion behavior.

## Governance Requirements

`evaluate_contract_governance()` and the Fabric schema-governance check share
the same policy:

| Case              | Current rule                                                                                                                                                                                      |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Breaking change   | Must use a major version bump and include owner, reviewer, `approved_major_bump=true`, `migration_note`, downstream impact summary, at least one ADR ref, and a non-`not_needed` migration status |
| Compatible change | Must use at least a minor bump and, when possible, emits a `MigrationPlan` with SQL statements                                                                                                    |
| Impact evidence   | The CI/runtime evidence surface reports impacted downstream surfaces as `connector:<id>`, `dataset:<id>`, and `schema:<id>`                                                                       |

The enforcement examples are in
`tests/repo_quality/tools/test_fabric_schema_governance.py` and
`tests/unit/fabric/connectors/test_contract_system.py`:

- breaking changes fail without governance metadata;
- compatible additions emit migration SQL;
- runtime registry contracts and CI snapshots stay version-aligned;
- evidence payloads include impacted surfaces and compatible migration plans.

## Runtime Contract Flow

| Step                     | API                                        | Purpose                                                                                      |
| ------------------------ | ------------------------------------------ | -------------------------------------------------------------------------------------------- |
| Define schema            | `DataSchema`, `FieldSpec`, `SchemaVersion` | Declare connector dataset structure and compatibility boundary                               |
| Bind schema to connector | `ConnectorSchemaContract`                  | Attach dataset pattern, quality thresholds, and approval metadata                            |
| Diff versions            | `SchemaEvolution.compare()`                | Produce an `EvolutionReport` with breaking/non-breaking changes                              |
| Evaluate governance      | `evaluate_contract_governance()`           | Validate version bump, metadata requirements, and downstream impact                          |
| Enforce at fetch time    | `ContractValidatingProxy`                  | Validate `FetchResult` payloads against the resolved contract and configured validation mode |

## Validation Anchors

```bash
uv run pytest tests/unit/fabric/connectors/test_schema_system.py -q
uv run pytest tests/unit/fabric/connectors/test_contract_system.py -q
uv run pytest tests/repo_quality/tools/test_fabric_schema_governance.py -q
uv run polisyos-tools connectors check-contracts --check
uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out _build/.tmp/fabric-schema-governance.json
```
