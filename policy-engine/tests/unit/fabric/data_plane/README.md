# Fabric data-plane tests

This suite covers ingestion modes, source and cursor admission, record/replay, streaming,
CDC, cleanup, quarantine and data-plane consumer behavior. The owning module's boundaries
and command surface are documented in [`src/polisyos/fabric/data_plane/README.md`](../../../../src/polisyos/fabric/data_plane/README.md).

Run the suite from `policy-engine/` with `uv run pytest tests/unit/fabric/data_plane -q`.
