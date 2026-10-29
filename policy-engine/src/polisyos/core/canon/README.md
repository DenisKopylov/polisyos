# Core canonical codec

`polisyos.core.canon.canon_json` supplies Core's canonical JSON facade over the
shared Common mechanics. Core and IR retain separate native-tag policies and
`CanonViolation` identities. Unqualified reads and default writes retain the
historical `.2` law; existing `.2` bytes, hashes and named hash domains are not
rewritten or reinterpreted.

## Direct bounded encoding

The module-level `to_bounded_canonical_bytes(value, spec, limits)` snapshots the
selected `CanonSpec`, encodes supported values under the supplied
`CanonicalResourceLimits`, and checks that the resulting bytes round-trip
under the same Core profile. The package facade now re-exports the existing
`to_bounded_canonical_bytes` and `CanonicalResourceLimits` for owner-admitted
primitive projections, including the bounded Fabric capture consumer. This is
an additive facade export of existing mechanics, not a codec/profile change.
The three representation carriers remain leaf-module surfaces; no persisted
`.3` writer or caller authority follows. Root must regenerate/review the public
inventory and reference companions before marking that review complete.

The vector counts actual encoded bytes, JSON lexical elements and physical
container depth, including native envelopes and `.3` raw-mapping wrappers.
Logical depth remains a separate `CanonSpec.max_depth` constraint. Supported
bounded values are exact built-in JSON scalars, bytes, lists, tuples and
dictionaries with exact string keys, and the three exact Core carrier classes.
Callback-bearing projections such as models, dataclasses, Decimal, enums and
custom mappings require a separately admitted owner projection. See the
[Common codec contract](../../common/README.md#bounded-canonical-codec) for
the resource and snapshot boundaries.

The exact `polisyos.canon.json@0.3.0` grammar structurally escapes ordinary
mappings containing `_type`. The `bytes_hex`, finite `float_hex` and opaque
`array_digest` carriers use their selected Core `.3` native tags instead;
ordinary maps with the same shape remain data. `float_hex` preserves signed
zero and obeys the selected float prohibition. The array descriptor identifies
its supplied representation; it does not attest or recover array contents.
IR does not acquire Core-only native tags. Newly introduced carrier emission
requires the exact `.3` grammar and the selected tag policy. Historical `.2`
hex and array-tag reads keep their existing primitive/dictionary meaning.

## Persisted artifacts and rollout

The direct bounded API does not enable a persisted `.3` writer or supply an
owner-authorized resource policy. A caller-chosen `policy_id` is a label, not
proof that a store, manifest profile, reader or backend is ready. Existing
artifact-writer admission continues to refuse `.3`; unknown declarations remain
unqualified or refuse authority use. Selected `.3` artifact readers must bind
the exact manifest and payload, complete codec flags, reader identity and
owner vector before their corresponding writers can be enabled. State,
checkpoint, Foundry/cache, installed and rollback consumers need their own
reader-first verification. No producer authority, currentness, G acceptance or
formal closure follows from a direct codec result.

## Qualified persisted reads

The selected Core artifact readers now use `core-tag-policy@2` for an explicitly
declared `.3` profile and retain `core-tag-policy@1` for `.2`. Core `.3`
`bytes_hex`, `float_hex` and `array_digest` native envelopes return their exact
representation carrier types; the float carrier preserves signed zero, while the
array carrier remains an opaque supplied descriptor. A similarly shaped escaped
ordinary map remains data. The direct codec contract and the persisted writer
fence above remain distinct. See the
[qualified read contract](../../../../docs/reference/canonical-json-profile-reads.md).
