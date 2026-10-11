# Independent delta review — native release schema v3

This final delta review binds only to the exact v3 patch below. It supersedes the v2 P29 hold for the root `change_class` semantic test. It is not G acceptance, release publication, or formal finding adjudication.

## Exact binding

- Source base: branch `codex/e02-unified-local-20261009`, HEAD `2ace03593a28a6bb5cc4688602fc731444f7408f`, tree `65f35862c296933b8507ab65c32dd041678b642b`, parent `0390c44e7f9871122c21afa78af844cbafaa1d0e`.
- Patch: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-release-schema-final-v3-20261011/native-release-fragment-schema-final-v3.patch` @ SHA-256 `0d0e537f54d0c68d1d56b1ed9ec6f3a29dc9e70218357d79e9d56ffa7e672478`.
- Manifest @ SHA-256 `0d7e741eead87f9b075024ee5a7fd4740ec4933d73fbc4c0782b32ab00defc29`; all 21 preimages and overlay postimages match. `git apply --check --verbose` exits 0. Independent full output: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/independent-native-release-schema-v3-admission-20261011.txt` @ SHA-256 `922502d009cf12d973aae30694cebb54a1d46105eecc651c75bff60d0319d33e`.
- Relative to v2, the only product postimage changed is the release-gate test file; the new test now asserts `report["contract_errors"] == invalid_structured_class`. All other 20 paths and the source implementation are identical to the previously reviewed v2 patch.
- Retained checks: the focused overlay pytest output @ SHA-256 `ec1be28a8368a0f682a45d900463e98af84cd52be2a7316379c6ed8fb54223f6` shows 12 PASS. Configured Ruff output for both checker and test is `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` (“All checks passed!”); Python compile exits 0. Complete-source CLI output @ SHA-256 `c71ff24ac5a1d5973b586e26a7ff6c7082e893c2cffa96465fc6e9ccce2c927f` remains exit 1 with three public-surface review holds.

Prior review identities: v1 scoped review `.../LOCAL/reviews/native-release-schema-final-v1-independent-20261011.md` @ `fe40fb393eace7371db4fd12e4cd876c29fba933f544127d3be521a1f0121d2e`; v2 delta review `.../LOCAL/reviews/native-release-schema-final-v2-independent-delta-20261011.md` @ `467cd85301272713b31ebac4a40346b8fb774918f670efdfecd6ef66023535a7`. The v2 review’s one P29 finding is resolved by the v3 test assertion.

## Delta verdict

**GO for this scoped native release-fragment schema candidate.** The README now distinguishes non-authoritative top-level `change_class` prose from enum-gated `[[compatibility_change]].change_class`. The v3 test proves both halves in the actual code paths: composite root prose is rendered unchanged, while a malformed structured enum is rejected; exact comparison of the complete contract-error list means any added root-class rejection makes this test fail. The test now exercises the declared distinction instead of merely checking a filtered error.

The earlier schema review remains applicable: root required fields are checked against release policy with meaningful string/evidence shapes, normalized `type` must match both policy and the real renderer, and every recursively occurring generated-client status is checked against the policy enum. The source census covers the complete 184 direct active fragments and separately the 185 TOMLs in the complete release tree; it reports zero root required-field shape, generated-client enum, unsupported-type, or TOML parse errors after composition. The root prose census preserves all 19 historically non-enum values instead of remapping them. Its complete source artifacts are in `.../raw/native-release-schema-final-v3-20261011/census.json` @ SHA-256 `8246267afb6a6c5fd028c84d0b75db41ba2c0db84c0fedb7d091885f8d091ed2` and `.../root_change_class_census.json` @ SHA-256 `21d526ca6a8ede083e5ff73283b0dc2f92b45816d3a1ae0d1ba9bc1c6e18eb9b`.

This is only a source-level candidate GO. The native release CLI is still HOLD: its exit-1 report has three `public-surface-review` errors for C12, the S3 profile-bound ref, and the typed loader. Full composed native repo gates and any source freeze remain UNRUN/outside this delta review. The manifest declares `closure_ids: []`; this review closes no E02 finding.

No product file was edited by this reviewer. This v3 note is an immutable review artifact for the cited exact patch bytes.
