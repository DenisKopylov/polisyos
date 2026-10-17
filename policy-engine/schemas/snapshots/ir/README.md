# snapshots/ir — IR Model ABI Baseline

This directory contains JSON Schema snapshots of IR contracts and serves as the baseline for semantic diffs (`tools/quality/diagnostics/abi_diff.py`).

## Role in the System

- Records the public ABI between `src/polisyos/ir/**` and its consumers (runtime, pipelines, analytics, and governance).
- Checked by the tracked [`abi.yml`](../../../../.github/workflows/abi.yml).
- A similar [`arch.yml`](../../../ops/ci/templates/workflows/arch.yml) is in the `ops` workflow-template directory. `.github/workflows/arch.yml` is absent from the snapshot, so this link must not be treated as a root CI trigger.

## Sources

- Registry entries: [`abi_models/catalog.py`](../../../src/polisyos/schemas/abi_models/catalog.py) (`module="ir"`); public model types are defined and exported by `abi_models/__init__.py`.
- Generator: [`gen_schema.py`](../../../tools/quality/diagnostics/gen_schema.py).
- Compatibility check: [`abi_diff.py`](../../../tools/quality/diagnostics/abi_diff.py).

## Contents

- `*.schema.json` — schema for one ABI model.
- `_manifest.json` — model index and generation metadata:
  - `schema_file`, `schema_version`, `priority`, `compat_mode`, `version_field`;
  - `sha256_full` and `sha256_semantic` for drift/compatibility checks.

## Historical README Summary (2026-03-03)

The counts and values below are preserved from the README summary for that date and do not describe the current manifest. For the contents and metadata of the inspected snapshot, use the canonical [`_manifest.json`](_manifest.json).

- Models: `48`.
- `generated_at`: `2026-03-03T16:49:25+00:00`.
- Priorities: `p0=16`, `p1=23`, `p2=9`.
- All models were active, with `compat_mode=strict`.
- `version_field=None` for `certification_result`, `data_view_request`, and `outer_search_result`.
- Naming note: the key `causal_sensitivity_result` maps to the file `sensitivity_result.schema.json`.

## Related Domains

- Trinity/Policy: `trinity_bundle`, `problem_frame`, `policy_spec`, `policy_portfolio`.
- Norm system: `norm_pack`, `norm_rule`, `norm_ref`.
- World/fact log: `claim`, `conflict_*`, `world_event`, `prov_activity`, `fact*`, `doc_*`.
- Analytics/gates: causal, transportability, calibration, certification, `gate_*`.

## Commands (from `policy-engine/`)

```bash
# Check and update only the IR snapshot
python3 tools/quality/diagnostics/gen_schema.py --models ir --check
python3 tools/quality/diagnostics/gen_schema.py --models ir
```

```bash
# Local semantic diff before a PR
python3 tools/quality/diagnostics/gen_schema.py --output-dir /tmp/current_schemas
python3 tools/quality/diagnostics/abi_diff.py \
  --baseline schemas/snapshots \
  --current /tmp/current_schemas \
  --format markdown
```

## Invariants

- Do not edit files in this directory manually.
- Make changes to the source models, then regenerate through `gen_schema.py`.
