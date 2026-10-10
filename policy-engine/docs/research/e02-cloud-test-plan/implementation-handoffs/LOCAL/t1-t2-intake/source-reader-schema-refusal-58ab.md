# Source-reader missing-schema boundary

Baseline: `58ab0ac58c4c3901e518e344fcccef85d22639bb`, tree `227722f77f441e09c1d07112b972d4988e9aa691`.

The source reader already enforces the requested property in `src/polisyos/runtime/http/services/control/evaluation_safety.py`: a missing `artifact_schema` is included in the binding-mismatch predicate and raises `ValueError("promotion_source_artifact_binding_mismatch")`. The red came from the test double, which compared the `ArtifactID` passed by the reader with the original string returned by `_persist_job_payload`; it therefore returned the valid manifest instead of the malformed one.

The test-only repair is confined to `tests/unit/runtime/http/test_served_unknown_target_scope.py::test_eval_safety_source_reader_rejects_missing_artifact_schema_as_typed_error`. It first proves that the same reference reads successfully from the real CAS, then makes the wrapper match the reader's typed `ArtifactID` before supplying the manifest with a missing schema. The test now exercises the actual refusal path without changing source-reader behavior or weakening its assertion.

P38/P40 classification: this is a test-double identity proxy in the existing typed-reference fixture class, not a product validation gap. The distinction is now exercised at the fixture boundary with a valid same-reference control; no product-side selector coercion was introduced.

Verification:

- Initial exact selector reproduced the failure before the fixture repair: `Failed: DID NOT RAISE <class 'ValueError'>`.
- The missing-schema test and adjacent v1.0/v1.1 reader control both pass after repair. Full output: `receipts/pytest-source-reader-schema-refusal-58ab.txt`.
- Focused Ruff check passes. Full output: `receipts/ruff-source-reader-schema-refusal-58ab.txt`.
- The source reader module is unchanged. Current SHA-256: `b16167f664bf19725d8ecd542eff6de7a7bea554f56cab03b25ed488cc9b5e35`.
- Current test-file SHA-256: `b3e38bdca0ca57bbd6221570f8585eb2587456e029dc1bacd744b25eeb7c6b35`.
