# E2.11 IR Transport and Streaming v1.0

## Goal

Define the interoperable contract for:

- JSON-first manifests with optional binary sidecars;
- delta artifacts and incremental relinking;
- observation-heavy streaming updates.

## Canonical Rule

The JSON manifest remains the compatibility and CAS anchor. Binary payloads are
optional delivery optimizations and must never replace the manifest as the
source of schema/version/canonical policy.

## Pilot Family

The initial binary/streaming pilot family is `observation_record_batch`.

Relevant contracts:

- `TransportDescriptor`
- `ObservationBinaryBatchArtifact`
- `ArtifactDeltaEnvelope`
- `IncrementalRelinkManifest`
- `ObservationStreamCheckpoint`
- `ObservationStreamUpdate`

## Wire Policy

- JSON manifest media type: `application/json`
- Pilot binary sidecar: `application/vnd.apache.arrow.stream`
- Pilot wire format enum: `BinaryWireFormat.ARROW_IPC_STREAM`
- Delta semantics: `append_only`, `upsert`, `full_replace`

## Incremental Relinking

Every delta that may invalidate composed/linker state should emit an
`IncrementalRelinkManifest`:

- `affected_slots`
- `affected_mechanisms`
- `affected_constraints`
- `affected_queries`
- `requires_full_relink`

If `requires_full_relink=true`, consumers must not assume localized refresh is
safe.

## Streaming Update Contract

`ObservationStreamUpdate` may include:

- inline `entries`;
- an Arrow sidecar referenced by `binary_batch`;
- a generic `delta` envelope;
- a durable `checkpoint`;
- a companion `relink_manifest`.

At least one of `entries`, `binary_batch`, or `delta` must be present.
