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
- signing: `SigningConfig`, `sign_artifact`, `verify_signature`, `sign_all_artifacts`, `verify_all_signatures`
- exact chronology evidence: direct module API
  `polisyos.core.artifacts.signed_evidence.FileSystemSignedArtifactEvidenceRepository`; it is not
  added to the eager artifacts facade because that would create a contracts/artifacts import cycle
- lineage/graph: `DependencyGraph`, `resolve_dependency_graph`
- integrity proofs: `CASIntegrityReport`, `build_cas_integrity_report`
- registry/environment: `RegistryBundle`, `RegistryBundlePayload`, `capture_environment`, `compare_environments`

## Current State

- Last updated: 2026-06-16
- The package still serves as the CAS source of truth for audit exports, runtime lineage, and registry bundles.
- The tree now explicitly includes `protocol.py` and the `environment_parts.py` facade alongside the capture/comparison helpers.
