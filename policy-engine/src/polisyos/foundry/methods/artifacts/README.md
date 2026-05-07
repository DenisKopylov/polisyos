# Foundry Method Artifacts

`polisyos.foundry.methods.artifacts` owns immutable provenance records for
method, chain, and execution evidence.

## Home

- `parts.py` exposes the public artifact functions and dataclasses.
- `_chain.py`, `_method.py`, `_evidence.py`, `_fingerprint.py`, and
  `_records.py` are private implementation slices.
- Public callers should import from `polisyos.foundry.methods.artifacts`.

## Authoring Rules

- Keep artifact payloads deterministic and content-addressable.
- Add schema-version changes beside compatibility tests.
- Do not add backend execution logic here; backend receipts are passed in from
  `backends/` and persisted here.

