# CAN R9.1 default-route profile ownership v3 independent review

**Verdict: GO for the bounded HTTP companion; no CAN/LA-021 closure.** This read-only delta review does not adjudicate CAN, external custody, or historical profile semantics.

## Exact pins

- Base: branch `codex/e02-unified-local-20261009`, HEAD `cd5651c3a6897f12d32212e3521e73bb570f137b`, tree `bb7186c24000b54fdb0ab8ce8d16b55c3658995c`.
- Patch: `LOCAL/raw/can-r9-1-default-route-profile-ownership-v3-20261011/candidate-v3.patch`, SHA-256 `2c0ffb69314f0eebc2fe960fea6aff669188149098125d66e05c70c5b62083c2`.
- Manifest: `candidate-v3-manifest.json`, SHA-256 `cf126f7e26536019ba65d426376d949481a4acaacfd99dadc99a89379e49d389`.
- Exact target preimages match: `runtime/http/routes/artifacts.py` `171854a8796630e7630683c15c2b3c009f94b038fd6482504eefcdd6a26ff159`; `tests/unit/runtime/http/test_artifact_surface_safety.py` `5e95df05377ea7699cb3500ca861bee525d5480cd2ac8b331d70f301dc4f5aad`. Read-only `git apply --check --verbose` passed.
- Author's source-bound focused receipt: `candidate-v3-stdout.txt` SHA-256 `543ea5a1c2ee643f2d6c85293547254c58d036f316c2af47aed6dc02304d3704`; seven focused tests passed. I inspected the retained command/output but did not rerun it.

## Property and remaining boundary

The default HTTP branch previously returned `store.get_manifest(artifact_id)` directly. The candidate derives the exact selected profile digest from that default manifest, then calls `resolve_manifest_by_profile` before the content/manifest/download/export consumer proceeds. That resolver verifies the digest, artifact ID, and selected bytes; in the current Core store it also enforces exact selected-view ownership. The catch maps an ownership-denied view to the existing typed 404. It does not silently fall back to a different profile or create a profile/owner grant.

The controls distinguish: (1) an artifact whose default identity is recorded but whose exact selected profile is not owned, (2) an exact view owned by another tenant, and (3) a removed blob. The first two are unavailable-profile 404s without payload/tenant leakage; the missing blob remains `artifact_not_found`. The existing scoped producer fixtures now assert ownership of the exact profile written, rather than relying on ID-only `record_artifact_owner`; the composed time-source and S12 tests retain their original status expectations. The actual route-consumer set includes manifest, raw content, download, export, and the artifact-inspector consumer.

**P40: SAME_CLASS_DEEPER.** This widens selected-view ownership from explicit profile selectors to the previously weaker default-selector route and uses one resolver boundary across its consumers. The negative matrix removes the property while retaining the route markers: a default-profile request with no exact-view owner must still refuse on each surface. The bounded residual is backend capability: the focused receipt exercises the local scoped FileSystemCAS and proves neither a production tenant index nor every external/custom backend's ownership policy. A backend that cannot verify selected-view ownership must fail closed or remain outside the claimed route; no global/current production state is inferred.

The previously failing R40 HTTP cases were 500s on a valid scoped fixture and on two expected 409 safety gates. The companion changes the fixtures to register exact selected-view ownership, enables server exception propagation for affected tests, and retains the expected 200/409 behavior plus new negative controls. The author's seven-pass focused replay is relevant evidence for this bounded companion, not a full R40 replay or final composed candidate receipt.

**Formal status:** `closure_ids: []`. CAN's wider mapping-option, raw-byte/profile-conformance, tag-family, producer-attestation, and profileless-history questions remain separate and open for the cumulative review.
