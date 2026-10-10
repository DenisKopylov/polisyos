# Native I001 scoped proposal

This is an unapplied proposal for the native Ruff `I001` backlog. It contains only import formatting fixes whose full import-statement AST signatures, import comments, and non-import AST are unchanged. The patch does not edit Ruff configuration, source files, selectors, or `noqa` directives.

## Input and denominator

- Classified input: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/pre-freeze-canonical-ruff-check-20261010/canonical-ruff-classified-diagnostics.json`; SHA-256 `d10452030a3479ff77de3dd068e4101a6487f31a0920f44576d4352b32bd8831`.
- Input source-manifest SHA-256: `d6fdd4f919c00e0c611b2cee81eeb132de8ff412c87a856b88edfc7999b55fb7`; every one of the 659 I001 source preimages matched its manifest digest before and after scratch processing.
- Ruff: `ruff 0.14.10`.
- Exact diagnostic denominator: 682 `I001` rows / 659 unique path values from the primary `rows` array. The row multiplicities are: 1 row(s): 644 file(s), 2 row(s): 8 file(s), 3 row(s): 6 file(s), 4 row(s): 1 file(s).
- The recorded 765-file source-hash manifest was verified with SHA-256 against the current worktree; no source mismatch was found for the I001 paths.

## Isolated Ruff method and review boundary

Each of the 659 source files was copied byte-for-byte to a private temporary scratch tree. Ruff ran with the repository `ruff.toml`, explicit `--select I001`, `--fix`, `--quiet`, `--no-cache`, and a cache directory inside that temporary tree. The source worktree was read-only for this proposal.

The candidate cohort is 438 files. For every candidate, the original and scratch result have identical ordered AST signatures for every `Import`/`ImportFrom` statement (including module, relative level, alias grouping, alias order, and `asname`), identical comment token sequences, and identical AST after import blocks are replaced with placeholders. The changes are therefore import formatting/spacing only; import execution order, grouping, comments, and all non-import executable syntax remain the same. This gives a bounded reason that import-time side effects are not reordered in the proposed cohort.

The remaining 221 files are held out: 214 reorder imported-name atoms (same atom multiset, changed order), and 7 change import statement grouping while preserving flattened atom order. Those changes can affect module initialization or custom import behavior, so the proposal does not assume they are safe. They need separate source-level review before any repair.

- Full proposed patch: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-i001-scoped-reviewed-proposal.patch`; SHA-256 `ab382dac3becba1629ed5b52cb5a0fdc60c3bacb3d7bd801320fc2c2a40681db`; 438 files; 174283 bytes.
- Path format in the patch is repository-root-relative (`policy-engine/...`); apply only after independent review.
- This is not a test or pass receipt. No tests or broad jobs were run.

## Package-family application batches

The single proposal patch can be reviewed/applied in the following independently bounded path families:

| Family | Files |
|---|---:|
| `policy-engine/src/polisyos/data_forge` | 1 |
| `policy-engine/src/polisyos/fabric` | 1 |
| `policy-engine/src/polisyos/foundry` | 1 |
| `policy-engine/src/polisyos/ir` | 1 |
| `policy-engine/src/polisyos/runtime` | 1 |
| `policy-engine/src/polisyos/scientist` | 13 |
| `policy-engine/tests/integration` | 3 |
| `policy-engine/tests/property` | 14 |
| `policy-engine/tests/repo_quality` | 2 |
| `policy-engine/tests/unit` | 395 |
| `policy-engine/tools` | 6 |

## Root/CAN companion exclusion check

- All 73 currently changed or untracked product paths were compared against the 659-file I001 denominator; the intersection is empty. There are 14 tracked Python companion changes and 9 untracked Python/stub/TOML companion paths:
  - `policy-engine/LOCAL/raw/v6-local-sibling-withholding-reader-verification-20261010/reader_probe.py`
  - `policy-engine/LOCAL/raw/v6-local-sibling-withholding-reader-verification-20261010/reader_probe_v2.py`
  - `policy-engine/LOCAL/raw/v6-local-sibling-withholding-reader-verification-20261010/reader_probe_v3.py`
  - `policy-engine/LOCAL/raw/v6-local-sibling-withholding-reader-verification-20261010/reader_probe_v4.py`
  - `policy-engine/LOCAL/raw/v6-local-sibling-withholding-reader-verification-20261010/reader_probe_v5.py`
  - `policy-engine/LOCAL/raw/v6-local-sibling-withholding-reader-verification-20261010/reader_probe_v6.py`
  - `policy-engine/LOCAL/raw/v6-local-sibling-withholding-reader-verification-20261010/reader_probe_v7.py`
  - `policy-engine/LOCAL/raw/v6-local-sibling-withholding-reader-verification-20261010/reader_probe_v8.py`
  - `policy-engine/src/polisyos/core/artifacts/backends/gcs_store.py`
  - `policy-engine/src/polisyos/core/artifacts/backends/s3_store.py`
  - `policy-engine/src/polisyos/core/artifacts/ir_adapter.py`
  - `policy-engine/src/polisyos/core/artifacts/manifest.py`
  - `policy-engine/src/polisyos/core/artifacts/store.py`
  - `policy-engine/src/polisyos/core/components/_cli_replay.py`
  - `policy-engine/src/polisyos/fabric/storage/tenant_cas.py`
  - `policy-engine/tests/integration/scientist/orchestration/workflows/test_r4_shared_study_admission.py`
  - `policy-engine/tests/unit/core/artifacts/backends/test_gcs_store.py`
  - `policy-engine/tests/unit/core/artifacts/backends/test_s3_store.py`
  - `policy-engine/tests/unit/core/artifacts/test_ir_adapter.py`
  - `policy-engine/tests/unit/core/components/test_cli_replay.py`
  - `policy-engine/tests/unit/fabric/data_plane/test_scale_out.py`
  - `policy-engine/tests/unit/runtime/quality/test_acquisition_planner.py`
  - `policy-engine/tests/unit/scientist/orchestration/engine/test_skg_snapshot_replay.py`
- The current CAN producer-spec proposal has 10 source paths; its intersection with the I001 denominator is empty:
  - `policy-engine/src/polisyos/core/artifacts/backends/gcs_store.py`
  - `policy-engine/src/polisyos/core/artifacts/backends/s3_store.py`
  - `policy-engine/src/polisyos/core/artifacts/ir_adapter.py`
  - `policy-engine/src/polisyos/core/artifacts/manifest.py`
  - `policy-engine/src/polisyos/core/artifacts/store.py`
  - `policy-engine/src/polisyos/fabric/storage/tenant_cas.py`
  - `policy-engine/tests/unit/core/artifacts/backends/test_gcs_store.py`
  - `policy-engine/tests/unit/core/artifacts/backends/test_s3_store.py`
  - `policy-engine/tests/unit/core/artifacts/test_ir_adapter.py`
  - `policy-engine/tests/unit/fabric/data_plane/test_scale_out.py`
- A read-only scan of all 76 existing `LOCAL/raw/*.patch` files found no patch header for any I001-denominator path.

## Full I001 denominator and source preimages

Every path below comes from the classified diagnostics primary `rows` array. Digests are current source preimages from the input hash manifest. `proposal-format-only` means the file is included in the unapplied patch; `hold-*` means it is deliberately absent from the patch.

| Full repository path | Preimage SHA-256 | Disposition |
|---|---|---|
| `policy-engine/src/polisyos/core/canon/canon_json.py` | `c5e60f4d47bc4fc5347809545609716c0ce030dfc6c3e3deee61d8ad5a086c95` | `hold-import-statement-grouping-change` |
| `policy-engine/src/polisyos/core/canon/hashing.py` | `a32caf919317c5667ac02bde68fa6a1d0fa064e1edeb44c89bc066a14a9272c0` | `hold-import-statement-grouping-change` |
| `policy-engine/src/polisyos/data_forge/domains/academic/batch/resolve_extract.py` | `8b588ddf7cef0d92eb57a2588a20f03f52a9959df9058c38581dcc7e50a74665` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/data_forge/domains/catalog/batch/checkpoints.py` | `fc4dd1cf2f148bc2298a44c08705986ed858eead2b028e5a7129edc65750c73d` | `proposal-format-only` |
| `policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py` | `5d5f5794e789476b2f32eb1c584ef0c14b19f04ab11c2d706311cca5d408cc29` | `hold-import-statement-grouping-change` |
| `policy-engine/src/polisyos/data_forge/kernel/snapshot/finalize.py` | `e8ed1ac5b5016bc0790d4c264a9a8a3d222769c86935be3d65460fe4045cbc43` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/connectors/contracts/source_contract.py` | `66ecd493fb781ecdbd6a9a80d52061bc41f5d45da48a78fad329a39366d1d0fe` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/connectors/federation/evidence_aggregation.py` | `34951e8af42d4fe2480de31072bb228cd86e1335e00d23a3c9c5c30f9c79e0be` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/connectors/federation/ranker.py` | `ab6176d88ba7decfdd40d205d845d84393502a9346a5de6c11270468de2ee9de` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/connectors/federation/types.py` | `9e0cf8e080efc1a27c4b30350f33ac179dd09c8901978b004c8a777a7db02d2c` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/connectors/quality/evidence.py` | `85d1ef1f05ea222e6617d4d767dbd10f777588965c4846924b84c72baa0c5733` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/connectors/quality/freshness.py` | `86dd54a10b35e3e4cefd87e023df9c78712c3dbcef79a384098620c9e18f52a7` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/connectors/quality/statistics.py` | `cff19fa8ec3ca82b16036167df55c2a362ae5c87312c792fa6059880800ab7a2` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/connectors/quality/validator.py` | `ede84b3bd497e36ec99dbdccc8fdc1da15d652cc4fc2a02974552bee39be125c` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/connectors/resilience/circuit_breaker.py` | `07f24deae0a79a045d4da8ec30cf03c6f0c5cae0a94ecceb48870d39ee88b6ea` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/connectors/resilience/rate_limiter.py` | `c082c55003b6710aac7bcb1a207f67d0083fe1da499b998d60f1a0d8228becbe` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/connectors/sources/graphql_api.py` | `634965323ef6ffc39b7691e9ff1b11c6589c94cb3b7fdd9c58ec88a0fc853282` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/connectors/transform/pipeline.py` | `ffbb927c49919291d63d100ce4ba4fa65645d0d28c98f8215caeda48756be6dc` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/connectors/transform/validator.py` | `9cdbbba4ab8128c8b90e5882a46e10456620976dd0350b5b654b8723c698d847` | `proposal-format-only` |
| `policy-engine/src/polisyos/fabric/data_plane/quarantine.py` | `58a80a91a06b537f8d54f3a09536e0a80e86405c424430169b26a6bea61393c6` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/provenance/export_provo.py` | `533ee7d17d01a6fab9d14b714a831bd4ffe4dc452460fd4738d2d96c21ceadd6` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/quality/__init__.py` | `9600f49bb3ac6915eb41017f2f5ccbeee4b67ea1b7777697dc796bca6cb69151` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/quality/quality.py` | `8dc607b2fd88a44f796e81dd6eb62e0b7f8098a06af742d4392d4e8fcd632ea9` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/security/__init__.py` | `f3daf5478d0686b00935ccfa3aca7623906990b0ab94f353bea6bfc4b2bf64e1` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/world/materialize/duckdb.py` | `fbb54a033152ff1fd54c8d4f11d6690eaa75ab467d7b0c9a372c21c92f122e53` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/fabric/world/store/validate.py` | `855ed0f71a225d56f16f1d8d92132e4947826cc3b4d48fb29f1e16d898601647` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/foundry/methods/artifacts/_method.py` | `89d11c480c8ccb563251d5c9e1bfa2919aeb8f52a91344f8086c73d5f01ab6f0` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py` | `e323a27c84916bceee5d14d5c4a2d58e009624de477f4703d38372cbac76ae78` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/foundry/methods/catalog/causal/id_engine/__init__.py` | `d64b67cc3ef38feb2df07b1fc6937825da7d716de27dd1d568a081d55a5b5bb3` | `proposal-format-only` |
| `policy-engine/src/polisyos/foundry/methods/compiler/__init__.py` | `5e366c0626e5a347d767bf2ff33cea0c7d2150cd3f707d3754995b8df38e7335` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/ir/kernel/time_semantics.py` | `cf9cf02e77ad4ddf877c93092e63256af149305ab6ea6d55bcb9a5c7f295030e` | `proposal-format-only` |
| `policy-engine/src/polisyos/ir/linker/_trinity_linker.py` | `fae506bfe2ec19bad0f2d76f942d1288be400998b2a4f15a471fec4ee44635dd` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/ir/loading/fact_log.py` | `26cd379e23be37ee759245a5b666c2256b75f2357cdb990283ff26118ca153ff` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/ir/model_layer/canon.py` | `4b3a32301664c15a70300ca7f99bc14467602ce38d1bfd300e57503aab57043b` | `hold-import-statement-grouping-change` |
| `policy-engine/src/polisyos/ir/observation/measurement.py` | `0cfed6ac8800b0b5e4a1bb7890b9a7b8275328896ae57b21b16427411a8be9a2` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/ir/registry/registry_fragments.py` | `ce7a13757afabd8859967d1c5fe07adb72d20247f6f2b5e680b8d8becd793a5d` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/ir/world/ids.py` | `9aa361f0f449285b3c6566b47bc3420cebf395beb102553b389fe0b50c968cb2` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/ir/world/quality.py` | `f8ebcd4cf7c2969b87d12176097e18ba09f72c1aea8665d0511003809a926a70` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/runtime/http/services/fabric.py` | `26747f76a132f004cf6a6bb85a211ee43e9c586de202353cfc6d7fea7bcead3c` | `proposal-format-only` |
| `policy-engine/src/polisyos/runtime/quality/scholar_academic_evidence.py` | `7bc48b86d1533f1c84b14ef867bbd933824d2d6f3d5c9dbc0f210f8ebfe190e7` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/agent/_drafter_orchestrator.py` | `761e9885e85a34bdf86ebbb256164c01581ebc05954f680ecc7dc4190c9fd62b` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/agent/constitution.py` | `947117416b930608c03177d330c99dd1e64da5ffb384dc72bf845ad2d798ae3c` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/agent/fabric.py` | `46c6a783fc6a90fb5c6697933d6e1ef5241f88e9c7b88f0f7b0260479b432041` | `proposal-format-only` |
| `policy-engine/src/polisyos/scientist/agent/promotion.py` | `97161d4bc40231245ae83749f476029fbe418e38da4ee27ba042b856fd1aad23` | `proposal-format-only` |
| `policy-engine/src/polisyos/scientist/agent/supervisor.py` | `478d2078da3db4862da4f33f61de7c1951eef71844e43c5f7a47b67bbe77d1cd` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/artifacts/__init__.py` | `3d6ae9dedf3052f46a671c1d20cce0333960d39265d8bbd9c410340f2410200b` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/evidence/source_quality.py` | `d532d33090db43dffad0576ee4bac66e04f84e390159fcb00dfdd9761d1b5054` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/governance/calibration.py` | `9ce1e9316c9e5b9ba35536994ee1350a499cb2d2db31789f3d14c3c71e09128b` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/governance/calibration_leaderboard.py` | `7396df2f45e9b7d9e2a4fb1267dbdc99080493229437b57e34f1178e1643f410` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/governance/calibration_validation.py` | `7665ea0eb7124104260017e1449312dc2102da66dd3a5d22c6849b9c8d9137a0` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/governance/passes/budget_pass.py` | `82a4ec76ad1269cb992ceca52c3c865066969f84c01dc0eddd33fd80a8943ee6` | `proposal-format-only` |
| `policy-engine/src/polisyos/scientist/governance/stress_scenarios.py` | `ad0a9d1ddbeed48741bc0c3ca26eb9aabdf7afa83115f9f16883c54495ec6f92` | `proposal-format-only` |
| `policy-engine/src/polisyos/scientist/methods/search/calibration_report.py` | `9b612dd01c29c8b0575b14644f668314fef0737d1e9b05a7907b4ddf99b75b10` | `proposal-format-only` |
| `policy-engine/src/polisyos/scientist/methods/search/strategies/base.py` | `9dcffa7b1276e18be70c9a3c1d9fc3e618b4f11b9cc8611f96de06a9744bb7e7` | `proposal-format-only` |
| `policy-engine/src/polisyos/scientist/methods/search/strategies/multi_objective.py` | `9473634533dbe9677b2cd3b7e167b56c4f935ed3db80d1a18e89115e0ccc5dcf` | `proposal-format-only` |
| `policy-engine/src/polisyos/scientist/methods/search/voi_calibration.py` | `a32cb0509b701435de1275ff5f9b4c0469dcf5979264f038e672d4916576e30f` | `proposal-format-only` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/compile/compile_foundry.py` | `ecbdd313006df6a75de5b5fb400a12be3ed5001d0a9f14c004be6167c4a04ac4` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/decide/build_verified_policy_report.py` | `b85dd6e73c163dc9bd97330ef43e1489eb46278bc9f6f23163563e93fcc12969` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_state.py` | `ffd1e477fd8396134af2ea9c5196307a0cd09efb6405585967740ba094b85e35` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/decide/run_policy_funnel_level5.py` | `94b4862b8da6da08872023c2ec2d8ac9014b8c9dc8051da37202b0b181d15b2c` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/decide/run_policy_translation.py` | `c2b79cfc2b61a279502f92abf7b406996b555f3acac019ac58b91f8b8012da8f` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/decide/run_translator_compliance.py` | `6412be59439742f0ca8bf8479a7efc9b5e822fe8ae8ec45c9c51bfed9f31de59` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/planning/assemble_legal_candidate_pack.py` | `289415f477696c13884b6f1816ce8286a3c93f2bf660f296c68ccbfd3c9cdab7` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/planning/build_execution_plan.py` | `c53545cf8cb93a1af4a4fa634a11a47adcfb81fe6ff01140042cc7bb8a855c4e` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/planning/draft_policy_options.py` | `d3992af33ec95443157f561ca12f6663075f90738e39c5afadfdaa86b472a1f1` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/planning/expand_legal_source_pack.py` | `9a9718120cf1bd3f97bb98905e31e09ca7d74749d72e57b323dd4c2a28665d23` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/planning/plan_policy_request.py` | `6b62b2bdee3b50602bdf2ce491872441e201c057514116b26dde10a49f4a86ff` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/planning/ready_to_run.py` | `db7c0b65249f006653a716f50398c70795212cec5e8af35e041e176854edab30` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/planning/run_source_gap_review.py` | `026770e2f01ad0689240b93bb3ee2bf2c8e94bc6ea4d75d25fc59b1cae89e586` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/planning/run_source_verification.py` | `6c2434cbf634f9bcb2bea3b985c6bdd571d6d77eac8ca5f3ebf59e95dd277ccf` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/orchestration/engine/fan_out.py` | `7a5229a46dc9aca66ff2ab06a6b7960d22a2a277bb7ea8294c98b537e1474e41` | `proposal-format-only` |
| `policy-engine/src/polisyos/scientist/orchestration/engine/runner/config.py` | `3657ff0f7deeb60fb01351273052f24ba7965db9fbaaea35d100f63c51ced176` | `proposal-format-only` |
| `policy-engine/src/polisyos/scientist/orchestration/engine/sub_workflow.py` | `260a1bf690f36ae64342075bb3af28e96082cf6d5b6e521be2e32b4b4157a334` | `proposal-format-only` |
| `policy-engine/src/polisyos/scientist/orchestration/llm/profiles/builtin_profiles.py` | `e1a8d9f9b16f549b9898820ab9e082c4534eaa734a6df737bf4381e65d614589` | `proposal-format-only` |
| `policy-engine/src/polisyos/scientist/orchestration/memory/applicability.py` | `cff56e7b79cda8abded22ad585ec84d43c9c7e07b1ede566334e08f15976d2d0` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/orchestration/memory/consolidation.py` | `7f3de1030ba29b7a49cd6b043bcc46178b7c835a1624c535ac348d8910fd9f4d` | `hold-import-atom-order-change` |
| `policy-engine/src/polisyos/scientist/orchestration/workflows/__init__.py` | `ba866b6887fe4a9b72cf4a60271f7918c9f07d033d804ecf9ac2ad3a8d20cf27` | `proposal-format-only` |
| `policy-engine/tests/_helpers/c7_synthetic_data.py` | `22ba84f8db13df430a28e31717680c3145f1e5036d7286b1c55a311db92d6a3a` | `hold-import-atom-order-change` |
| `policy-engine/tests/_helpers/hds_quality.py` | `389e71836146218e2b09a9d1eca0aee524baa1011586d2c442db221bc932a01b` | `hold-import-atom-order-change` |
| `policy-engine/tests/_helpers/scientist_runtime.py` | `f506c8b714388dceca16a275d3e84c5ae7923e6ca712d6738835de25981265cd` | `hold-import-atom-order-change` |
| `policy-engine/tests/contract/test_c0_foundry_scientist_compat.py` | `fdef8f0e6054dbd151fc2ef6e8a7950e1210d2a229b9088f2c9bc611d4d4604b` | `hold-import-atom-order-change` |
| `policy-engine/tests/contract/test_golden_record_ids.py` | `913e708488cf02aef7872743523fd9df99047f928d395bdd10150aa895e2a0f0` | `hold-import-atom-order-change` |
| `policy-engine/tests/contract/test_ir_migrations.py` | `de230e4529bc9c09e2a5a9fbad848b75be74f99e9b263c8e8d7de0a5e5f60405` | `hold-import-atom-order-change` |
| `policy-engine/tests/contract/test_run_experiment_slo.py` | `5bfc15165d9c20a52a3149aedd49bc1a4bec41cf2225f3b204593a028b1e2abd` | `hold-import-atom-order-change` |
| `policy-engine/tests/contract/test_trinity_contracts.py` | `443a680f8aa069989e6d143cd6c098d20e1bb54b22a0cb609d6a0a2fb3fc55c5` | `hold-import-atom-order-change` |
| `policy-engine/tests/contract/test_trinity_linker_contract.py` | `35b1f643d90a2f4657d3951e59ae52b65dcdf2ff1695f7cd46ac51fa0db4e7eb` | `hold-import-atom-order-change` |
| `policy-engine/tests/contract/test_world_abi_contract.py` | `1772422b2426189a68a80d76969a7ba0b14166489acab4b7dba0aa3f0b1f3b47` | `hold-import-atom-order-change` |
| `policy-engine/tests/integration/data_forge_runtime/test_catalog_to_runtime_bridge.py` | `43abe2ac2c2eedbe1232f11ba00fde79b4783e964345c59c1c18a03f5fa362d7` | `hold-import-atom-order-change` |
| `policy-engine/tests/integration/lex_ir_foundry/test_normpack_factlog_method_bridge.py` | `cdaa79d61a5d8907a2cc7181b729eae619540f2c63d21367f0e0e5e202565049` | `proposal-format-only` |
| `policy-engine/tests/integration/scientist/test_checkpoint_resume.py` | `da8ce0745c462c7be03f1597df198f6e287ea5bb94fdbc6e2590d423328a35c7` | `proposal-format-only` |
| `policy-engine/tests/integration/scientist/test_workflow_tracing.py` | `2e305f2216ceae1c63eadf7aaed0c224ca878f50d7bc8ef23936245afe5fe296` | `hold-import-atom-order-change` |
| `policy-engine/tests/integration/test_phase0_quality_validation.py` | `cf80b9689766809eace6a0f7a836c15aa8f99348608e588fcc0352eb92191fb2` | `proposal-format-only` |
| `policy-engine/tests/performance/test_benchmark_runtime_pipeline.py` | `5439493eefcae7afb4a17d17408fc53248af806db6a135aab2af7aae687e2424` | `hold-import-atom-order-change` |
| `policy-engine/tests/performance/test_scientist_runtime_paths.py` | `b7658c6cece8b69e65de84ae123eeacea638f101a90fbc21f5995e4dab63c3ea` | `hold-import-atom-order-change` |
| `policy-engine/tests/property/common/test_serialization_properties.py` | `b9e88172a5d36accd98d304d987e488596cf353c09054072575e7c77c3edeba7` | `proposal-format-only` |
| `policy-engine/tests/property/foundry/data_plane/test_bindings_properties.py` | `e3c610e04174d6b9fd00d1a88e91529c6278e015f6fa2960644060b8a341fd7d` | `proposal-format-only` |
| `policy-engine/tests/property/foundry/methods/catalog/bayesian/test_bayesian_properties.py` | `8878976705196aec256d9de368850c37ff678f7878c69f91542bccaeb4576bb0` | `proposal-format-only` |
| `policy-engine/tests/property/foundry/methods/catalog/causal/test_did_properties.py` | `94af73881e6129e954c1ad50d9041c68e3d87f123984e5595ba782db2aab4fe6` | `proposal-format-only` |
| `policy-engine/tests/property/foundry/methods/catalog/econometrics/test_iv_properties.py` | `790497afe1a1f3c5b1475e982418c757123a0b75ddd55b56f69db4839ca617bd` | `proposal-format-only` |
| `policy-engine/tests/property/foundry/methods/catalog/optimization/test_lp_properties.py` | `2bf88be610a4a12f39eba7b48f9fd3d62c59f56b9063fb2d26e12709ac4c664b` | `proposal-format-only` |
| `policy-engine/tests/property/foundry/test_constraints_properties.py` | `5689529e96c6fb360ff3701041097c35ea05bbebc57e49b8cd98ace9653ce03e` | `proposal-format-only` |
| `policy-engine/tests/property/foundry/test_slot_schema_properties.py` | `ccdb42eb0dbbc9d5a9cd82aa05696df4a427fb729a8ca917be76b9928d125131` | `proposal-format-only` |
| `policy-engine/tests/property/ir/test_phase3_properties.py` | `e7c37778775740faab5bb7a194f2290948e9125830eb05d56c59b39ed6e8863a` | `hold-import-atom-order-change` |
| `policy-engine/tests/property/runtime/http/test_access_invariants_properties.py` | `71a48898a46f2b37046afa8db67c31b0e73f7c1882e8da0e175c3658a9b6ba6d` | `proposal-format-only` |
| `policy-engine/tests/property/scientist/engine/test_property_budget.py` | `d0a72ed292e5bebbc1d8d8cae7c030f6949b5420328685019775deb6b91210d3` | `proposal-format-only` |
| `policy-engine/tests/property/scientist/engine/test_property_checkpoint.py` | `0f25475b27561ccf9aaab4fd289595537a0495b89898a3f3e710ca8914050062` | `proposal-format-only` |
| `policy-engine/tests/property/scientist/engine/test_property_condition.py` | `5773151b7dd794ebafadb9b549e986fd9f94b5f82f07b624a1534fa2bdf92ce6` | `proposal-format-only` |
| `policy-engine/tests/property/scientist/engine/test_property_idempotency.py` | `628cfe6bb9a3ec81ef1dc4c7a92f97e0c845d425c9b7c5e27517b7ed9e9d17cd` | `proposal-format-only` |
| `policy-engine/tests/property/scientist/engine/test_property_state.py` | `8948fd3886af9e52f6dfb9949ecdf63bce8e7bc7c3fd39f4695a4055358efb3f` | `proposal-format-only` |
| `policy-engine/tests/repo_quality/architecture/test_components_id_semver.py` | `df09ee2e0594b7abe5018c7c3ed05a2e0794ce10471305312eb194cf866897a1` | `proposal-format-only` |
| `policy-engine/tests/repo_quality/architecture/test_repository_best_in_class_phase4_3_god_module_budgets.py` | `2d91117c9bdaea5e41406c64f3fe33986db72bca26c2a3ba9b1e6b4cbfd7880f` | `proposal-format-only` |
| `policy-engine/tests/repo_quality/tools/test_expert_adjudication_labels.py` | `7f3076b31558d88b0dcabe268f43a33cf498fb4e1fc5b5b334cecaafe76cb828` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/berl/test_metrics.py` | `5d762f06f40397ce041d159a2f08958688cac4650610ffa88b62142244854ea6` | `proposal-format-only` |
| `policy-engine/tests/unit/calibration/test_diagnostics.py` | `f53af4f42abdbda38a221ddb0ee1fae078cfc15e912db9017dbd97d2c8e345d8` | `proposal-format-only` |
| `policy-engine/tests/unit/calibration/test_multiclass.py` | `a23008fe5f7c34f3d02a0f554077e59a1d12021e22b8238f30eab1a797cb1164` | `proposal-format-only` |
| `policy-engine/tests/unit/calibration/test_recalibration.py` | `d126609ca97ef19bf7933212a233595d2a0f6f33595a1fd45364076895080bc5` | `proposal-format-only` |
| `policy-engine/tests/unit/common/test_timestamps.py` | `d25f93d82e136dc933c53d53b70678cd1637304aa8cebeee23a993f895d5f13f` | `proposal-format-only` |
| `policy-engine/tests/unit/core/artifacts/test_async_store.py` | `dda8d14da68846e8c2df061c18ee678d6efe0154959370b97e5473b7a037a2f4` | `proposal-format-only` |
| `policy-engine/tests/unit/core/audit/test_safe_tar.py` | `7a14e48d084ae8e67d3686ed6dcacbaa53726bf64431da48cf8f0c97f24ad6ac` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/core/contracts/test_bounded_liveness.py` | `0b26438ad8d0e00c20e53e9ffbf9db5907a504baa03c95e84a8a225643167f45` | `proposal-format-only` |
| `policy-engine/tests/unit/core/contracts/test_execution_plan_contracts.py` | `23d614ddbed2fd5f5a361c7531b2a25bcfd8d141f8dd9c1466a1ea22e4ea31c4` | `proposal-format-only` |
| `policy-engine/tests/unit/core/phase0/test_canon_json.py` | `19dd0144c4ff594513cbe0aa45f3eeef03065a3c4f97970ee3b8b818a3e6fad8` | `proposal-format-only` |
| `policy-engine/tests/unit/core/phase0/test_decorators.py` | `d633cb5896bd84fc3bfdc9a620e2d5946cb14e78307009534b98b0001ca8a008` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/core/phase0/test_environment_manifest.py` | `ecb42584e3d65a16035ef80545e154b183225f6b9c60195619ed5a807def7588` | `proposal-format-only` |
| `policy-engine/tests/unit/core/phase0/test_run_context.py` | `ba2e51668cccb71a0156ff912ff10d554f7383cc8dd72d6062f6183240a6d065` | `proposal-format-only` |
| `policy-engine/tests/unit/core/phase0/test_tracer.py` | `74bb2650bb6bb65b3b5db3927d84f7686efa372a16830b29de91149541310611` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/core/security/test_cell.py` | `2b62a60d14d5504ac75abf6117543afdf9a0d12e1ff7c7486435eed2e61750f6` | `proposal-format-only` |
| `policy-engine/tests/unit/core/security/test_fulcio.py` | `b19412e05d0751749f053b104cc80521992c1cca565906a28f632a783ce910ce` | `proposal-format-only` |
| `policy-engine/tests/unit/core/security/test_identity.py` | `d907a0ba7aad222ef10d81c5baa4100be9d6ad6a1100f4a28ecd105e3ea1da9a` | `proposal-format-only` |
| `policy-engine/tests/unit/core/security/test_registry.py` | `c7b09732c21c289a38e63c7cd68bda77ff7ff6f4ba2adbd898a8f61f90deb2da` | `proposal-format-only` |
| `policy-engine/tests/unit/core/security/test_tee.py` | `e35583cc44472645f936b6f41c61a40b0e547c991fcbe91b2a61e9c6b4cc8bed` | `proposal-format-only` |
| `policy-engine/tests/unit/core/security/test_tee_middleware.py` | `af09e052f8780f3eaea9d21d30d49366509044cd524a90135d649fcf9010449a` | `proposal-format-only` |
| `policy-engine/tests/unit/core/test_backend_dispatcher.py` | `4f8b6a771f542729f239c01330f5a3e177e384fd26dffcf5c95598a2b5de31f4` | `proposal-format-only` |
| `policy-engine/tests/unit/core/test_error_base.py` | `6033a5f2c6ad3e080abe1b7283cdd0f013ae1b919b9cfad2c4dcd3a7b682da69` | `proposal-format-only` |
| `policy-engine/tests/unit/core/test_hashing.py` | `706ba4db2cb2767eccf98b60957e5f044ad260c60aff3a5fda6e5786a618ac0b` | `proposal-format-only` |
| `policy-engine/tests/unit/core/test_llm_core.py` | `5de4046006fb35942a30eb161d7e403d6eceee7067c22deae8bbec1972c5da5d` | `proposal-format-only` |
| `policy-engine/tests/unit/core/test_pipeline.py` | `8c2d44278b73cbefc9d8577e4bd4918a0961d068664ad240020c23c79841634c` | `proposal-format-only` |
| `policy-engine/tests/unit/core/test_registry_base.py` | `40c8e88e6d3ebcadc3816a3948ca14ebd275a789705d8854f50bc62e3be4314d` | `proposal-format-only` |
| `policy-engine/tests/unit/core/test_registry_generic.py` | `224c90f6c955c6a2e18c1743c7792b0de46861694018a4bbad076c3ca4633ed7` | `proposal-format-only` |
| `policy-engine/tests/unit/core/test_scoring_framework.py` | `6f4095481b39abf8bd66fce9c952b2376f55dd2bc516fb2bb10de66fa757a92f` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/academic/batch/test_graph_builder.py` | `72b4865f3c27a0db6da2dd230231d0639893be7eced08e329af9144e610a291c` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/academic/batch/test_qc.py` | `a6676a20782dd760b349df60151ae7d1a1d2e4785ef2c29a5ea7aceb6359b06a` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/academic/batch/test_run2_pipeline_upgrades.py` | `cf0f35f25ff0caf9e39d31518798b3435af4d61130bb39032902672376e5041b` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/academic/batch/test_skg_versioning.py` | `968fa5bc05639aa265b0540501c9f20fd1097c05debabbad3f4cdef8bd937614` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/academic/batch/test_transport_score.py` | `0562e4f2c511d83817e39fd30b72d8c9a59a1e79bc20bc78d4e364908a0a966c` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/academic/knowledge/test_canonical_resolver.py` | `f57a0cda792219339da466a3983e9a631f141a354539403e42ffa40157d1e89e` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/academic/knowledge/test_parameter_selector.py` | `8279fe17895007b0b8488ca5cd8825615f3fb305f0b80cf7c9ec99afc7d0b733` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/academic/knowledge/test_types.py` | `4e0af24d4d4a5caf390335020231b34243a12cc11c3c3c184b650259d8bd50b5` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/catalog/batch/test_ckan_curation.py` | `bc8cf4673ecaddaf718d9de76eadb054d68f042742ab7f02b651f9ebbaed0566` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/catalog/batch/test_core_sources_ingest.py` | `718b6a25e9a0b0439286c9bd37b043db5fac6b404f82a0d358ac4121f9ed3e4e` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/data_forge/domains/catalog/batch/test_graph_builder.py` | `130436138f2e1215b44407a4331c5b5ac2f64fa4326addce3eef82aadc302324` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/catalog/batch/test_qc.py` | `ecad4ec40f838da9a91df867975c1966658ad71e58971e00eacb41ed64cc9ad8` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/catalog/knowledge/test_proxy_resolver.py` | `5a029a8d08fee2c6f5a0908d4d0afdef4cce5da062707e8f84a7003d8d547570` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/catalog/knowledge/test_registry.py` | `a90eb5b9c7e6642932a5007bfddc6b3bfdcfb554ac874486a77b7410f3861988` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/catalog/knowledge/test_types.py` | `b179c97d70f36a778c2be88cf890120e5b67918639e3b7c854f800fb95dcd568` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/ukraine/test_adapters.py` | `60f0be42b41f2e17bd6d7fd96f4c939fbf1eac9c7c6e81a2d646f3c42b60cce3` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/domains/ukraine/test_demography_artifacts.py` | `5de202cf2d990e3d4b36cfff384da79ec80a95258e1ddac5f69cfd1302f9682f` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/legal_batch/test_claim_bridge.py` | `64b3d342908149aad560080a5104776e4f73c4217dcf026c730499dcbef96888` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/legal_batch/test_entity_resolver.py` | `fe531e6f7ddf8ba5c1c67efbfde405aaf0349be8d0554184cd3944734c4cb718` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/legal_batch/test_graph_builder_partitions.py` | `acfa1b8f2b7f2c603ec30b79cd84546401a17c5bdb2cf6c5e6bc4a8072472ba6` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/legal_batch/test_pipeline_llm_gate_integration.py` | `baa9be6450bd8e1ed3f3facb4c4e124db7639e12aaa13bbe6e28c161c4cd73d9` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/legal_batch/test_pipeline_reasoning_filters.py` | `eb58c70e47a21d677688f8418a6817368c20806f81ae9152dc64466084b2a050` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/legal_batch/test_publish_bundle.py` | `906b0e9414aaeaf82988e6139fd718d0b89df2b6b1aa5646d9f2a2d26363e2da` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/legal_batch/test_qc_benchmark.py` | `efd4be9642e642023f236f26720585b0e78058fb4b877f1a6208c41740410531` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/legal_batch/test_sharding_config.py` | `7833061550790c3e9922c5d9dcf80ef7107939ddf3eb7ebf4ba5229e340f1b06` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/legal_batch/test_spo_extractor_normalization.py` | `41d85463c06447024733c066334247d6721429171007fafcd0fb7a60e71264f2` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/test_phase0a_foundation.py` | `87a9522a36ae947edb966d17cbd04e7d6a2c562a69afdd49c201ba56c99e433c` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/test_phase1_shadow_shared_kernel.py` | `2c97b24cbf170f86d9867a70acabc98adb719b96ac27dfb69a1c179e3c58f718` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/test_phase1_shared_kernel_cutover.py` | `2fb7209bdeea7d2a8409646eb6464c123cd176e82c9ee0c302b64c379238571a` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/data_forge/test_phase4_legal_cutover.py` | `568cb02db44159907e78c6e0958fcd7b3ec2063f398a8aeafb90c7d8faf6d3c8` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/test_phase5_ukraine_scaffolding.py` | `076504b1bea31b9caaff93320e5a98d142903913cce8fcd8acebf2f9aa7bd9bd` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/test_phase7_schema_quality_observability.py` | `61fbee6e92c0e6c545c0444ce7606efc5c62569709c7b591462c8bd528c6f264` | `proposal-format-only` |
| `policy-engine/tests/unit/data_forge/test_repository_sota_phase1_foundation.py` | `ad3eaaafed126b85b14c882b1d6f613fb0bd09aee07e59fca0064c3e981d617e` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/data_forge/test_w9c_provenance_manifest.py` | `7cc78ca446b450476e902b71ac84512606fb98b26f513a8240e51ba4415e2d24` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ddm/test_delayed_label_replay.py` | `c91422f563f9b51384e7dfd51645e4b78a2adfe95ee5a4bd58dfbe364ef3440d` | `proposal-format-only` |
| `policy-engine/tests/unit/ddm/test_full_acceptance.py` | `d32d1847c1686c04ed7a8add6ecbad6dd50d506278a8bf00cb546922680267ba` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ddm/test_synthetic_drift_delay.py` | `46886033be8660904762d359e80b7e66dbf283d61f10ce314a6a02d2e83b04e3` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/bindings/test_binding_profiles.py` | `420ed25820d973abb91f870ef0f0033b0a69c84f0f762dcf566392b7bac665d2` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/conftest.py` | `16f8fa44c54469d37ccadb79f0aacc4a2e1f82e42117eb4184e96100652fec9a` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/profiles/test_source_profiles.py` | `c40d0a01595aecd33346d5ada845ec58d16d903cc566d5a18ca224cf07d6213f` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/fabric/connectors/reference/test_sdmx.py` | `e541bd06b3c377c7914c3bde1a6d9d90bd2fb13248cafd4819b89393fc935f6d` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/reference/test_static_csv.py` | `4387e4ff5c6f163ff47301ced10203fdca2209f73d8c798c693a2d2de2f24895` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/sources/test_ckan.py` | `600bd2f4136f471c801a3074f8b7f0bf64075dcf0086b34d1f47dfaddd038ee5` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/sources/test_connector_family_expansion.py` | `3655635101001e89493e1a6bd2bae2c89410475dacee059a2a1e9fa080564bca` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/sources/test_opendatasoft.py` | `0febaa23911f0d282adb8b5e82d640538991f533a77bc5a678270644176a7363` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/sources/test_production_connectors.py` | `d2cbf42d646197cf88b728028897451ae90222d7da7748653385813c80912eaf` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/sources/test_socrata.py` | `dbf6a04384ab647aa7a0d1e84465940562fb6a253f4139da0621dc8a4fbc975e` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/sources/test_sparql.py` | `057af1d7bd0b24dc0668b4061f09da19bbeed1b7e460737549246847a2173d8a` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/sources/test_wave1_integration.py` | `0ee7131d69101428d9a88675a1b98176ef8deda84b8af4c8839304553f19879f` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/sources/test_wave2_integration.py` | `72349f909fb3702eae4fad0b423b5beca8397c48f45c0d7acc7092acf02092cc` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/sources/test_wave3_integration.py` | `8b272c2c072c8dacbad39dce0017cfacae00d0605b6ccaa9782009618937a5cf` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/test_cache_system.py` | `a7d1c9fc438f33bc67eb6e9caa2b2bb7a2953c7e1bd929cbb8140c04f10e7e14` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/test_components_bridge.py` | `05c903f2f88b3c9165b21af3a0e79b74620372fb57d6bef00a8649f040247b23` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/test_contract_system.py` | `30ec86e5d3691f337307f6cc3c88a7da834b526b986c046295732dd0db7fafd7` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/test_harness.py` | `0859e6ce7341c0e66bdf46df3b5d45210b7302f4622993bfc3583b4aa5648390` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/test_integration.py` | `db10a0024e515f6d193878e0e861bc4548d32f009356cb3c2dbbf0d9db0f9c17` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/test_quality_statistics.py` | `7deb687b2e49842ef765a61ebcf939bf60cc119f40de6971054d86d54ac4ce9b` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/test_quality_system.py` | `770318624934cbb4ae025c7bcc41db1346534cc1cb0c5b93ad18e5985bc7feb3` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/test_schema_aware_cache.py` | `9b13b27699c261abf7973b582b964bd77b951a8f70a510c6fb33e8aa20b123d1` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/test_type_system.py` | `19e1688dc8481f7d4878817e8d50d51ebda496b8dfec54d85526d241fb74444c` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/connectors/transform/test_filter.py` | `dfda6d4101d0ccff438b43dc6595fd0daa484e93967023fef7437a18c65d47e0` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/data_plane/test_benchmarks.py` | `cd80a2e65215db22befb5916d28f0eab81e8912d2077db354795a25bac5b9b73` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/data_plane/test_cursor_store.py` | `998929cbaabc30e2d9960a1b628c426eb0a45d234b32a2d06e4dd11fdade9d27` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/fabric/data_plane/test_record_replay.py` | `ca1792b7b93c35869b5513f207990c8a003c57f8c4c71cd965f1b8aa2127c08a` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/pii/test_presidio_detector.py` | `d2b770643dba90057477274b63cbfde6052ce4faac11030e1c48e49fc7485dcb` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/test_access_control.py` | `b6a796bbd30473ae9d83a720042d525d0265ae48073b33a2d0d0bee037dcbfdf` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/test_concurrency_bounded_runtime_phase2.py` | `44ab7e31733758219627e35d32facd9fb7bb7ee3e8cac30aa995334a6e42421f` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/test_data_catalog.py` | `a4dfba6b94ff23989a0a5582e64d629d6330d773171a0777707c2fcccf4cc48c` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/test_decision_data_envelope.py` | `751ec479cfed67037c5a38275f7631e0e5e004c1145a9a3ac089a99d0fa8cd20` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/fabric/test_entity_resolution.py` | `5959bb0d5a542c398fd0b646ffecaf87ec828b017915773036ac829b73af243e` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/test_ingestion_quarantine.py` | `b41162385105bb00c64e3c843816624f4227511e4805703507f51fce28f9ee70` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/test_ingestion_security.py` | `578cbf7d977b07c860e05386a1c7ff4c36aa4ea04d63ade8a31842360d8e7633` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/test_legal_evaluation.py` | `68ecdd24fb2b07d6de39e0a5a9be664550d0ac3fbd1aac7114a29642c5af12de` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/fabric/test_provenance.py` | `332f8aede1b00a7b31a9a6d59abd215c1094da93124862c7e11ba4799c36cb40` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/test_quality_indicators.py` | `6602f58b4d87a6b74b040e883c0d1c56d649827cd79e4f73b5297ff30a8359cf` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/fabric/test_safety.py` | `ec50b0dbaa8db5943080411d6aa2938ca85cbd4027730f3cb381e226b6e5cedb` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/test_security_integrity_phase1.py` | `a4d32ff7e6bed2b28cecea7e01c86e10e932737a79d4a839e5a6fc669d1cdcdf` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/test_storage_port.py` | `5a7d7edc4904a2492ea88d03a86bfc22024118f7bf6f75c55f3b89e3ce7d0778` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/test_world_branch_governance.py` | `8ececec2f825ebcf3b7b748588e941628fba05d7f912a9496008f025a62861b4` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/test_world_kuzu.py` | `12426f2002458a2d2d26c6148ca19ba63511e164a1dfa0b029589a7e287d0c68` | `proposal-format-only` |
| `policy-engine/tests/unit/fabric/test_world_materialization.py` | `519e626f4f9366e5d5d84281f79d2f253435b28b6b0fb522f8656cc2f4fa32c1` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/agent_sim/test_actor_critic_numerics.py` | `f324c6bb588091b4b25d8f1fce1dc037c5ab3d89fd670fd41a950e792bd5a8fb` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_adaptive_agents.py` | `60ab0003ca7d1a3930ecd938b4a6f132ad99da904293337f136cac6f82e81761` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_agent_artifact.py` | `a95517d6ad45fa59c1e6aa11bdbfb806119c3df32fe7652d95813961fddaea3b` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_agent_simulation_step1.py` | `32b2d15739c42e8e2df77cca996b28f8688dbc8dff81b5bc9551b15c72369ad4` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_agent_simulation_step2.py` | `29c44d3c01e0f8aa5a7af07557fb87e472db1694408381562c0918270f203f95` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_agent_simulation_step3.py` | `ede06b13dfee0bd47ef7991359453842e2372c58cb130f55488c5ed58290f522` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_agent_simulation_step4.py` | `95fee820d4d3beba88cebdeb0974a3455ec7aa668c9cb5190bb1870afbc2306f` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_agent_simulation_step5.py` | `9b9936d9d6fe6d4fbc5289be16cedd62da7664af968729bb3247fc2e431c3ef2` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_agent_simulation_step6.py` | `a6f53efab2bc951f230a784847d0dc61c72ecd4ef8be908637f6f66408f2dcea` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_distributions.py` | `d28cf56c395dfc4271fde4b25b4d3445fa9815ea4b8c3ae864ac182e78305c8a` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_executor.py` | `d9e22404ac98ec685f82a1ad71860ca7b9ce9c2beb64b391effa5d017e9bfd2b` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_graph_mechanisms.py` | `3b3c7144e59c728bda67b9db0f5401b2364af513ec51d1855c1e1fb3d35bd39d` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_jit_compatibility.py` | `90312fcafa7b59147922780c696640f64beac1ac32fda6bdfe61065900f2cc58` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_jit_training.py` | `003a038ee4971f650d3b9477b4a31c07dda00b54af273bb72040c39df2a119a2` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_mechanisms.py` | `b5660b4ded2ef154cd0ec8347d27d69e3749dfbc37e604f119783b1abe2ccaf2` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_monitoring.py` | `4f774f0073f9cee05479051357ca3a2cfa20703c51cc499226e53f2fcae566ae` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_population.py` | `27f8755255f7f3eb7459fbaa31641cebe208d9fdc89eb2205212b7515193ea2f` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/agent_sim/test_training.py` | `528ce93f40d223d41c5012216785fd731ad10793362e117bf98e4a462a33fcc3` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/analysis/test_attractors.py` | `0c6b8c135e7de761590773604f3c90f6f6fe102af7d7350aea0371c6f11f6cd0` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/analysis/test_feedback_fixed_point.py` | `a91661a6931fb4cb3d06b453878b49c25fb3ba8d3c94c08ac8c58187416eab30` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/analysis/test_health.py` | `7d30882511aec6b843a6d60e30ff7baa5cf58e8dac966e42d043c0757a2cbb9f` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/analysis/test_loss_numeric.py` | `01201c97ad33b594d97149502a8936a07d6f3a3982cc0baebe2b8c3c4c713aa2` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/analysis/test_merge_determinism.py` | `7e86d10a8e9b54091597002f9fa76d3b1143252e0f11ff3bec36771a6b841de5` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/analysis/test_merge_engine_regressions.py` | `6a550992822718ace6b56df6fbbcdeed5d9a141a1b1942fe7aaa014722ed7955` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/calibration/test_auxiliary.py` | `0dab1cd1d5b99c196691d5aa6b97defa9b0e629f96d996cb41189e4e52b66005` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/calibration/test_bijectors.py` | `1b82eeb5c90483460ba4c042ea5157e9360b192d0402f2cb3d6973fcd2cda911` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/calibration/test_calibration_robust_set_selector.py` | `af88ef3d4bba84fbc86f83da03c866b107bf621dd7c0a8e2a52ec8856f87435e` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/calibration/test_calibrator_fidelity.py` | `442a84fe3b13e9fe89b93385651fd13bc5448fabff843ce6cae270721cc79946` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/calibration/test_calibrator_mvp.py` | `093fd2b9d00f9964fc1925ef42a912b4a940359576f1b3d316f89f8733587e07` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/calibration/test_hessian.py` | `abe2105006c9a635dfeebbbb5cbd51d9540c9c7f0f11af6908a42b6f7bfb476b` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/calibration/test_loss.py` | `629995047727029a1ce5f01f2d1accde55b66a796bbddc95f6a77f7d60684ac8` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/calibration/test_multi_start.py` | `39070fd2af17b37a5788624a34f31d7dfbcd0b31a49be771749cc19ca52797d2` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/calibration/test_preflight.py` | `dd8dc09594e64abec9401d9cd46fdb29e2af3c162b991dcecfbcba4c5766456c` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/calibration/test_pure_executor.py` | `c4877190d7fb2b2c247326ae6556139ab21815206c52e55c6e5b821a42139607` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/compile/test_compile_determinism.py` | `32dec898676dcd2f9dffedb0fc1c9d4b9a8c6c4fa0bb47f61a90d5522ab961f0` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/compile/test_lowering.py` | `217fdc971db6a3b8d01c1b8d64e2947e8641631ad6ab29c01549a9189cd1c820` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/compile/test_program_graph_ops.py` | `1ab42419cf653635f758c505213f1136b6bd482621f9713d1fafaa7550ad86c0` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/conftest.py` | `53c808c34be3ea5d31db2c8e5172c0c75235a0ea1f11846416dacc2501b5ec40` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/contracts/test_fidelity.py` | `80a916d79e7ecae8b76e58ca7f727fbd20b93f8e83f5a2910a82e4a2b2d53d04` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/contracts/test_global_state.py` | `18dbb33373a3747df95afd06f71de1c837e5dd9ec06de016f9b7d89efd53d521` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/coupling/test_adaptive_observations.py` | `0fdd594bfb02b5364272739ca3674023c5f4b99ca345e13bef4598a849606642` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/coupling/test_des_kernel.py` | `bcaa49e2f9b0daaf4b1be2fb43ad68c5b523e2acead8a2468605f79c67c972e2` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/coupling/test_executor.py` | `c615f09cf23989c1687f4790b854d3c74d1f50236bfd7981474f7db3abfd663f` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/coupling/test_queue_runtime_contract.py` | `ce3136dfaf324ccdf8bfd5c192e25c7c7eceeb9c9dc4c2f775b2322b0a6fc591` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/data_plane/test_bindings.py` | `40ef65321c54311c6df8c0cb768a56287d8742ca29d90012bbe17860dc36169f` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/facade/test_compile_facade.py` | `8f9100b9bd92e333267be429d9e54e7f924d50324be5ca3d74c739e64acca57b` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/facade/test_execute_facade_smoke.py` | `0df7f6a9199980a1818d69f61f1302dd8ee917d12b15d21d725fa976be1b233d` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/facade/test_public_modules.py` | `611ceee33d2d5a7c41bbc5a4ef86dfc9ae3c0a500e64405415831c35efafb30c` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/hygiene/test_mypy_plugin.py` | `9173a182522778b5ed2b245bb80faa35209f7f96214d4ccef30422e46eeb343f` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/mechanisms/test_fiscal.py` | `59a54f8c242c819e782ec6395e7c026cd5c6cc98d8467af3414e7edf0ea9bff5` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/mechanisms/test_gradients.py` | `67e3d962ce047596998c6b8216f20939bec8d3027cfd567bb3c3f7f7fd42028f` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/mechanisms/test_labor.py` | `c7f1eec2a7ecd81839aaec5c7cec874cd952801351a23192a62cb0eb99095796` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/mechanisms/test_welfare_bound_sidecar.py` | `660f9d814071da8f5f2cb1af132b58750f0808e53d2924a8eec966bfcf9d32c9` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/method_regression/conftest.py` | `1f94c934dc91730e646c9d6aff7f6a8c183bbe5cfcf0c960c039a1b3b7187e28` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/method_regression/test_golden_regression.py` | `4406a1321c05b580c99791ab7e29264231330c9e2b291b28267d11984ad3e61a` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/backends/test_backends.py` | `225be875ed66356acc53779e69fa28858ee3ce7b3a906cf2495d63ccedac2981` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/backends/test_chaos.py` | `26168741b615796ea752c419796621d6ad3c978b162cacf22aba6607b6ba4709` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/backends/test_checkpointing.py` | `cfcad95a33db7fab57c561537a0d74a76ebbbd6f1c0901f63b3a522fc9bf08e6` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/backends/test_numerical_stability.py` | `2e7fa711efa34c924f335d429ad16de704f0fc6dff8442c0b92332fbe254ecea` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/backends/test_validated_dispatch.py` | `24999fe8829b9233916669f503f46f690ab1ff83f9d4b1fc67bda07eff5699e4` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/bayesian/test_pmd_hmc.py` | `58de14402880b133386bda7caaaa7bbf251b6a1138035e0c25e32752b16199f5` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/bayesian/test_prior_sensitivity.py` | `0f77e1b433fe708166ef906d477b8efa2634c6296654380d293d09be00625b46` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_actual_causality.py` | `60bae0eb36d896acf9331166acd7ec36e887b3573ed00175a1c258c30623e64d` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_algebraic_calibration.py` | `d518dd48414494951397568550c676ac5d896fe38ea15b5669a328ea746cdf60` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_bounds_engine.py` | `8f545c45372e3d8a2739f427a210968d019897f73fd3f39b8c7733f85d9498ef` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_causal_bcf.py` | `209a8292db3e70ea074cb29b3c1a1db51172c15c331ae80da5e28997e6d14cd8` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_causal_engine_g.py` | `99f10d2daf4e8e475a9c6a25dda8e87dd6267b603194358e96379c1f2eee9af7` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_causal_engine_phase10.py` | `a662ef7e552e7f72f500fece3c56ecd83aa5a03f88593bd17552bb2380c99bf5` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_causal_fairness.py` | `4b78a9a6d244a3c95f86eb839aa9e252403b2b27a18f4228fb74886edb056b10` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_causal_fairness_sfm.py` | `53cd0a933c4efa9245b9554023077b38cda38022c6c97e3836514dfe2c3379fd` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_causal_rl.py` | `cdd0553e6cdefa348d45daee8f7d756897b46caa3eaed74f774196b1706efb60` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_ci_backends_jax.py` | `3ccd2bbf8dd362762343e32cab24e61637f74808be2207b606ab1e9f66cd0df8` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_continuous_treatment.py` | `fa4d8c6464bc828a564a796c153ed34ec44962d0bf778feab2f9296780d4b1de` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_cyclic_id.py` | `b419218bfbe9e3acd73845963d4401a623f7e42651b29812b1aefc308cc26949` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_dagma_discovery.py` | `9c8b326059e21f49bb86d31f388151daaac45299ee99389a4321112f8ea373f4` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_density_ratio_distributional_ot.py` | `99d48ecef033d67f3b6d7b6d1554871da2914a7459d6f3c01d57aa1dfaa4c2b5` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_diagnostics.py` | `4d8ea67af9548eb6b1c58d41754a06f6b5a86e25c1e3b4e1fad189688bde649d` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_did.py` | `203e4eecc8898912c72fb61e149cc33d90a5a246daf962303209e347a790ed77` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_distributional_bounds.py` | `f545753dc468f73d4d86a7b9ff2f821b4b9ce1522b7ab3a4a80c80c7c8289719` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_dowhy_refute.py` | `0dbe5676bd4af0a991c765ff5455f6f2eb1613dbe891a10230022423ba54c825` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_dtr.py` | `37c36319732e0192c38e3c538fcb5a8d68e3d37464fcbf9432915f34c07b357a` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_dynamic_registration.py` | `18c4f4b6c564b6fc7abe8b01e755b1b04c8f22fcc3a99bed50d775becdb5f089` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_econml_adapter.py` | `c69aa8fe9b45797bc7f902a034c8e2c4c1b44168a441e2348be1e03f788b4488` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_endogenous_group_inequality.py` | `f68f42c7b7bc704da25cc8c616754b18a3b1b2a567a3833814557be67062f317` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_estimand_compiler_kb.py` | `ae0574fdde9918eb49b907d9d572cdf4afebbcf57db94fc14450257132d61598` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_estimand_compiler_track_c.py` | `ebc1b237c0fe8f5e1043b81ee63c1fe06a39d4ac18e6d1fb39a1ec7ca4fa14e4` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_forest_dr.py` | `facf9da69da0a629bbf899610de27f80b6268d0714a35089a3a926a9af10d128` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_frontier_methods.py` | `14fa81b3699d6924d1f767d8ec0af6b4d73b32048011d879959168d13f57f1a2` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_g_computation.py` | `c20c1d34879c1d59e3c8b236b79455cbcc150c94a9211b0baddde3a9f4901814` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_g_estimation.py` | `c4d7cf0f493242a14a827572b47bc0df16a44c2714ce4973027d75bfe3d09cae` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_gcm_fit.py` | `545a1ea96087f8564ad9956d4ba2b7bca1667543dd4249af6b54f37b9a6f0520` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_gcm_query.py` | `339aa36dba89cbbdf7c2c7e5144067775ada84b8fab43940e5443cedc2e0937c` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_hp_actual_causality.py` | `e8461963d99ef5a8f975f1507dc95d6316ae7d9bf4856653cc2561734793bcff` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_hte_methods.py` | `a429f1fc0f81f9721338b356951172e7928e898b6707dc70b1db76f5bd8d7a5c` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_interference.py` | `1236c1857fd48b5911df111d55fe8a1b0e0057656b515933c6c75d93ed72b381` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_invariance_tests.py` | `a7d1a7ff8de1dbc252b3cbd22301ea88dbb9dec0b6b1c1d94aee32e3dde1b524` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_lp_bounds.py` | `34a7fdef8d62af80028538918a26b33d47532cd3cbe965b44e6a05de856330e1` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_measurement_error.py` | `785ecc70badfb1410ece836d02f6d241f7bae054b2de69a253b2e85c59152a38` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_model_class_compatibility.py` | `a6eeb0f126790a77967832c5d8bfbebd2dfa79649bf85cd54c7278633a24c861` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_multi_treatment.py` | `0bd1407e3306584f899699cfb06a4fa5fc3964d2c3e720d3c7d2bab4d7f417ae` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_ncm_engine.py` | `18455749c83a79b3ec46b5aa3b9faa35b3e7ded22d4c310bc0a4a4044b6e7480` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_nuisance_layer.py` | `172c9fcf13fce7d1dec82ba224a525f0164e28ffa72db543da9342948a6a2a47` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_operator_valued_methods.py` | `43bf3621c96637297d3cea580a216b0a502db1f4c23ce5f2cb01e68004417e91` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_optimal_design.py` | `af046d0274e8c0899ffab99de3012f5bdc7c763036108e1e6c2e3f3f326b9cc0` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_pcmci_discovery.py` | `3bc7ace7a70a38c0a0c4518ed4579c6bd422ac3e56553f0e756032aeb16f5eef` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_protocols.py` | `47461e61a065ec611d61b9f114f3736a9738ed174882ffeeae121125e82b7dd9` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_query_validator.py` | `c16c4c5310976a592b351655094633991e4c96e8fc63f71f44c20bd2d5600235` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd.py` | `ed5a1196a771090b37535bb3f86295707f56a4f574e7253a17b2982c701ac66e` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_recourse_manifold.py` | `f021a80edbf5e802fda40a8b00d684b6ace55d0712cc81f6cf944945e3c9c085` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_schema_resolver.py` | `aa4fb2a77a5a93ba33e2d752b0b6ca9a7fe024e15644ceaa62cbb63bbb0ad46c` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_sensitivity_benchmarks.py` | `0c1b60a5e21afdb07bee6e00df019947c6a1953b6735e720c70790032d53f622` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_sensitivity_metrics.py` | `aac29b5d726a62d7175275930316f6801bb30f8dd61cdf371e32405ad5893c8f` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_stochastic_policies.py` | `3ec80a7e6ceb16a8608f4ad57f313b4786fe5ed6cd90545c285eb75de1539715` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_structural_time_series.py` | `774734d700ead76b722b5c7e2dc9ff4367a558de6c446de5aad252cbbb0c9718` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_superlearner.py` | `508be6a2782f31e072aadc0f564ce669a089ff73dfb554d20f8f8775490212b9` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_symbolic_gold_suite.py` | `d90fef322073979ce89dc82ff573969e9057e94e5581d74cfac4cad5e3009289` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_temporal_estimand_compiler.py` | `781a49cc5a45963a2410795dcd61c0e2341b1e02e667881edc65f24491d3ebe7` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_temporal_trajectories.py` | `4ff1da7f8a28b16c02e02ee9acbd0394f1bb3a25ec78b5191eec204e8c2a64ff` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_transport_bounds.py` | `f75865c137e917386d9c2424775db9cda2f91f58b213b83c83a5ec8502e36a75` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_twin_network_query.py` | `3ae76719c0a4951ee8d40f7e95b8d6d60e6926d98e4dcdebcd2c3fc0f813c54b` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_validity_eval_pack.py` | `e99dbdbec1242fe58ff82fb7928f565bb441b2cd7b76d838a39aea57153906ae` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/causal/test_z_transport_estimand.py` | `0560a5aa2613c7cb250591529c6f576ff549f6076122173bb33f351753df90a6` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/econometrics/test_advanced.py` | `43301e099d8722bac85b3d8b661b2c6bab656bafb8af381cdc55ada1a92ed5e9` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/econometrics/test_dependence.py` | `fd8ab70029aef9219b698ae819eec890f1473f93efbbdaf197cb923eb2278c04` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/econometrics/test_expansion.py` | `2431de69a425e9e75e7dd49cd224ef8e00567128da1256c8bd7b3e90ae8d5519` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/econometrics/test_iv.py` | `80be84117a5a020539016760e84b032a0bf1e8748082a98602d540958b101238` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/econometrics/test_mobility_latent.py` | `eea2917d05e921d45eac3c8ac03d142e20b8bf6eb7e1835a1a6563e3b9e118e5` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/econometrics/test_panel.py` | `3a54adcda774c55370c392826dddbe3e944a1dea2151a73c4bd44b5a4a9ad2e3` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/econometrics/test_protocols.py` | `dc50dc8e6e6dab1c159843e6d9f90966e06a50dee6a7fc815da6852c6346dc34` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/econometrics/test_thresholds.py` | `916cc110060ab85f727fb8b953f93273f2e0323ea3f0fc012aeb9b8c0a855ce7` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/econometrics/test_timeseries.py` | `daaab45652dc98eb6baf4303c7e3aa807390290dd331775cf84e5fad17e6350a` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/microsim/test_methods.py` | `401216f4b8b7084711a5a945376c1358e85709b7d5948727f037cfb66fdd175e` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/ml/test_advanced.py` | `3475c673a3186fb84319c2df1a734ce791d4d8284e5ecf6af83f8f37f26d1a2f` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/ml/test_frontier.py` | `ce161f1a8f94d93a294679a74373c0b985279e56682d905de2570a5986b9e84f` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/ml/test_methods.py` | `d433929e11e5e45a1b7c0c61993b0c763a2f4bd2e16fd78244d48bea42e06520` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/ml/test_phase5_uncertainty.py` | `3115283c90e9d74cdaee68911291a503bbc39b607303da81ac3adbda3fd886e2` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/ml/test_shift_diagnostics.py` | `77103e69cdd52a1b37fda14d9a0495206a9a57fb4fc60d39e2f473477a951228` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/ml/test_transformers.py` | `b8ab713014ceb91f32ed2cac5b58b03cf294c2b3f03228a95a2d0111b094cf92` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/network/test_block_causal_bridge.py` | `63a80525685c7dce4ad71aab2fc9fe167c1f7c4d1124cf73483cc4ab65ff9485` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/network/test_diffusion_null.py` | `8b9f800073faadc0587904edf14a33f3b75b5bef75b9020d84036e62c2de4a28` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/network/test_embedding_fidelity.py` | `449ec2876728016208a79e9719e68afcc531a533e7e8b1cb5289d14691987221` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/network/test_ergm.py` | `007466a225f6e0dd4d0d684e5acb7a0d8fb53dbc7baa88228bdab9c6cea238b6` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/network/test_methods.py` | `82d7a0c6994fe84889ee18e0df57108377bf504c8f68f1a2d9ac29072b1b2f59` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/network/test_missingness.py` | `bee64c70fbde9843d40934fc554310cc7ab8def7fc7f01033f28b33ce4693224` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/network/test_sbm.py` | `d3ccc60c4b0e36c7af3c34840144a5fd753f85a43afe5243e80fe74ad9372cd7` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/methods/catalog/optimization/test_advanced.py` | `626b7444b51cafc9d6d7e4fb5fce0fa883a10a410ce83949e944dcb4b33e28e2` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/optimization/test_auction.py` | `33fdc25a33707ce1f77704cc14cb6f1d3089d0c1f466bef22112503b0b126523` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/optimization/test_methods.py` | `d901c45510311289f4c0a9eb59825ebe1386b8f753f1a585fdd9a6bd290b9d66` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/optimization/test_moment_dro.py` | `4252e17727ccc4d79db202c9c71becc229908b225fe83f67abc51c5807904377` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/optimization/test_protocols.py` | `b357f52254e5d5461c485d8849afb2af2883009b3c385601dea6fdf41c788ed8` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/optimization/test_sequential.py` | `9669d3d3eb5a8a168e20406b370c87bd5ee82eab8666565b98ed94982b09a700` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/policy/test_mcda.py` | `f63ee49f601bc34d588f8c3260c7aaf921787d275ce0a10f80b831a6ba05f5c4` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/policy/test_welfare.py` | `37b373f753d037e4e80d32691575ac458bcd0e6f3bcbb861e0d863b65ce9f871` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/sensitivity/test_dependent_copula.py` | `29c9419c716d14aa7284f77ca468b3f3641ada4a7c450fb61d5aaa36a652e121` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/sensitivity/test_distributional_indices.py` | `e6b8a05faddb47ec3ffdf532f786a01c30d74e54de8f2ef5c866e8ca76cf85f9` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/survey/test_adaptive.py` | `6a63cb19adea9557bdd325a490e6495e4661da6f37e760dd1529e545eeda31a9` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/survey/test_estimation.py` | `3586152c9b7ea0291c989ddb204751669171739afaab3e6df4b540726f1ee078` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/survey/test_semiparametric.py` | `1b168272d39964816030e30cacc029a3fb9a98110661c7e06b9a5a6e903d9bd9` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/survey/test_weighting.py` | `45d871ebfbabd78fd229692155f703a91c8c53ed555b99e8d1befae2a39a5230` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/catalog/test_workflows.py` | `cbbdd93fc6ff64923e0c745fe0cb981cdb1588e39dd5edd394d01605a8807176` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_artifacts.py` | `a71b81fcbfa54e81a8188ebcdcd5e4bd12b765c510949b14dc35ec4d7eeb1f2b` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_causal_engine_integration.py` | `9f6846ec0991cf5ca6dfb911f315fec7e6a5bb92757ebd0667dd48c9e2c6abf1` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_compat_matrix.py` | `f9cba0cd5adb9cd7997abda068363a7a29e7e1738f03d2896d33e764b53b80f0` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_compiler.py` | `a015d14b41eb7bce0ab0b9ed96e79663be29e71aebd1f19f1f7801e646a5805f` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/methods/test_composer.py` | `0aa58ad4447e7a35b2512dae8056c01e0ff9151bcabb82879b74c0a37da9a926` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/methods/test_composer_hardening.py` | `88a67c39f5a8fa57f4c9a1c5c552321fbcfe5235370776f3b3eeace0cacffa56` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_cross_backend_consistency.py` | `07ba54cd23531686ab561ee58e36dea94c43486f1cf2b57314b75e192450b359` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_dim_var.py` | `45d4c520411e1bdfdf5dba87a14e34a2e957dff1c437015f512f2c6b0298d676` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_dispatch_fallback.py` | `5919c7977c405f51251888220b6ba11b99ac94c352a8b52b9d4b214674676817` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_dispatch_runtime_selection.py` | `ac6ea5f8e2c979710fd36081fd798507f4eb9ad7989800dee128da8e210499e5` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_equivalence.py` | `d05de46de91627bfab6f96ea26fbf74e39fc45719010f1c09e889d4ad117f0a1` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_foundry_purity.py` | `60433b6f7ec304d1caf607d88b293affa9573d357ad6cae054c48c8eb19dcf13` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_foundry_v2_domains.py` | `756ffdde7ff1af729b93d586ece541d90ee33fc1cb99657c112308d6c1cb2bb6` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_foundry_v2_unified_runtime.py` | `6d74ca2e6f20b3107fd2d64dff1c0331c6d2cf393c6f36b0cc4b1b2fa0fcc158` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_hot_reload_safety.py` | `28b807a170c01a2ef09dd553bfa4c34267c65d867fdfe51f09b8955d9d163082` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_linker.py` | `e7b975cb4d2d5199947c9f4e7c8f47e9f9de2683a8661b1a40c2557344064ad6` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/methods/test_metadata_pipeline.py` | `6c073bf2603f82762a6ed04611b6a3131a71a7c6c4e599834e858ea6a37bdd3e` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_method_contracts.py` | `570963b83277a7c04422d59802e22aa5444b13f10ddc7c87e675830aa0169b8b` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_output_monitor.py` | `8063024023058874a8d840d7b8a45f4f668a41ad3be3b2fed5b932baaa11d271` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_plan_optimizer.py` | `f87197b0f8047155bc34339d71729a0a2e10ad06166a9d0b392cbdf54f31ea0a` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/methods/test_profiler.py` | `b39f271c2a760687f5ea2249bfb72cbe94a8d21958c1bce500058951d99d1fc0` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_registry.py` | `fa4398df07a91e64fbc5b2cb9184ca2eef9543c4831a7d464af7c358fa5e2d04` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_selection_v2.py` | `3776f4eff999194eda8bd1e993b857f8890c5aab59ef9eb9f51bc6018f7063cc` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_semver_resolution.py` | `c4dba5df95936f182cb33f37444974ebb3c648339eae8535f40a631f560c0404` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_sl5_fixture_coverage.py` | `5143ce4b98a7e694108038d84f4aa9aa02fd17d59fa44e2e54a0f0f23dfe019b` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_testing_infra.py` | `32b1deaa78e552dc7e5f029b7eb6161ae2fea8c0edf9796f2c73e1f74dcf96f4` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/methods/test_types.py` | `4db4b942f1d8eea7ccc776579e635530fbd286ef48ebc86d5666d7bfc58592c0` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/plugins/test_economics_social_weights.py` | `98a16714bc896920eba8464278864df3903b6e4324d0018c39e32a02be4a79fa` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/plugins/test_plugin_system.py` | `bd346a223453d01311486e067fa7c36f83895e88b9efc5a2a90dd0ee87691678` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/runtime/test_constraints_executor.py` | `230f4244dd18b0e818683128ffb583cfa8df8229b0277808f8f87eb92b7db0bf` | `hold-import-statement-grouping-change` |
| `policy-engine/tests/unit/foundry/runtime/test_execute_feedback.py` | `007e45d96f0cabf1e5b917ca343b140f9da8e28476f7a245eafeaf8558b4946d` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/runtime/test_execute_input_bindings.py` | `dc835cd6bccb4ee2a494343583536f27d0e7d18c6d6ce8d1f2e13ae4e23936d7` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/runtime/test_execute_requires_input_bindings_ref.py` | `1e6b961f8d8e6e87e79bc90bb251366fc410116e508c45f2e905b91dd0c7d781` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/runtime/test_executor_fail_semantics.py` | `78b0cdc5ad28160c552b688ed6f37c00eee480192a1aac4b22e78a10848e1b52` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/runtime/test_executor_private_modules.py` | `6ebed28dfd57eae8c4099a9c42c133fc8054e4eb79114170c7ba93f46671e13e` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/runtime/test_executor_runtime_semantics.py` | `1afada022b31ff6e397b90e0419c2ddc208c3725b92f2c7e57201e299cd27a46` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/runtime/test_fingerprint.py` | `a8e8e6bac06a68f0357fd86f8d5f982d3753350a20631d15851c6e5f900350aa` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/runtime/test_jit_compilation_tracker.py` | `67e7891ecc72f42485cd7783a6fb4074eaf2b3e4fe9ddc419e002dac300135ba` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/runtime/test_jit_stability.py` | `6247c99d16acc14106d47015e63c0d284b6dd60ddd0658cf469aba9715f516c4` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/runtime/test_nan_guard.py` | `f2d038b52407f935d5620f4cfb8203976512c06728ee4c6d2322cc182a0ae8e7` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/runtime/test_nan_guard_public.py` | `b1df12198f6b198f4dcbecc9c99ff9c916beff0cc47fc1f01d66b489851387ce` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/runtime/test_patch_executor.py` | `878c86a6e1f6b7d6ef0d2552b25035077b58f6d241ad1bd486f357f7edd1a24d` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/runtime/test_patch_vm_parity.py` | `e5c0d23789e1e814adb0334945e953d5c30e654a227fb6483f9ef5b12b918438` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/runtime/test_runtime_batch.py` | `6eb6167575a460441c14abf135741941e9283c2d0d362bbad478788024b362d2` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/runtime/test_step_specialization.py` | `9ce7ccd403e1550bd3b495bce62a6a2f05bcda0c350d55022691c9ee02e9fb24` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/runtime/test_timing.py` | `86ef8a49b5d3f1029b69de5b7022429ff76978fd0a6a5adf456ccbdf1bb4282d` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/uncertainty/test_delta.py` | `a0524d337692bfac190c25b66d909a0971f5ec0f1acb69ee8fe37f7c84c21d87` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/uncertainty/test_dispatcher_routing.py` | `7b9b322b2fcdd8d417aaac4c0203065980446fc440d8b33f275d94920b2be615` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/uncertainty/test_monte_carlo.py` | `0fa296ed8499dcccc6a28ce971dfe2c7b3823a2db398c3147048afdf43ad8045` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/uncertainty/test_quasi_mc.py` | `9bcfe0a3c6db15c6248c13cecbf104367f3fac0f0b7aa45701bc118feb8624a3` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/foundry/uncertainty/test_sensitivity_indices.py` | `374b287491a4739a0d34d143dbb90568068edc96dead3ba48f997a251b5b8ca9` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/uncertainty/test_uncertainty_propagation.py` | `1b47161e5c362791d832de233f7ab6a806fc43ab3d0ae77c2e12cdb072565b2d` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/validation/test_constraints_v2.py` | `4c3615df4ba818b2ebbd47b02a3ef8d03e4c892ba9d76432458a4a17e0319d82` | `proposal-format-only` |
| `policy-engine/tests/unit/foundry/validation/test_phase2_judge_stack.py` | `0a9aaed94daff2ba3707a1ab253749685c66ea53309e485eb488173a1554e667` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ir/analytics/test_bounds_report.py` | `c0537b61fd8af1ff71d9e553b574c9397afa09e5e4d9ffd5a9cda02c4e113118` | `proposal-format-only` |
| `policy-engine/tests/unit/ir/analytics/test_calibration_diagnostics_report.py` | `c4515d693e8378499484665a6dd383e0ec2faf1ccbd6904c24b8547c936aa71b` | `proposal-format-only` |
| `policy-engine/tests/unit/ir/analytics/test_estimand_nodes.py` | `bad8115be6b649a5a13382b2544653bd487352e16a0d8bbdffa1ac55dc24a2db` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ir/analytics/test_kb_from_harmonized.py` | `8ee00dedc1ae7dacfda79baf5cfcfed97f8d91fdcf789c4027fa0fc321955bf3` | `proposal-format-only` |
| `policy-engine/tests/unit/ir/analytics/test_query_validation_report.py` | `c90a4aa3b873f788b1c13ad40c205b84e668a09ba7426913a903f0ba9fddc7f8` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ir/analytics/test_shared_invariants.py` | `f9fd34107f280c18c49691a269c43f8da1f1c005ab3e969f341130c524c4d065` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ir/analytics/test_track7_audit_evidence.py` | `f7a279408e8884cbd6c5920cf9fd810f90ae9f647ff938f68daf1023ee0c33bc` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ir/analytics/test_z_transport_estimand.py` | `3806d44dd983a83f27bd23451ba0c7e5f1cffd189a46e66db32da086e34082a6` | `proposal-format-only` |
| `policy-engine/tests/unit/ir/data/test_harmonizer.py` | `46eddbaf73c6dbaca7325ea46e21cf273f6eca87d59b87ee991cdaa948b5bbb9` | `proposal-format-only` |
| `policy-engine/tests/unit/ir/data/test_versioning.py` | `16cf768f4434305c1be31ff4e22c47c900842c987465d8d81ab753ab79045002` | `proposal-format-only` |
| `policy-engine/tests/unit/ir/governance/test_mechanism_semantics_contracts.py` | `1ef676214c3fd379122c64cbc60ea3fbd1e7dbd32a4cfa2237be5717fe0c4b2f` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ir/governance/test_phase5_governance_contracts.py` | `d4d308a91d93ce7d5be3a398a6b4a9c3792e5dbc6eb46fd080e3c49d4fb2d2a0` | `proposal-format-only` |
| `policy-engine/tests/unit/ir/observation/test_bundle_schemas.py` | `f4b9408c8c235b97ef8b4c007b36f38e5e656dfb3bd5a15b5c88404a94170e74` | `proposal-format-only` |
| `policy-engine/tests/unit/ir/observation/test_causal_readiness.py` | `ea19e5fd45235b33049502d16987fcc6f83e73ec6b28cf45b90193caa63f6bc8` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ir/observation/test_contracts.py` | `4cc637e12e677029c4090a96cd5e19458877ce460eede06b1ed800b4d9f9940c` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ir/observation/test_measurement.py` | `9d0eaed571aa62f338b2d5f76902c2bc8565b0f0be865230291837a3d886d817` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ir/test_alignment_certification.py` | `5aa662978113953e0547eac5a4798a5b307e9ece49da60ff43ecb07b88bc549a` | `proposal-format-only` |
| `policy-engine/tests/unit/ir/test_canon_hardening.py` | `1ec45f6e6a3498b230050c2609eb569b59993d277f6a4fbce7756074d95e645c` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ir/test_causal_graph_kuzu.py` | `6a8323d9feb27430d5ded830d72ff5334ec84b0d44594fc77389ae9943bd2d9e` | `proposal-format-only` |
| `policy-engine/tests/unit/ir/test_frontier_causal_contracts.py` | `1591a414562255ba970af45669188cfda4171e7d89ffc267a3aab0531b07b4dd` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ir/test_interoperability_bridges.py` | `90db014edb06c5c6466226179c8a8588c87610c6f89a7f4dac25a53fe1358524` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ir/test_mediation_effects.py` | `241927cb3f3c7b957649d89f661eef949fe58ac767ee7922b4e154158d3b46c5` | `proposal-format-only` |
| `policy-engine/tests/unit/ir/test_partial_identification.py` | `5a5b1dfcadc825268071ee13195d64caa391e091d44fc91964d30c603fb015ea` | `proposal-format-only` |
| `policy-engine/tests/unit/ir/test_phase3_fuzz.py` | `a7d46d7bfd17c5af952d257f4576650f48d773b8e5b1ed5220613ed336c29b12` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ir/test_transportability_models.py` | `84b42d8a88593fa463c691b4d9f024026bf24ffe49ba85da17dd2dd41094bfb3` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/ir/test_trinity_loaders.py` | `6f46dadaccb2b172f865edf5c344149d32379abcaac1a7103d31877f0264a075` | `proposal-format-only` |
| `policy-engine/tests/unit/lex/legal_evaluation/test_transport_constraints.py` | `ae3a3b16e24713e24061172f4ff657ab689f3d188739c9a44a56b12d1b1fdba2` | `proposal-format-only` |
| `policy-engine/tests/unit/lex/mirror_contracts/test_factlog.py` | `ab298b34e3b39176bdf42038952e6d8de3a79c4dc3f94a218357bc49d51d4306` | `proposal-format-only` |
| `policy-engine/tests/unit/lex/test_api_transport_constraints.py` | `b260614a1faa82f4d438a3145d06d8721e92a62f4c3b6ecfa46fd76e921557a2` | `proposal-format-only` |
| `policy-engine/tests/unit/lex/test_intervention_artifacts.py` | `ee6ab082e27815981722829413f9a11fdda6c8592800c8925ed2b3050afc89cc` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/policy_grammar/test_universal_policy_grammar_compiler.py` | `81a910bd65b06570e3d01a3e4c358ba9c4df4ee35e18e825b58a81193ad86599` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/remediation/test_cal_04.py` | `8300c2809fc36330b1d13f679bc21e589696a2050b4287e11c18cec9f0fe4bf8` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/remediation/test_cyc_04.py` | `2cfe701290c57875d1544724ff618030e769530cc38cc2c84a7df6c4b56e7439` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/remediation/test_dfi_02.py` | `f72982b622be5d5bdf5eb67f77370312796f6ee40049d0617c4200dc4677cc18` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/remediation/test_dur_02.py` | `22aa14c0d4e8a3ad6c0bcc0ae1101bfeff551f2fb69c89610507cf80210449a8` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/remediation/test_eco_01.py` | `f0dd85cfd6f0f2c2a92c643b3cf3fb73ab708e984a54d5510fd375f6235b44ad` | `hold-import-statement-grouping-change` |
| `policy-engine/tests/unit/remediation/test_exe_02.py` | `34a2a44040561fd7af9b03de765f5accb3fc6726f4c1e74e47821afa483a7104` | `proposal-format-only` |
| `policy-engine/tests/unit/remediation/test_res_04.py` | `2b68386ccd19bc331dc8cc8ac92bb2080da293189b6c2a3e165d11c2c585f925` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/remediation/test_srv_03.py` | `71da1325e7ed6b7d05b33f893cdcdc6de0bf98df7f02b6df158c457b4ff4ba3a` | `proposal-format-only` |
| `policy-engine/tests/unit/runtime/http/test_cycle_board_projection_access_replay.py` | `3dedb4f0a08763a48ae6dd891e68b686db4488e22e9a388d617109faafd38f83` | `proposal-format-only` |
| `policy-engine/tests/unit/runtime/http/test_error_semantics.py` | `c33cc82642f2b82d3c4f25f8d211a614d4fcdef9384cf894267721c00aa4e1cd` | `proposal-format-only` |
| `policy-engine/tests/unit/runtime/http/test_runtime_api_observability.py` | `ecf60711696ad37c98a7e384eb4443875a110516493fdd117688932863862f56` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/runtime/quality/test_acquisition_owner_store_requirement.py` | `aa691989401bf90a303a2f6b2519d956f7d3d67fc8768cd91817958e3d065bce` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/runtime/quality/test_design_axes_graded_outcomes.py` | `0264333fb0a361d2ea61d2d5864ee9baee50f5046cbaf5254f577d6baad9221c` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/runtime/quality/test_policy_design_case_integration_skeleton.py` | `51d86e54ca3e7299e144774cd00ea1c5a6f6a06d861cbf242cfe8c8dce703b06` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/runtime/quality/test_scholar_academic_evidence.py` | `eb37b4483dc868fb3d9f6a427b5fa4b9e568b008875f789b0e2eb6127d3d6df9` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/runtime/quality/test_scorecard.py` | `02c5f55571259c91f3a0c840d2897dfefc62c4975b6d64c0d95f8929fdeaa6a1` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/runtime/quality/test_workspace_composition.py` | `3979d48467928a65b469bce921f58ff6cfd15d83a38359cae200afb41e41afc0` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/runtime/test_runtime_manifest_paths.py` | `36eb6b73781c1d5f3d96e327d778623228b30948b110916c84143bbd33aa8245` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scholar/search/test_providers.py` | `83e1214a3c0251220ba106951745a12fc5ea8c4ef241dd23c39ed1057512cf3e` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/adapters/test_foundry_bridge.py` | `4ce3b768efaae2e042b1505c6bb2070730f6b8a10dcc1433d040739f0585f344` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/agent/test_agent_protocols.py` | `965e48e94cb672e27a3e5914785a61e04bab9b40176af89d41ab2a1794e005ab` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/agent/test_constitution.py` | `45c8fc904aa8f804de102155f4ddef974a178b30bca37f1e0f612d4b59f85602` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/agent/test_drafter_formatting.py` | `c5bc08312d351dfb184611264292229631f792f42e6a47b9a71ab15d076b9f3c` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/agent/test_drafter_llm.py` | `62e29fac63c46fa9964df55813a72ea4a980ffac24d01973d2b42e68772dffc6` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/agent/test_drafter_models.py` | `0352363d87414965e096d3d2ff42a06873d55331f048220dbef5a9f2547b91ab` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/agent/test_drafter_passes.py` | `9fe8c23a811a8ecb6ed31f9e5adc8aa189543bf513f1580b14f6c1ebe77ae87e` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/agent/test_eval_harness.py` | `592600972cec05de71607b0675ff4db57346d19db80d4d848d27f627726f2e64` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/agent/test_fabric_v2.py` | `d6500df27fb83b8572fff46100d5cbd62c35b65310d96f66d8101f978014121d` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/agent/test_multipass_drafter.py` | `1e7c08dcc1eb092fc3dc4b6d1630367417dfefeb4a1bd6c985549f86495789dc` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/agent/test_norm_loader.py` | `6fc7adfc1a56788e71acbcae81c375652e56e69aa192f4c576a94c3324dceb60` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/agent/test_persistent_memory.py` | `12f1cd5399e0b83a2cd8abbda5453b561077a95949ccd8f4bb07137521daed6f` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/agent/test_rag_index.py` | `0aa4095838106ba7d9eafee1e0f7909babb2c1104403195c54b36b7d7f57ece5` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/agent/test_router.py` | `73a5cddc752f31a85b148e9ea31eac72f1f588a3ed43bffd50a2f8e64e063d07` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/agent/test_supervisor.py` | `f425434d1a4e39d3f90adac15264f83d23b559ce28145f9b1cd3864f64644124` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/agent/test_workers.py` | `c43923c308383f28a7b38ae9c0973e904a2a28a24a61efc08ffc0e00ee4c4857` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/agent/tools/test_tool_loop_hardening.py` | `3acf16297f38b445307c4d32826c963efadc3a8ba765f484c5a9d76b5817d4b0` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/agent/tools/test_tool_registry.py` | `cf2f4c7e889f83965ab8c81a177fb2307c7ad3ca446770a517ba2a7fb10fe709` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/agent/tools/test_tool_schema.py` | `eb31db1f16e683c2c53ee6e85bad7294e4038a6c8c486d970b3c75d29c29d80b` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/compute/test_compiler.py` | `410d4ccbdc3c981bfe6fe1525c41098f260e97963513bdbd8a28afd71e644f3c` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/cross_graph/test_cross_graph_evidence.py` | `7c9553aa705ddd97cad8ed17d16036d0501ca83aa1d98d218f2b973f95a2fa35` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/discovery/test_active.py` | `9b6f9961871ed951b10a79dd8641a6fdab6267b7480245e51a7971f7b337fd54` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/discovery/test_output.py` | `d1151c82913bcea1d876aa9f87b42cb9708e5aa41bdd23516ed96c3aa08f53a2` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/discovery/test_priors.py` | `9abfdcf25e4dc4410625411bf5b8d2b55fe33207fce17c047f067673e5b3643c` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/discovery/test_stability.py` | `4cd9c3444f61ff8ea6394b0888981a69349f448be436446de9f6024aafbf2818` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/discovery/test_utility_judge.py` | `e1884bfb37cbd8c5e0fbd6e15296425904737f7d5b2a7b79b72c2a7748b59cc5` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/evals/test_authority.py` | `248bb44786d6a50f7532c8bc93a716afcb0885e1a397e4d8df63ecf6f5281b32` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/evals/test_authority_integration.py` | `c9eb2707742b5f14b2deafd66c7a2402dd1fdb065a1a1731e3cf11b446ed3e39` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/evals/test_frozen_web.py` | `1ce54da71d0584ff5a42ce61d60ffd8c7dbdada02f490f902464c7ac4526f75f` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/evals/test_sentinels.py` | `dccadb0c536afa174d28363b30cf3ba2c62f2625a59aed3518cc44bdac46d0c1` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/governance/conftest.py` | `86eb14363ea26771aa61bcc65f063f9255649a72546517a1fbce62f0e6ace5af` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/governance/human_review/test_decision_packet_integration.py` | `94b5f8c3118875e56f39dda0f1b0fcfc2fb762e6b1645243a4452e27f72e83aa` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/governance/human_review/test_governance_integration.py` | `3dac81a35205492adec77bed55d4f858412862f2f63f339813f7d83240f6f51a` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/governance/human_review/test_models.py` | `81dfb104fced850c80692438bd485c9afe146df4c05fa24e45b4f33db7652943` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/governance/human_review/test_queue.py` | `747f457ceab1c613c2d99ae3da482d09d7e97a1589e98df8aca21960880094a1` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/governance/test_calibration_governance.py` | `12a22b12905d12129b199947ca9ad8020eac4ad298fae837549b4649648672a9` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/governance/test_calibration_leaderboard.py` | `8d94a84b6fb1e988c1ae4450522d71fa82620fb792d5d3967b6a7420e86873b7` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/governance/test_governance_validation_shims.py` | `8ada0abf2c59f95366df2f7121f302cf57c97a2e1bc41c2ed3f42a4ce0e855ee` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/governance/test_incentive_compatibility_pass.py` | `1828aace0a3c70313a57070423f534bcfa43ef2418fd8a064c40a7117f5392f6` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/governance/test_legal_pass.py` | `8190a307ec7da1dd91e22e73a5f55f2e1f41218f31054d3114543ccf089290db` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/governance/test_norm_execution.py` | `f8cc905f0b3cfa078b3ade9d178c2e09b8941bbc8b01ad51603c11245e8cc16f` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/governance/test_pass_registry.py` | `6d3a9ada921747dc095c1959edd0b93148ce77763525c1ec97157789d0b12409` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/governance/test_schema_pass.py` | `4b73cfcad97b5875a3b07491640656846b40df9baf36d85864d1e535373d930f` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/governance/test_validation_pipeline.py` | `c5e6b3da2a19f62da3fe1e8b6290a507959ad03e0ee33bab409e0bc2c3bc27a5` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/methods/autotune/test_execution_plan_autotune.py` | `96f4e74a8c5ed8bcf53e6ae0892e58a1f3b9e77a8478230af132b145aa20bb4e` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/methods/autotune/test_registry_and_runner.py` | `84ee9b6484b95ca9c7e46034aa57d7de926866d924716536eb84f89750cdfe21` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/methods/backtesting/test_adversarial.py` | `6fdc7b24ccac28cafa270721c08e1f5daf756cda95778155ce227f069e034986` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/methods/backtesting/test_cv.py` | `0139dff16f11f71b665abc0136b1f65196bf8a198a1b2c3a57cb28f7099b4929` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/methods/backtesting/test_distributional.py` | `7783819fb3a44f9fd0c9af837196f2a95d42a8d9d93d284868689988332a3fd9` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/methods/backtesting/test_ipw.py` | `a3eb56b213fe594c1bf1112e940560a6f933c39fa01642a60b0a2bb9351aba54` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/methods/backtesting/test_masking.py` | `f7e0323b57faf3f4ab83c86fee99239158a9ade04be5e52821530087358765ee` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/methods/backtesting/test_temporal.py` | `120ecf3d6c0f62969d810aaea88d4b8b5675fa86f8d4e4f99227c13323ef5a04` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/methods/causal/test_latent_separation.py` | `fcbfbc98069b1f6ff7a5e30a652732dbcb904f95f2de808be2efab27e71a82c5` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/methods/causal/test_transport_resolution_cache.py` | `44a27839ce44b7bd57624674c7b44b07a1136968f4881194069474cb85a6988b` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/methods/doe/test_analysis_enhanced.py` | `451b18624814af0e459f9940fd7f4ff3fdcfe66d019c68c173773cbbaca1b33b` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/methods/doe/test_multi_output.py` | `ad0a9e0a7874577b0bea0402700c88c5921c32420e7ca85255258d6bf87a8be1` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/methods/doe/test_sampling.py` | `2d92daa4d3297cd4305aaa07eab4e691fa5a6ebda94d59d13f78f35961ff0bc6` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/methods/doe/test_sensitivity_benchmark.py` | `b52055cf89740a49b43abe4d6133e615218ba45f9d596013f635fc0842978784` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/methods/doe/test_sensitivity_plan.py` | `406d609242f1fe5215aa3c8f6642910e1a3ec3296589621969c36c99c04c1db0` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/methods/doe/test_uncertainty.py` | `dcaa1ea7d909db267265a482f95623d348482c9a3ae51afe82b412fbea0b4acc` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/methods/research_dag/test_invalidation.py` | `dd653491cae09ea06e35a5823a76623100d4a20ef7e9493d6da36f5f38882efd` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/methods/research_dag/test_models.py` | `4c758301b154893a54d0a77a05941876bdefbb31c96dc572fef4cd90c43d8119` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/methods/research_dag/test_projections.py` | `92baf1a1c4c964673e5306a608379c7b26c3c6ac75c97017e44314cc63df4ae3` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/methods/research_dag/test_replay_plan.py` | `7901085b1d7eca2272e296aa288cac4810d86f715e4217f4c0000284db05a1b0` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/methods/research_dag/test_workflow_integration.py` | `a7aa0e32ecf03b3d4ae28e2b950f5ed1a101b342555482ada00825daa3860485` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/causal/test_run_abm_consistency.py` | `3d7bebb5d8ba3cd7b89bf34db16c2c517e141ddb3b36bcc9798d7cef5d31ed02` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/causal/test_run_causal_ensemble.py` | `1d10ca1f295e0b3ff91f738eaef7b59a116d78d0143ea0e92cbd64b79ef2d657` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/compile/test_compile_foundry.py` | `2f6153c321618d00df202f13d8c6647f0b4866c4c3a3fea4a10810843b79f84c` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/compile/test_link_trinity.py` | `90a1494cd570dbd766acbb6e9aea6d5611eb51e0e5841c30a346aec45bf28ad4` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/data/test_build_data_snapshot.py` | `4c47f4d74eafccd6a1a5833d0923b04225b17a9f6f0982ee728f15883de628cc` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/decide/test_build_verified_policy_report.py` | `bb8b3629ecd4e2195aaa0e6a95efb5cff5c7d63c2b30410f83a89248da49aafe` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/decide/test_phase5_decision_packet_preflight.py` | `03d46d713bec03ed25d8064c0164b294af8b31d99dc73705579e8c06c0e33380` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/decide/test_policy_translation.py` | `b2a9baee76860d00bc2368b02ed3a2ad674bf63afd061d3eb543365c1c748d74` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/planning/test_assemble_legal_candidate_pack.py` | `f963630cf2f4f19cb49ff556e07ba05dd6e0a97d4fd894017127703bb5fa06cc` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/planning/test_build_execution_plan.py` | `14458e3f8ef80616c5ec912d3ed4c028ee49bbf2c706a6056a99609c05d67c7e` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/planning/test_build_method_catalog_snapshot.py` | `fc3a7277088bda983d4512ed61f5a817ccae29a498837d3d9294eca17d0b6b0e` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/planning/test_draft_policy_options.py` | `407bf20f34d3dd9559b40abf300516c1c6bf719a7947122304c1e9fdbad12710` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/planning/test_expand_legal_source_pack.py` | `3f73e224c295046320070bc278e123f104976d25165aab5128a24720863b8876` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/planning/test_plan_policy_request.py` | `1182b8d0837b7041f2c0937cc16faed5c38fd6a238d6dfc248456710de76c979` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/planning/test_run_discovery_blueprint_runtime.py` | `ed26df96bb76417ac32366070f451c321d5f68c5ee1ea4124b8c9dbc49e111ee` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/planning/test_run_evaluator.py` | `b6e6c474ef48480cd2d760098392f6185132ef3a8b0d49638ce82e53964293a0` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/planning/test_run_preflight.py` | `37f4001effef6580ec9da9cb4d76e6b4e174561b5aa0a2c014a6253b00aa0aad` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/planning/test_run_source_gap_review.py` | `12fc31f78db2908c11532048e066bbfd09f05f88264c5d97cb640720e3ca958d` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/planning/test_run_source_verification.py` | `7bb3a4a1abd5ff21cad28d51bc3dedac6182b76abd074f21566f550c033b14d8` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py` | `bc96488f74c41a97769e990465138ed186c8eff6a932dc578fade85a282ba790` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/nodes/builtins/test_guards.py` | `76b062ed1d309ff8c33aba597c6cc78aef5b7bbd99810ba47452888ba4f2e9e4` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/test_state_builtins.py` | `a7b329ea580ea29b466072ed7e0674184c0f12283e73465c265f5b2186df0e3a` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/nodes/builtins/test_tracing.py` | `fcf5e806cf87852c51b4e784b68c842855eb56fc554b01ef486906735148201f` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/builtins/test_validation.py` | `885e15a45626bef298a53787c6e8d7ff06fcbe5dfa430ed98f0778b130555efe` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/nodes/conftest.py` | `5efe0ef0510816c884b4ae09930fadeabd058eb8dfb16b1f3e281fdd5096d9b7` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/nodes/test_data_plane_gate_node.py` | `604ba9eac651b49e76b0eae8dde8a151fff48d67e2022efc27984419339bf70c` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/test_enrich_knowledge_node_freshness.py` | `9da09db08079f6bbe25926c98d0dd39e77716e10a207de89dd082755b4509c8c` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/test_legal_check_node.py` | `5db5353f9ba0ca98344c1b3d7465267cd6c4e25661c41def2347313c9c471eaa` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/nodes/test_run_simulation_feedback_overrides.py` | `0e2d11c6029b3ec4644b6fb8823168936d6237824eef93c55d0d3a25d791bbfa` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/engine/locks/test_fcntl_lock.py` | `7b121bb67189c8112f941a9253116b7e613497832074b35d6440545f7419af6e` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/locks/test_lock_metrics.py` | `34dcf2294feb67824caf439633c0b0d5530ff1837b69a0a81f415675df1b6c18` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/locks/test_redis_lock.py` | `c67f134d64981a1a1dd3dd478b0dc1ae0547d0b7a9040adfd92364c35efaef3d` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/runner/test_config.py` | `e5bec1a16aec2acd86fa69ffd5dc0433d9dc269edec89e717f9cbabe7f984f12` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/engine/runner/test_fallback_runner.py` | `46ebf470762385b9f511379e1510e5c10d2455152081999b4c5d14ffd5b2dbc5` | `hold-import-statement-grouping-change` |
| `policy-engine/tests/unit/scientist/orchestration/engine/runner/test_health_check.py` | `ddf2c74b0af04162d5dba38b4a608796dcf004a3bed2a4c5a69ae9d8eab4b794` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/runner/test_task_router.py` | `cd2a41ff8e8883ebd413f9331b8d049411b36a29277edc12884e60271a279b17` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/runner/test_worker_pool.py` | `0d050ff03c7d104d73ddb133a522f5b8c7bf0f248c2e64a5e09ef94b623d7d79` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_budget.py` | `fed7ad30c7621dab538ae552b5bcb557c56be2eff0b5e4cf325022dcb19690d4` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_checkpoint_gc.py` | `c283ee687bd7722b02d4e02793daac83504410f6f816cd21a8fc9b9641f24ee9` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_circuit_breaker.py` | `19fdaec33d56a6082e9eb5354af176810d0f4d90902bbfd312e61af0b5d33a94` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_condition.py` | `1cf1b22059dc727327e08df3a467b5158ed93be533983cde039b91d492a66df3` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_condition_compound.py` | `d5c4a16c6052fc90a56399142e1ea76a292810ce947b8f5256f70ecd0cd447d4` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_conditional_workflow.py` | `4437bddc311ac0c1d0016e31c5e482019adf7c76be35fb7b9ef0241ebd2a5785` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_convergence.py` | `0bcc447c3bb51727651098248a956d18491b3fb2313342798c2181bbc1d016a4` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_convergence_semantic.py` | `a49b1d1d30b655fedab519da2b64f7b6f20da901b9a0caacffad0d1d2c303cd2` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_engine_executor_v0.py` | `dda15c9f26f300918e54fa7db01a8cb3512450b3616c5a6671c0ad567b0a645c` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_engine_registry_v0.py` | `7654acfb9009a9e062eead0de9dd9d205c363b6d3a7570d0fd59860d0d964608` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_executor_metrics.py` | `3092cef8a6974529d5889c599c80d3af16a361a9f1c9270dfa46d3e0def8f280` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_fan_out.py` | `0765ac2bcbecfc71307c6cce752fe7ac3aa7f765a8a0d87f4f21ba81556f10b4` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_fan_out_async.py` | `cec0bdef5fa65d2d97633c9ea7204ca39fe02c1e629339a15ce2a34e99a293f9` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_iteration_state_machine.py` | `1f86a320f937312830793e7fa66cc5a02cc20a689a5fecc2ec46b9f83cc58220` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_metrics_slo.py` | `6e8235afdad196b806e56a4c3c72d71f205ac0f2c1bd63b3d6eaed453c52b0d3` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_node_registry_components_bootstrap.py` | `38acab83415cb17025ece98266aa6356cf26d13ce17c91da5267c4f8441d3337` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_reliability_operational_evidence.py` | `6ab236b2adc0cf7880f823dc3a4234b5673d4c221e46e2d97540aaf32e44f437` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_sub_workflow.py` | `17595a409fcfd5b12fc9f840e65cb8b9fab9e0459a4aeba15acb2dce4afa5c8b` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_tenant_isolation_e2e.py` | `2d0aaacb3dab74245024e5a8b6faa770c92c543d45a1a86a8669a48c78f18783` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/engine/test_topo_tiers.py` | `0285567599af51064acd9ac70bd67c093d3d78ff41307b787e8fb4e5e707a1a5` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/kernel/conftest.py` | `cc7ec0b667952e2efb63915697ee8f911fd1977adfd1015d0c2efa4fa0ff40c6` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/kernel/test_budgets.py` | `d4ca7b1d7184d5c616373bff9d877a951308e54b54e29666b057baffecdc77cf` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/kernel/test_fsm.py` | `36dfcd4c246982ac4c01c8b42f997bcdc1f6a4efdb5ce1ec6bbb5613d0359912` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/kernel/test_guards.py` | `4fa023270cde624910ffacc9f915201c6ff13eade36d5b934d0dce2d1feb5f1d` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/llm/test_budget_enforcer.py` | `b460b96f674b8ee8dcf70c768408f94d5acd1797cb549def13fc91a5fa2887e1` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/llm/test_cost_metrics.py` | `bef7aa0de4133162c63515a6614b47ff3492ddc7a668971e20ddd9b3f4fd6464` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/llm/test_fallback_router.py` | `c7e6b03e654c0d695638a63427b1f37fc6265893b300fd0e4d30bd825cfaee20` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/llm/test_llm_cycle_preflight.py` | `7a03e49b0830d0319b6a032ebc308043c037a5fc5a6cce0732adc481e79464cb` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/llm/test_streaming.py` | `1463a241bcc378be1e12415d25bd648b2e1acb9267d52fe590723e6414014c9f` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/memory/test_applicability.py` | `733dd289984671a9da21005350a8be6b146118d05fcdba38c7ef8d5c52ef1d5d` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/memory/test_consolidation.py` | `1e908ee249a7f8acca35ef7066452dd855a2d3f8974efe16cc18e961c7f4865b` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/memory/test_contamination.py` | `91a40ac1f986fa0a3eb46849c1b4e03834ebd8616cb8ce7846c04ee402ed95c3` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/orchestration/memory/test_retrieval.py` | `0e9f3006882230f0af068c77caee1d1663f83454b7206b92dd74ec81e1e38f34` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/workflows/test_engine_default_workflow_e1_7.py` | `a1cb8aea79d240e36f2d6e1e52daef922eb4b12806f94e897b0df6e0557694ae` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/workflows/test_engine_default_workflow_p8.py` | `748769cad9161b4e0dd77f134c66e5a2b6b7cabeefa4f5bfd27c19678a831549` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/workflows/test_workflow_selection.py` | `8ad3f34028f86f02a98c0ee437e65b331cfd5fb06c7ef805a9ae4f5c8899292c` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestration/workflows/test_workflow_selection_ext.py` | `097449888ee4aea975688f9dff18bd13061329370113e2423abb832febab6a92` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/orchestrator_v2/test_compatibility_contracts.py` | `099adb2f64ade0f02f43b31127ef2027cade5fa00aab93627cc75676c1a6a9a7` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/search/strategies/test_bayesian_adaptive.py` | `e595eecce3e87ed674a071513253f477fb450160326cb73b64d7eca92ba69788` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/search/strategies/test_ensemble_surrogate.py` | `44b7b6179960a322db4e8d9952a651f7bda8bc312b9ec3852ac58ddaeb56cfd1` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/search/strategies/test_multi_objective.py` | `83900905e60873525ccc2f1b6bebe4f150ca813a176eb5380a200d62c5146c1b` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/search/strategies/test_random_grid.py` | `5383828824ee1551c1d09afbd24c1628672aedf96ea63ceab355d4bfa7e232be` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/search/strategies/test_space_codec.py` | `b09216e4e46354a227ab3ef0dd09a734468213c9666e695425e02b59333a6f6d` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/search/test_adversarial.py` | `d1698de96c3aed729b1670b542e6fca75f4257b342c50b10766adb933b476b21` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/search/test_cost_stopping.py` | `5be71426a16abb77d196a1a9bd82371266368fb3baa559a1a8cdc166ab519a5f` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/search/test_diversity.py` | `70de44593c77f8d6d771b490cc637af4f6d0e3cd5db5a0c9bfbe98f77980e2c9` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/search/test_latent_governance.py` | `3932b76320181ea777dbf099276a2abb0a53688b6e610f554279711eb84f596c` | `proposal-format-only` |
| `policy-engine/tests/unit/scientist/search/test_pareto_transfer.py` | `2d9588023559d94c178e9e71ce93d450eed00809349b2de1e9b6d5b0febaf84b` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/search/test_promotion_evidence.py` | `cb2d87d0f1f54660f2c52447cb2f9ad4d0df8a759e5faa0cdf9432b4a1ffbb7a` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/search/test_voi_models.py` | `f80b4a5c8dea482675cbb86ecc394d6d645d994cde82f0204a289dd1d2ce15f4` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/search/test_voi_reports.py` | `cd0d8e11e1683066b692b9ac1f5fe5d691da842224ae84d446cf4d456b6d4513` | `hold-import-atom-order-change` |
| `policy-engine/tests/unit/scientist/validation/test_metric_validation_benchmarks.py` | `a07da043d4974517f9f7ccec02d9025387aa91be56fe8c9753396a7780f5224c` | `proposal-format-only` |
| `policy-engine/tests/unit/security/test_policyos_runtime_abuse_gates.py` | `88a2c7ad5e5505cdb95da812c767b7bf7a0eddeda8f706eed4b093e357798c53` | `hold-import-atom-order-change` |
| `policy-engine/tools/archive/migrate_to_trinity.py` | `7376bd594c637bae7962a2ba7cc73ac2fe48cc1268b1b85cb191ef058279cd9e` | `hold-import-atom-order-change` |
| `policy-engine/tools/ci/check_scientist_best_in_class_phase1_3.py` | `fa362e9fbddd08e5456f334c724a0c28b581ef57e4f46d0888f42311e9a79ecd` | `hold-import-atom-order-change` |
| `policy-engine/tools/ci/check_scientist_best_in_class_phase1_4.py` | `afa01103c57b5bf702e8b0f81289d3e61b9411d4fcdcb4bd18e578edb5d50b61` | `proposal-format-only` |
| `policy-engine/tools/ci/check_scientist_best_in_class_phase2_0.py` | `03011e72637bfaba40cc80d18d5198f04b2351551d1ad4c376eab0fe54dc8880` | `hold-import-atom-order-change` |
| `policy-engine/tools/ci/check_scientist_best_in_class_phase2_3.py` | `e6739e1985c0ea71d9cf4b034ff19280c41fc3701713da8965a170bc8e35b16a` | `hold-import-atom-order-change` |
| `policy-engine/tools/ci/check_scientist_best_in_class_phase2_4.py` | `cc930b1e68b2700072e1a87c318e21cb820b5029c132fac6659c278436baac38` | `hold-import-atom-order-change` |
| `policy-engine/tools/ci/check_scientist_best_in_class_phase2_6.py` | `4e9af1ad93a746636a8b9b2c53a5eca0a18228387a0cf5994cf8909342aeb406` | `hold-import-atom-order-change` |
| `policy-engine/tools/ops_runners/experiments/run_msme_discovery_addendum_20260501.py` | `77ce2bd4606876dbc34ceaf09cc180b5474681be86576d55d4f29dd9bed19632` | `proposal-format-only` |
| `policy-engine/tools/ops_runners/experiments/run_msme_final_fresg_suite_v3.py` | `07a9d4d94c478895d0763079c9686006f5e7c5eaa9268ec68337b333af93558d` | `hold-import-atom-order-change` |
| `policy-engine/tools/ops_runners/experiments/run_msme_grand_tournament_v2.py` | `3557b4bd089130b33a2dbb698438156d275f2ceb15f7922d26f0b9f6eedd5afa` | `hold-import-atom-order-change` |
| `policy-engine/tools/ops_runners/runtime/run_canary_matrix.py` | `7734d98c28560d0d9670f33db21b17bb2a097c8fc0cb186888ebf1cdcf8e3b04` | `hold-import-atom-order-change` |
| `policy-engine/tools/ops_runners/ukraine_data/build_edr_identity_seed_candidates.py` | `6077f99966c026b94cbf4d1a8592684553e45c2c234d3adf813a87f4cb325270` | `proposal-format-only` |
| `policy-engine/tools/ops_runners/ukraine_data/pre_shard_lex_corpus.py` | `3aa7512433d929ef1d3661d6311b41fdc34126cf042d5ba230cc20b034e4a4f1` | `proposal-format-only` |
| `policy-engine/tools/quality/diagnostics/check_setup.py` | `30dc443f37ba7e55a6cd37ec4854b1db25c91064163e0ddf16062c02abe76a80` | `hold-import-atom-order-change` |
| `policy-engine/tools/quality/diagnostics/check_udf_perf.py` | `6436ed29dce8b3184563841f49be23a938546cea0a7250f4cd106312f1cff1d5` | `hold-import-atom-order-change` |
| `policy-engine/tools/quality/validation/check_policy_design_case_layer2_s1_graded_outcomes.py` | `5b719c36b547cd781506e0abbf121da07eec5d0d040bfa764662301a49ad5a69` | `hold-import-atom-order-change` |
| `policy-engine/tools/quality/validation/check_policy_design_case_pass1b_hardening.py` | `3373b56e300c9847eac1df2dec6ac9b95f36abed255b865a2c743f95ef345250` | `hold-import-atom-order-change` |
| `policy-engine/tools/quality/validation/fabric_decision_data_coverage.py` | `da9b7fc793a04c9d6f3157f1be95d263313ab45c21279ef976f63076ab164afd` | `proposal-format-only` |
| `policy-engine/tools/quality/validation/run_universal_compilation_integration_realism_check.py` | `6b857a48327a0506b847f1c2bf34ef86f14bd6773f6c3f6ec45e754577d53a38` | `proposal-format-only` |
