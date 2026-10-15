# tools/ops_runners/runtime

Utilities for Runtime API contracts and operational tasks involving legacy runs.

## Role in the System

- keep `Runtime API <-> OpenAPI <-> frontend client` synchronized;
- support inventory and archiving of legacy data in `runs/`.

## Scripts

| Script                          | What It Does                                                                                         | Used By              |
| ------------------------------- | ---------------------------------------------------------------------------------------------------- | -------------------- |
| `export_runtime_openapi.py`     | Exports deterministic OpenAPI JSON (`schemas/runtime_api_v1.openapi.json`)                           | Manual run / release |
| `generate_runtime_client.py`    | Low-level raw TS/JS generation stage for a package-owned scratch handoff                             | Package generator    |
| `check_runtime_api_contract.py` | Checks OpenAPI and full canonical generated-family drift; validates invariants                       | `ci.yml`             |
| `inventory_legacy_runs.py`      | Inventories `runs/<id>/manifest.json` before cutover                                                 | Manual/Ops           |
| `archive_legacy_runs.py`        | Creates a deterministic tar.gz archive of `runs/` plus a JSON report (optionally deletes the source) | Manual/Ops           |
| `runtime_state_cleanup.py`      | Dry-run/apply cleanup for registered `.polisyos` slots                                               | Manual/Ops           |

## Related Directories

- `src/polisyos/runtime/http/*` (OpenAPI source)
- `schemas/runtime_api_v1.openapi.json`
- `packages/runtime-api-client/types.ts` and canonicalRuntimeApiClient.{ts,js}
- `runs/*` (legacy manifests and archiving)

## Typical Usage

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
corepack pnpm --dir packages/runtime-api-client run generate -- --openapi schemas/runtime_api_v1.openapi.json
PYTHONPATH=src:. uv run python tools/ops_runners/runtime/inventory_legacy_runs.py --runs-root runs --output _build/.tmp/legacy_runs_inventory.json
uv run python tools/ops_runners/runtime/runtime_state_cleanup.py --slot runs --dry-run
```

## Notes

- By default, `check_runtime_api_contract.py` checks OpenAPI and the full canonical generated family; `--skip-client-drift` remains only as a compatibility flag for OpenAPI-only invocations.
- `archive_legacy_runs.py` creates a deterministic archive (with normalized uid/gid/mtime) for reproducibility.
- `runtime_state_cleanup.py` does not delete `production_data` without `--approve-production-snapshots`.
