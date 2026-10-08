# A332 exact-candidate native check

Candidate: `332ba0b91e9a85774d48d101d4af86e3a3baf911` (`4e21c90467913c6dae1c85b84b8c7a42a1dc9124`), based on `2605d13916f4dd38f216419562c04718ba4c2028`. This is an independent, bounded G-local runtime receipt; code acceptance and finding closure remain separate decisions.

The selected export has 3,485 tracked entries (70,143,489 logical bytes), with source manifest SHA-256 `768ca5ca1f9a31211a7501b539caf09be09d08d817b2875e07cea3e56b149136`. It includes the complete tracked `policy-engine/tools` tree and the selected test/import closure. The isolated runner used the existing G venv, Python 3.14.3 / pytest 9.0.2, one numerical thread, no installs, and scrubbed production-data/common-credential variables. All tracked export files/modes remained exact. Each deciding run's candidate import audit had zero errors.

## Deciding results

| Selector | Result | Cases | Wall / peak sampled RSS | Evidence |
| --- | --- | ---: | ---: | --- |
| `test_direct_foundry_value_port_refuses_sparse_owner_profile` | PASS | 3 | 24.797 s / 1,072,224 KiB | `results/direct_sparse_owner_profile/receipt.json` |
| `test_default_cycle_preserves_simulation_only_result_and_history` | **FAIL on candidate** | 1 | 23.879 s / 1,086,864 KiB | `results/default_cycle_simulation_history/receipt.json` |
| `test_informative_voi_candidate_core_readback_and_preview_refusal` initial run | UNRUN: incomplete harness inputs | 1 attempted | 25.823 s / 1,100,880 KiB | `results/core_voi_projection/receipt.json` |
| Same Core selector, one authorized input-repair rerun | PASS | 1 | 25.718 s / 1,112,144 KiB | `results/core_voi_projection-repair1-registry/receipt.json` |

The original five-case wave therefore yielded three passes, one candidate failure, and one Core attempt that must be classified as harness-input error/UNRUN. The single authorized Core-only rerun passed, leaving four deciding passes and one candidate failure. The default-cycle failure is specific: `validate_generation_cycle_run_history(persisted)` returned `generation_cycle_historical_projection_mismatch` instead of the empty issue tuple expected by the test. No slice-base replay was made, so P41 attribution is not established.

## Core input correction

The initial export omitted `policy-engine/architecture/policy_design_case/layer3_gy_claim_dependency_field_registry.json`, a tracked file required by the pinned production factory. The exact candidate Git entry is mode `100644`, blob `a055f369d8cc40cc47ed4e85ab796a3acb2cba00`, 1,825 bytes, SHA-256 `1bdc2e1005b5ee2fc78cda31353b78dfe5447704445bb3238eb072cca1300deb`. It was added only to the ignored export; candidate source and G Git state were not changed. The loader reads this single fixed registry and checks its inline field rules against the candidate `ClaimRecord` model; no sibling registry files are referenced by that loader. The isolated rerun then passed 1/1 with 1,740 candidate module origins audited and zero origin errors.

The original Core pytest exit was 1, but it stopped at `claim_dependency_registry_missing` during app construction, before the test's deciding readback/refusal behavior. It is retained as raw harness evidence and is not counted as a product failure. The exact supplement and relevant tracked source blob IDs are in `results/core_voi_projection-repair1-source-supplement.json`.

Four earlier harness attempts are preserved under `results/summary-attempt*-harness-error.json`; they exposed origin-root and incomplete `tools.lib` closure issues and are not product evidence. The concise per-attempt classifications, exact commands, environment, integrity facts, and raw artifact hashes are in `native-receipt.json`. Full stdout, stderr, JUnit, origin audits, and runner receipts remain in their result directories.

The test run created only zero-byte runtime `root.lock` files in the isolated candidate and pytest temporary data under `/private/var/folders/zm/nt7795nd0djbxr7ctd5yl4p40000gn/T/pytest-of-deniskopylov/pytest-686`. Nothing was deleted or moved. Disk free at closeout was about 43 GiB.
