# Artifacts (`polisyos.ir.artifacts`)

`polisyos.ir.artifacts` defines the minimal CAS I/O protocol for the entire IR
layer. It contains no domain logic for specific artifacts: the package defines
`ArtifactID`, the store contract, schema metadata, and helpers through which
`analytics`, `observation`, and typed refs persist and load canonical payloads.

## Role in the system

- **Depends on:** `polisyos.ir.model_layer.canon`
- **Used by:** `polisyos.ir.analytics`, `polisyos.ir.observation`, `polisyos.ir.registry.refs`, `polisyos.core`, `polisyos.fabric`
- This package is a thin boundary between domain models and real CAS backends.

## Key concepts

- **Artifact identity** — `ArtifactID` fixes the canonical `sha256:<hex>` identifier.
- **Store protocol** — `ArtifactStore` defines the minimum JSON/bytes persistence contract.
- **Schema metadata** — `SchemaInfo`, `CanonInfo`, and `PutOptions` describe the stored payload.
- **Lineage normalization** — input refs and artifact refs are normalized before writing. A private IR-owned structural input edge accepts Core or IR string-root artifact IDs, then the existing strict normalizer validates and converts each edge at the write boundary.
- **Profile-aware reads** — `get_json_artifact()` requires the store's raw
  `get_raw_manifest_bytes()` capability. It parses the exact selected sidecar before any IR
  profile model can fill defaults, requires every current `CanonInfo` field, then reads
  the payload through that same artifact selector. It decodes and re-encodes under the
  declared formatting options and existing IR tag family; only an exact byte match is
  accepted. An ID-only raw reader needs no typed-manifest method; a full profile-bearing
  selector still requires exact typed-view resolution and is never downgraded. A typed
  manifest Mapping alone is not raw-profile evidence. Profile-less
  historical artifacts remain unsupported and require a separate compatibility decision.
  The check proves the declared profile reproduces these bytes, not which producer chose
  it. Byte-only reads cannot recover input properties that leave no byte witness—for
  example, whether `exclude_none=True` was intended when no null value appears.
- **Core/IR compatibility** — the current default Core `put_json` producer emits a
  complete profile and shared tags such as `decimal` can be read by a fresh IR reader.
  Supported stored formatting options are verified by a decode/re-encode equality check;
  reads do not rewrite payload bytes. The Core adapter and write-through cache preserve
  exact typed artifact-view selectors for raw manifest and payload reads.
  The Core-to-IR writer adapter accepts typed options or a `Mapping` and projects the
  complete declared Core write-option set, including tenant context, same-input closure,
  authority, and warnings; malformed values and unknown fields fail before persistence.
  IR artifact-ref normalization validates against the shared strict ref model. Unknown
  mapping keys, model fields (including excluded fields), and declared structural fields
  fail before a selected manifest or payload read; supported scalar IDs remain ID-only
  selectors and do not stand in for a selected-view ref.
  Core-only `float_hex`, `bytes_hex`, and `array_digest` tags remain unsupported by IR,
  even though Core and IR currently use the same canon name/version. A complete profile
  is a decoding input, not proof of an IR producer or authority. Raw Core writes and
  historical profile migration remain separate C02/G compatibility decisions.
- **Shared helpers** — analytics and observation bundles use the same `put_json_artifact()` / `get_json_artifact()` surface. When needed, a producer can call `put_json_artifact(..., return_selected_profile=True)` to receive the exact profile from that same write operation. Unsupported stores refuse before calling the writer; writer exceptions propagate without a current-default lookup fallback.

## Public API

The table lists selected facade names. The complete export set is owned by
`__all__` in `src/polisyos/ir/artifacts/__init__.py`.

| Type/Function                                        | Description                                                             |
| ---------------------------------------------------- | ----------------------------------------------------------------------- |
| `ArtifactID`                                         | Validated canonical artifact identifier                                 |
| `ArtifactStore`                                      | Protocol for CAS backends                                               |
| `PutOptions`, `StorePutOptions`                      | Write metadata, schema information, and lineage inputs                  |
| `normalize_artifact_ref()`, `normalize_input_refs()` | Normalize typed refs before persistence                                 |
| `put_json_artifact()`                                | Persist a canonical JSON artifact and return a standardized ref payload |
| `get_json_artifact()`                                | Load artifact bytes and decode them into a JSON object                  |

Full reference: [docs/reference/ir/](../../../../docs/reference/ir/index.md)

## Current state

- Last updated: 2026-10-14
- Files: 6 Python files under this package tree
- Exports: 33 public names in `__all__` in `__init__.py`
- Current usage: shared I/O layer for analytics artifacts, observation bundles, and typed `ir.refs`

## Explicit `.3` generic reads and callback boundary

Generic `get_json_artifact` accepts a complete selected `.3` canonical profile,
uses the `.3` grammar and retains `ir-tag-policy@2` as materialization context.
Its `.2` interpretation remains `ir-tag-policy@1`. Exact view selection and
byte re-encoding checks remain required. Core-only native descriptors stay
unsupported; their escaped ordinary mapping shapes remain ordinary data.

This does not qualify owned callback projections. Their private snapshot decoder
still uses the historical `.2` law, so the shared owned-profile admission refuses
`.3` before payload access or profile callbacks, even when a row or callback says
it is accepted. The private decode boundary repeats the same codec guard. A future
owned cohort must migrate and behaviorally qualify that entire path before the
guard is extended. Persisted `.3` writers remain fenced. See the
[qualified read contract](../../../../docs/reference/canonical-json-profile-reads.md).
