# D CAS delta → F consumer disposition

Read-only, source-pinned assessment. No tests were run; local test execution was left to G's dispatch while D's compute slot was active.

## Identity

- G baseline: `83a1d894bfffab4127eb921625602ceaf72c69b6`.
- Selected D composed candidate: `556329c9cdd183197e644299381550f81f061620`, tree `a7a581044ee5c9e91b8c514c9aad4ff3051ce6a5`.
- Exact `policy-engine/src/polisyos/core/artifacts/store.py` blobs: baseline `72127a25ff25d4a034d376ba1452f54e96914931`; candidate `092ffebacd3623539e8cb097e46a2ce9300bb606`. The candidate path blob equals the selected D source commit `b6e47f50c5bc24ecb0249d47e9dc0f4588c332aa` path blob; this statement is path-content identity, not an ancestry claim.

AST comparison of `FileSystemCAS` at those exact blobs: no removed methods; six added (`_admit_import_members`, `_publish_admitted_staged_import`, `_require_bound_context_for_owner`, `_require_import_input_owners`, `_snapshot_from_paths`, `get_verified_snapshot`); nine changed (`_load_verified_snapshot`, `_publish_staged_import`, `_put_blob_and_manifest_once`, `_read_cas_file_no_follow`, `_verify_staged_artifact`, `import_exact_view`, `import_subgraph`, `open_member`, `verify`). Existing public signatures are unchanged; `get_verified_snapshot` is additive. The `_transactional_read` TypeVar annotation change is type-only.

Relevant companion API/dependency changes: `_integrity_ops.py` adds snapshot `manifest` decoding and `verification_report()` projection; `protocol.py` adds the optional `VerifiedSnapshotArtifactStore` protocol. `_transfer_ops.py` is newly used by the import-admission/publish path. `manifest.py`, `ownership.py`, `ir/artifacts/io.py`, and `async_store.py` blobs are unchanged. F has no call to `get_verified_snapshot`, `import_exact_view`, `import_subgraph`, or `open_member` in the scoped causal/graph/MethodJob/readback path.

## F consumers and action

**Repeat one causal-query consumer selector:**

`tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py::test_actual_query_consumer_binds_complete_cas_projection_and_original_request`

At `policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_queries.py`, `_load_bound_query_result()` calls `get_manifest(ref)`, `verify(ref).ok`, then `get_bytes(ref)`. D changes the implementation and error/ownership path behind `verify()`: it now obtains `_load_verified_snapshot(ref or aid)` and projects its report, including selected-view/type checks from that snapshot. The named selector drives the real query consumer and CAS and corrupts peer projections while requiring refusal, so it is the smallest existing test that covers this changed consumer contract. This is the only F-adjacent rerun I recommend for this delta. NCM also calls `verify()`, but it is outside the accepted F graph/query scope reviewed here; do not add it to the F replay without a separate criterion.

**Do not repeat the F graph/MethodJob/fresh-reader selector solely for this store delta:**

The accepted graph consumer path in `graph_reconciliation.py` reads through `get_manifest()` and `get_bytes()`; `ir/artifacts/io.py:get_json_artifact()` delegates to `get_bytes()`. The fresh-reader helper constructs a second `FileSystemCAS` and calls `load_causal_graph_model`. Those APIs and `_read_verified_blob` did not change. The selected F tests use `FileSystemCAS(tmp_path / "cas")` with no `tenant_id`, so `ownership_enforced` defaults false; the added `_require_bound_context_for_owner(opts.tenant_context, owner)` in `_put_blob_and_manifest_once` returns immediately with `owner is None`. Those tests do not call `verify()`, `get_verified_snapshot()`, imports, or `open_member()`. Thus they do not consume the changed verification-snapshot route, and the new scoped-owner write branch is not exercised in that fixture. This is a concrete path-based reason not to rerun the 9-case graph selector as a CAS-delta replay; it does not claim that owner-scoped production writes have been tested by F.

## Behavior and limits

`verify()` is the material F-facing changed behavior. For regular CAS files, the new snapshot computes the same content digest and validates the selected manifest/reference identity; it now reads a single verified byte/manifest pair and has explicit no-follow/nonblocking reads. `open_member()` and `_read_cas_file_no_follow()` add `O_NONBLOCK`, which does not change regular-file F traffic. The new bound-tenant-context check rejects a mismatched supplied context under an enforced owner; missing context remains allowed in this write path unless `require_bound=True` is requested (used by imports).

This is a consumer-impact disposition, not a full D review, F closure decision, or finding closure. Exact runtime confirmation for the changed causal-query consumer remains **UNRUN here**; G should dispatch only the selector above on the immutable composed candidate. No production data is needed for that fixture-based consumer check.
