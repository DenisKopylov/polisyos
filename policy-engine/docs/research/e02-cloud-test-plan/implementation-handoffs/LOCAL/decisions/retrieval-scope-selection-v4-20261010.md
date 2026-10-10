# Retrieval scope selection V4 — unapplied patch

State: **patch only; not applied; no tests run**. This revision incorporates the V3 independent finding that a fallback may select a different metric while remaining an alternate source for the parent request. It widens the shared predicate’s typed relationship rather than adding a fallback-only exception. V3 and earlier source slices remain unchanged.

## Source slice and exact footprint

Root reported the authorized candidate source advance as `f52809e8210714131f53c7b90bd53a9215c69d69`; this patch is based on the still-matching retrieval preimages from source slice `8aad335337e765dd70d901fe1bb14f7e50282475`. Exact preimage SHA-256:

- `src/polisyos/fabric/retrieval/service.py` — `db94b6159844b4adbf844c0e798a0e423c283ae10a5a3f510eff06ef7e3cf543`
- `tests/unit/fabric/test_retrieval_service_catalog.py` — `d46376ee4600f968e8f975a6192654dac09c952e7b7b711bd013e296d8d52ce0`
- `src/polisyos/data_forge/read_api/catalog.py` — `241945f6132ffaa41822d28bf994714009582387c321619354718297be87b255`
- `tests/unit/data_forge/read_api/test_catalog_graph_builders.py` — `d29d044900ca3c7fc494e42b3fdc7379b208039b89bd40f5afd42b958c61637b`
- `src/polisyos/fabric/retrieval/README.md` — `c8b04d2090acfbb12e486baba88cca32597c8a550f22ffb7ed3b67f55dc11b28`
- New release fragment: `release-fragments/unreleased/2026-10-10-fabric-catalog-scope-filtering.toml`
- V4 patch: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/retrieval-scope-selection-v4-20261010.patch` SHA-256 `e438bf4baf4d9dd05c4afef96cc4a476a36e325c3714ec2333c25d66629cd1a8`

The six-path footprint is unchanged from V3. It includes retrieval selection and its unit tests, the lazy catalog read_api export and its identity test, README, and one release fragment. No generated artifacts or duplicate normalizer are included.

## Selected target and request-scope relation

The shared filter distinguishes `catalog_metric_id` (the selected source target used for exact C05 catalog identity) from `request_metric_id` (the DataNeed occurrence whose scope governs that target). A primary plan/candidate uses the same metric for both. A fallback uses `fallback.metric_id` for the C05 source-target identity while inheriting `plan.metric_id` as the request-scope key. Thus a corrected-metric fallback cannot escape a known mismatch just because its target metric differs from the parent request. A target with no matching request occurrence is unverified, not compatible.

The filter still covers selected FastLane/catalog/ExploreLane plans, public candidates, and fallbacks. ExploreLane request scope is applied before public candidate/plan emission; raw local-index metadata is preserved, and the current source does not read selected results back from that index. The direct discovery endpoint remains a raw candidate-only surface with no executable plan or selected run-profile.

Identity admission requires a unique exact tuple from `reconciled_metric_binding_population`: catalog target metric, connector, request dataset, normalized optional profile, and a registered source admitted for the selected run profile. Metadata and ID spelling do not establish that relation. C05/profile and exact dataset-read refusals propagate.

Only definite country mismatch or disjoint time ranges are incompatible. Full containment is compatible; partial overlap and malformed/unknown supplied scope are unverified. Every same-metric DataNeed occurrence is considered; a target is removed only when all applicable occurrences are explicitly scoped and proven incompatible. Mixed scopes remain unverified because FetchPlan has no occurrence reference. No fetched-row scope, source truth, or scientific availability is claimed.

## Added discriminators (proposed, not executed)

The fallback regression sends the selected FastLane plan through `resolve()`, gives it a fallback with a different catalog metric, and pairs a fallback whose catalog coverage is incompatible in both geography and time with a compatible alternate-metric fallback. It asserts the incompatible fallback is removed and the compatible fallback remains. A second public `resolve()` control supplies no request occurrence for the selected plan and asserts an unverified warning instead of silently treating the fallback relation as compatible. Prior V3 mismatch, positive, ambiguity, C05 refusal, raw-index, identity-collision, and read_api identity controls remain in the patch. These are proposed tests, not receipts.

## P40 and bounded residual

Bucket: **SAME_CLASS_DEEPER**. The V3 escape is the same property quantity: a selected output can retain a target known incompatible with its request scope. The widened invariant now carries an explicit source-target/request-target relation across plans, candidates, and alternate-metric fallbacks, and treats unmatched request scope as unverified. The bounded residual remains missing DataNeed occurrence IDs in FetchPlan, so mixed same-metric scopes cannot be assigned to an individual occurrence. Falsifiers include the actual alternate-metric fallback mismatch/compatible pair, unmatched-request control, existing FastLane/catalog public-output checks, ExploreLane request controls, duplicate-scope cases, and C05/material-read refusals. Returned-row scope and scientific availability remain `not_established` / `surface_out_of_scope`.

Relevant patterns: P06, P31, P38, P40. Verification remains `verification_missing` pending root application, focused tests, and import-architecture review. No formal closure claim is made. The V4 diff was reconstructed in memory against exact preimages; Python AST and TOML parsing passed. No product files were written, and no tests, linters, or Git commands were run.
