# Artifacts (`polisyos.core.artifacts`)

`core.artifacts` provides the content-addressable storage and reproducibility layer for PolicyOS.
It owns artifact ids, manifests, signatures, dependency graphs, registry bundle payloads, and
environment fingerprints.

## Role in System

- **Depends on:** `core.canon` for canonical hashing/JSON and `core.contracts` for typed refs.
- **Used by:** `foundry`, `scientist`, `fabric`, `scholar`, `runtime`, `registry`, and `audit`.
- **Boundary function:** gives every higher layer a stable CAS-backed artifact model.

## Key Concepts

- `FileSystemCAS` - deterministic on-disk CAS layout with manifest and signature sidecars.
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

### Read-only local CAS access

`ArtifactReader` is the narrow read-only interface for consumers that need verified artifact
reads without a write-capable store surface. `FileSystemCAS.open_existing_read_only` returns
this interface and requires an already-existing CAS root, layout, root transaction lock, and
per-artifact stripe lock. It creates no directories or lock files and does not run orphan-stage
recovery. Use the ordinary `FileSystemCAS` writer for writes and lifecycle management.

`ArtifactReader.has()` addresses the exact selected view. A genuinely missing selected
manifest returns `False`; an ID or profile-qualified reference never falls back to another
manifest. When the selected manifest is present, the reader requires its blob and validates the
exact manifest and blob contents. Dangling symlinks, non-regular members, a present manifest
without its blob, malformed or mismatched content, and filesystem status/read errors raise typed
refusals rather than being treated as absence. `get_manifest()` and `get_bytes()` preserve
their typed failure behavior.

The reader does not establish producer identity, tenant ownership, issuer authority, authenticity,
or currentness from access to local files. It assumes a stable trusted CAS root and cooperating
file-lock users; the path checks do not bind every ancestor through directory descriptors and do
not claim protection against hostile concurrent parent replacement. The read-only opener is a
local Python API and adds no HTTP endpoint.

- storage: `FileSystemCAS`, `PutOptions`
- JSON writes bind supplied canonical metadata to the selected encoder specification
  before serialization in the filesystem, S3, GCS, IR adapter, and tenant quota
  preflight paths. A conflicting profile is refused before persistence. Supplied
  mapping profiles must include every canonical field; historical profileless reads
  retain their existing default-view behavior. This coupling describes encoder
  settings and does not establish producer authority.
- manifests/refs: `ArtifactManifest`, `ArtifactRef`, `InputRef`, `SchemaInfo`
- selected-view profile: `artifact_manifest_profile_projection` and
  `artifact_manifest_profile_sha256` delegate to the existing versioned CAS lifecycle
  projection and digest. `resolve_manifest_by_profile` rehydrates and content-binds the
  selected sidecar using its artifact ID and exact profile digest. Cross-layer consumers
  import these from the artifacts facade; they do not copy the projection algorithm or
  import its private lifecycle owner. A profile selects a manifest view; it does not
  attest producer authority or currentness.
- write-selected profile result: existing `put_bytes`/`put_json` methods accept the strict
  keyword `return_selected_profile=True` to return the exact profile computed and committed
  inside the write lease. The default stays profileless for a default view. Caching, cloud,
  IR, and timeout-aware async adapters forward the explicit request; unsupported wrappers
  refuse before cache-local mutation. This is a write result, not producer authority or
  currentness. The runtime authority-artifact owner requests the same write-selected
  view for its linked diagnostic event, authority envelope, and payload, then retains
  those exact profiles across the references. Historical profileless refs are not rebound.
- producer-bound profile selection: `profile_bound_ref` resolves the supplied ref
  through the CAS store and returns the same typed ref pinned to the exact manifest
  view selected at this producer boundary. A profileless input binds the current
  default view now; it does not attest the historical selection of an older artifact
  or establish producer authority/currentness. Cross-layer callers use this facade.
- current write replay: `expected_artifact_manifest_for_write` reconstructs the exact current
  manifest from the payload bytes, typed write options, and persisted creation time by calling
  the same lifecycle constructor used by CAS writers. It fails when the supplied artifact ID
  does not bind to those bytes; it does not independently establish producer authority.
- authority-envelope and diagnostic-event links persist their selected manifest profiles.
  `resolve_authority_envelope_ref` and the runtime authority event resolver check the fixed
  kind/schema and pass the exact typed view to CAS reads. Historical profileless links keep
  resolving their actual default view and stored manifest version; the reader does not infer
  a producer profile for them. Profile selection is not producer authority or currentness.
- `FileSystemCAS.inventory_snapshot(artifact_id=...)` rechecks the complete local member-name
  set and owner generation while verifying only the selected artifact ID's visible views.
  The active tenant scope can hide other tenants' views, which remain unresolved by construction.
- `FileSystemCAS.manifest_inventory_snapshot(kind=...)` is an additive public method on the
  existing `polisyos.core.artifacts.FileSystemCAS` class. It rechecks the complete local member-name
  set, every visible manifest profile, and owner generation while selecting all visible
  manifests of one exact kind. It deliberately does not open or verify payload blobs, and its
  entries carry no blob digest or size receipt. A consumer must re-resolve the exact selected
  profile and verify each selected payload through its typed read before reconciliation or
  admission. This optional metadata-only port is not a new `ArtifactStore` protocol requirement
  and does not replace `inventory_snapshot`'s full payload-verification contract; consumers without
  the method keep using the full inventory API.
- local publication durability: `ensure_directory_durable`, `fsync_directory`, and
  `AtomicFileDurabilityError` expose the existing filesystem helpers through this
  facade. Cross-layer consumers reuse these exports rather than importing the
  private writer module or duplicating its algorithm. Directory sync failures
  propagate; `AtomicFileDurabilityError.replaced` discloses whether a name was
  already published. This is a local filesystem boundary, not a power-loss or
  multi-host guarantee.
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
- failed verification reports retain the digest and size of any safely acquired blob and
  the digest of acquired manifest bytes, including malformed or mismatched metadata.
  These are measurements of the refused read, not verified artifact admission. Reports
  normalize integrity reasons without reopening repaired files; errors before a safe
  blob read carry no invented digest or size. Verified reads and signature consumers
  continue to refuse the original validation failure.
- signature batches: results retain exact selected references and disclose `state`,
  `admitted`, `finished`, `inventory_exhausted` and `abort_reason`. Local failures keep the
  other item results. `require_complete_valid(required_refs)` reconciles every distinct
  exact view and requires VALID for all; legacy `ok` still permits unsigned/untrusted rows
  and cannot authorize an all-confirmations publication. A DTO supplied by another caller
  is not a fresh local verification result or a transferable attestation.
- registry/environment: `RegistryBundle`, `RegistryBundlePayload`, `capture_environment`, `compare_environments`

## Current State

The async adapters accept explicit `unbounded=True` for an owner without a
deadline. Omitted or `None` timeout retains the established helper default;
combining a finite timeout with `unbounded=True` refuses before backend access.
Workflow consumers carry their original deadline through the adapter. Native
async backends retain their own scheduling policy; this option does not preempt
already-entered filesystem calls or roll back a completed publication.

- Last updated: 2026-10-16
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

The internal write-owner type retains the concrete tenant established by owner resolution
and the existing optional cell identity. Transfer callbacks accept only blob, manifest and
signature members; their stream measurements and verified receipts expose read-only fields.
These type refinements preserve the existing admission guards and runtime behavior.

Transfer intake hashes incoming blobs without buffering their payloads and retains bounded
manifest/signature bytes. The common archive/directory/exact-view admission holds artifact
and input leases before private staging, and reapplies that invariant before durable intent.
For a scoped import, a present manifest `tenant_context` must match the active owner's
tenant and cell, with `None` cell identity compared exactly. If the artifact has no current
tenant claim and the manifest context is absent, the receiver can make a first local owner
claim through the durable CAS transaction; the original manifest bytes remain unchanged
and its producer context remains absent. This records receiver-local custody only: it does
not establish producer/source ownership or permission to transfer. Already claimed bytes
admit only an already-owned, byte-identical manifest/profile/signature view as a true no-op,
with no private stage, claim or owner-generation update. Foreign bound contexts and
non-identical views of claimed artifacts refuse before staging or publication. Mixed
packages stage only their unclaimed subset. This describes the current filesystem CAS
boundary; whether strict bound context is required for every first claim is an unresolved
G-level authority decision, and this behavior does not ratify a public cross-tenant transfer
policy. Ordinary producer writes may retain an unspecified context; an explicit foreign
bound context refuses before put/resume intent.

An unscoped non-authority cache remains a separate consumer and may retain exact bound
metadata without emitting scoped claims. Write-through caching now publishes at the
durable remote owner first and uses the existing exact-byte read consumer to populate the
local cache. It preserves an unrelated first-writer local default and copies the remote
selected manifest's actual bytes, including its creation time, instead of generating a
second manifest from write options. Cache degradation follows the configured warn/raise
policy; the durable-owner reference remains the write-through result.

### Import outcome reporting

`ImportReport.imported_artifacts` remains the legacy count of unique artifact IDs recognized in incoming members. It is not a count of verified or newly published views. `received_artifact_ids`, `published_refs`, `reused_refs`, and `integrity_verified_refs` expose those separate facts. Default and explicit selectors for the same manifest profile share one canonical profile identity in these new views; the legacy `imported_refs` tuple keeps its original selector values.

A published view is one whose manifest has a non-null stage in the durable owner transaction intent that completed. This includes recovery of an earlier pending intent and does not claim that the current invocation wrote the bytes. A reused view was admitted as an exact existing owner view or had no manifest stage in the completed owner transaction. When integrity verification is requested, the importer invokes the real verifier for staged members and exact reused views; the returned verified-ref set contains only successful verifier results. With verification disabled, that set is empty. These fields report local CAS state, not external custody, signature trust, provenance authority, or production currentness.

### Profiled Core JSON writes

ArtifactStore.put_json binds the supplied CanonInfo to the selected Core
CanonSpec, serializes with the Core codec, and verifies the emitted bytes by
decoding and re-encoding them with that same codec before any backend write.
Nonconformant declared bytes are refused with
CanonicalProfileRefusalError("canon_profile_payload_nonconformant"). This
preflight applies whether or not return_selected_profile is requested.
FileSystemCAS, GCS, and S3 share the rule; cache, namespace, and async facades
inherit it by delegation. Native bytes and finite floats remain supported when
the spec permits them. Recognized tag forms that decode but do not re-encode to
the same bytes, such as bytes_hex and float_hex, are refused rather than
persisted as unreadable profiled JSON. The public Core encoder applies this
round-trip check before returning bytes, so direct and framed Core producers
inherit the same admission before they call put_bytes. A refused encoding is
both a Core CanonViolation and a CanonicalProfileRefusalError carrying the
profile refusal code.

put_bytes remains byte-preserving and does not infer JSON from arbitrary
payloads. load_core_json_frame_records applies the same conformance primitive
to each length-prefixed record. Core artifacts exposes a frame reader but no
matching frame writer; domain-owned frame producers remain responsible for
serializing records under the declared Core profile before calling put_bytes.

### Profiled Core JSON reads

Use `load_core_json_artifact` or `validate_core_model_json_artifact` for semantic JSON values. These resolve the selected manifest, require a complete supported `CanonInfo`, and verify that the exact selected bytes round-trip under the Core codec before returning a value. The typed reader adapts the decoded value only through the requested Pydantic field schema, preserves Core-native tags, and performs terminal model validation with strict mode. Its union bridge reads direct model choices from Pydantic CoreSchema, selects a model only from a unique declared Literal tag or a unique required-key/extra-policy shape, and leaves final union-mode selection and validators to one terminal model validation. It supports both Core Python-mode writes and JSON-mode model dumps without changing the IR tag contract; unresolved ambiguous model mappings receive no inferred branch. `read_core_json_artifact_bytes` applies the same admission while preserving the original bytes for a downstream typed decoder. `load_core_json_frame_records` applies that check to every length-prefixed record after verifying the complete stored payload identity. Async callers use `aload_core_json_artifact`. Missing or malformed profiles are refusals; the Core-only tag policy remains separate from the IR codec facade.

The confidence-ledger loaded-deployment identity follows source-declared lazy facade providers before it admits the source closure. Literal PEP 562 dictionaries and guarded name-set branches that import a literal module and return the requested attribute contribute provider edges. Dynamic or ambiguous provider expressions fail closed. After the facade API is frozen, from the repository root run `cd policy-engine && uv run polisyos-tools architecture guardrails sync --skip-deep-import-baseline`, then run `cd policy-engine && uv run polisyos-tools architecture guardrails check`. Generated snapshots remain separate from this contract until that review is complete.

The exact same-owner no-op witness binds the producer and receiver to the same tenant and cell and verifies that every selected manifest carries that context; an unscoped same-byte cache intake does not establish this owner no-op case.
