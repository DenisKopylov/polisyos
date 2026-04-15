# ADR-0104: IR Canonical JSON and CAS Hash Policy

Status: accepted

Date: 2026-04-12

## Context

IR artifacts, world IDs, fact logs, analytics contracts, and CAS manifests all
depend on canonical bytes. The previous canon path had several ambiguous
behaviors: unknown canonical `_type` objects decoded as plain dictionaries,
dataclasses were flattened through `dataclasses.asdict()`, `None` handling was
implicit, recursive payloads had no depth guard, and `sha1` remained available
beside default CAS hashing.

## Decision

Canonical `_type` is reserved for canon-generated typed envelopes. Supported
types are `datetime`, `date`, `decimal`, `bytes`, and `float`; unknown values
raise `CanonViolation` during encode or decode instead of silently passing
through.

Structured objects use field-aware normalization. Pydantic models are dumped
with aliases and the configured `exclude_none` policy. Dataclasses are traversed
field-by-field by the canonicalizer and are not converted with
`dataclasses.asdict()`, so nested `BaseModel` values keep their canonical model
semantics.

`CanonSpec.exclude_none=True` is part of the ABI for field-bearing structured
objects. Callers may opt out with `CanonSpec(exclude_none=False)`. Raw mappings
preserve explicit `None` values as JSON `null`, because a dictionary key with
`None` can be semantically different from an absent key.

Canonical recursion is capped by `CanonSpec.max_depth` and defaults to `128`.
World-ID payload normalization uses the same default cap before hashing.

Datetime values are normalized to UTC with a `Z` suffix. The generic canonical
serializer continues to interpret naive datetimes as UTC for legacy
compatibility, but fact-log `tx_time` is stricter: it is mandatory,
timezone-aware, and normalized to UTC `Z`.

Floats are forbidden by default. Analytics contracts that need binary64 values
must opt in with `CanonSpec(forbid_floats=False)`. NaN and infinity are always
forbidden by default, finite values are serialized with a stable 17-digit
representation, and signed zero is normalized to `0`.

Content hashing is SHA-256 by default. `blake2b` remains an explicit non-default
option. `sha1` is available only as an explicit deprecated legacy branch and
emits a `DeprecationWarning`; it is not part of the canonical CAS execution
path.

`content_hash(str)` encodes strings as UTF-8 and hashes the resulting bytes.
`content_hash(bytes)` hashes raw bytes. When string and byte payloads must remain
semantically distinct, callers must hash `to_canonical_bytes(...)`, where bytes
are represented by a typed canonical envelope.

Migration functions may omit `schema_version` and allow the migration framework
to stamp the registered target version. If a migration function returns its own
`schema_version`, it must match the registered edge exactly; otherwise migration
fails with a structured schema-version error.

## Consequences

CAS hashes remain stable for existing JSON-like payloads while schema-evolution
and nested structured-object paths fail closed. New canon features are recorded
in `CanonInfo` metadata with canon version `0.2.0`, `exclude_none`, and
`max_depth` so persisted artifacts can explain the byte policy used at write
time.
