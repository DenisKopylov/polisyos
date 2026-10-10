# RES-03 final local admission attempt

Date: 2026-10-10. Read-only source snapshot observed at HEAD `13e411da7d9e505856fc336b3d25fd0aabdb1f66`, branch `codex/e02-unified-local-20261009`. The candidate was still advancing, so this is an exact observation anchor, not a source-freeze claim. I did not start a server, run tests, query the catalog, inspect catalog payloads, or change production data/configuration.

## Result

The named local roots let me identify one offline L01 data-root receipt and its selected L6 profile. They do **not** identify a current serving instance for RES03. The offline root is labeled `LOCAL_DATA_ROOT_01`; its selected root manifest reports `research` as its default runtime profile, generated at `2026-05-10T00:00:00Z` and observed at `2026-10-08T15:41:45.962265+00:00`. The L01 packet explicitly calls this an owner default, not an admitted served profile. No runtime process, environment profile, request context, catalog selector, or actual API/root tuple joins that receipt to a present RES03 request.

The exact B13 packet remains limited and does not bind an actual catalog input path/content identity. The prior `catalog_fetch_source_unreadable` was not replayed, and the packet says the terminal join is `UNRUN`. The latest L02 correction confirms that a factual L01 packet is published; it also says that packet does not establish the task-specific matching input/profile/owner/API/law/evaluator tuple. Thus the authentic positive stays `not_established`; this is not evidence that the local catalog or its owner is absent.

## Exact named receipts re-read

Unified-local `INPUTS.json` is `@b000d61906fc0d732287f1a50cbb1ca902c23f4d08a292e4330734f5147431da`. It names two existing private custody roots. The aliases and their relative interpretation are defined by `LOCAL/t1-t2-intake/README.md`. I used only receipt paths named by those inputs/receipts and did not enumerate either root.

The current named L01 B13 packet is `L01::parallel-20261008-l01/packets/B.json` (`b2ea97c8e1e9001e33e5c96a15208809d283117d429b0bc97d2a41c256c41ac5`). It records:

- B13 status `limited`; `production_input_admission=not_established`; `input_bytes_digest=withheld_no_disclosure_admission`; formal G closure `not_adjudicated`.
- Criterion: a real simulation and its scoped partial result survive a later-stage failure and reach the served consumer with the failure reason; producer/CAS output alone is insufficient.
- Prior receipt fact: `catalog_fetch_source_unreadable`, unreplayed, no producer-only served-route proof, terminal join `UNRUN`.
- Its minimum is exact local read-only catalog/acquisition/history inputs; the L6 artifact pair; a matching manifest or legitimate versioned replacement; source/context/tenant/run references; relevant source/version and time-role refs; and the consumer route.
- Its packet state says the connected plan did not bind the actual input path/content identity and asks for the exact opaque alias and refs. This is a historical packet assertion, not a conclusion that no packet exists now.

The separately named L01 A-L6 receipt is `L01::restart-20261008-bindings/packets/A-l6.json` (`c6ab16fa192483dbfaccca6b634e79129709e6d2ba6f7b05d9e152090a3bf61f`), with `binding-readback.json` (`d3c8e15fa6a76e93703db0e38e837c7c1b5597674e0716943de04a29f7025e43`) and `source.json` (`5092071cf08f36358a3eb00b77e3169ea5dbf47a02e4141fcca5bf75baf38d38`). The A-L6 receipt’s `local_receipts` names exactly three selected-root metadata files: `root-manifest.json` (`b893eb0590cf151afd89ed0cb0c288fddf09a93f3e36305679e33aaeb55dd6c3`), `l6-selected-bindings.json` (`551c1b66cd0644d6e7a29492d51952d7e18b3406c3fb5921ae9b6c6e3a1bc491`), and `public-alias-index.json` (`db427943dfd71c99ad1bf405f24a145b8769eb04f91a0de0f2bc0ddf40bd49b2`). I resolved only those exact locators under the first INPUTS root.

Within that receipt’s own three-member L6 denominator, root-to-bundle checksum binding passes; the observation-routes member matches; the knobs and Lex-map members fail both size and checksum comparisons. The A-L6 consumer check is `UNRUN` and explicitly belongs to L02. The selected bundle is for L6 intervention-substrate/observation-method routing, not RES03 catalog/acquisition. It is not an admitted replacement for the mismatched L6 members, and it does not supply the RES03 dataset selector. No alternate versioned replacement is named in this exact selection; I did not search other roots or versions.

The current L02 source-pinned manifest is `L02::manifest.json` (`c8b83ebe68bbd3568d9bceb7626863c3acb5616ab2c717bf2a3d13130b0cc769`). Its exact late-input correction, `L02::prepared/l02_late_input_independent_review.json` (`8f06c226e12132c91b836507d014cbc161f53f998054817edabdee20d941c347`), requires current wording to say the L01 factual packet exists while the exact matching tuple remains `not_established`; it supersedes the older no-packet wording. The correction says the L01 packet does not provide a source-matching profile or authentic consumer.

The L02 V1 row in `L02::prepared/l02_input_packets.json` (`a6104430660f645c96d0308a5ab5dbae21695cf78400e5bec4fbd607d859907f`) sets the minimum to matching criterion-specific L6/local catalog/acquisition/history inputs, a matching L6 artifact pair and manifest or legitimate versioned replacement, and source/context/tenant/run refs. Its owner roles are L01 factual supplier, C05 Catalog/profile supplier, and C10 A served lifecycle consumer; V1 depends on Q1. Its verifier is an authentic ordinary POST/job → owner-bound context → N5 → CAS → fresh GET with matching manifests. This is the V1 workpacket criterion, not a license to invent missing source semantics.

## Serving configuration and existing source path

At this observation, `POLISYOS_PRODUCTION_DATA_ROOT`, `POLISYOS_EXECUTION_PROFILE`, `POLISYOS_RUNNER_BACKEND`, `POLISYOS_CATALOG_RUN_PROFILE`, `POLISYOS_CACHE_HOME`, and `XDG_CACHE_HOME` were unset. A process-argument check found zero matching Python/uvicorn PolicyOS runtime processes. This is only a local snapshot; it says nothing about a remote or otherwise unobserved service.

The current `resolve_production_data_root` API selects an explicit run parameter, then `POLISYOS_PRODUCTION_DATA_ROOT`, then a working-directory-relative default when allowed. The local receipt alias `LOCAL_DATA_ROOT_01` is not itself evidence that a live request selected that root. The runtime container accepts a catalog profile and control-registry-provider override; without an override, the default catalog provider builds the Slice-0 fixture graph. A profile string or an offline manifest does not establish a request-bound source.

The existing source-backed path is available once the exact selector is supplied: `DefaultFabricPort.snapshot` accepts a typed `DataViewRequestRef`, resolves its dataset ID, asks its configured catalog store for runtime tier, fetches through its configured connector/fetcher, and persists the data artifacts. `BuildDataSnapshotNode.execute` calls Fabric only when the incoming state lacks `data_snapshot_ref`, includes `data_view_request_ref`, and the execution context has a Fabric port. The current RES03 test instead constructs a synthetic `DataSnapshot` in a temporary CAS, includes it in `ExperimentState.inputs`, and builds context with `DefaultFoundryPort()` only. The node therefore returns early and skips Fabric/catalog acquisition. The served fixture can pass while the selected catalog or profile is mismatched; that is the P38 divergence.

The current test file hash is `9a572f253f82d3899895c8f9a9739e88314c73cf392115de6fb395ce5cce0d34`. Its earlier 4-pass receipt reports a different test hash (`7f1456fc14d2f15b88926e7d77388a3802d99b2e53311931db98a47e7d5f722c`), so that result is not a replay of this current file. I ran no test in this attempt.

Relevant current source hashes: `build_data_snapshot.py@b2a37ad9d4bcafecc3f6185b01c6ec6fd179aa9dc0d256310ef2009b8485e658`; `fabric_bridge.py@729648c0d5a46bce9799ba647530da02f9ad9e6a909fd7971303b53075e2a240`; workflow `builder.py@39b0a80bf4e336e42f60a32f44011869309b74f1d1297cab6705298320b26c95`; `production_data.py@af9fc09b0436cc22254efaecb747974e8d10961862edf8c61a14127e908ec4ac`; `container.py@9b96fa1cd315b5ebe715352232ddeddb3a0ce874798e36f75344ed714a31a29a`; and `control_registry_providers.py@cd7cb561b727fa91bfd96499aca13b122e36dbee49ecd4930425a63512a8a2a0`.

## Smallest safe next step

There is no exact dataset ID, selected acquisition profile, optional distribution ID, or source-backed `DataViewRequestRef` in the named inputs. Therefore even a minimal authentic catalog query would require guessing, and I did not open the database. The existing read-only session supports one parameterized `ds_datasets WHERE id = ? LIMIT 1` check and, only if the selected profile names one, one exact distribution-row check. `DatasetCatalogStore` is not appropriate for this bounded preflight because its constructor fingerprints the entire database twice.

The minimum evidence packet is:

1. **L01/A:** the exact existing catalog/acquisition/history input and L6 pair, with matching manifest or a legitimate already-versioned replacement; opaque source/version and relevant time-role refs; owner/custody, purpose, and currentness. No new manifest should be manufactured.
2. **C05/V1:** the accepted catalog/profile basis, exact dataset selector and optional selected distribution, and the corresponding request/ref semantics.
3. **C10/A after Q1:** the actual serving root/profile and request context bound to tenant/cell/run, plus the existing consumer/API recipe that will resolve the persisted simulation ref on a fresh read.

Once these inputs are supplied, the smallest safe sequence is an exact parameterized metadata read through `open_catalog_read_session(..., overlay_path=None)`; run the existing Fabric producer with the admitted request and configured catalog/profile; persist the simulation and later failure; then resolve those same refs through a fresh actual consumer. Missing/corrupt/profile-mismatched controls must refuse. The previous `authentic-closeout-admission-current.md@ced95ecf16172b983b1e990739c76dd47ece8574ec154442ab933d90854d21aa` contains a prepared one-row read-only recipe, still unexecuted because no owner-selected IDs were supplied.

If the owners cannot provide the packet, the honest disposition is to preserve the original held/limited state and the existing synthetic route as a fixture-level witness. Do not infer source absence or require a generic external issuer: the outstanding facts are exact source/profile selection and the live serving binding.

P37: the exact named receipt identities and L6 member comparisons are `recomputed`; the local root-manifest profile/version/time are `owner_supplied`; RES03 source selection, replacement validity, catalog content binding, current serving root/profile/context, and currentness are `not_established`. Capability labels for the authentic positive remain `input_missing`, `bridge_missing`, `verification_missing`, and `semantic_test_missing`; the synthetic route has a separate bounded fixture positive.

P40 bucket: **same custody/currentness class, one level deeper**. The exact private L01 receipts resolve the offline L6 root and selected profile, but do not join it to a RES03 catalog request or live consumer. The distinguishing case is a successful fixture route under a different source/profile selection; the current test cannot detect it because it skips Fabric. The class-level falsifier is one owner-supplied matched source/profile/context tuple that is consumed by the real producer and read back by the actual fresh consumer. No per-instance code patch is justified before that tuple exists.
