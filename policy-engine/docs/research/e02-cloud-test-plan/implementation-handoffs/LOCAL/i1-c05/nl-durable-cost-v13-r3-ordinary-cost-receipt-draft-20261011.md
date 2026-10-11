# NL ordinary POST durable-cost R3 receipt draft

Status: this is a bounded receipt for the selected ordinary-NL cost consumer path, not a formal closure or a production-monetary claim. The full R3 consumer/capability review remains pending.

## Deciding run

At source HEAD `978c7ed8c140c4d651b7d80f12c4470c8f9b0818`, the selected five-test run passed: **5 passed, 0 failed, 28.99 s pytest time** (48.559 s wrapper wall time). Exact source-bound command and complete output are retained here:

- `LOCAL/raw/batched-blocking-focused-20261010/s3-v20-emp-scan-nl-cost-v15-http-consumers-20261011/command.json` SHA-256 `d8aa9f22d141218b533d3c636d17a3253dae5fa0e34691a458f58014eca1e1ed`; recorded source HEAD `978c7ed8c140c4d651b7d80f12c4470c8f9b0818`, exit 0, wrapper wall 48.559 s.
- `stdout.txt` SHA-256 `f3792de64b96d87964f9ee0e5403570d6c1b22900be650a20e02600a91c40be2`; stderr is empty, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- `junit.xml` SHA-256 `3934273c6344ea2f702924be3c8334e8156b76c5b6abefa9e72401e846b9c08f2`.

The exact selectors were:
`test_artifact_inspector_resolves_exact_manifest_profile_for_all_views`,
`test_selected_manifest_lineage_preserves_each_input_profile`,
`test_selected_manifest_authority_controls_all_artifact_http_surfaces`,
`test_real_forecast_report_is_limited_in_fresh_diagnostic_http_view`, and
`test_ordinary_nl_post_persists_and_serves_durable_cost_events_after_reopen`.

The target test postimage is `tests/unit/runtime/http/test_nl_pipeline_cost_projection.py` SHA-256 `64cccf2fbf49f94f5a887890a3b014f40d5c8d985f9d706ca9a89bfa8d64e520`. The actual run recorded the same source snapshot before and after; `command.json` holds the complete source fingerprint map and command environment.

## Bound fixture and observed behavior

The target is a local simulated-provider witness, not real billing. The selected fixture's durable ledger contains seven `simulated-qwen` / `simulated_gateway` events with `cost_origin=reported`, `status=committed`, and explicit `amount=0.0`. These are known reported zero values from the configured simulation, not missing amounts coerced to zero. The test then adds one crash-after-begin event with `status=pending`, `cost_origin=unknown`, and no amount or receipt. Its ledger still reports `pipeline.cost_usd=null`.

The exact admitted binding persisted in all seven committed records and the pending record is:
- run `R_6bf9b54f58bb389a`;
- tenant `aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa`;
- cell `cell-a`;
- execution profile `dev`;
- control job `f5d065560c254e83b822fce0dafca922`;
- ledger key `nl-run:R_6bf9b54f58bb389a`.

The core run identifier in the HTTP route differs from the control-job-owned ledger run identifier; the test checks the binding joins through the persisted job and run details. It asserts unique event IDs, matching run binding, and same owner/profile/tenant/cell. After constructing a new `FileBudgetLedger` over the persisted file and binding that reader, the tampered-control-job probe returns no steps with `llm_producer_control_job_owner_not_established`. The fresh `GET /api/v1/runs/{core_run_id}/agents` then returns all seven committed events and the pending event, matching event ID, origin, status, durability, receipts, amount, digest, model, and provider against the ledger.

The retained fixture source files are:
- `fixtures/test_ordinary_nl_post_persists0/.polisyos/control_plane.sqlite3`: 200,704 bytes, SHA-256 `c168a7f87ddef18867f12a9dbc1a06bf294522a99f800f736140b761d3a571d8`;
- `fixtures/test_ordinary_nl_post_persists0/.polisyos/runs/.runtime/llm-cost-ledger.json`: 17,074 bytes, SHA-256 `028bb198e2917f9c93816c120e35e547751894fbf656fc59bd71cc0dd106ff3b`.

## Source boundary and residual

Relevant current source hashes: `tests/_helpers/runtime_http.py` `1a79ae8be843fe500d653cce92a4da4d17d2c43a8d6a2f21d659ff9c04586fcf`; `job_nl_admission.py` `304a8160f52a8c2e5ba181db154b1e843efe57e86e68eab65beeb1ea4fa2d63f`; `job_nl_execution.py` `3926d2c43b3ccec3bd9f4c71a46bb4d0981eb36705b270752415a0f8b88bcb8f`; `nl_pipeline.py` `9a1507fe29095553fa6c4780bd3d417ee1dd4fc42fd4c28b01b31250d09feb17`; `budget_ledger.py` `9c04d537d978797d91affdeea8d5c44cece0166a360f7ce4745cfdc1cf2b3036`; `budget_middleware.py` `2b39861329dd273d026cf46062d38f03af417fb3c0d3ce04e6103a8a97aed79c`; `debug.py` `0067f0d1c949b7a69525850ac7eb0d865ca7b8d4d0e3306cd1163c3f02acf24c`; `control_plane_store.py` `85a39db53d8502520fd7ee333df0e63df608f547aa4897dba0a054f76ba13888`; `routes/runs.py` `953ff42e3a0f4c16d12400317af37ee2d0dc2fe77b1f7fced9c194170406c52`; test `test_insights_api.py` `3097e5b3116d9083e2286451da7ef1b5dbfc8be15b45644f450d9a72b9fbc156`.

The test proves only the local simulated ordinary-POST → persisted ledger → reopened reader → fresh GET path and its owner-tamper refusal. The observed job remains candidate-only N4 (`candidate_limited`, `n4_proposal_only`); N5/N9 are `not_run`, currentness is `not_established`, and the typed Security report ref is unavailable. That is the correct route boundary, not Security evidence. The full-source Security positive remains separate and unproven. B10, B66, B67, and B68 remain **UNRUN as individual whole-property reviews** until the planned full R3 wave. No broader capability closure or external-production currentness follows from these five passes.
