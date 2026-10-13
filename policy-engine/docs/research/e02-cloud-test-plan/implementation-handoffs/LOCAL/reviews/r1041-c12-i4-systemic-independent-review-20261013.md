# R1041 — independent C12/I4 profile and serving review

Read-only source, contract, criterion, and existing-receipt review. This is not a G adjudication and grants no finding closures (`closure_ids=[]`).

## Decision

The current source shows two separate typed request paths: Catalog resolution carries a `CatalogRunProfile` through `DataResolveRequest`; Legal Lex search carries a frozen `LegalQueryGenerationIntentV1` snapshot through `LexSearchRequest`. The original I4 exit does not require a single DTO to contain both. I found no evidence that those requests must be coupled unless an actual caller needs them together.

R1042 demonstrates the bounded Legal leg in controlled fixtures. It does not demonstrate the Catalog public request/current-reader leg. Current source and tests contain a real Catalog fixture path and typed refusal expectations, but neither that Catalog test nor a profile-specific TestClient Catalog currentness test was executed in R1042 or this read-only review. The concrete next evidence step is a focused current-HEAD Catalog route/currentness run; it does not imply a source-code defect or justify inventing a combined DTO.

## Source and receipt boundary

I read the current checkout at branch `codex/e02-unified-local-20261009`, HEAD `9511169e1a7f6dbd4137de824905dfbff8992a3f`, tree `d6d48c83b5a60afdead8066253bc30cd216f5913`. The last supplied root source frame, `root-author-source-frame-r1055-20261013.json` (`dbb113c2a571de08e2cf89c0c9076f0cbe7e0f217964993101ad58c40cefff79`), is pinned to the earlier HEAD `226cedb822e6e242d861ea8c903c9b396375dd0e`. HEAD subsequently advanced to `9511169e1a7f6dbd4137de824905dfbff8992a3f` in the N6 producer-budget reconciliation commit, whose parent is `226cedb822e6e242d861ea8c903c9b396375dd0e`. Its shared `run_lifecycle.py` changes add producer-budget reconciliation elsewhere; I re-read the current `data_resolve` method at line 5329 and did not treat the old frame as current. This review binds the paths in its JSON manifest to the present source hashes and does not claim a repository-wide freeze.

R1042 is a historical run at HEAD `226cedb822e6e242d861ea8c903c9b396375dd0e`: 60 passed, 0 failed, 0 errors, 0 skipped over three test modules. It reports 6,216 source inputs stable during that command and 1,709 owned product modules. The command used deterministic synthetic encoders and controlled local fixtures. Its exact command and output hashes are cited in the JSON receipt. It is not a current-HEAD rerun or production-model/authority proof.

## Separate Catalog and Legal paths

**Catalog.** `DataResolveRequest` is strict and contains optional `CatalogRunProfile`. `/api/v1/control/data/resolve` accepts that request. `ControlPlaneService.data_resolve` validates request and server profiles, refuses conflicts with a typed 422, and forwards the selected profile. `RetrievalService` joins the selected profile to the open Catalog source identity and current publish receipt, requires producer profile-input coverage to be established, and checks the row’s profile ID before admitting a Catalog plan. Missing or unknown coverage is not promoted to currentness. `CatalogServingSourceSelection` is a separate app-level candidate path selector; selecting a path does not establish its currentness.

Existing test source includes a real Catalog fixture sent through `ControlPlaneService.data_resolve`: the selected `prod_full` profile returns the canonical WDI plan, and omitting it expects a typed `catalog_run_profile_unresolved` refusal. Other source tests cover server/profile conflict, malformed selection, currentness drift, coverage, and source selection. R1042 does not run these tests. The existing TestClient `data/resolve` test only checks a generic response shape, so the current evidence packet still lacks a profile-specific public-route-to-current-reader receipt.

**Legal.** The selected-profile endpoint reads the persisted selected fact generation and returns an immutable inventory snapshot. `LexSearchRequest` accepts that typed Legal intent, without a Catalog profile. The fresh Legal store checks that the intent’s generation ID and full canonical inventory bytes match the newly selected generation; it then checks current projected members, saved vector/index alignment, and the live encoder’s declared asset/device/dimension and rule identity before vector results. Missing, empty-present, malformed, stale, and unavailable profiles take text mode with typed refusal. R1042 includes producer-to-fresh-reader and actual HTTP vector/text tests for this controlled path.

## Original criterion coverage

The task map names five IDs and the historical ledger preserves six criterion occurrences because LA-046 has separate `REQ-01` and `ACQ-01` acceptance. Each is retained separately in the JSON manifest with its original source range and historical disposition.

- **LA-028 / DFK-02:** the typed source registry and shared profile/seed selection now feed the default batch and lazy module views. The retained batch YAML has the same current SHA as the canonical YAML, but the compatibility copy remains. Selection tests exist and were not run here. This is candidate source evidence, not a closure.
- **LA-032 / UDF-05:** the current demographic reader selects a whole new or legacy layout and refuses mixed, incomplete, ambiguous, or present-invalid members; source-inventory reader tests exist and were not run here. This is a separate historical-data property, not a Catalog/Legal DTO requirement.
- **LA-033 / REP-01:** the Runtime public exports lazily target the Scientist replay owner and the CLI uses that canonical target; the compatibility alias still exists. Its current lifecycle/import tests were not run here.
- **LA-040 / EMB-03:** R1042 exercises changed text for a reused ID, withdrawal, encoder/model/dimension and projection invalidation, selector refusal, fresh selected-generation intent, current member mismatch, and HTTP vector/text behavior. It is the only listed criterion with direct passing behavioral evidence in R1042; model and production semantics remain outside its fixture authority.
- **LA-046 / REQ-01:** current compiler source parses explicit profile identity/scope, rejects malformed/conflicting aliases, accepts `text` or `request`, and separates required constructs from candidate proposals. Generic compiler tests exist but were not run here and do not establish the actual N7 acquisition result.
- **LA-046 / ACQ-01:** the coverage ledger separately requires actual admitted N7 inputs to change the WMR; a resolver that only records the input is insufficient. Current N7 source passes a capability resolver, but this review did not trace or execute an admitted-input-to-WMR change. REQ-01 cannot close ACQ-01.

## Semantic boundary and next check

P37: Catalog profile selection is caller/server declared and validated; it is not currentness. The serving gate recomputes/join-checks current publish receipt, exact open-session database identity, established producer coverage, and profile membership. The Legal selected inventory/member/index relation is checked against fresh persisted bytes. Loaded encoder assets are recomputed, but that does not establish executable `encode` behavior.

P38 divergence is witnessed by the R1042 test `test_runtime_asset_provider_cannot_detect_same_asset_query_callable_swap`: it replaces the query encoder’s `encode` method while retaining measured assets; the reader accepts the asset profile and returns `entity-decoy` for query `target`. The implementation measures the model/assets, not the executable behavior. This is the same encoder-identity class one level deeper; the bounded residual is a trusted executable/code identity bound to the loaded encoder, which is absent from the inspected contract. Do not patch by enumerating callable sites. This limits semantic-vector correctness claims, not the narrower request/profile and currentness checks.

The bounded root next step is to run the existing real Catalog fixture through the profile-selected current reader on current HEAD, adding a route-level TestClient assertion only if the I4 public-surface acceptance requires that boundary. Include missing, malformed/conflicting profile and stale/unknown profile-input coverage controls. Do not use the Legal DTO as a carrier for Catalog selection unless an actual caller demonstrates that composition.

Pattern pass: P01/P02/P04/P05/P10/P12/P29/P31/P32/P37/P38/P40. The Legal controlled run crosses producer, persisted artifact, bridge, consumer, verification and HTTP surface; Catalog has a source-wired path and test source but the selected current public-route receipt is missing from R1042. Candidate evidence remains distinct from authority. R1041 ran no tests, imported no product modules, and changed no source, index, or Git state.

## Durable bindings

The JSON companion binds the exact canonical task/docs, original criterion spans, current source hashes, complete `.py` token-census denominator and match sets, R1042 deciding output references, current HEAD context, gate classification, limitations, and empty closure IDs.
