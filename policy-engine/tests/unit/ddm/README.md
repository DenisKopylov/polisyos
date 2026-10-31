# DDM unit tests

These tests cover the canonical Drift-and-Degradation Monitor contracts, source
admission, readiness and replay behavior. The package defines its production-source
boundary in [`src/polisyos/ddm/README.md`](../../../src/polisyos/ddm/README.md).

Run the suite from `policy-engine/` with `uv run pytest tests/unit/ddm -q`.
