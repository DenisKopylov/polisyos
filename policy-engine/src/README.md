# Source Tree

- Owner: team-architecture
- Purpose: canonical Python product packages for PolicyOS runtime, data, IR, fabric, foundry, scientist, and supporting domains.
- Allowed contents: importable product packages, package-level authoring docs, typed source modules, and package assets that are required at runtime.
- Local verification: `uv run pytest tests/contract -q`
- Maintenance: new top-level packages require an architecture contract update before adoption; compatibility shims must carry a dated sunset.
