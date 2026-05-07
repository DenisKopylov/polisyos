# Generated Index: IR Schema Snapshots

Owner: `team-ir`
Source: `schemas/snapshots/ir/_manifest.json`
Last updated: 2026-05-05

This index is a local generated-index placeholder for Phase 4.10. Phase 6.4 may
replace it with a tool-rendered catalog, but the contract below is stable.

## Contents

| Category | Files | Policy |
| --- | --- | --- |
| ABI schemas | `*.schema.json` | Generated from registered IR ABI models. |
| Manifest | `_manifest.json` | Generated snapshot inventory and hashes. |
| Local docs | `README.md`, `AUTHORING.md`, `index.md` | Human navigation only. |

## Regeneration

```bash
cd policy-engine
python3 tools/quality/diagnostics/gen_schema.py --models ir
```
