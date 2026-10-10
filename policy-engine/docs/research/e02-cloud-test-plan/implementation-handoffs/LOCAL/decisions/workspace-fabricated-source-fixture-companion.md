# Workspace fabricated-source fixture companion patch

Source base: `c4563fd4da93bf9cc06de3dc77554a8a0d117359`. The candidate includes the known 10-file WIP; the target test hash below is the current working-copy version. No source or test file was modified while preparing this patch artifact.

Target: `tests/unit/runtime/quality/test_workspace_loop.py` at SHA-256 `79bd68ce68927f8bc2f5488bb28361e843fde1ad0a43622f5a27a769d9201b68`.
Typed response model: `src/polisyos/data_forge/domains/catalog/knowledge/types.py` at SHA-256 `90bd4901c233e37c3136f8c094eacebfb0116378d43518719c542d4ff2f3a09e`.
Patch: `LOCAL/raw/workspace-fabricated-source-fixture-companion.patch`
Patch SHA-256: `61b7350f36efed1bce57a745ad03e4fd45f55e39478e089f92ff45b7e391e3f6`

The current fake row is a hand-written `FakeRecord` that does not satisfy the now-strict `DatasetSearchResult` consumed by `DatasetSearchResponse.from_result_rows`; intake fails before the intended source-contract property. The patch replaces only that row with a genuine `DatasetSearchResult` instance. It keeps the test's claimed World Bank source/tier/connector and vector status while leaving source dataset ID, variables, coverage, quality, and access at the typed model's incomplete defaults, so the real `MeasurementRootProducer` reaches `DataRequirementAdmissionGate` and the existing expected refusal. The test retains its no-CAS-write assertion. The distribution fake and production guards are unchanged.

P40: SAME_CLASS_DEEPER fixture escape. The remedy is the canonical typed row path, not a DTO relaxation or production special case. This candidate is patch-only and was not applied or test-run.
