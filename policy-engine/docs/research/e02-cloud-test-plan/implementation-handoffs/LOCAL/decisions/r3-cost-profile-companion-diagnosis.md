# R3 retrieval-profile companion diagnosis

## Scope and evidence

This is a read-only diagnosis of the frozen R3 replay for source revision `13e411da` as identified by the parent task. I did not edit source or rerun tests. The captured composed run is under `LOCAL/raw/composed-mac-current-source-20261010/r3_monetary_and_history_get/`:

- `metadata.json` records the exact composed pytest command and complete output inventory; SHA-256 `3147d26008f1f2379ec1faae6b427a0f1a35d8c4aa9588a2313d0d231419b42b`.
- `junit.xml` SHA-256 `ce31708de021eadcdaa1fe2cba725d9d5215eb377b715ea125c433e340a59f25` records 161 passed, 1 failed, 2 warnings in 25.36 seconds.
- Captured standard output is `stdout.bin` (`2b966da263a3aaa0a0f28b64a60f202e7914117323c7b88864ac5558309bf7d1`); stderr is empty (`stderr.bin`, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).
- The sole failing selector is `tests/unit/runtime/http/test_nl_pipeline_cost_projection.py::test_simulated_nl_producer_costs_settle_and_capture_four_origins`. JUnit reports `RuntimeError: no_model_variant_completed:simulated-qwen: _FakeRetrievalService.resolve() got an unexpected keyword argument 'run_profile'`.

Relevant source hashes at diagnosis: `test_nl_pipeline_cost_projection.py` `50d578cd48e1a527642cce52d69f122a0ca4a47a969de18578677c4a901d1754`; `nl_pipeline.py` `aa5dcbbfaef0c17905b85d9dca6696fb6d7ac6b4f5501075d53d2e5aa1965142`; `fabric/retrieval/service.py` `db94b6159844b4adbf844c0e798a0e423c283ae10a5a3f510eff06ef7e3cf543`; `run_lifecycle.py` `4f941cd8b069020cc3d70bd4ac61f129d881c68d77e673278cea7d00265b5fd3`; `test_control_service_di.py` `a350618bae4942c3e2184ad6b801b0180f7ac05a84495072649dbc2c3b90faed`.

## Finding and P40 bucket

This is the same test-companion API-drift class at one shared fake, not a retrieval-property failure. `_FakeRetrievalService.resolve` at test lines 51–67 accepts only `request` (line 55). The ordinary production call passes the selected profile as a keyword even when it is `None`, so the helper throws before the simulated run can reach its cost assertions. The test’s outer `no_model_variant_completed` wrapper is not the cause; the underlying `TypeError` is captured verbatim in JUnit.

The production interface is explicit: `RetrievalService.resolve(request, *, run_profile: CatalogRunProfile | None = None)` at `src/polisyos/fabric/retrieval/service.py:310–320`. The NL pipeline builds `DataResolveRequest(..., catalog_run_profile=self._catalog_run_profile)` and calls `retrieval.resolve(..., run_profile=self._catalog_run_profile)` at `src/polisyos/runtime/http/services/control/nl_pipeline.py:5657–5670`. The public `data_resolve` path likewise computes the configured/requested selected profile and passes it by keyword at `run_lifecycle.py:3840–3865`. No production change is indicated.

## Fake and real consumers in the test module

- `test_simulated_nl_producer_costs_settle_and_capture_four_origins` replaces the `RetrievalService` constructor with `_FakeRetrievalService` (test line 287). This is the failing path; it exercises `_run_variant` and reaches `resolve` with `run_profile=None` under the current fixture configuration.
- `test_ordinary_nl_post_persists_and_serves_durable_cost_events_after_reopen` monkeypatches the real `RetrievalService.resolve` and `.execute_fetch_plans` with the same fake methods (lines 546–553). It passes in the captured run, but its selected execution path does not establish that the retrieval method was reached; its pass is not a profile-forwarding witness. Making the shared fake signature compatible will also prevent a latent sibling failure if that path reaches retrieval later.
- `test_workflow_report_ref_preserves_selected_profile_and_rejects_mismatch` does not use this fake. It tests selected `ArtifactRef` preservation only.
- The fake's `execute_fetch_plans(plans, persist_payload=False, allow_fallback=True)` at lines 69–84 accepts the currently used keywords and is not implicated. The real method has keyword-only `persist_payload` and `allow_fallback` at `service.py:519`; no companion mismatch is evidenced here.

A nearby existing control in `tests/unit/runtime/http/test_control_service_di.py:155–185` records configured `prod_full` forwarding through public `data_resolve` and verifies a conflicting `rest_backfill` request is rejected before retrieval. That selector was not part of this composed command. The inline cost test needs its own NL-consumer propagation assertion because the public method control does not exercise the `nl_pipeline.py` call site.

## Minimal repair and acceptance controls

Update the shared fake to mirror the production boundary, for example:

```python
def resolve(
    self,
    request: DataResolveRequest,
    *,
    run_profile: CatalogRunProfile | None = None,
) -> Any:
    self.resolve_profiles.append((request.catalog_run_profile, run_profile))
    assert request.catalog_run_profile == run_profile
    ...
```

For the four-origin cost test, configure a valid non-null `catalog_run_profile`, such as `prod_full`, on its `ControlRegistryProviders`, retain a reference to the fake via `service._retrieval`, and assert at least one observed pair is exactly `("prod_full", "prod_full")` (and all observed pairs match). This proves the selected profile reaches the actual NL retrieval seam instead of merely making the fake accept a keyword. Keep the existing reported-zero, estimated, unknown-null, reuse-zero/origin-link, and aggregate-null assertions unchanged. Preserve the separate existing conflict control; do not make the fake silently ignore or substitute the profile.

The smallest falsifier is a call with a request profile different from the keyword: the fake should reject the mismatch, matching the real `RetrievalService.resolve` rule, while the valid selected-profile case continues through the existing producer and four-origin assertions. No new profile enum, API DTO, or retrieval semantics are needed.

Pattern pass: P31 favors correcting the one shared fake interface used by both consumers rather than patching the call site; P38 does not support treating this as a cost-property failure because the captured underlying exception is a mismatched test-double signature; P40 bucket is same stale-fake API class, not a new runtime class. Acceptance is the focused test reaching and retaining all four producer cost origins while asserting exact profile forwarding, alongside existing profile-conflict refusal coverage.
