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

### Atomic local byte replacement

`write_bytes_atomic(path, data, durable_parent=False)` delegates to the existing
Core atomic writer to create or replace a local file. It returns `None`; this is
the replacement operation for mutable owner pointers, unlike
`write_bytes_once`, which preserves an existing destination. Callers still own
any serialization lock and domain-level update checks. The Search ticket owner
uses the replacement facade under its existing ticket lock to advance its index.
`durable_parent=True` preserves the existing required directory fsync and
`AtomicFileDurabilityError.replaced` disclosure if that fsync fails after
replacement. The facade adds no filesystem algorithm, CAS identity, provenance,
authority, currentness, multi-host or additional durability guarantee.

### Immutable local byte publication

`write_bytes_once(path, data, durable_parent=False)` is the narrow facade for an
atomic create-if-absent write. It returns `True` when this call created the
destination and `False` when a name already existed. A `False` result does not
prove that the stored bytes match the requested bytes; a caller that supports
idempotent reuse must compare exact bytes and refuse a content conflict.
`durable_parent=True` requires the parent-directory fsync and raises
`AtomicFileDurabilityError` if it fails after publication. The helper delegates
to the existing atomic writer and does not provide CAS identity, provenance,
authority, or currentness.

### Read-only local CAS access

`ArtifactReader` is the narrow read-only interface for consumers that need verified artifact
reads without a write-capable store surface. `FileSystemCAS.open_existing_read_only` returns a
`ReadOnlyFileSystemCAS` that implements `ArtifactReader` and additionally exposes
`get_raw_manifest_bytes()`, `get_manifest_by_profile()`, and `verify()` for profile-aware semantic
consumers, plus `open_member_bounded()` for strict selected JSON reads. The bounded method returns
the same pre-entry usage-bearing attempt as the writable filesystem store; it does not expose
writer operations. The opener requires an already-existing CAS root, layout, root transaction lock, and
per-artifact stripe lock. It creates no directories or lock files and does not run orphan-stage
recovery. Use the ordinary `FileSystemCAS` writer for writes and lifecycle management.

`ArtifactReader.has()` addresses the exact selected view. A genuinely missing selected
manifest returns `False`; an ID or profile-qualified reference never falls back to another
manifest. When the selected manifest is present, the reader requires its blob and validates the
exact manifest and blob contents. Dangling symlinks, non-regular members, a present manifest
without its blob, malformed or mismatched content, and filesystem status/read errors raise typed
refusals rather than being treated as absence. `get_manifest()` and `get_bytes()` preserve
their typed failure behavior.

`read_raw_manifest_bytes_bounded()` accepts a full `ArtifactRef` for its exact
profile-qualified view, an `ArtifactID` for the owner-authorized default view, or
an `ArtifactID` plus an explicit profile digest for that exact sidecar. The
filesystem owner applies its existing ownership guard and no-follow regular-file
preflight before allocating manifest bytes, and returns an immutable transfer
receipt. An explicit digest never falls back to the default. Core's
`read_core_manifest_profile_bounded()` parses only those bounded bytes and derives
the full `ArtifactRef`; profileless metadata is available only through an explicit
candidate inspection option, while Core semantic JSON reads still refuse it.
Caching stores obtain this receipt only from their durable view owner, never from
a local cache hit.

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
- intake and capability helpers: `validate_return_selected_profile` accepts only a real bool,
  and `require_return_selected_profile_writer` checks that a writer method declares the selected-
  profile keyword. The latter is signature preflight only: callers must verify the actual write
  result, and a missing selected profile remains a refusal. `matches_runtime_protocol` and
  `matches_runtime_protocol_definition` check structural presence; `matches_artifact_store_protocol`
  also checks a Core-to-IR adapter's actual owner for raw-manifest capability. These checks do not
  establish content integrity, authority, or currentness. `CoreToIRArtifactStoreAdapter` is the
  existing bridge for IR callers. `decode_core_json_payload` decodes supplied bytes but does not
  read or verify a CAS artifact; `artifact_reference_parts` normalizes a selector but does not
  resolve it; `with_ambient_ownership_enforcement_if_supported` may return the input store when no
  hook is available and is not proof of tenant enforcement.
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
- bulk verification: `BatchAuthorizationLossSignal` is a caller-owned, one-way stop
  request; only a configured request-scope authorizer may request it after detecting
  loss of scope. The verifier stops new executor admissions, drains already-admitted
  callbacks, and returns their rows with `state="aborted"` and
  `abort_reason="authorization_lost"`. This signal does not preempt active work,
  infer authorization from per-artifact errors, or itself establish a permission
  decision. The current CAS/CLI chain has no production authorizer bridge into this
  signal.
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
- signature batches: current producers preserve per-item result rows, including rows
  collected before a batch abort, and expose runtime lifecycle fields (see “Current State”).
  These rows are not an exact-selected-reference reconciliation; no
  `require_complete_valid(required_refs)` predicate is implemented. The legacy
  `BulkVerificationReport.ok` remains outcome-only and does not authorize an all-confirmations
  publication. Batch reports are diagnostic, not fresh verification or a transferable attestation.
- registry/environment: `RegistryBundle`, `RegistryBundlePayload`, `capture_environment`, `compare_environments`

### Bounded selected Core JSON reads

read_core_json_artifact_bounded(store, selected_ref, *, limits) is the strict
path for consumers that must bound selected manifest and JSON payload bytes
before parsing or Core value materialization. The caller supplies a
profile-qualified ArtifactRef, an explicit CoreJsonReadLimits(max_bytes,
max_depth, max_elements, max_manifest_bytes) from the selected resource policy,
and a CoreJSONArtifactBoundedMemberReader. The metadata-byte limit is a
separate required field; it does not reuse the payload-byte limit. The additive
bounded-member protocol extends the legacy streaming reader; it does not change
legacy open_member behavior. A strict bounded read never falls back to the
legacy context because that context drains and hashes unread bytes on normal
exit. A metadata-only caller can use
read_core_manifest_profile_bounded(store, selected_ref, *, max_manifest_bytes)
before payload admission. It returns the exact raw manifest bytes, parsed typed
manifest, CanonInfo declaration, effective reference, and observed byte count.
Consumers that hold only a profile-qualified lineage `InputRef` can call
read_core_input_manifest_profile_bounded(store, input_ref, *, max_manifest_bytes).
The bounded backend selects by the edge's exact artifact ID and explicit
profile digest; the Core owner parses those same raw bytes and derives the full
effective reference, including kind and media type, from the selected manifest.
Missing or malformed profiles refuse without falling back to a default view.
Role-specific kind/media expectations remain the consumer's responsibility.
`CachingArtifactStore` forwards this bounded selection and member stream only to its default manifest owner; it does not replace a missing durable-owner receipt with a local cache hit. The current cached S3/GCS owners do not expose that bounded receipt contract, so semantic JSON reads through them refuse before a full-byte fallback.
The strict payload route parses typed and raw profile views from the same
owner-read byte sequence, then passes its exact SHA-256 into
open_member_bounded. The owner re-reads and verifies that exact profile, requires
its actual regular-file size to equal manifest byte_size, and rejects a member
over max_bytes before yielding any payload. A scanner depth/element refusal
aborts inside the context, so the owner closes without its ordinary drain-and-
hash finish. Positive admission still requires complete size and digest
verification plus the existing tagged decoder and canonical-profile round-trip.
max_elements counts containers, scalar values, and object member names.
The verified `CanonicalProfileRead` names its contextual decoder as `core-tag-policy@1`; this is a reader identity, not a producer claim or a persisted manifest field. Core keeps its recognized `array_digest` form distinct from IR admission and does not thereby validate an array descriptor or referenced array.

Successful results and typed refusals expose
observed_manifest_selection_bytes, observed_manifest_verification_bytes,
observed_payload_bytes, and their observed_source_bytes total. These are exact
selected-store API transfers for the first manifest read, owner verification-
manifest read, and payload bytes returned to the reader. If an attempted
component has no exact owner count, that component and the total are None;
known transfers remain available. Full-transfer decode and profile refusals
retain exact usage. The separate observed_payload_size is owner fstat data; it
is not confused with payload bytes actually read. payload_integrity_verified
is true only after the complete owner receipt. On a stat-preflight size
refusal, the payload size is retained and payload bytes read is zero. Counts describe bytes
transferred by the selected store API; they are not a claim about physical disk,
OS page cache, hardware prefetch, ownership-index or transaction-journal reads.
Metadata-only selected-manifest reads report their actual transfer count too;
a stat-preflight refusal can therefore report a file size with zero bytes read.
The CAS ownership index, transaction journal, and their generation files remain
outside these artifact-source counts. These per-member limits do not establish
whole-input process RSS, concurrent-memory, or all-CAS-metadata bounds. No
resource-policy default is invented here. The API also does not choose
scientific shape limits, establish source authority, or prove HTE suitability.

`failure_stage` identifies the phase that refused. Member phases are set at the
operation boundary: `bounded_member_size_validation`,
`bounded_member_bounds_validation`, `bounded_payload_read`, `bounded_payload_finish_read`,
`bounded_payload_bounds_validation`, and `bounded_payload_finish_validation`.
The finish-validation phase begins after the last owner read returns and covers
the final opened-file identity, size, and digest checks; a read failure remains
at its read phase. Manifest transfer, post-read validation, and close have
separate phases as well. A separate optional
`cleanup_failure_stage`, `cleanup_exception_type`, and `cleanup_exception_code`
retain a close failure without replacing an earlier read/validation failure or
its exception chain. If close itself is the only failure, the refusal names the
close phase. A verified payload can retain `payload_integrity_verified=true`
when a later close failure prevents the read call from succeeding; integrity
does not convert that cleanup refusal into admission.

The HTE bridge preserves typed Core source-read and cleanup phases unchanged.
After a complete selected-source read, profile, schema, or semantic refusal is
reported as `hte_selected_source_validation`. Legacy normalization assigns
separate `normalized_hte_input_serialization`,
`normalized_hte_input_bounds_validation`, `normalized_hte_input_write`, and
`normalized_hte_input_profile_validation` phases at their operation
boundaries. HTE cleanup diagnostics preserve a string-valued exception `code`;
an absent or non-string code is reported as `None`.

## Current State

The async adapters accept explicit `unbounded=True` for an owner without a
deadline. Omitted or `None` timeout retains the established helper default;
combining a finite timeout with `unbounded=True` refuses before backend access.
Workflow consumers carry their original deadline through the adapter. Native
async backends retain their own scheduling policy; this option does not preempt
already-entered filesystem calls or roll back a completed publication.

- Last updated: 2026-10-20
- The package still serves as the CAS source of truth for audit exports, runtime lineage, and registry bundles.
- The tree now explicitly includes `protocol.py` and the `environment_parts.py` facade alongside the capture/comparison helpers.

Batch verification and signing consume explicit iterables lazily with a bounded pending window.
An optional cancellation event stops new admission; an exception while advancing the inventory
also aborts the batch. Per-item callbacks convert ordinary `Exception` failures into item-level
ERROR results and continue, while `BaseException` retains its control-flow meaning. Executor
submission failure or a `BrokenExecutor` from a future stops further admission. Already collected
callback results remain in the report, along with a `<batch>` ERROR row for a global abort.

Both `BulkSigningReport` and `BulkVerificationReport` expose runtime `state`, `admitted`,
`finished`, `inventory_exhausted` and `abort_reason` fields. `admitted` counts successful executor
submissions; `finished` counts callback results collected by the batch; and `inventory_exhausted`
becomes true only when the iterator's `StopIteration` is observed. `state=complete` means the
inventory was exhausted without a batch abort; it does not mean every item succeeded. The legacy
`BulkVerificationReport.ok` remains outcome-only, may be true for unsigned or untrusted rows, and
is not a completeness or publication predicate. Historical report payloads without runtime
lifecycle fields deserialize those fields as `None`; they are not inferred complete. A partial
report cannot authorize a publication that requires confirmations for every selected reference.

Bulk verification also accepts an optional `BatchAuthorizationLossSignal`. The caller owns the
decision to request it after its configured request-scope authorizer establishes authorization loss;
the batch stops new admissions, drains admitted callbacks, and retains their rows with an explicit
`authorization_lost` abort reason. The signal is caller input, not permission evidence. No configured
request-scope authorizer currently reaches the CAS batch-verification callsite, so this is a bounded
mechanism with a controlled consumer witness rather than a production authorization bridge. Batch
signing remains cancellation-only and its report excludes this verification-only reason.

These APIs do not provide `require_complete_valid(required_refs)` or an all-confirmations publisher.
A consumer that needs that policy must supply and reconcile its own exact required set and freshly
verify each selected reference. This report is a diagnostic result, not a transferable verification
attestation.

Cancellation stops future admission but does not preempt callbacks already running. A single
iterator operation may block; this is not hard preemption of arbitrary producer code.

The default filesystem inventory materializes the full CAS name/member census and visible IDs
before yielding, without reading every manifest or blob during that first census. On successful
exhaustion it recomputes active-scope membership. Cancellation cannot interrupt the initial
filesystem walk; it stops later item admission only. These signature batch methods do not accept
a deadline. Detailed reports also require O(N) memory.
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

Use `load_core_json_artifact` or `validate_core_model_json_artifact` for semantic JSON values. These resolve the selected manifest, require a complete supported `CanonInfo`, and verify that the exact selected bytes round-trip under the Core codec before returning a value. The typed reader adapts the decoded value only through the requested Pydantic field schema, preserves Core-native tags, and performs terminal model validation with strict mode. Its union bridge reads direct model choices from Pydantic CoreSchema, selects a model only from a unique declared Literal tag or a unique required-key/extra-policy shape, and leaves final union-mode selection and validators to one terminal model validation. It supports both Core Python-mode writes and JSON-mode model dumps without changing the IR tag contract; unresolved ambiguous model mappings receive no inferred branch. `read_core_json_artifact_bytes` applies the same admission while preserving the original bytes for a downstream typed decoder. `load_core_json_frame_records` applies that check to every length-prefixed record after verifying the complete stored payload identity. Async callers use `aload_core_json_artifact`. Missing or malformed profiles are refusals; the fixed core-tag-policy@1 remains separate from ir-tag-policy@1. Its identifier is reader context, not a payload tag, manifest field, or producer attestation. HTTP schema/content semantic previews use Core's bounded selected-member reader and return the existing typed conflict when byte, depth, element, or selected-manifest limits are exceeded.

For a resource-bounded read, call `read_core_json_artifact_bounded` with explicit payload and selected-manifest limits, then pass its result to `validate_core_model_bounded_read` when the consumer needs the same typed-artifact owner checks as `validate_core_model_json_artifact`. The carrier retains immutable selected raw manifest and payload bytes, exact limits, and measured counts. Its `profile_read` and `value` accessors decode a fresh Core value from those bytes; mutating a returned mapping cannot change a later typed validation. The bounded validator rebinds the carrier to the exact selected ref, manifest, canonical profile, payload digest, and recomputed measurements, then runs Core alias/tuple adaptation and strict model/schema validation without storage reads.

The confidence-ledger loaded-deployment identity follows source-declared lazy facade providers before it admits the source closure. Literal PEP 562 dictionaries and guarded name-set branches that import a literal module and return the requested attribute contribute provider edges. Dynamic or ambiguous provider expressions fail closed. After the facade API is frozen, from the repository root run `cd policy-engine && uv run polisyos-tools architecture guardrails sync --skip-deep-import-baseline`, then run `cd policy-engine && uv run polisyos-tools architecture guardrails check`. Generated snapshots remain separate from this contract until that review is complete.

The exact same-owner no-op witness binds the producer and receiver to the same tenant and cell and verifies that every selected manifest carries that context; an unscoped same-byte cache intake does not establish this owner no-op case.
