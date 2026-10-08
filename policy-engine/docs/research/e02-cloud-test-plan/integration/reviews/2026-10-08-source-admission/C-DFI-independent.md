# Independent DFI delta review — C carry admission

**Verdict: HOLD the DFI resume-currentness claim on this candidate.** The new receipt correctly binds its listed checkpoint/ledger and DuckDB output basis, and the existing tests contain meaningful failure, retry, mutation, and benchmark-consumer scenarios. One selected runtime input is omitted: the resolved source profile and its execution policy. A same-ID profile change can therefore leave the receipt equal and preserve old completed shards.

## Exact source and footprint

The input was parsed from `policy-engine/_build/e02-g-continuation-20261006/R/next-intake-20261007-2018/C-carry-admission.json`. C's snapshot is `dac9d700fe684d5b4c0ae3fbcff66f5d05b2f6f2`. The reviewed base is `12190b1e8a25a6e9c2edc3b9c08f106e76ea5b63` (tree `fcfe8de3a6cbc0dd1c0df1d02b65cc2d7c1cee04`); candidate is `ab44166335130463178e65dfc29a252c96afe479` (tree `b1eaa06c81fae89d56ae467e8036d5923b886f3d`). Git confirms the base is an ancestor and the merge-base is `12190b1e8a25a6e9c2edc3b9c08f106e76ea5b63`.

The complete base-to-candidate Git diff has **30 paths**: 6 production Python modules, 1 test file, and 23 handoff/evidence companion paths (A=22, M=8). The full path/status/blob/size manifest is in the adjacent JSON.

- Production: `policy-engine/src/polisyos/data_forge/domains/catalog/batch/_core_sources_ingest_contracts.py`, `policy-engine/src/polisyos/data_forge/domains/catalog/batch/benchmark.py`, `policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources/api.py`, `policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources/registry.py`, `policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources/validators.py`, `policy-engine/src/polisyos/data_forge/domains/catalog/batch/pipeline.py`.
- Test: `policy-engine/tests/unit/remediation/test_dfi_03.py`.
- Companion paths: 22 evidence artifacts plus the updated DFI handoff JSON; these preserve earlier 158/29-case outputs, Ruff output, package/profile probes, wheel and installed-consumer evidence. Their recorded checks target `12190b1e8a25a6e9c2edc3b9c08f106e76ea5b63, 198076863e143dea9f89f02734b13d50dae3eed5, 4a9350bf3e43d1785ab7ff51b37da442e84aca8e`; none targets `ab441`.

The handoff JSON committed in `ab441` still names candidate tree `fcfe8de3a6cbc0dd1c0df1d02b65cc2d7c1cee04`, while the actual `ab441` tree is `b1eaa06c81fae89d56ae467e8036d5923b886f3d`. Its `implementation_commits` end at `12190b1e8a25a6e9c2edc3b9c08f106e76ea5b63`. Treat the old checks as prior-candidate evidence only; the carried delta has no final-candidate handoff/check receipt yet.

## Defect: receipt omits selected source-profile identity

`validators.py` builds `catalog_core_ingest_output` from `config.run_signature`, the planned work-package/terminal-ledger JSON, and hashed contents/schema of the inventoried catalog tables. A work package serializes its `profile_id`, but not the resolved `SourceProfile` or `SourceExecutionPolicy`. `config.run_signature` hashes the `DatasetBatchConfig`, source-registry YAML, and metrics map; it does not read the fabric source-profile registry.

That omission is material. The run path resolves a profile from `SourceProfileRegistry` into a connection configuration and an execution policy. Profiles contain `base_url` and transport/runtime fields, and the public registry permits replacing an existing profile ID. If the same profile ID now resolves to a new endpoint while the checkpoint, source-registry YAML, and DuckDB bytes stay fixed, `_build_core_output_receipt` recomputes the old digest. `_prepare_core_output_resume` takes its equality return, then the observation loop skips each completed shard. The benchmark consumer recomputes that same receipt and can treat the previous result as current/full-ready even though the selected profile changed.

This is a static source counterexample, not a runtime replay. The receipt predicate for profile-currentness is **not_established**; code tests `profile_id` and other serialized inputs, not the resolved profile content. This is a P37/P38 boundary issue: a typed, hash-bearing receipt is present, but its basis omits an actual producer input.

The smallest discriminator is a fixture-only pair: unchanged-profile control must permit resume; then replace the same profile ID with a different `base_url` and rerun with the old checkpoint/database. The changed-profile case must invalidate terminal shard reuse (and keep the benchmark partial until the fixture re-fetches) while the control stays reusable. A digest should bind selected, runtime-effective profile/policy fields without copying secrets; secret changes need a non-secret revision/reference or explicit invalidation. No live production endpoint, data, or external truth is needed.

## Existing test evidence and scope

The carried 26-case receipt is `policy-engine/_build/e02-g-continuation-20261006/R/cleanup-20261007/preserved/C-old/e02-c-catalog-20261006/.tmp/e02-C2/raw/catalog-delta-8dfa/dependent-tests.receipt.json`@`69564e834e1051cf2701b7f77b6ff00e4c78b42d8248ce03e877cbb38306e361`. It reports `pytest -q` exit 0 on `8dfa7f3c544461c0ff081861848fcc5d8523da5b` / tree `3eac9b5cf816e30f9c1bacc81d80e2dc75d81681`, whose second parent is `ab441`. The selector list is exact: three DFI selectors, one core-source alignment-audit test, the full `test_publish.py` file (12 named test functions at 8dfa), and four retrieval selectors. The source-worktree stdout path in the receipt is absent in this checkout, so its raw 26-case count/output cannot be recomputed here. The selectors exercise receipt invalidation for ledger/output/config changes and benchmark consumption; none changes a profile's content while keeping the profile ID fixed. This receipt is useful dependent behavior evidence, not an independent source review.

No tests were run for this review. No production data was read. No source, test, environment, or Git-ref changes were made. No E02 finding closure is asserted.

## Pattern pass

P37/P38 are the relevant risks. The target pattern is to make the currentness gate recompute every selected producer input that affects fetch semantics, then prove it with a same-ID profile-mutation adversary and unchanged control. Current status: `verification_missing` for this profile-boundary discriminator; source-profile currentness is not established.

G receipt-access qualification: the original source-worktree stdout locator above is absent locally. The independent CAT review resolves the committed alias at `51609922447716115c22287ac79c218d13cd9067`, verifies its 80 bytes against SHA-256 `64576d99c4cef913eb9b9bd4e5a096807fe2289f77eb08a67c7de2e43fc6349d`, and confirms the 26-case receipt. This resolves output transport only; it does not add a same-ID profile mutation test or remove the DFI source counterexample.
