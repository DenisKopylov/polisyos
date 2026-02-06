# ABI Schema Snapshots

This directory stores ABI model registry and committed JSON Schema snapshots used by CI.

## Layout

- `abi_models.py`: single source of truth for ABI-tracked models/enums.
- `snapshots/ir/*.schema.json`: committed IR schemas.
- `snapshots/fabric/*.schema.json`: committed fabric/world enum schemas.
- `snapshots/*/_manifest.json`: generator metadata and per-model hashes.

## Workflow

1. Update ABI model code.
2. Run `python3 tools/gen_schema.py`.
3. Review diffs in `schemas/snapshots/`.
4. CI runs `tools/abi_diff.py` against baseline and blocks unversioned breaking changes.

## Compatibility Modes

- `strict`: producer must not emit unknown fields for older consumers (typical when `extra="forbid"`).
- `tolerant`: additive optional fields are considered backward compatible.

## Priority

- `p0`: breaking changes can fail CI without required version bump.
- `p1`: breaking changes are warning-level by default.
- `p2`: informational tracking.
