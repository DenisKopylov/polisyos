# Artifacts (`polisyos.core.artifacts`)

`core.artifacts` provides the content-addressable storage and reproducibility layer for PolicyOS.
It owns artifact ids, manifests, signatures, dependency graphs, registry bundle payloads, and
environment fingerprints.

## Role in System

- **Depends on:** `core.canon` for canonical hashing/JSON and `core.contracts` for typed refs.
- **Used by:** `foundry`, `scientist`, `fabric`, `scholar`, `runtime`, `registry`, and `audit`.
- **Boundary function:** gives every higher layer a stable CAS-backed artifact model.

## Key Concepts

- **FileSystemCAS** - deterministic on-disk CAS layout with manifest and signature sidecars.
- **Typed manifests** - `ArtifactManifest` captures payload identity, producer context, and schema/canon metadata.
- **Ed25519 signing** - detached signatures and trust/revocation policy support.
- **Exact signed evidence** - `signed_evidence.py` binds the raw blob, exact manifest sidecar,
  and exact detached-signature bytes into a separate CAS evidence record. It deliberately
  requires the filesystem exact-byte port; a generic `ArtifactStore` cannot issue anchor proof.
- **Dependency graphs** - artifact lineage can be exported, imported, and verified as a graph.
- **Environment capture** - reproducibility fingerprints track platform, runtime, and optional git/TEE context.
- **Registry bundles** - registry payloads are stored as first-class CAS artifacts.
- **Integrity reports** - `CASIntegrityReport` projects verified store reads and manifest authority links into audit proof records.

## Public API

- storage: `FileSystemCAS`, `PutOptions`
- manifests/refs: `ArtifactManifest`, `ArtifactRef`, `InputRef`, `SchemaInfo`
- selected-view profile: `artifact_manifest_profile_projection` and
  `artifact_manifest_profile_sha256` delegate to the existing versioned CAS lifecycle
  projection and digest. Cross-layer consumers import these from the artifacts facade;
  they do not copy the projection algorithm or import its private lifecycle owner.
- integrity errors: `polisyos.core.artifacts.ArtifactIntegrityError` (the canonical
  facade export for read-time CAS integrity failures)
- signing: `SigningConfig`, `sign_artifact`, `verify_signature`, `sign_all_artifacts`, `verify_all_signatures`
- exact chronology evidence: direct module API
  `polisyos.core.artifacts.signed_evidence.FileSystemSignedArtifactEvidenceRepository`; it is not
  added to the eager artifacts facade because that would create a contracts/artifacts import cycle
- lineage/graph: `DependencyGraph`, `resolve_dependency_graph`
- integrity proofs: `CASIntegrityReport`, `build_cas_integrity_report`
- immutable proof input: filesystem `get_verified_snapshot` retains the selected manifest
  bytes and one locally checked blob snapshot. Verification, private-stage checks and the
  audit report derive size, digest and metadata from that pair. The audit builder requires
  this optional `VerifiedSnapshotArtifactStore` port instead of composing separate reads.
- signature batches: results retain exact selected references and disclose `state`,
  `admitted`, `finished`, `inventory_exhausted` and `abort_reason`. Local failures keep the
  other item results. `require_complete_valid(required_refs)` reconciles every distinct
  exact view and requires VALID for all; legacy `ok` still permits unsigned/untrusted rows
  and cannot authorize an all-confirmations publication. A DTO supplied by another caller
  is not a fresh local verification result or a transferable attestation.
- registry/environment: `RegistryBundle`, `RegistryBundlePayload`, `capture_environment`, `compare_environments`

## Current State

- Last updated: 2026-10-06
- The package still serves as the CAS source of truth for audit exports, runtime lineage, and registry bundles.
- The tree now explicitly includes `protocol.py` and the `environment_parts.py` facade alongside the capture/comparison helpers.

Batch verification/signing consumes explicit iterables lazily and keeps a bounded pending
window. An optional absolute monotonic `deadline` and cancellation stop new item admission;
explicit inventories check each supplied item before and after producer advancement, including
duplicates and exhaustion. A single user iterator operation may still block; this is not hard
preemption of arbitrary producer code.
running physical callbacks drain before return, so uncooperative I/O can outlive that logical
budget. Global `ArtifactBatchAbortError` preserves completed results with an aborted report;
BaseException retains its control-flow meaning. Legacy `<batch>` diagnostic rows and total
counters remain, while explicit completion fields describe actual admitted items.

The default filesystem inventory still materializes an O(N) canonical name/member census and
visible IDs before yielding. It checks cancellation/deadline between filesystem operations;
one syscall remains a physical boundary. Detailed reports also require O(N) memory.
The importer with `verify_integrity=True` consumes a full typed per-view integrity report,
reconciling exact member membership, actual blob digest/size and manifest digest/profile
against its measured intake before publishing. This does not add a signature trust policy
or replace a scientific publisher's required all-signature confirmations. That A-owned
signature publication consumer remains explicitly absent until separately integrated.

### Transfer generations

Reusable exports publish a complete privately staged generation. Archive destinations admit
only missing paths or regular files; symlink aliases and other filesystem kinds are refused
before staging. Existing archive permission bits are preserved. The archive is synced before
one atomic replace, and the previous inode remains available at `ExportReport.previous_generation`.
New archive and directory outputs start with private staging modes (0600 and 0700); existing
output modes are retained.

An existing owned nonempty directory requires a native atomic exchange (`renameat2` on Linux,
`renamex_np` on Darwin). Missing or empty directories use atomic replacement. Unsupported
platforms/filesystems refuse the exchange rather than temporarily removing the public path.
The previous directory remains at the named generation path returned by the report. The
operator owns retention and eventual reclamation of these history paths; publication does
not sweep them. Inventory metadata, files, and directory entries are synced before selection.

A parent-directory sync failure after replacement raises `ExportDurabilityError` with
`replaced=True` and `previous_generation`; both complete generations remain readable, while
crash durability remains uncertain. This is a local filesystem publication boundary, not a
power-loss, hostile-parent-mutation, ACL/ownership, or distributed filesystem guarantee.
Archive import sources likewise require a regular supplied pathname and a regular opened
descriptor, with no-follow and nonblocking open flags. Ordinary permission modes are verified;
special set-ID bits and uid/gid ownership remain outside the native permission witness.
Importers keep one archive inode or one directory descriptor pinned from inventory through
member reads, so a concurrent generation replacement cannot mix their input bytes.

### Scoped import admission and passive caches

Transfer intake hashes incoming blobs without buffering their payloads and retains bounded
manifest/signature bytes. The common archive/directory/exact-view admission holds artifact
and input leases before private staging, and reapplies that invariant before durable intent.
A scoped importer requires the manifest's declared tenant and cell to equal the explicit
write owner, including exact `None` cell identity. Already claimed bytes admit only an
already owned, byte-identical manifest/profile/signature view as a true no-op: no private
stage, claim or owner-generation update. Mixed packages stage only their unclaimed subset.
Unbound or foreign imports into a scoped owner refuse. This implements the bounded
fail-closed recommendation in the E02 B closure decision; it does not ratify a public
cross-tenant transfer policy. Legacy unbound-to-scoped import consumers need a matching
bound source manifest. Ordinary producer writes may retain an unspecified context; an
explicit foreign bound context refuses before put/resume intent.

An unscoped non-authority cache remains a separate consumer and may retain exact bound
metadata without emitting scoped claims. Write-through caching now publishes at the
durable remote owner first and uses the existing exact-byte read consumer to populate the
local cache. It preserves an unrelated first-writer local default and copies the remote
selected manifest's actual bytes, including its creation time, instead of generating a
second manifest from write options. Cache degradation follows the configured warn/raise
policy; the durable-owner reference remains the write-through result.
