# Runtime Quality Contract Fixtures

Owner: `team-runtime-quality`
Consumer: `tests/repo_quality/tools/test_runtime_quality_contract_fixtures.py`

These fixtures freeze the Phase 0.2 contract examples for the honest
diagnostics substrate. Each JSON file is intentionally tiny and wraps a
contract-shaped `payload` with:

- `fixture_id`: equal to the filename stem;
- `contract_name`: the contract snapshot the payload targets;
- `expected_status`: one of `pass`, `rejected`, or `quarantined`;
- `expected_failure_code`: `null` for pass fixtures, typed for fail-closed
  fixtures;
- `hds_invariants`: ADR-backed semantics protected by the fixture.

Fixture filenames must encode the expected status by ending in
`_pass.json`, `_rejected.json`, or `_quarantined.json`.
