# D public API and compatibility erratum

Read-only correction to `R/CD-stop-C4-a795-20261007/D-cost-AST-consumers.md/json`. The earlier report's statement that the facade/inventory stayed unchanged is accurate for the final D source delta, but should not be read as saying the entire candidate adds no root exports relative to current G or `main`.

## Exact comparison

Candidate: `a795967a80818a61fbc939a8d1b1ec8b0fca6477` (tree `2cd7e7058eeb0431b0571b30af3ad80b9a3c2668`). Current integration checkout: `9806442ddb47d624a2940bac75d9d6248e934c48`. `main`: `198076863e143dea9f89f02734b13d50dae3eed5`.

For each of `6c1729a7bc86cf90d443d73515d98dd4ebfa2894`, `4645738aee05809552e95aecb14d365793fc6bb2`, `9def216eda8aa02c61ec5a89e603627d47633a75`, and `3b31e136e5ccf9ee17ecb112e1f902cb0f95b0d2`, the diff to `a795...` is empty over `src/polisyos/scientist/__init__.py`, `architecture/public_surface/inventory.json`, `docs/reference/public-surface.md`, `architecture/public_surface/contract.toml`, and `docs/reference/generated-artifacts.md`. The final D test-only commit after `3b31...` does not alter those paths.

Within the five audited surface-companion paths, the comparison from current G or `main` to `a795...` changes these three paths: `src/polisyos/scientist/__init__.py`, `architecture/public_surface/inventory.json`, and `docs/reference/public-surface.md`. The candidate facade and inventory each have 42 exports; current G and `main` each have 39. The three additional stable fully qualified exports are:

- `polisyos.scientist.NativeSearchService`
- `polisyos.scientist.SearchServiceCheckpoint`
- `polisyos.scientist.SearchLoopRunner`

These were introduced by ancestor commit `5bd73d8d61f652e8628528bb9b49ef49c8e03a2a` (implementation, root lazy exports, and `2026-10-06-native-search-resume.toml`) and inventoried/documented by ancestor `5eca5d0df09f3296aefe20a0797aa14837da01ff`. Both are ancestors of each listed D product commit and of `a795...`, but neither is in current G `980...` or `main` `1980...`. Thus the prior 42-name candidate inventory reconciliation remains GO; the omission was the comparator boundary, not the 42-name identity result.

The independent inventory receipt is `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/continuation/public-inventory-independent-review.json@4a4475c78938883b45a59133fc7d4cfea410b064`. This review also parsed candidate `__all__` and confirmed the exact ordered 42-name match to the inventory list. This is static inventory evidence; no generator or full runtime API gate was run here.

## API and persistence boundary

The additive aliases are Python package exports, not HTTP endpoints. The two introducing commits touch no OpenAPI or generated-client artifact; their release metadata says `generated_client_compatibility = "not_applicable"`. No OpenAPI/client regeneration is indicated by this D surface delta, and no public DTO signature change was found in the reviewed changes.

Persisted compatibility has a separate, real behavior change. `2026-10-07-search-complete-history-resume.toml@a795...` classifies the format changes as internal, while its `service-required-history-admission` compatibility row explicitly names the stable public `NativeSearchService` alias alongside internal checkpoint profiles. That distinction is right: the alias/signature stays, while persisted restore refuses profiles without complete history validation. Its structured fields are `change_class = "runtime-state-format"`, `impact = "breaking"`, and `surface = "stable public NativeSearchService alias; internal checkpoint profiles"`; generated-client compatibility is not applicable.

Concrete format pointers in candidate source:

- `src/polisyos/scientist/methods/search/contracts.py`: `SearchServiceCheckpoint.schema_version` is literal `search-service.v2`.
- `src/polisyos/scientist/methods/search/strategies/adapter.py`: serialized `version = "strategy_adapter.v2"`, `history_digests`, and `consumed_history_count`; restore rejects unsupported versions and validates the consumed rows/cursor.
- `src/polisyos/scientist/methods/autotune/bayesian_generator.py`: `schema_version = "bayesian_candidate_generator.v3"`, `history_digests`, and `consumed_history_count`; restore binds the count to native optimizer iteration.
- `src/polisyos/scientist/methods/search/service.py`: persisted restore requires the generator history-validation callback before admission.

The compatibility guide is `docs/how-to/search-checkpoint-profile-compatibility.md@a795...`. Old/unsupported profiles are retained but refused; the documented paths are the original compatible reader or an explicitly new run, with no automatic migration. This is a breaking persisted-state/restore behavior for an existing public class, not a changed Python signature or wire schema. Keep it described as such rather than collapsing it into “internal only.”

No source changes, tests, installs, or refs were made. This erratum is ignored scratch for the parent to use in the append-only D pack/prompt correction.
