# Independent review — R3 skipped provider-preflight launch consumer

Verdict: **GO for this test-only candidate delta against the R6 virtual source postimage.** This is not a runtime receipt, accepted source checkpoint, or formal G closure; `closure_ids` remains empty. The root-owned composed runtime replay remains **UNRUN**.

## Identity and exact source basis

- Review worktree: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`, branch `codex/e02-unified-local-20261009`.
- Actual committed root at review readback: HEAD `c19e502ddfa9dec45e5de72b380003250a2d676c`, tree `995205c8ad00bdc57aad490a727f11887078fc46`, parent `022c70f26f5cdb3c9aa6c4af87dc13f7071a5064`.
- Candidate patch: `LOCAL/raw/r3-preflight-skipped-launch-consumer-v1-20261011/patch.diff` SHA-256 `cd5d46fb2b5c6fbc9ad48e1c6da97dba97d38ec6ce7a619cf347100bab96cf9e`; manifest SHA-256 `48285e28d60ff4c698fa1bb120b4c6f3ce3df16739422c3dc58c3a47d818e0dc`; source/test static receipt SHA-256 `c76a7ca9bc5525635b412467269f55c6cbd6515b0031434a1a70f4a2b34188cc`.
- R6 source patch: `LOCAL/raw/r3-preflight-producer-ledger-v4-r6-20261011/r3-preflight-producer-ledger-v4-r6.patch` SHA-256 `dbcbdfeb48cfd8df6072d6d6008fc3d2b247b36475c7b4908e0f59f716fd9ed2`; R6 manifest SHA-256 `e35c2b13df45625b9324183105e29a0a69cad21be21bc723b8cecc9a86c25cc7`.
- The candidate changes only `policy-engine/tests/unit/runtime/http/test_control_api.py`; exact target postimage SHA-256 is `3788cda45c3d1f27fdd8104a1f08ede18576215929d88531722585a19aa58c13`.

I independently checked all four R6 patch preimages against the committed c19 tree. All match. In a disposable temporary tree, `git apply --check` and application of R6 produced all four manifest postimage hashes; the candidate patch then passed `git apply --check` and produced its exact target postimage. Full deciding output is retained at `LOCAL/raw/r3-preflight-skipped-launch-consumer-independent-v1-20261011/replay.stdout.txt` (stderr is empty). The R6 manifest retains its historical `base_head=022c70f...`; its `run_lifecycle.py` preimage did not match that earlier commit but does match the new committed c19 tree. The earlier pre-commit mismatch and its resolution are recorded in `resolved-base-probe.txt`; root composition metadata should cite c19 as the actual source base without rewriting issued packets.

## Property reviewed

The test `TestLaunchNlRun.test_launch_nl_run_simulation_preflight_skipped_is_durable_refusal` calls the actual imported `run_provider_preflight` through the existing launch seam. It does not inject a `ProviderPreflightReport`. In the real producer, `POLISYOS_LLM_SIMULATION_MODE=true` yields `status=skipped`, a skipped `simulation_mode` check, and the precise reason `POLISYOS_LLM_SIMULATION_MODE is enabled` (provider verification source, lines 490–541). Fetch and completion-client sentinels make unexpected network access fail immediately.

On the R6 virtual lifecycle postimage, ordinary `POST /api/v1/control/runs/nl` uses the generic `status != "ok"` gate. The test requires a rejected launch; `GET /api/v1/control/jobs/{job_id}` must report a failed job at `provider_preflight`, include the durable report reference and the same producer report payload, and the pipeline sentinel must remain false. This crosses producer → route consumer → persisted job/progress → GET consumer, and protects the exact simulation skip case.

P40 bucket: **same existing non-ok status-gate class**, deeper by adding the genuine producer outcome `skipped`. It broadens coverage of the existing status predicate and introduces no status enum or special-case production branch. A bounded removal probe is stated in the manifest: narrowing the lifecycle predicate to `status == "failed"` would admit this `skipped` outcome and violate the rejection assertion. That mutation was reasoned from source, not executed.

## Checks and limits

The candidate static receipt records Ruff check, canonical Ruff format check, AST parse, and exact in-memory replay as PASS. I independently reproduced patch application and exact postimage hashes as described above. `pytest`, the full composed runtime test, server/GET execution, provider network checks outside sentinels, and the broader R6 suite are **UNRUN** by this reviewer; root must run the named test on the final composed source. No external provider, live currentness, or authority claim is established. No G closure is proposed.
