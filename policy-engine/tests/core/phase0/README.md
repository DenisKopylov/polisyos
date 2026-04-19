# Core Phase0 Tests

`tests/core/phase0` is the deepest platform-safety slice inside `tests/core`.
It covers artifact storage, canonical serialization, signing, run context,
audit export, and observability. The directory currently contains `23`
`test_*.py` files plus a local `conftest.py`.

## Purpose

- Protect content-addressed storage, registry bundles, and provenance shims.
- Keep canonical JSON and environment manifests reproducible.
- Verify signing, audit export, tracing, logging, and run-lifecycle behavior.

## Where To Start

- [`../../../src/polisyos/core/README.md`](../../../src/polisyos/core/README.md)
- `test_artifact_store.py`, `test_canon_json.py`, and `test_observability.py`
  for representative artifact, canon, and telemetry coverage.
- `conftest.py` if the change depends on local fixtures or setup.

## Public Entrypoints

- Artifact and provenance tests:
  `test_artifact_store.py`, `test_artifact_export_import.py`,
  `test_artifact_graph.py`, `test_provenance_contract_shims.py`
- Signing and trust tests:
  `test_signing.py`, `test_store_signing.py`, `test_cli_signing.py`
- Canon, environment, and run lifecycle tests:
  `test_canon_json.py`, `test_environment_manifest.py`,
  `test_run_context.py`, `test_registry_bundle.py`, `test_cli.py`,
  `test_cli_resume.py`
- Audit and observability tests:
  `test_audit_export_verify.py`, `test_audit_manifest_compat.py`,
  `test_tracer.py`, `test_metrics.py`, `test_logs.py`,
  `test_decorators.py`, `test_propagation.py`, `test_observability.py`

## Depends On / Depended On By

**Depends on**

- `src/polisyos/core/artifacts`
- `src/polisyos/core/canon`
- `src/polisyos/core/observability`
- `src/polisyos/core/run`

**Depended on by**

- [`../README.md`](../README.md) and the wider core slice
- Contract, runtime, scientist, and foundry tests that rely on the same
  artifact and observability guarantees

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full phase0 slice
uv run pytest tests/core/phase0 -q

# conceptual: targeted probes
uv run pytest tests/core/phase0/test_artifact_store.py -q
uv run pytest tests/core/phase0/test_canon_json.py -q
uv run pytest tests/core/phase0/test_observability.py -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/core/phase0 -q
```

## Reference Docs

- [`../README.md`](../README.md)
- [`../../../src/polisyos/core/README.md`](../../../src/polisyos/core/README.md)
- [`../../../docs/reference/generated-artifacts.md`](../../../docs/reference/generated-artifacts.md)
- [`../../../docs/reference/public-surface.md`](../../../docs/reference/public-surface.md)

## Last Updated

2026-04-17
