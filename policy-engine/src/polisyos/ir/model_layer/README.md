# IR Model Layer

`polisyos.ir.model_layer` owns the low-level model contracts that describe IR
payload semantics rather than loading or registry composition. It contains:

- `model_spec.py` for the Trinity `ModelSpec` "how" artifact.
- `canon.py` for canonical JSON and content hashing helpers. Its fixed
  `.2` `ir-tag-policy@1` and explicit `.3` `ir-tag-policy@2` decoders remain
  narrower than Core and refuse Core-only native tags such as `array_digest`.
  These identities describe materialization context, not producer attestation.
- `predicate.py`, `queries.py`, `types.py`, and `units.py` for shared model
  vocabulary used by governance, observation, analytics, and linker code.

Do not add loading, registry, observability, or other cross-cutting
implementations here. Adapter code belongs under `polisyos.ir._adapters`.

`polisyos.ir.model_layer` lazily re-exports the documented `types.py` vocabulary, including `SelectorOperator`, by identity. It remains a value/type facade and does not decide policy admissibility.

## Canonical reader versions

The generic selected IR artifact reader uses `ir-tag-policy@2` only for explicit
canonical `.3` profiles. Unqualified reads, default writes and selected `.2`
profiles retain `ir-tag-policy@1`. Both policies keep IR's narrow native tag set.
`IR_V3_TAG_POLICY_ID` is exported by `canon.py.__all__`; it is not re-exported by
the top-level model-layer facade. Owned callback cohorts and `.3` writers remain
unqualified and refused until their separate admission is demonstrated.
