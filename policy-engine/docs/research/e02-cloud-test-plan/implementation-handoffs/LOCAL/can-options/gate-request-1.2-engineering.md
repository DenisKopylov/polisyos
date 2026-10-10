# GateRequest 1.2 selected-view engineering receipt

This is an implementation candidate for the pending G decision; it does not record formal schema/API acceptance. Root owns the generated ABI snapshots and public schema outputs.

The candidate request now carries a typed `selected_replay_refs` entry for every valid `ExperimentState.inputs` key. `ExperimentState.inputs` is declared `dict[str, ArtifactRef]`, so this remains an artifact-only binding. Malformed contracted replay refs stay explicit in `replay_summary.invalid_refs` and also receive canonical raw-JSON digests in that summary, binding the complete supplied JSON into request identity without typed-tag collisions. Equivalent JSON with reordered keys has the same digest; changing any malformed value changes the request and rejects a cached approval. Unrepresentable values, cycles, non-string object keys, and non-finite numbers refuse request creation. These digests are identity data only and do not confer artifact authority. Malformed non-replay values also fail closed rather than silently dropping from request identity. `None` profile digests remain absent and are not materialized.

Request IDs include the normalized request context and gate semantics under schema 1.2. The governance cache reads schema 1.1 requests but reissues from current inputs before decision admission. New state stores full typed request refs, and persisted decision lineage uses the existing profile-preserving `input_ref_from_artifact_ref()` bridge. The tests exercise an unchanged payload selected under two manifest profiles and verify that a change reissues the request and discards the prior approval.

The first five-file serial run had 39 passes and 3 failures. One was an `ArtifactID` cross-package comparison in the new binding assertion and was fixed by comparing canonical strings. Two assertions encoded the older replay-summary projection, which hid other missing optional refs. They now assert the full missing-ref list and preserve the malformed-present entry in `invalid_refs`; malformed-present and absent refs remain distinct. The pre-hardening five-file serial run passed all 42 tests; the follow-up malformed-input identity run passed all 43 tests.

The follow-up malformed-input identity batch is recorded as `invalid-identity-*`; its serial five-file suite passed 43 tests. Ruff formatting, canonical Ruff lint, C901, and `py_compile` pass. An earlier Ruff invocation using the wrong caller/config produced 333 findings and is retained as a nonreceipt; the canonical product-root command over the same nine Python files passed cleanly. The touched helper added no `ANN401` or C901 finding after decomposition.

Final verification (`final3-*` receipts for the prior batch and `invalid-identity-*` for this follow-up):

- Canonical `.venv/bin/python -m ruff check --config ruff.toml` and `ruff format --check` passed for all 9 changed Python source/test files.
- `py_compile` passed for the same 9 files.
- Ruff C901 check passed for the 4 changed source modules.
- Release-fragment TOML parsed successfully.
- The latest focused pytest run reported `43 passed, 2 warnings`; JUnit independently records 43 cases, zero failures, and zero errors. Warnings are Python 3.14 TorchScript deprecations plus xdist benchmark-disable notices.

Complete streams, JUnit, and source hash receipts are under `raw/gate-request-1.2/`. `invalid-identity-pre-test-source.sha256` and `invalid-identity-post-test-source.sha256` contain the 11-file hash manifest; all source hashes match. `invalid-identity-output.sha256` pins the final test and verification outputs. Earlier runs are retained separately and were not overwritten.

Canonical Ruff output SHA-256: `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` (`raw/gate-request-1.2/canonical-ruff-check.txt`).
