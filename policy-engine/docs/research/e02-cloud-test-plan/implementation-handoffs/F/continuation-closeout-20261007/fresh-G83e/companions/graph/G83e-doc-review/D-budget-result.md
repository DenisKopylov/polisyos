# Exact-680 owner-budget factory check

## Result

The entire current-candidate `test_service_owner_budget_factory.py` file passed: **10 passed, 0 failed, 0 errors, 0 skipped** on implementation `68070854bddba2593efaef59a107a3cbe3b08d4d` / tree `459895cbc549d8f4b6c8fd38510f5ab2cb690c4e`. It exercises the actual native SearchLoop factory, TextGateway response, budget enforcer/ledger, persisted CAS checkpoint, fresh-reader restore/resume, and an owner change after ask preflight. Coverage includes true zero and paid snapshots on two budget keys, cutoff refusal, positive and negative `1e-1000` unresolved settlement, actual owner change, and refusal to resume under changed key/limit.

The deciding JUnit is `results/owner-budget-factory.attempt-02.junit.xml` (SHA-256 `a540cfc627c54d2e133fd29598f6638cc2103f082e5261969b856ee2aa285a08`). Full stdout and stderr are retained beside it. The run reported six non-fatal harness warnings (two pytest-asyncio ini options and four async marks) because plugin autoload was disabled; the imported TextGateway helper defines but does not collect those async tests. Pytest reported 7.809 seconds; total wall time was 11.777 seconds; sampled process peak RSS was 554,800 KiB.

## Source and runtime identity

The test ran from the isolated archive closure at `policy-engine/_build/e02-g-continuation-20261006/R/incoming-20261007-1146/I/D-budget-local/checkout/policy-engine`. Its source/test/config manifest contains 2,926 tracked files (55,426,610 bytes), extracted from the exact Git candidate. All 2,926 file hashes and modes matched before and after the run. The changed test itself is `policy-engine/tests/unit/scientist/methods/search/test_service_owner_budget_factory.py` with Git blob `a0aea243679bf00941607134cc21990b4e2d5e0f` and SHA-256 `922009de411b72438d0e05f6dd7c82e984e2db0a9d995e0f8833b3b0a756889f`.

The reused G Python 3.14.3 environment has an editable-install `.pth` that adds the live checkout to `sys.path`; the runner removed the live product root and source entries, used the isolated candidate as cwd and import path, disabled external pytest plugin autoload, and enabled a candidate-only Polisyos import guard. All 833 loaded `polisyos` module origins were under the candidate and byte-matched candidate Git blobs; there were no origin mismatches. Project test `conftest.py` and its explicit helper plugins remained active. The selected installed package versions and actual paths are recorded in `environment-readback.json` and `polisyos-origins-attempt-02.json`. The 174 installed distribution names/versions are preserved in `dependency-inventory.json` via read-only `importlib.metadata`. `pip freeze` was unavailable because this uv-managed venv has no `pip` module; no installation was attempted. No dependencies were installed and no production data was used.

## Harness-input correction

Attempt 1 also collected 10 cases but JUnit showed four passes and six failures. Each failure was the same `FileNotFoundError` while the candidate runtime imported `dependency_authority.py` and loaded the digest-domain registry during fresh restore/resume. The missing tracked input was `policy-engine/architecture/production_quality/method_catalog_dependency_digest_domains.toml`; those six failures were caused by an incomplete test archive, not assertion failures. The first attempt’s complete outputs and source origins are preserved.

I recorded one bounded harness repair and added only that exact-680 Git blob (38,632 bytes; SHA-256 `186078f2cd5c24cdef007449109d5667f60f4f7949c9b663026e5658e538bb5b`) to the isolated closure. A staging-path preflight caught the first placement one directory too high before rerunning tests; the misplaced copy is preserved at `results/repair-01-misplaced-config-copy.toml`, and the correctly placed candidate file is hash-bound in the repaired source manifest. The permitted single rerun then passed. See `results/harness-repair-01.md` and `.json`.

## Limits

This closes the current-candidate positive receipt gap for this specific 10-case file. It does not establish broad regression, production-data behavior, unrelated backends, or overall E02 finding closure. The G integration checkout remained attached to `codex/e02-integration` at `855cb26a7a2c9fea60356663cf81e7d01e20c738` with a clean tracked status throughout.
