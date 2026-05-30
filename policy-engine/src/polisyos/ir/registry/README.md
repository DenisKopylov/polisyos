# IR Registry

`polisyos.ir.registry` owns artifact-reference and registry composition contracts. It
contains:

- `registry_fragments.py` for registry fragment composition and conflict
  reporting.
- `refs.py` for typed artifact references.
- `public_surface.py` for the registry-owned view of IR facade metadata.

Bibliographic and document-fragment citation refs live in
`polisyos.ir.loading.citations`. The retired `polisyos.ir.references` aggregate
must not be recreated as a physical `registry/references.py` module.

Keep concern adapters out of this package. Cross-cutting integration code must
live under `polisyos.ir._adapters`.
