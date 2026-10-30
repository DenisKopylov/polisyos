# Core artifact tests

These tests cover canonical artifact identity, manifests, CAS storage and ownership,
typed refs, lineage, transfer, integrity and fresh-reader behavior. The owning package
contract is documented in [`src/polisyos/core/artifacts/README.md`](../../../../src/polisyos/core/artifacts/README.md).

Run the suite from `policy-engine/` with `uv run pytest tests/unit/core/artifacts -q`.
