# schemas — Policy Engine Contract Baseline

`schemas/` stores fixed contract artifacts shared by `ir`, `fabric`, `runtime`, and clients. CI uses these files for drift and compatibility checks; do not edit them manually outside the generators.

## Directory Contents

| Artifact                                                       | Purpose                                                           |
| -------------------------------------------------------------- | ----------------------------------------------------------------- |
| `snapshots/ir/*.schema.json`, `snapshots/fabric/*.schema.json` | JSON Schema baseline for semantic diff                            |
| `snapshots/*/_manifest.json`                                   | Generation metadata and hashes (`sha256_full`, `sha256_semantic`) |
| `snapshots/connectors/contracts.json`                          | Snapshot of source-connector contracts                            |
| `runtime_api_v1.openapi.json`                                  | Committed OpenAPI contract for Runtime API v1                     |

The code ABI registry package is `src/polisyos/schemas/abi_models/`: `__init__.py` owns enum/dataclass definitions and the public model API/selectors, while `catalog.py` owns registered ABI entries. This directory is reserved for JSON/YAML/OpenAPI snapshot artifacts.

## Where to Check Current State

This page describes where contracts live; it is not a consolidated inventory of their current sizes and versions. For owners, statuses, and committed outputs, use the [generated-artifact catalog](../docs/reference/generated-artifacts.md) and its [source registry](../architecture/generated_artifacts.toml). For any specific value, check the corresponding source contract and snapshot or manifest.

- Code ABI model API and registry: `src/polisyos/schemas/abi_models/__init__.py` and `catalog.py`; ABI snapshots and manifests: `snapshots/ir/` and `snapshots/fabric/`.
- Source connector contracts: `src/polisyos/fabric/connectors/sources/_contracts/`; committed snapshot: `snapshots/connectors/contracts.json`.
- Runtime API source: `src/polisyos/runtime/http/`; committed OpenAPI snapshot:
  `runtime_api_v1.openapi.json`.

These are distinct sets with different denominators: the number of models in the registry is not the number of schema files in a snapshot, and the number of connector definitions is not the number of OpenAPI operations. When stating any count or version, name the exact artifact and its own version or generation metadata; do not combine them into one “current” counter.

`packages/runtime-api-client` owns the full generated client chain; its
low-level renderer writes only to a caller-provided private scratch path,
while `types.ts` and the canonical TS/JS client are the committed outputs.

## Architecture Flows

```text
src/polisyos/ir/** + src/polisyos/ir/world/abi.py
  -> src/polisyos/schemas/abi_models/{__init__.py,catalog.py}
  -> tools/quality/diagnostics/gen_schema.py
  -> schemas/snapshots/{ir,fabric}
  -> ABI checks: .github/workflows/abi.yml + .github/workflows/ci.yml
```

```text
src/polisyos/fabric/connectors/sources/_contracts/*
  -> polisyos-tools connectors check-contracts
  -> schemas/snapshots/connectors/contracts.json
  -> arch check: .github/workflows/ci.yml
```

```text
src/polisyos/runtime/http/app.py
  -> tools/ops_runners/runtime/export_runtime_openapi.py
  -> schemas/runtime_api_v1.openapi.json
  -> tools/ops_runners/runtime/check_runtime_api_contract.py
  -> packages/runtime-api-client/scripts/generate-runtime-api-client.sh
  -> packages/runtime-api-client/{types.ts,canonicalRuntimeApiClient.ts,canonicalRuntimeApiClient.js}
  -> apps/runtime-dashboard/scripts/generate-api-client.sh -> apps/runtime-dashboard/src/api/types.ts
```

## Related Directories

| Directory                                           | Role relative to `schemas/`                                                |
| --------------------------------------------------- | -------------------------------------------------------------------------- |
| `src/polisyos/ir`                                   | Source of Pydantic ABI models for `snapshots/ir`                           |
| `src/polisyos/ir/world/abi.py`                      | Source of enum ABI (`edge_kind`, `node_kind`) for `snapshots/fabric`       |
| `src/polisyos/fabric/connectors/sources/_contracts` | Source of connector contracts for `snapshots/connectors/contracts.json`    |
| `src/polisyos/runtime/http`                         | Source of the OpenAPI contract for `runtime_api_v1.openapi.json`           |
| `tools/quality/diagnostics`                         | ABI snapshot and semantic-diff generation (`gen_schema.py`, `abi_diff.py`) |
| `tools/devx/connectors`                             | Drift/compatibility checks and connector-snapshot updates                  |
| `tools/ops_runners/runtime`                         | OpenAPI export, hardening and drift checks, runtime-client generation      |
| `packages/runtime-api-client`                       | Committed runtime SDK (TS/JS)                                              |
| `apps/runtime-dashboard`                            | Generation of OpenAPI types for the UI (`corepack pnpm run generate:api`)  |

## Commands (from `policy-engine/`)

```bash
# Check the baseline without modifying it
uv run --extra ml polisyos-tools diagnostics gen-schema --check
uv run polisyos-tools connectors check-contracts --check
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
```

```bash
# Update the baseline
uv run --extra ml polisyos-tools diagnostics gen-schema
uv run polisyos-tools connectors check-contracts --update
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
corepack pnpm --dir packages/runtime-api-client run generate -- --openapi schemas/runtime_api_v1.openapi.json
```

```bash
# Synchronize UI types
cd apps/runtime-dashboard
corepack pnpm run generate:api
```

```bash
# Local ABI semantic diff (before a PR)
uv run --extra ml polisyos-tools diagnostics gen-schema --output-dir /tmp/current_schemas
python3 tools/quality/diagnostics/abi_diff.py \
  --baseline schemas/snapshots \
  --current /tmp/current_schemas \
  --format markdown
```

## Maintenance Invariants

- Do not add Python modules or package markers to `schemas/`; product imports go through `polisyos.*`, not `import schemas`.
- Do not edit files in `snapshots/ir` or `snapshots/fabric` manually.
- Do not edit `snapshots/connectors/contracts.json` manually; use `check_contracts.py --update`.
- Every Runtime API change must be accompanied by synchronized updates to:
  - `schemas/runtime_api_v1.openapi.json`,
  - `packages/runtime-api-client/types.ts` and the canonical TS/JS client,
  - `apps/runtime-dashboard/src/api/types.ts`.

## Subdirectory Details

- `schemas/snapshots/README.md`
- `schemas/snapshots/ir/README.md`
- `schemas/snapshots/fabric/README.md`
- `schemas/snapshots/connectors/README.md`
