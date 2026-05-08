# IR Model Layer

`polisyos.ir.model_layer` owns the low-level model contracts that describe IR
payload semantics rather than loading or registry composition. It contains:

- `model_spec.py` for the Trinity `ModelSpec` "how" artifact.
- `canon.py` for canonical JSON and content hashing helpers.
- `predicate.py`, `queries.py`, `types.py`, and `units.py` for shared model
  vocabulary used by governance, observation, analytics, and linker code.

Do not add loading, registry, observability, or other cross-cutting
implementations here. Adapter code belongs under `polisyos.ir._adapters`.
