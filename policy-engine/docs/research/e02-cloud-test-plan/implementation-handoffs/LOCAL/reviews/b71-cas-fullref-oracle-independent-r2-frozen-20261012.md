# B71 CAS full-reference test oracle — independent R6 review

**Verdict: GO for the exact R6 test-only patch.** This review does not change production source, alter the author packet, or close B71. Classification is **P40 `SAME_CLASS_DEEPER`**: the second same-class finding was widened to the complete current `ArtifactRef` identity and the real read/admission/custody behavior, rather than another narrow regex correction.

## Frozen inputs and scope

Reviewed author manifest `LOCAL/raw/b71-composed-cas-test-oracles-author-r6-20261012/manifest.json` with SHA-256 `fd84c240ee35df0e3179e730fa2a71d9abbbefd961a195e5a1f90c3827416b17`. Its virtual patch is `ae8b3fb3be234d1341d481a3ef74097bc9cde46cd8cf88880d78e67ba1060914`; the only target is `policy-engine/tests/unit/remediation/test_res_01.py`. The current target was still the bound preimage `ee36f8ffcfe9196823fc9eef812486eec31d584dc4be94a08518e0e9dcda14d0` at review, and an isolated copy patched from that preimage produced the exact postimage `560854a5054fcb7bdc221e9109371aeb513678ac2136efdef6f6f43bf10b9614`. `git apply --check` also passed. No production file is part of the patch.

I recomputed all ten `packet_files_sha256` entries, all four declared runtime source-origin hashes, the R154 raw output hash, and the R4/R5 lineage-manifest hashes; every value matched. The checkout sources imported by the verification interpreter resolved to this worktree. A fresh import reported `ArtifactRef.model_fields = artifact_id, kind, media_type, manifest_profile_sha256`, matching the four-axis matrix. The detailed per-file bindings and copied full outputs are under `LOCAL/raw/b71-cas-fullref-oracle-independent-r2-20261012/`.

## Failure diagnosis and property coverage

The R154 output is bound at SHA-256 `a11a0766c768c466b684a1a5f82e0d7c34615be68d2336f8f7b7d058f90a4e27` and records 36 cases: 33 passed, 3 failed. All three are oracle mismatches, not product-source failures:

- The collision observer stored `str(artifact_ref)` and then searched for a bare artifact-ID string. The production call passed the complete `ArtifactRef`; its formatted string includes ID, kind, media type, and profile, so the bare ID is not a substring. R6 records the full refs and checks the ordered pair directly.
- Altered `kind` and `media_type` refs are rejected on the actual `FileSystemCAS.get_bytes`/`get_manifest` path with `ArtifactIntegrityError` before `NodeResultCache` can apply its later producer-epoch check. The old assertion for `immutable_epoch_mismatch` described the wrong layer. R6 asserts the typed storage error and then proves the fresh cache is still empty.

R6 covers each current identity field. A missing alternate artifact ID fails with `FileNotFoundError`; wrong kind and media selectors fail with the canonical CAS `ArtifactIntegrityError`; the profile axis builds a real selected manifest for the same bytes and artifact ID, with unchanged kind/media/schema and a foreign producer, verifies the selected-profile read and producer, then expects cache custody to reject it. Every variant checks fresh-cache `size`, `has`, and `get` remain empty; a warmed cache keeps the valid original entry; a new cache object reloads via the original ref. No broad exception catch masks a different failure.

This matches the source path: `_read_entry` passes the complete `ArtifactRef` to `get_bytes` and `get_manifest`; CAS validates kind/media against the selected manifest; `_verify_cache_artifact` checks producer/schema custody; `load_entry` only indexes after `_read_entry` succeeds. The cache identity helper delegates to the tuple of artifact ID, kind, media type, and manifest profile. These guards and source hashes are unchanged.

## Independent verification

On the frozen R6 virtual test file plus the current checkpoint consumer module, I ran the bounded suite under the repository `.venv` (Python 3.14.3; modules resolved under this worktree): **38 passed in 5.91s**, command wall **8.60s**. Independent Ruff returned **All checks passed**. The exact command, complete stdout/stderr, JUnit XML, patch application output, Ruff output, and runtime-origin receipt are retained in `LOCAL/raw/b71-cas-fullref-oracle-independent-r2-20261012/`; `independent-bindings.json` binds their hashes. The test overlay had no product-source mutation.

## Boundary

The R6 overlay includes bounded local cases for the B71 behaviors—continuation with full valid state and no unnecessary cache seed, missing-state refusal, the `allow_replay` route, and duplicate refs not counting as independent coverage. These tests strengthen the CAS identity/admission oracle; they are not the full protected B71 candidate evaluation or its 14-contour review. That complete evaluation and formal closure remain unadjudicated; `closure_ids: []`.
