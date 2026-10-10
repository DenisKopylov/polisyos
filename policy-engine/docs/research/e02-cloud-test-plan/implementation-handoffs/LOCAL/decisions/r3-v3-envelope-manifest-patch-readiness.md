# R3/V3 envelope manifest patch readiness

Status: patch-only. No target source/test file was written, no test was run, and no Git operation was performed.

The staged order is the red-only authority reader test, then the implementation patch plus the existing R3/V3 companions. The red test builds actual same-schema and same-content CAS envelope views with differing tenant context, redirects the payload's selected profile link through a read proxy, and expects the strict identity reader to reject it. This isolates the selected-manifest profile property from schema/name and blob-content checks.

The implementation rebuilds the envelope's expected manifest through `expected_artifact_manifest_for_write`, using the exact selected bytes, existing writer-options helper, expected identity context, and persisted `created_at`. It assigns the selected manifest's persisted schema version before comparing `artifact_manifest_profile_projection`; Core therefore retains historical v1/v2 projection rules. It also checks the default/profileless path by comparing the default selected manifest to the same expected projection. No timestamps or historical bytes are rewritten.

P40 classification: SAME_CLASS_DEEPER. The repaired invariant compares the full canonical Core profile projection rather than adding a tenant-only check.

Patch SHA-256:

- Red-only: `4dbecab20d197cb64efd7af2ce33e58ae35ea2b4657218e916ffb68e0267112a`
- Implementation plus R3/V3: `f6a20e844d8308708c0a3b04828afde69f67fa45bfcc0f7fa202466ca83a5ce4`
- Readiness record: `205e284c06c02a3472b6be353fbdf481d22512ed3baafb48a1fbf634f35ff397`

Target hashes before patch preparation and in-memory post-patch hashes are in `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/r3-v3-envelope-manifest-patch-readiness.json`. The prior R3/V3 companion patch was included byte-for-byte with SHA-256 `460973918615c8f59dfdf7973e317c29b5d408d0118de4718f430b5d0fec50da`.
