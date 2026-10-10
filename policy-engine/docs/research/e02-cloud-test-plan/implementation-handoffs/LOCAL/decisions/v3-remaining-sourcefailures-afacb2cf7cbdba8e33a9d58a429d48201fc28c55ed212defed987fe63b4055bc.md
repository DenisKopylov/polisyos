# Remaining four acquisition integration failures — patch-only diagnosis

## Decision boundary

The retained native run is the 22-test command recorded in `LOCAL/raw/v3-owned-producer-typed-http-verification-20261010/command.json`: exit 1, 18 passed and 4 failed in 76.148 s. Full stdout, stderr, and JUnit remain at that run path; their SHA-256 values are in `LOCAL/raw/v3-remaining-sourcefailures-20261010/patch-receipt.json`. This agent did not rerun tests or alter source. The only proposed source delta is the unapplied unified diff `LOCAL/raw/v3-remaining-sourcefailures-20261010/v3-remaining-sourcefailures.patch`.

## Findings and proposed bounded repair

1. `test_served_acquisition_selects_committed_human_authority_and_reopens_worker` reaches the real NL producer with the fiscal request retained in `read_failures.json`, but the producer job fails because the base `WorldModelRecord` is `bound`. The actual `derive_candidate_scenario_wmr` contract requires `authority_status == "limited"`; `build_world_model_record` has an existing `candidate_only` input that selects that status. The patch sets that argument only in this candidate fixture. It leaves the runtime admission check intact.

2. `test_active_dataforge_row_builds_limited_candidate_world_with_source_time_unknown` fails while persisting the existing `core.registry_bundle` artifact. The captured CAS intent has `owner: null`, no claims, and `status: pending`, while a committed owner-generation record for the same artifact names the correct tenant and `cell-a`. The test writes derived artifacts through the unscoped control-store facade. The patch obtains the existing explicit tenant/cell-scoped CAS view before those fixture writes; it does not touch CAS admission or ownership enforcement.

3–4. The two WDI-consumer failures are one `SAME_CLASS_DEEPER` root-selection/fixture-provisioning defect. `persist_wdi_route` receives no `generation_cycle_repo_root`, so recursive generation sees no local dataset catalog and returns `substrate_catalog_missing`; the later `RealValueOwnerGateway` also sees no `dataset_catalog.duckdb`. The WDI helper tries to add owner rows by monkeypatching an imported alias from `tests.unit...test_acquisition_authority`, but `_resolver` actually looks up `_baseline` in `tests._helpers.acquisition_production`; consequently neither its fixture catalog nor its SHA-bound root manifest is built for this route. The patch changes the monkeypatch to that actual helper module and makes its catalog builder idempotent for the same prepared path. It prepares one scratch repo at `tmp_path / "wdi" / "repo"` using the existing `_resolver` / `build_slice0_fixture_catalog_graph` recipe and `production_admission_inputs`, passes that exact root to the actual `persist_wdi_route`, and later reuses the same root through `make_wdi_port_case` and the real gateway. The existing root manifest binds the fixture catalog bytes by SHA; the fixture intentionally supplies no production bundle entry, so with the required catalog and owner files present the N5 path should reach its intended typed `production_data_bundle_missing` refusal. All writes stay under pytest's `_build` fixture root; no repository `production_data` is changed and no owner/gateway is mocked.

P40 classification: the N6 and N5/L1 consumer failures are the same root-binding class, one level deeper, so the proposed repair widens the fixture root contract across the producer and downstream consumers rather than adding a separate exception for each test.

## Exact patch footprint and evidence

The patch changes only:

- `tests/integration/core_runtime/test_acquisition_authority_served.py`
- `tests/integration/core_runtime/test_acquisition_world_growth_chain.py`

The exact input source hashes for these tests and their helper/runtime dependencies are recorded in `patch-receipt.json`. The diagnostic readback `read_failures.json` contains the four JUnit failure records, actual NL request, failed core artifact/trace reference, CAS intent and owner-generation evidence, and missing scratch-root files. Its input run artifacts are cited by path and hash; no copied source snapshot is included.

The next discriminating check is the existing 22-test command from `command.json`, after root reviews and applies the patch. Required outcomes are: the actual NL job completes; scoped registry artifacts persist without a pending ownerless intent; N5 refuses specifically for the missing bundle; and the real WDI gateway reads the selected owner-bound fixture catalog. This patch is not yet applied or verified, and these expected outcomes are not closure claims.
