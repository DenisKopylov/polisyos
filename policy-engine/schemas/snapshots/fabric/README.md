# snapshots/fabric — World-ABI Enum Baseline

This directory stores JSON Schema snapshots for `edge_kind` and `node_kind`, which serve as a stable enum boundary for world/Fabric integrations.

## Role in the System

- Protects graph-layer compatibility through the same ABI-gate mechanisms as `snapshots/ir`.
- Serves as the baseline for `tools/quality/diagnostics/gen_schema.py --check` in CI.

## Data Sources

- ABI type definitions: `src/polisyos/schemas/abi_models/__init__.py`; registry entries: `src/polisyos/schemas/abi_models/catalog.py` (`module="fabric"`).
- Enum-class source: `src/polisyos/ir/world/abi.py`.
- Generator: `tools/quality/diagnostics/gen_schema.py`.

## Contents

- `edge_kind.schema.json`
- `node_kind.schema.json`
- `_manifest.json` (model metadata plus `sha256_full`/`sha256_semantic`)

## Recorded State (2026-03-03)

- Models: `2`.
- `generated_at`: `2026-03-02T16:48:08+00:00`.
- Both contracts have `priority=p0`, `compat_mode=strict`, and `version_field=null`.

## Commands (from `policy-engine/`)

```bash
python3 tools/quality/diagnostics/gen_schema.py --models fabric --check
python3 tools/quality/diagnostics/gen_schema.py --models fabric
```

## Invariants

- Do not edit schemas or `_manifest.json` manually.
- Every enum change in `src/polisyos/ir/world/abi.py` must be accompanied by snapshot regeneration and a passing ABI gate.
