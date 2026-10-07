# Directory Health Dashboard

- Generated at: `2026-10-07T09:35:52+00:00`
- Contract: `architecture/policies/directory_health.toml`
- Mode: `fail_closed`
- Status: `failed`
- Directory contracts, tracked-file volume and local-document presence, fixture registrations, and the configured filesystem-residue scopes.
- Not measured: documentation substance, runtime behavior, fixture adequacy, or hosted CI. Tracked-file metrics exclude untracked/ignored contents; missing local roots are not inspected. Filesystem-residue checks use their separate on-disk scopes.
- Top-level path moves active: `False`
- Contract errors: 0
- Closure findings: 7
- Metric regressions: 4

## Metrics

| Metric | Value |
| --- | ---: |
| `archive_report_promotion_backlog` | 0 |
| `closure_data_only_pytest_count` | 0 |
| `closure_empty_ui_component_directory_count` | 0 |
| `closure_forbidden_lifecycle_commit_count` | 0 |
| `closure_forbidden_product_import_count` | 0 |
| `closure_non_product_init_count` | 6 |
| `closure_over_threshold_feature_without_owner_count` | 0 |
| `closure_phase_local_junk_count` | 0 |
| `closure_top_level_loose_file_count` | 0 |
| `closure_unregistered_frontend_fixture_count` | 0 |
| `closure_unregistered_generated_api_count` | 0 |
| `empty_directory_count_outside_ignored_roots` | 1 |
| `example_asset_count` | 45 |
| `golden_record_count` | 19 |
| `high_volume_subtree_documentation_coverage_percent` | 97.84 |
| `max_directory_depth` | 18 |
| `non_product_python_root_count` | 8 |
| `product_asset_count` | 15 |
| `source_local_residue_count` | 16 |
| `test_fixture_count` | 412 |
| `top_level_directory_contract_coverage_percent` | 95.24 |
| `undocumented_frontend_subtree_count` | 0 |

## Local Residue

| Class | Count |
| --- | ---: |
| `ambiguous_fixture_directories` | 0 |
| `examples_tutorial_assets` | 45 |
| `generated_benchmark_reports` | 0 |
| `golden_records` | 19 |
| `ignored_source_docs_schemas_tests` | 16 |
| `local_reports` | 0 |
| `product_seed_assets` | 15 |
| `source_adjacent_residue` | 1828 |
| `test_fixtures` | 412 |

## Product/Test Asset Counts

| Class | Count |
| --- | ---: |
| `examples_tutorial_assets` | 45 |
| `golden_records` | 19 |
| `product_seed_assets` | 15 |
| `test_fixtures` | 412 |

## Maximum Directory Depth By Root

| Root | Depth |
| --- | ---: |
| `.benchmarks` | 1 |
| `.cursor` | 2 |
| `.devcontainer` | 1 |
| `.polisyos-tools` | 1 |
| `.vscode` | 1 |
| `apps` | 8 |
| `architecture` | 7 |
| `benchmarks` | 3 |
| `data` | 2 |
| `design` | 2 |
| `docs` | 18 |
| `examples` | 5 |
| `ops` | 5 |
| `packages` | 4 |
| `release` | 1 |
| `release-fragments` | 2 |
| `schemas` | 3 |
| `src` | 7 |
| `tests` | 7 |
| `tools` | 5 |
| `vendor` | 2 |

## Largest Subtrees

| Subtree | Tracked files |
| --- | ---: |
| `docs` | 7231 |
| `docs/research` | 3841 |
| `docs/research/e02-cloud-test-plan` | 3443 |
| `tests` | 3306 |
| `src` | 2916 |
| `src/polisyos` | 2915 |
| `tests/unit` | 2410 |
| `docs/superpowers` | 2348 |
| `docs/superpowers/journals` | 2251 |
| `apps` | 1345 |

## Findings

- `report_only` `top-level-directory-contract` `.benchmarks`: top-level directory has no directory contract
- `blocker` `non-product-init-files` `docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261006/pr38-r2/owned-facade-author/postimage/policy-engine/src/polisyos/calibration/__init__.py`: __init__.py lives outside product and allowed non-product roots
- `blocker` `non-product-init-files` `docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261006/pr38-r2/owned-facade-author/postimage/policy-engine/src/polisyos/foundry/uncertainty/__init__.py`: __init__.py lives outside product and allowed non-product roots
- `blocker` `non-product-init-files` `docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261006/pr38-r2/owned-facade-independent/author-READY-inputs/postimage/policy-engine/src/polisyos/calibration/__init__.py`: __init__.py lives outside product and allowed non-product roots
- `blocker` `non-product-init-files` `docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261006/pr38-r2/owned-facade-independent/author-READY-inputs/postimage/policy-engine/src/polisyos/foundry/uncertainty/__init__.py`: __init__.py lives outside product and allowed non-product roots
- `blocker` `non-product-init-files` `docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261006/pr38-r2/owned-facade-independent/immutable-inputs/postimage/policy-engine/src/polisyos/calibration/__init__.py`: __init__.py lives outside product and allowed non-product roots
- `blocker` `non-product-init-files` `docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261006/pr38-r2/owned-facade-independent/immutable-inputs/postimage/policy-engine/src/polisyos/foundry/uncertainty/__init__.py`: __init__.py lives outside product and allowed non-product roots
- `blocker` `directory-health-regression` `top_level_directory_contract_coverage_percent`: metric decreased below baseline (observed=95.24 baseline=100.0)
- `blocker` `directory-health-regression` `high_volume_subtree_documentation_coverage_percent`: metric decreased below baseline (observed=97.84 baseline=100.0)
- `blocker` `directory-health-regression` `max_directory_depth`: metric increased above baseline (observed=18.0 baseline=10.0)
- `blocker` `directory-health-regression` `closure_non_product_init_count`: metric increased above baseline (observed=6.0 baseline=0.0)
