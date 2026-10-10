# Independent delta review: retrieval scope selection v4

Result: **GO for application and focused verification**. This is a static review of the unapplied patch; it is not a runtime receipt, source acceptance, or G closure. No tests, linters, architecture gates, or Git commands were run.

## Exact inputs

- Patch `LOCAL/raw/retrieval-scope-selection-v4-20261010.patch` — SHA-256 `e438bf4baf4d9dd05c4afef96cc4a476a36e325c3714ec2333c25d66629cd1a8`.
- Decision note `LOCAL/decisions/retrieval-scope-selection-v4-20261010.md` — SHA-256 `0e92b62b53a637cb1257efd592aef17105758ac6f7671449195ecf16aaa4a9a6`.
- The five existing source/test preimages in the note match: retrieval service `db94b6159844b4adbf844c0e798a0e423c283ae10a5a3f510eff06ef7e3cf543`; retrieval unit tests `d46376ee4600f968e8f975a6192654dac09c952e7b7b711bd013e296d8d52ce0`; catalog read facade `241945f6132ffaa41822d28bf994714009582387c321619354718297be87b255`; facade tests `d29d044900ca3c7fc494e42b3fdc7379b208039b89bd40f5afd42b958c61637b`; retrieval README `c8b04d2090acfbb12e486baba88cca32597c8a550f22ffb7ed3b67f55dc11b28`.

## Delta finding resolved

The v3 alternate-metric fallback escape is closed at the shared predicate. `target_status` now takes separate `catalog_metric_id` and `request_metric_id`; primary plans/candidates use the same metric for both, while a fallback joins C05 using its effective metric and inherits the parent plan metric’s request occurrences. An unmatched request metric returns `unknown` with `request_scope_unmatched`, rather than silently returning `compatible`.

The added different-metric fallback regression passes through `RetrievalService.resolve()`. Its mismatching `metric.corrected` fallback resolves to a C05-style binding for UKR / 2020–2024 against the parent DEU / 2025 request and is removed; the compatible alternate-metric fallback remains. A separate unmatched-parent-scope control preserves the fallback as unverified. This is the minimal falsifier for the v3 finding and covers both sides of the relation.

## Prior blockers rechecked

- The shared predicate gates FastLane and catalog plans/candidates, ExploreLane request-scoped candidates before emission, and plan fallbacks. The mismatch tests assert both public `ResolveOutcome` lists are empty; the raw local index remains intact and is re-filtered on request resolution.
- Fabric uses the exact existing country normalizer through the lazy `data_forge.read_api.catalog` export, with an identity test; the direct domain import is gone.
- Duplicate-scope controls distinguish a genuinely mixed compatible/incompatible pair from the separate all-incompatible pair.
- Partial time overlap remains unverified, while only definite disjointness is incompatible. Reconciled C05 identity, registered source/run-profile admission, and reconciliation/exact-row refusals remain fail-closed in the inspected hunk.

## Scope and status

The remaining documented residual is unchanged: without a DataNeed occurrence ID, mixed same-metric request scopes cannot be assigned to individual targets and remain unverified. The alternate-fallback discriminator uses a focused C05-shaped fixture, not a new production authority claim. Root should now apply the exact patch and run the focused retrieval/facade tests, Ruff, and the import architecture gate; the real catalog route controls should be included in the composed replay. No formal G closure is proposed, and verification remains **UNRUN** until those receipts exist.
