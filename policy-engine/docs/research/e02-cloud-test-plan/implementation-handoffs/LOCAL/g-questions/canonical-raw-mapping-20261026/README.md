# G decision request: preserve or refuse raw `_type` mappings (R4 precision correction)

Status: **draft for G decision, not approved and not closure**. R4 evidence frame: HEAD `f3635dedb8eb8115e62f139ac077165f3b529fad`, tree `5366ce42efd8e3fe1d8867ebfeb370f01e604e20`. The runtime probes below executed at HEAD `580d6256412efac3b8265592b805a9e848ec8530`; all 22 pinned source/test files were rehashed at R4 HEAD and match, so this receipt-only advance changes no probed source bytes.

## Decision requested

Should ordinary application mappings whose literal one-underscore `_type` key matches a recognized canonical envelope be a losslessly representable value in persisted canonical JSON, or should current APIs reject those inputs before state persistence and cache lookup?

**Recommendation: Option A**, a separately versioned mapping-escape grammar. Current public state and Foundry inputs admit these mappings, and the separate runner-wire owner already escapes them to preserve user data. Keep the current `.2` reader semantics unchanged.

## Evidence

`ExperimentState.params` accepts `dict[str, Any]` values and `Decimal` values. The public `run_experiment` entrypoint accepts a `Mapping` and validates it as `ExperimentState`. In the current Core and IR probes, the raw map `{'_type':'decimal','value':'1'}` and `Decimal('1')` emit identical `.2` bytes; both selected readers return Decimal. In the state probe, the Python-mode payload bytes also compare equal (`state_python_dump_core_bytes_equal=true`), while the JSON-mode dumps compare different (`state_json_dumps_equal=false`). The same historical stdout contains a misleading field named `state_projection_core_bytes_equal`: its invocation script assigns `cenc(raw_j)!=cenc(dec_j)`, so the recorded `true` means those projection bytes DIFFER. The field name must not be read as equality; the invocation and receipt are cited in `inputs.json`. A direct Foundry `compute_static_params_hash` probe gives the raw map and Decimal the same cache hash before compiler lookup. Sync and async state persistence call `put_json(state.model_dump())`.

The Foundry hash producer is a key part of this contract. `_convert_value_for_canonical` currently turns native Decimal, bytes, and float inputs into plain tag-shaped dictionaries before calling the Core encoder. Therefore a new mapping escape alone would not distinguish raw user maps from native values on this path; Option A must preserve their type distinction until the versioned encoder.

The repository already defines a different answer for worker transport: its runner serializer escapes a user mapping with the same `_type` key into a `mapping/entries` envelope, and an actual outcome test verifies the user mapping survives. This is evidence for an existing pattern, not authority to reuse that wire tag as canonical profile law.

The earlier refusal-only packet classified the map as out of contract. This draft corrects that classification: the selected canonical profile reserves `_type`, but current state and cache APIs admit ordinary mappings with it and the writer currently accepts the colliding input. The product choice is whether to preserve this exposed input domain or narrow it explicitly.

## Option A — add a versioned lossless mapping escape (recommended)

Add an explicit mapping escape in each affected canonical owner at its existing version slot (proposed `.3.0` per owner), using the bounded `mapping/entries` shape as a reuse-first implementation reference. A raw user mapping with the exact `_type` key is encoded as mapping data before its contents can be interpreted as a typed envelope; the wrapper is data transport, not a tag-policy change. Native Decimal/date/datetime/bytes/float values retain typed interpretation only where the selected owner already supports them. Core and IR keep separate owner-specific type policies.

The seven materializing forms are the UNION across the two current owners: Core .2 recognizes `bytes`, `bytes_hex`, `date`, `datetime`, `decimal`, `float`, and `float_hex`; IR .2 recognizes only `bytes`, `date`, `datetime`, `decimal`, and `float`. Test all seven tag-shaped raw mappings as mapping data under the new escape in both owners. Test native typed round trips only for types supported by that owner; do not widen IR to Core-only `bytes_hex` or `float_hex`. The reserved key is exactly one-underscore `_type`; `__type__` remains ordinary data.

On the Foundry path, change `_convert_value_for_canonical` to keep native Decimal values native and carry any non-native typed representation (such as the intentional `float_hex` form) in an explicit internal typed carrier until encoding. Do not convert both ordinary maps and typed values to plain dictionaries before the mapping escape. Include the selected profile/generation in the specialization-key transition or invalidate the old process-local cache before `.3` keys are admitted.

Use each existing `CanonSpec`/`CanonInfo.version` slot; do not add a producer-attestation or tag-policy field. Add explicit readers first, verify installed/no-checkout consumers, then enable each owner's `.3` writer. Keep the Core and IR owner policies separate: preserve Core's `.2` opaque `array_digest` behavior and IR's refusal of that `.2` tag; do not widen IR to Core's native typed tag set. Unknown or malformed unescaped typed envelopes continue to refuse. A newly encoded mapping envelope admits its inner raw map as data even when that content resembles an unknown or malformed tag. The mapping envelope is not an array descriptor or authority.

Keep all `.2` readers and historical `.2` bytes intact. A `.2` reader continues to interpret a recognized tag as the selected typed value; do not add a tagless-only legacy reader, infer original Python producer type, auto-import old bytes as maps, or rewrite/readdress CAS objects. Roll back by disabling new writers first and retaining `.3` readers for any `.3` artifact already emitted. Any later migration must be an explicit new artifact/view with lineage and actual execution time; it cannot establish the predecessor's original input intent.

## Option B — narrow admission under the existing `.2` law

Document and enforce that plain user mappings containing a one-underscore `_type` key are not admissible where the selected Core/IR policy would materialize them. Reject before run-state persistence and before Foundry specialization/cache lookup; keep the refusal typed and propagate it. In particular, Foundry's broad `except Exception` fallback around canonical serialization must not turn a semantic refusal into a JSON fallback.

Apply admission to the original user value before Foundry's internal Decimal/bytes/float tag conversion. Cover direct `ExperimentState` inputs, sync/async state persistence, checkpoint and node-cache persistence, and direct Foundry static parameters. Keep worker-wire behavior unchanged. Preserve Core `array_digest` and IR refusal, `__type__` mappings, and all valid native typed inputs. This changes the accepted public API domain and needs release notes plus tests proving refusal occurs before store/cache effects.

## Common rules and acceptance signal

Reuse the current version field for wire-law selection; do not use `reader_policy_id`, schema version, manifest digest, producer build version, or a new manifest field as proof of input intent. Do not create a new status enum. Neither option changes authority, admissibility, publication status, audience, freshness, provenance, or time semantics. Canonical version identifies a grammar; it does not attest producer identity or event time.

The state-read projection is outside this collision class: JSON mode preserves the raw mapping as an object and serializes Decimal as `'1'`. Specifically, the historical probe output's `state_projection_core_bytes_equal=true` is a misnamed field: the recorded invocation code computes `cenc(raw_j)!=cenc(dec_j)`, making true mean DIFFERENT. This is confirmed by `state_json_dumps_equal=false`; see the invocation/receipt/stdout pins in `inputs.json`. Do not rewrite that historical RAW probe; correct its interpretation here.

For A, fresh Core and IR readers under each owner's exact new version preserve raw maps as maps, including nested mappings and samples whose exact `_type` value is any of the seven UNION materializing forms. Native typed round trips are required only for types already supported by that owner; in particular IR does not gain native `bytes_hex`/`float_hex`. Existing unescaped unknown/malformed typed envelopes still refuse, Core `array_digest` stays opaque under its existing rule, and IR keeps refusing it. Pin exact byte/ID changes and historical `.2` fixtures. Foundry must keep input type until encoding and produce distinct hashes for raw-map and native Decimal inputs, with cache generation/version separation across rollout. For B, each affected entry boundary refuses before persistence/cache lookup, the typed refusal survives Foundry's fallback, and valid owner-supported native values plus existing worker-wire mapping round trips stay intact.

The evidence denominator is the concrete `run_experiment`/ExperimentState input, sync and async state persistence, checkpoint and NodeResultCache persistence, Foundry static-parameter hashing/cache lookup, and the separate runner-wire transport named in `inputs.json`. This is not a census of every repository canonical-serialization call or production prevalence. Installed/no-checkout consumers and the complete CAN suite remain unverified.

Pattern pass: P04/P05/P07/P10/P27/P29/P31/P32/P35/P37/P38/P40. The canonical arbitrary-map capability is not implemented under `.2`; runner-wire is a separate owner. No capability is claimed complete and no G closure is asserted.
