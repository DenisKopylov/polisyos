# CAN R9.1 cloud not-found V3 — independent delta review

Decision: **GO for root application and the serialized composed replay.** The V2-only divergence is corrected; this is not a G acceptance or formal closure. Runtime tests, canonical Ruff for this exact V3 artifact, SDK integration, and live-provider checks remain outstanding.

## Exact source and patch identity

Reviewed in `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`, branch `codex/e02-unified-local-20261009`, HEAD `022c70f26f5cdb3c9aa6c4af87dc13f7071a5064`. V3 patch `LOCAL/raw/can-r9-1-cloud-notfound-v3-20261011/candidate-v3.patch` has SHA-256 `97d4da058bce6a37da9e12f832343e2b3e352b98f8b032e8ec378be9723c4d6d`; manifest `manifest-v3.json` has SHA-256 `36a4297101e2e34f35332b26282e280a23b09d71000b7d72b2e4693928f6445e`. All four current cloud source/test bytes match the manifest preimages. The held R9.1 patch `LOCAL/raw/can-authority-writer-reader-r9-1-20261011/can-authority-writer-reader-r9-1.patch` has SHA-256 `3f7ca78550d8aaa9ec4dc36f260c2f7a2b8a4a84b83ec0ea0b855a11ecb5a153`; all three reader/writer/test preimages match its manifest. Non-mutating `git apply --check --verbose` passed separately for each patch. Their seven paths are disjoint. No product, index, or history changes were made in this review.

The V3 delta from the reviewed V2 patch removes `NoSuchObject` from the direct positive S3 code set and adds unknown-code/404 controls. The GCS source delta and the remaining S3 routing changes are unchanged from V2.

## Property and V2 falsifier

Property: only provider-established object absence becomes `FileNotFoundError`; namespace, authorization, transport, malformed, and unrecognized provider failures remain errors.

The earliest concrete divergence in V2 was the direct input `ClientError(Error.Code="NoSuchObject", HTTPStatusCode=404)`: V2 accepted it as object absence even though the adapter has no named S3-compatible-provider contract establishing that data-plane code. V3's positive S3 branch now recognizes only `NoSuchKey/404`; generic `""`, `"404"`, and `"NotFound"` plus status 404 still require a successful `head_bucket`. Other status-404 codes return false from the classifier, so the original provider exception propagates without a namespace probe. This closes the specific V2 mismatch and makes the unknown-code policy class-wide rather than a one-name exception.

The V3 tests add `NoSuchObject/404` and `UnrecognizedProviderError/404` controls for direct and cached `get_bytes` and `has`, preserving the exact exception object and asserting zero `head_bucket` calls. A default-manifest probe control asserts an unknown head error propagates, the attempted blob write is the only PUT, and no default manifest is created. Existing V2 controls remain for `NoSuchBucket`, `AccessDenied/404`, contradictory code/status, successful namespace confirmation for generic 404, and failure of the namespace check. The full candidate's AST receipt passes for all four postimages; `git apply --check` passes. V3 backend tests and canonical Ruff were not run by this reviewer and are explicitly UNRUN in the author packet; the V2 27-test receipt does not transfer to V3.

## Held R9.1 composition

Source review of the exact held R9.1 candidate confirms the typed `ArtifactRef` path resolves the requested manifest profile through `resolve_manifest_by_profile`, binds the selected bytes, and checks selected kind/media before reconciliation. A genuine object absence from these backends reaches the reader's `authority_cas_missing` path; an extant artifact with a missing selected profile or malformed selector is classified as `authority_payload_mismatch`. Namespace and permission exceptions are not `FileNotFoundError`, are not caught by those branches, and therefore cannot be reported as missing CAS. String/ID callers preserve default-view behavior. The read and backend changes do not establish issuer, custody, currentness, or producer authority.

This source composition is compatible across all seven declared patch paths, and both exact patches apply independently at the recorded base. No composed R9.1 consumer replay or cloud SDK/provider call was run here; root should execute the complete backend modules and direct/cached authority-reader consumers on the applied composition before freezing receipts. No formal finding is closed by this review; `closure_ids` remains empty and G retains adjudication.

## P40 disposition

P40 bucket: same provider absence-versus-operational-error class already widened over S3 reads, `has()`, and default-manifest creation. The V2 unsupported-code finding is now resolved by refusing unknown codes across all these routes. The V3 unknown-code controls are a worked example of the generic fail-closed rule; no further per-code patch is indicated. Remaining verification labels are `verification_missing` for the V3 behavioral replay and real provider SDK integration, and `semantic_test_missing` until the composed R9.1 consumer replay is run.
