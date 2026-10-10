# Selected-reference Core→IR composition review

Read-only review of the local candidate composition; this is not G acceptance or a formal finding adjudication.

## Source boundary

- Candidate checkout: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`; branch `codex/e02-unified-local-20261009`.
- Exact candidate HEAD at review: `80f043c0c007ca14dfd4927f980e391f4fcdc62a`, tree `a9af1372c08712c3a58a367cad085a4926243f7e`, parent `021560651b7ab84857f7cd5ef1ecf08408cd548c`. HEAD is receipt-only; the reviewed source is the dirty composition on that base, not a frozen commit.
- At capture: 448 tracked paths differed and 375 paths were untracked (494 porcelain entries). The tree was advancing concurrently. The file hashes below bind the source bytes I inspected.
- Scope: selected-view preservation across Core CAS, IR adapters, lineage consumers, uncertainty consumers, and caches. No source edits, Git mutation, heavy numerical work, or G adjudication.

## Verdict

Partial. The central IR read path now preserves a typed selected ref through adapter → raw manifest sidecar → blob bytes, and the input writer retains the selected profile on persisted lineage. Five focused tests passed. The wider path still has valid selected-view cases that fail or lose declared lineage, so this is not a complete selected-ref composition.

## P40 bucket

**SAME class, deeper escape:** selected-view identity is still confused with content identity at downstream read/lineage boundaries. Treat this as a second-level escape of the selected-ref class. Widen the mechanism across the consumers below or record a bounded residual with a falsifier; do not patch only the first locator.

### Findings

1. **Selected lineage edges cannot always be rehydrated.** Core `InputRef` stores `artifact_id`, `role`, and optional `manifest_profile_sha256`; it omits `kind` and `media_type`. Core `ArtifactRef` selection requires those fields, and `get_manifest` verifies them against the selected sidecar. The current reconstructors first load the default manifest by ID, then attach the selected profile to its default type: `scientist_node_adapters.py:827-837`, `foundry_consumption.py:1423-1437`, `backtesting/orchestrator.py:188-202`, and `foundry/calibration/identifiability.py:1370-1381`.

   Reproduction against the current Core CAS: write identical bytes under two manifest views with different `kind`; an `InputRef` selecting the second view contains its ID and profile hash, but rebuilding an `ArtifactRef` from the first/default kind fails with `ArtifactIntegrityError: Artifact reference type does not match selected manifest`. Calling the exact selected `ArtifactRef` succeeds. This is a supported store state, not malformed input. A resolver must recover type from the selected sidecar (for example, a profile-addressed manifest read) or the persisted lineage edge must carry enough type data. Falsifier: selected lineage with same bytes/ID and distinct kinds must resolve the selected manifest, while a wrong profile must refuse.

   Narrow contract choice for the handoff: (A) add optional `kind`/`media_type` to Core/IR `InputRef` and emit them for new selected-view edges, omitting absent fields for legacy profileless inputs; or (B) extend the existing Core store read interface with an owner-verified profile-addressed manifest lookup `(artifact_id, profile_sha256)` that returns the selected sidecar’s type fields. The current `has_manifest_view(id, profile)` seam already resolves ownership without kind/media; extending that seam avoids duplicating type metadata in every lineage edge, but requires every backend/protocol adapter to implement the same refusal semantics. I recommend prototyping B first; if any supported backend cannot resolve/authorize the sidecar by ID+profile, choose A with additive optional fields and schema/generator updates. Do not treat either option as decided or as G acceptance.

2. **Recursive closure deduplicates by ID and drops another view’s parents.** In `scientist_node_adapters.py:814, 822-825`, `visited` is `set[str]` keyed only by `artifact_id`. I created two views of identical child bytes with the same kind but different lineage parents, then a root referencing both views. Actual `_reference_closure` returned paths `['root', 'root.lineage[0]', 'root.lineage[0].lineage[0]', 'root.lineage[1]']`; parent A was present and parent B was absent. Both child-view bindings were present, which makes this easy to miss with a shape-only check. The property is complete ancestry of each selected view; the implementation tests content-ID uniqueness. The falsifier must require both distinct parent bindings, and changing only the second view’s parent must change the observed closure. This is a material custody/completeness gap for the closure evidence.

3. **Cold read-through cache cannot serve the raw selected manifest.** `CachingArtifactStore.get_manifest_bytes` at `caching_store.py:313-324` reads only `_default_manifest_owner()`; with supported `write_through=False`, that is the local store. For a remote-only selected view, `has`, `get_manifest`, and `get_bytes` can resolve the remote view, but `get_json_artifact` reads raw manifest bytes first and fails on the absent local `.view.<profile>.manifest.json`. I reproduced this with a fresh local cache and exact remote profile: `remote_has=True`, `local_has=False`, `cache_has=True`, then `get_json_artifact(...)` raised `FileNotFoundError` for the local view sidecar; the failed request did not populate the cache. Existing raw-profile cache coverage exercises write-through/durable-owner only. Falsifier: cold read-through selected-ref load must resolve the remote raw profile and payload together, populate the cache if configured, and refuse a wrong or malformed selected sidecar.

4. **Some real uncertainty consumers flatten the top-level ref before admission.** `confidence_pass.py:73-81, 137-141` extracts an `ArtifactID`, reads the simulation payload by ID, and passes the ID to the new admission function. `backtesting/orchestrator.py:517-548` and decision-packet enrichment `enrichment.py:2737-2772, 2798-2809` do the same. The normative-arbitration path `run_normative_arbitration.py:665-671` preserves and passes the typed `ArtifactRef` (useful control). The new reader correctly includes selected profile in its child envelope/report lineage comparisons, but the first simulation-result selector can already have been flattened. Present behavior remains fail-closed: the admission reader always reports `draw_success_ledger_missing` and `draw_basis_verifier_missing`, so this is not evidence of a current false positive. It is still an uncomposed consumer path: carry the typed simulation ref from state through the initial read and admission, then test sibling manifest views with different lineage.

The independent concern is content authority: `get_json_artifact` uses the persisted Core profile only to decode and verify canonical bytes; its docstring explicitly says this is not producer attestation. Nothing in this review treats that profile as law, issuer, currentness, or custody proof. BERL’s feature-dependence/law profile is a separate content contract and was not independently verified here.

## Direct evidence

- Focused command, exit 0: `.venv/bin/pytest -q tests/unit/core/artifacts/test_ir_adapter.py::test_ir_write_round_trips_selected_lineage_profile_through_fresh_core_reader tests/unit/core/artifacts/test_ir_adapter.py::test_ir_reader_preserves_selected_manifest_view_through_manifest_and_blob_reads tests/unit/core/artifacts/test_ir_adapter.py::test_ir_reader_gets_raw_profile_from_cache_durable_owner tests/unit/ir/test_uncertainty.py::test_uncertainty_loader_preserves_selected_manifest_profile tests/unit/core/artifacts/backends/test_caching_store.py::TestCachingArtifactStore::test_get_bytes_local_miss_remote_hit`. Output: `..... [100%]`.
- Fresh AST parse of all 2,707 `policy-engine/src/polisyos/**/*.py`: 2,707 parsed, 0 errors. The exact-selector scan found six `.artifact_id` arguments to `get_manifest`: the four lineage reconstructors listed above and two `caching_store.py:250-251` calls guarded by `manifest_profile_sha256 is None`. It found no ID-only selector for `get_json_artifact` or `get_manifest_bytes` in source.
- The author’s `shared-refs/current-selector-scan.txt` is not current for this tree: it still reports `uncertainty.py:2149 get_json_artifact(... ref.artifact_id)`, while the reviewed source passes `ref`. Re-run the canonical scanner against the frozen composition; do not carry its earlier residual count forward.

## SHA-256 of inspected source / evidence

- `src/polisyos/ir/artifacts/io.py`: `2b8805c49aa2446c7930eee7265b30154c5a450955eac57d152123d78441cadc`
- `src/polisyos/ir/artifacts/contracts.py`: `f98fc6921e8fb40fe18abe10b91c1a1b8f94e8c6ff0ba697bed6fc51974abe08`
- `src/polisyos/core/artifacts/manifest.py`: `fb1fb68e18b80ba83ee2aa6b94a011386ede96bc75c492123bb4de3bec45639d`
- `src/polisyos/core/artifacts/ir_adapter.py`: `6d9a09f93d92a080f4b5fd8df310f1be2c41a50d36090c2c341e8a49948cf047`
- `src/polisyos/core/artifacts/backends/caching_store.py`: `9ab07a1920377017c897fb3c0db514ecaeb8fe73833e198b676556b6d4c43383`
- `src/polisyos/ir/analytics/uncertainty.py`: `6d0b1d550581d6a1305ec70335ccde5cccb88422a3cf6fabe03923afd0540ab5`
- `src/polisyos/runtime/quality/workspace/scientist_node_adapters.py`: `8332ae077f6d097f36c380bba204559f9280df105902a532019dcac2f7bc04a3`
- `src/polisyos/runtime/quality/workspace/foundry_consumption.py`: `37b7db1c6dcbbc4f97bdae6dbab4d02cfe67c1bc522c2018226c24bdce4876a3`
- `src/polisyos/scientist/governance/passes/confidence_pass.py`: `c1fa32d73f1d7ce05513c4a6e3972df1f447509d3c6a17f46fcb17c141ad6c84`
- `src/polisyos/scientist/methods/backtesting/orchestrator.py`: `53b99e93d0da5c5a07dd8e9d99cbb50df99a0819b7fb98d31a07c3d195cb4908`
- `src/polisyos/scientist/nodes/builtins/decide/decision_packet/enrichment.py`: `4ec5bab2f9e721ac0092d24b9375abb13db0111013b161d05a2d0e56aef99cf3`
- `src/polisyos/scientist/nodes/builtins/governance/run_normative_arbitration.py`: `171ecf8f05b537253521ecaf800fb61b730d410a105a6d0288904a565aa36324`
- `src/polisyos/foundry/calibration/identifiability.py`: `68b66f08fc5f0f225adc5110c3624c4c57b982654472fc3d787ead4a981df11f`
- `tests/unit/core/artifacts/test_ir_adapter.py`: `b963a0e67370646fe941cc64d2bf6751f5cbc99619c83055be17d05f34fc9697`
- `tests/unit/core/artifacts/backends/test_caching_store.py`: `df322346f50d545b2eb7049c7ff03f4827abe7282b7e8fdff2ab92fe513d1fe2`
- `tests/unit/ir/test_uncertainty.py`: `e143a946fe90d9a466f4b5cf60b9f586acaf272ec35feffb7613e346ee6d208a`
- `implementation-handoffs/LOCAL/shared-refs/source-census.txt`: `bb9004cd93da5d3562a8f8b23f0bc68c323b097007391c2b039e9fd3d94054d5`
- `implementation-handoffs/LOCAL/shared-refs/current-selector-scan.txt`: `e0e594fa6719f64acd88d35352b2ac1517522db9223962d89f2dbfd8f829dd69`
- `implementation-handoffs/LOCAL/shared-refs/current-ir-boundary-census.txt`: `3929eb1cb7a1ab94440088761be05a900b2c457c9184f89b72519349d83ad09a`

Remaining checks belong to the composed source freeze: update the stale census, add adversarial selected-kind and duplicate-content/multiple-view lineage controls, exercise cold read-through raw-manifest loading, and preserve exact simulation refs through confidence/backtesting/decision-packet consumers. No final capability claim is supported by the five focused tests alone.

## Follow-up delta review — selected-ref mechanisms at `a499098`

This section supersedes the earlier mechanism findings for the current dirty composition. It remains an independent review, not G acceptance or formal finding adjudication.

### Exact review boundary

- Checkout: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`; branch `codex/e02-unified-local-20261009`.
- HEAD `a49909826cf87f164dae36c26b21fb5d188ca835`, tree `bdce171c3fa6a3fc7781b42ea2523af1c0c5f2ab`, parent `704082ef53d8e5aca645fd814b9c85b5db3e5168`. Branch status at capture: `codex/e02-unified-local-20261009...origin/codex/e02-unified-local-20261009`.
- The selected-ref implementation under review is still uncommitted. HEAD/tree therefore identify its base, not the reviewed source freeze. The path hashes below bind the actual bytes read. Other concurrent working-tree changes were not reviewed by this packet.
- Scope: Core profile-addressed manifest resolution, IR typed-selector reads/writes, filesystem/cloud/cache adapters, selected-view lineage closure, and actual uncertainty callers.

### Verdict and P40 bucket

**Partial.** The earlier selected-kind rehydration, content-ID-only closure visitation, and cold remote raw-sidecar failures are closed by the current mechanisms and focused behavior checks. The earlier uncertainty-caller finding is not fully closed: the reader now preserves a typed ref, but three production consumers flatten the top-level simulation ref before their first read and before uncertainty admission.

**SAME class, one level deeper:** selected-view identity still gets discarded at consumer intake. This is the selected-ref identity/content-identity class from the prior review, not a new class. The source has not yet shown the end-to-end property across these callers. Do not count this as a closure merely because `get_json_artifact` itself now accepts typed selectors.

`ConfidencePass._resolve_simulation_result_id` returns only `ArtifactID`; `ConfidencePass.validate` then calls `store.get_bytes(sim_result_id)` and passes that ID to `load_simulation_result_uncertainty_admission` (`confidence_pass.py:259-275, 73-81, 137-140`). Backtesting parses `simulation_result_ref["artifact_id"]` into `sim_id`, reads by ID, then admits by ID (`orchestrator.py:935-943, 963-967`). Decision-packet enrichment reads `simulation_result_ref.artifact_id`, serializes it to a string, and passes that string to admission (`enrichment.py:2737-2745, 2796-2809`). In `uncertainty.py`, an ID-only ref is resolved through `store.get_manifest(id)`, which selects the store default (`_normalized_artifact_reference`, lines 2346-2356). Thus a typed ref selecting one manifest view is not bound through these actual consumer paths.

The discriminating case is two `foundry.simulation_result` manifest views with the same blob ID, kind, media type, and schema but different selected input lineage. A consumer offered the non-default typed ref must read/admit that exact view and observe its lineage; changing only the selected view's parent must change the consumer's lineage result. Current tests establish fail-closed outcomes for missing draw-ledger/verifier evidence, and the admission reader unconditionally returns those limitations today, so this review found no path to a positive numeric admission. That bounds the present impact to selected-lineage/report correctness; it does not close the selected-ref composition property. Keep the typed ref through the initial payload read and the admission call, then add this same-content/different-lineage consumer falsifier.

The author census `shared-refs/current-selector-scan.txt` reports `get_json_id_only=0`; that predicate does not see the raw `get_bytes(ArtifactID)` calls above and cannot establish this end-to-end property. Treat its zero as a callee-call census only, not a selected-ref consumer proof. It also reports six ID-only `get_manifest` calls, some guarded by the profileless branch; no zero-count inference was used here.

### Mechanism verification and removal controls

- `resolve_manifest_by_profile` now resolves `(artifact_id, manifest_profile_sha256)`, validates the returned manifest identity/profile, constructs the exact typed ref, and binds it to `store.get_bytes`. Filesystem, S3, GCS, caching, and the Core→IR adapter expose the profile-addressed path; the optional-store fallback accepts only the default profile. IR reads pass typed refs through raw-sidecar and payload reads; raw canonical metadata is strict and malformed/omitted fields refuse before payload bytes. IR write lineage retains the selected profile.
- `_reference_closure` now keys `visited` by `(artifact_id, manifest_profile_sha256)` and resolves profile-bearing parent edges through the same helper. The real test constructs two same-byte child views with distinct parent inputs and asserts both parent paths/IDs are emitted.
- `CachingArtifactStore.get_manifest_bytes` now reads the owner’s raw selected sidecar and, for a cold non-write-through cache, falls back from local to remote. The real cold-cache test asserts successful IR decode, exact raw bytes and selected manifest metadata cached locally, and wrong-profile refusal.
- In-memory removal controls against the reviewed runtime code: removing `get_manifest_by_profile` makes valid non-default resolution fail with `TypeError: Artifact store cannot resolve a non-default manifest profile by digest`; removing the remote raw-manifest fallback makes the cold selected read fail with local `FileNotFoundError`; replacing the closure’s full-view visited key with artifact ID alone yields `parent_a=True, parent_b=False`. These are bounded removals of the properties themselves, not marker checks or hypothetical future-verifier recursion.
- Actual consumer smoke/negative tests pass and confirm the present limited behavior: confidence limits unverified narrow intervals, backtesting refuses a simulation result without draw admission, and decision-packet enrichment records degraded paths for invalid uncertainty output. These tests do not cover the selected same-content/different-lineage consumer case above.
- Candidate-bound focused tests were run with `policy-engine/.venv/bin/python` resolving `polisyos` from this checkout’s `policy-engine/src`. Results: selected-ref adapter/cache/closure/IR uncertainty/backtest-input tests `10 passed, 2 warnings in 13.25s`; selected S3/GCS exact-view backend tests `2 passed in 0.04s`; confidence/backtest/decision-packet limited-consumer tests `3 passed, 3 warnings in 4.70s`. Cloud backend tests used the repository’s unit fixtures, not live cloud credentials.

### Source and test byte fingerprints

SHA-256 values are for the exact dirty working-tree bytes reviewed, relative to the checkout above:

| Path | SHA-256 |
|---|---|
| `src/polisyos/core/artifacts/protocol.py` | `20adc14e1f7f014b1a90dd05c8602f50fafe762ce93728973053ac4e15f59736` |
| `src/polisyos/core/artifacts/store.py` | `f787817462174c52d3ffdce9586d74a1c42276af8f38fae08d73c5f8bb7beec2` |
| `src/polisyos/core/artifacts/backends/caching_store.py` | `a94a862cb583c44a98ceffc43a0e51a1dcba92dc1516ea75abc714f912fad0bf` |
| `src/polisyos/core/artifacts/backends/s3_store.py` | `30fb469878aa2c4300c2c616f278700dbb251bdbf047c17c522d5dbcc484da43` |
| `src/polisyos/core/artifacts/backends/gcs_store.py` | `607cb3af71c9e5247cf8bce986401d53c9c62a191538d11f75779c00823fb758` |
| `src/polisyos/core/artifacts/ir_adapter.py` | `61ecbd49c9accff56c80356039a974e3f152b97eb23820a03ca8f2903e849e76` |
| `src/polisyos/core/artifacts/__init__.py` | `58d631185a44f6e4df0933f4501e9f63637917730bc6b3f5533f01f5b20fb701` |
| `src/polisyos/ir/artifacts/io.py` | `2b8805c49aa2446c7930eee7265b30154c5a450955eac57d152123d78441cadc` |
| `src/polisyos/ir/artifacts/contracts.py` | `5a91debc543cf31d1481b923cd9a534e811e49c670e7cdb33f6400c8ab0a345a` |
| `src/polisyos/ir/registry/refs.py` | `bbac14368f7091bf8135f621999e9b702d711c31a95e87e7ceaa1bd963c8fe72` |
| `src/polisyos/ir/analytics/uncertainty.py` | `6d0b1d550581d6a1305ec70335ccde5cccb88422a3cf6fabe03923afd0540ab5` |
| `src/polisyos/runtime/quality/workspace/scientist_node_adapters.py` | `5697b0ae7f7473e4f16d6abed233e74c9d753479e31ece20764f521cb92253fb` |
| `src/polisyos/runtime/quality/workspace/foundry_consumption.py` | `25a71c978c05bf9b30c2d824441e4b0b9d66542e8274222b8751e3f9583a56b6` |
| `src/polisyos/scientist/governance/passes/confidence_pass.py` | `c1fa32d73f1d7ce05513c4a6e3972df1f447509d3c6a17f46fcb17c141ad6c84` |
| `src/polisyos/scientist/methods/backtesting/orchestrator.py` | `a5e8d90d02b6314a112f85adb6876e85c2528f8b37d83f1e8c0215c6467306cc` |
| `src/polisyos/scientist/nodes/builtins/decide/decision_packet/enrichment.py` | `4ec5bab2f9e721ac0092d24b9375abb13db0111013b161d05a2d0e56aef99cf3` |
| `tests/unit/core/artifacts/test_ir_adapter.py` | `d55fb471892e743a4c2cdc3dff393c1da937783c65e503ced54cc7a4d6afd9a1` |
| `tests/unit/core/artifacts/backends/test_caching_store.py` | `78ebd05ade9dac6627b69b5c0cae14ea15af6c43c091157d9282cb1c5d15d53f` |
| `tests/unit/core/artifacts/backends/test_s3_store.py` | `83368ab5000db96236fc5e0b47504be10cc5ff532474ec276e24479c05bef832` |
| `tests/unit/core/artifacts/backends/test_gcs_store.py` | `1d458a30b209c2f5c287d57bee046ecf537dbef4097e1603c3c4b17be4bc1849` |
| `tests/unit/runtime/quality/test_workspace_scientist_node_adapters.py` | `27c8377f31e8ea44cf479eb42f3ea821610e1be2c99c7e230062dd2b9d26e143` |
| `tests/unit/ir/test_uncertainty.py` | `e143a946fe90d9a466f4b5cf60b9f586acaf272ec35feffb7613e346ee6d208a` |
| `tests/unit/scientist/governance/test_confidence_pass.py` | `a244c5b7f277c625ab35c4d7cbe8c6e4c9855b96b0adfd179f18bc92e1f20782` |
| `tests/unit/scientist/methods/backtesting/test_backtesting.py` | `5df3a2adafae439ddef016e37bf1e17c731972fcc641fbbafca01a3f85588600` |
| `tests/unit/scientist/nodes/test_decision_packet_node_v3.py` | `791f1ad5b7aa3a83abdd45499dd348a55f91829228d79a3b7b3bbe1022dfde0f` |
| `implementation-handoffs/LOCAL/shared-refs/current-selector-scan.txt` | `ede6498035f3a2d654cb71ccd7b91641cd80776f99f67a1b485f6f56638e93f5` |
| `implementation-handoffs/LOCAL/shared-refs/current-ir-boundary-census.txt` | `3929eb1cb7a1ab94440088761be05a900b2c457c9184f89b72519349d83ad09a` |

No source edits, Git-history changes, heavy numerical fits, production reads, or G adjudication were performed by this reviewer. The source freeze must recheck these bytes after the remaining consumer intake decision/change.

## Independent exact-source composition review — `b2cd1fbb`

This review is source-bounded to the committed candidate snapshot below. It is not G acceptance, does not make formal finding decisions, and must be followed by a delta review of any later composed source.

### Boundary and outcome

- Candidate source commit: `b2cd1fbb0c9aaa21a05cbf999330a2e07fe81f23`; tree `65c44e4872c0efb0772ee955c2b92351c2486892`; parent `00c200c2ec33786a80dd41209eca46a2539dac5c`.
- Candidate checkout: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`; product root: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`; expected branch `codex/e02-unified-local-20261009`.
- The source freeze manifest is `implementation-handoffs/LOCAL/raw/source-integration-preflight/attempt-2/source-commit.json` at SHA-256 `612ac67b54113c2b6b6a754f8786aad23a530e683fc1da99ff156124172c6eb5`; paired precommit manifest SHA-256 `07b4a9d179d65cebc462295cf907eecfd39fc94804baba147486515a53f9ac55`. The readback recorded 627 manifest paths checked, 0 byte mismatches. The source checkout was read from this exact committed composition; the manifest, rather than a moving branch head, is the source identity for this review.
- **Verdict: partial.** The selected manifest view now survives the Core→IR adapter, profile-addressed Core/CAS paths, cloud/cache readers, history serialization, and several actual consumers tested below. One same-class deeper loss remains at the derived-observation contract-projection boundary and is reproduced with two valid same-ID views. This is a blocking source-composition finding, not a G closure.
- Formal G closures proposed by this reviewer: `[]`.

### Full source census and P40 bucket

The census walked every `*.py` beneath `policy-engine/src/polisyos` (2,709 files; 2,709 parsed; 0 parse errors). The exact scanner/output is `implementation-handoffs/LOCAL/reviews/selected-ref-final-census.log` at SHA-256 `a550f2585adaf796b2613b05fdb246beda560e091b5d0b475ed36ca2bb943da3`. It scans direct `.artifact_id` arguments to `get_manifest`, `get_manifest_bytes`, `get_bytes`, `get_json_artifact`, and `verify`, because those calls can select a default view if the typed selector has been flattened. It found these 10 callsites:

| Callsite | Classification |
|---|---|
| `core/artifacts/backends/caching_store.py:251-252` | Both calls are inside the `InputRef.manifest_profile_sha256 is None` branch. Selected profiles go through the exact-profile availability path. Default-only by construction. |
| `core/security/chronology_anchor.py:568` | The verifier receives the ID together with the record-bound blob bytes and exact raw-manifest bytes; the same routine compares their raw hashes and invokes strict identity verification. This call does not fetch a default manifest view. |
| `foundry/calibration/identifiability.py:1375` | `_response_input_ref` calls `get_manifest(id)` only in the profileless branch; the selected branch resolves by the supplied profile before creating/reading the typed ref. |
| `foundry/calibration/uncertainty_adapter.py:792` | `get_manifest(id)` is likewise the profileless branch; selected views resolve with `resolve_manifest_by_profile`. |
| `runtime/quality/derived_observations.py:1090` | **Escape.** `_load_source` calls `_manifest_projection(store, projection.artifact_id)`, and that helper reads the default manifest by ID. The projection has no profile field and its input edges omit parent profiles. |
| `runtime/quality/derived_observations.py:1169` | **Same escape class.** `_load_transform_family_registry_artifact` verifies and reads `projection.artifact_id`; `ArtifactContractProjection` cannot express a selected profile, so the generic projection/read boundary cannot preserve one. |
| `runtime/quality/workspace/foundry_consumption.py:1440` | This call is guarded by `item.manifest_profile_sha256 is None`; the selected branch resolves the exact profile. |
| `runtime/quality/workspace/scientist_node_adapters.py:833` | Parent `get_manifest(id)` is only the profileless branch; profile-bearing parents use the profile resolver before constructing the typed ref. |
| `scientist/methods/backtesting/orchestrator.py:325` | Same explicit profileless/default branch; profile-bearing inputs use the selected-profile resolver. |

**P40: SAME class, one level deeper.** The residual is typed-ref→raw-contract-projection identity loss. The two derived-observation callsites are consequences of one generic projection contract, not separate instance fixes. The correct repair boundary is the projection/source-of-truth mechanism and all its consumers; do not add per-callsite deny-lists. This is the second observation in that class, so widen the generic mechanism or retain a bounded residual with the falsifier below. No further review ladder is proposed.

The property is: a caller-supplied `ArtifactRef` selects an exact manifest view, and a derived recipe must bind to that selected manifest and selected parent graph (or refuse if it cannot). The code turns that selector into `artifact_id` alone, then reconstructs its contract from the default manifest. The divergent case is the same blob ID, kind, media type, schema, and producer with two profiles whose `authority_evidence` parent IDs differ: the selected profile is silently projected as the default view and recipe construction still succeeds. This is a P38 proxy at the exact boundary it exists to police.

### Minimal falsifier and observed result

The reproducer uses the repository's actual `_case_inputs` and `_registry` fixture helpers, an in-memory temporary `FileSystemCAS`, and a supported second manifest profile. It changes only the selected view's `authority_evidence` input to a second valid persisted artifact while keeping the source blob and contract bytes identical. The complete command and deciding stdout are retained at `implementation-handoffs/LOCAL/reviews/selected-ref-derived-observation-probe.log`, SHA-256 `e18d616712f6ca00aa75e1c88f7e98f309939cef8993dbe799d24b053c5c1783`.

Observed: `same_blob_id=True`, `selected_profile_present=True`, `manifest_inputs_differ=True`, `projection_defaults_equal=True`, `projection_contains_selected_parent=False`, `projection_matches_default=True`, `build_derivation_recipe_result=ACCEPTED`, `result=FALSIFIER_REPRODUCED`. Thus the consumer accepts a typed selected ref but binds its recipe to the sibling default lineage. The falsifier closes when the selected projection contains/binds that selected profile and its selected parent graph, or when admission refuses an unsupported selected view. Merely preserving the declaration or ID is insufficient.

The generic fields responsible are `ArtifactContractProjection` (ID/kind/media/schema/producer/input graph/hash, but no selected profile), `ArtifactInputEdge` (role plus ID, but no selected parent profile), `_manifest_projection(store, artifact_id)` (default `get_manifest(id)`), and subsequent ID-only payload reads. The smallest structural direction is to extend the existing selected-view resolver/projection contract and make projection verification plus payload reads consume that exact selected view, including selected lineage edges. This review does not prescribe a new architecture or implement the repair.

### Independent verification across consumers

The test process used `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/.venv/bin/python` with `PYTHONPATH=src:.`. In the source-bound wrapper, `polisyos`, `core.artifacts.protocol`, `core.artifacts.ir_adapter`, and `runtime.quality.derived_observations` all resolved from this checkout's `policy-engine/src/polisyos`. The captured argv and wrapper output are in `selected-ref-final-tests.log` at SHA-256 `2c0426403eb34aa8a213b42fd0d8b96e9dc9b818603708ec73a46ec3faa96103`. A direct `python -m pytest -q` rerun of those same targets returned process `exit_code=0`; stdout showed 72 progress dots at 70%, then 30 more at 100%, with no failures. Its warnings were TorchScript deprecation and the existing deprecated governance import. No numerical fit was run.

The 102 focused test cases exercised:

- all of `tests/unit/core/artifacts/test_ir_adapter.py`, including typed Core subtype projection, selected profile through raw manifest and blob reads, invalid profile refusal, and unknown mapping-field refusal;
- selected cold cache read-through and exact-view S3/GCS fixtures using identical bytes;
- IR uncertainty profile reads and strict raw mapping normalization/refusal;
- Phase 3 selected certificate schema view and R3 response-input selected-kind resolution;
- confidence pass, backtesting uncertainty intake, and decision-packet selected simulation lineage/refusal behavior;
- authority-envelope resolver and runtime authority-writer selected profile/lineage checks;
- selected-profile debug artifact and cost API/export readers;
- acquisition-history model behavior and the source-bound JSON roundtrip probe below;
- derived-observation cache/source graph checks, including existing forged manifest-contract refusal tests. Those existing tests do not exercise the selected same-ID/different-parent view, which the falsifier above shows is still accepted.

Acquisition-history serialization was independently probed with four refs carrying four distinct valid profile digests. The row passed `model_dump_json()` and `model_validate_json()` with all four profile digests intact. Complete output is `selected-ref-history-roundtrip.log`, SHA-256 `b9f522e324f8720cd78cb762bc3caffdd95e71c003120ed0581dcae5adfc24ce`. The authority-envelope and export tests establish selected-byte/view delivery, not issuer, law, currentness, custody, or institutional authority; this review makes no such claims.

### Exact source/test byte fingerprints

Hashes bind the source bytes read for the review boundary. The complete census includes all 2,709 source `.py` paths, while this table covers the direct receiver set and the focused test files.

| Path | SHA-256 |
|---|---|
| `src/polisyos/core/artifacts/backends/caching_store.py` | `39eadd5a3e8adbb064f5ae49869c54632c011fc6b82e4a6354263f05c82d956e` |
| `src/polisyos/core/security/chronology_anchor.py` | `e2d502bca1f83e75517aa78f52ac8fe596827ecf0ff717841207370856b66b4b` |
| `src/polisyos/foundry/calibration/identifiability.py` | `da9138ef086aefbbc913c31b830cd42b584696be635546f3694abfc7c21211c1` |
| `src/polisyos/foundry/calibration/uncertainty_adapter.py` | `535da135171162fb69d8e8f20c5c35625f08a7f2da1c62286945f401790456cc` |
| `src/polisyos/runtime/quality/derived_observations.py` | `94adb603b2ee23bb8cd32bd460d0baf7ad2c61b88d398e0f2b683fec9060a095` |
| `src/polisyos/runtime/quality/workspace/foundry_consumption.py` | `245cd985c806a0ca908bb8763d0e7ee847b05f6519fb266fec7968f1d2f21128` |
| `src/polisyos/runtime/quality/workspace/scientist_node_adapters.py` | `c5b08bbf387dc20d027b22009b2e0ebfff45915b5866d7a89d24d88bc3fbd6f9` |
| `src/polisyos/scientist/methods/backtesting/orchestrator.py` | `caa6966993b9e0966cb18308c48181c3ba46d1804ad094b7017ed0ad50cf92c0` |
| `src/polisyos/core/artifacts/protocol.py` | `48142e837245c6504b0333f7ce3900201fa4608b1693b3ed64afe8c0985a77b2` |
| `src/polisyos/core/artifacts/ir_adapter.py` | `9ccaa1b3e09b550d9544f18ef9963ea9c7e06e173d4b57796c8211c0776d18c9` |
| `tests/unit/core/artifacts/test_ir_adapter.py` | `8e9f2c7fc264884a1d971cf8d8a10b848cd02d1611ee54f06da27b2e561a77d4` |
| `tests/unit/core/artifacts/backends/test_caching_store.py` | `50656216fe49470718504e06ec235fbbbbcbb793d159c638ef6a6f1facf35a73` |
| `tests/unit/core/artifacts/backends/test_s3_store.py` | `1fd32850820cc238abf6478b554fa20e657441aa402d2e0b8f7f05f95acfa19d` |
| `tests/unit/core/artifacts/backends/test_gcs_store.py` | `1d458a30b209c2f5c287d57bee046ecf537dbef4097e1603c3c4b17be4bc1849` |
| `tests/unit/ir/test_uncertainty.py` | `b926160cd03daf5fd789e9f29118ab588cbd1a04407972e47b6828ecd8d812b4` |
| `tests/unit/ir/registry/test_refs.py` | `383df20b1daf7f8fa87a6b7d93acdf5269596e4ffa1448284db175e1e9a8e570` |
| `tests/unit/scientist/policy_design/test_phase3_decision_layer.py` | `2e41f35b5c5e09ffbca0af1e6a762d619bdd2702bfce8eb98e504483fb597fda` |
| `tests/unit/foundry/calibration/test_identifiability.py` | `48d985e9b8639a3255fb7944982d5f5d478729d5019c727fe04bd9a80873ea38` |
| `tests/unit/scientist/governance/test_confidence_pass.py` | `740807f90fccbdab4e9e001d679780c7cdef092f3d8867725ef4275a1e209b53` |
| `tests/unit/scientist/methods/backtesting/test_backtesting.py` | `177e437def83c40fa408d79ce7bc0acc04c2dd80760bfc4ac2bbeb7fab5ccc2b` |
| `tests/unit/scientist/nodes/test_decision_packet_node_v3.py` | `2a0dc58fc9c2b0780045e4498c4e6734b68c580c5861876d39bbb70eb0a9f612` |
| `tests/unit/core/artifacts/test_authority_envelope_ref.py` | `690e89706035e4a016bdf43a1e1939616bef69b3ba666e569cdf2add5733aad8` |
| `tests/unit/runtime/quality/test_authority_reconciliation.py` | `00c6fc11445b267b08caea0c9fb6d5fb38f0056202136983c791c9a940003482` |
| `tests/unit/runtime/http/test_debug_api.py` | `77df8151deaad07753eb19a7a44d32dd3c05746da3cf94adcb81b97c42faaaab` |
| `tests/unit/core/contracts/test_run_candidate_simulation_acquisition_history.py` | `253efb3878b75cb82591da2b92e2879903e121ca8c9c45121f76972e47580455` |
| `tests/unit/runtime/quality/test_derived_observations.py` | `e67c270c31d2c19889410e18f4a253e8ed3aa610eaca8561af433f093d841eaf` |

### Remaining review state

The broad selected-ref tests pass and the earlier adapter/cache/backend/caller paths are supported at the stated test boundaries. The derived-observation falsifier remains open at this exact source SHA. A later structural projection change must be reviewed at its exact source commit, including the complete projection and consumer denominator, then rerun the falsifier against the selected branch plus the existing focused tests. Until that delta is independently reviewed, the composed selected-ref property remains partial. No formal finding closure is proposed here.
