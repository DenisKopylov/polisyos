# Independent review: R1214 ABM reference identity test successor

Verdict: **GO for root composition and the focused native verification wave**. The R1214 delta corrects the R1212 test-oracle defect by comparing the complete reference identity across distinct Core and IR ref classes. This does not claim runtime tests passed, publication readiness, G acceptance, or formal closure. The version-owner decision and generated schema/catalog outputs remain release blockers.

## Frozen identity and exact reconstruction

Candidate: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r1214-abm-cross-reference-test-oracle-successor-20261013/candidate.patch`, SHA-256 `b3d79b6b7f56df6565d24abd3390fdddf81fd6aecf44046eda9cf4cddb6003f3`.

Test-only delta: `...`, SHA-256 `89933c24b40ce65ffe244131f53e0a57fd70d2c528230c46b3b865d8aefd35f3`. Manifest: `...`, SHA-256 `0abf698ab33beef9722651b9b2cfdd1a54d0db9eeb878013498edc3925fcd35b`. Decision: `...`, SHA-256 `d6141a30fc12691ebf5be25a9602647dc9c4d79de88e253984512d0c269383a6`.

The qualified base is HEAD `691b0082846279f318c54a8e5618807a0d810698`, tree `eb4ab69bf76126a07a9585755aba68b7197ea75f`, frame R1210 SHA-256 `31687de984b4625c20d358d57b031ef44c6fff5c03e38095655ef23f2e8c1779`. Both files still match their recorded preimages. Strict in-memory reconstruction of the full patch matched both manifest postimages. Independently applying the test-only delta to the exact R1188 test postimage produced the same candidate test hash.

| Target | Current/preimage SHA-256 | Candidate postimage SHA-256 |
|---|---|---|
| `src/polisyos/ir/analytics/phase4_dynamics.py` | `1f87901cf69a44b480350dc896a18ed0340bcbbffa5e2505a14eadaa81a1f939` | `0f97b93e4ba07ac0b3b66aa1cd42906f61bf8257edf5d1f7e46a712103d617ec` |
| `tests/unit/foundry/methods/catalog/simulation/test_abm_receipt_strangle.py` | `7c51c0ca869a0c110b9567bba70366fb120df91fb3bd4a30f05080fd95bad354` | `c80f0821fb700e63ced99dcc2f8d37c2c0cf4acc35383b442812b2cfc37fec2c` |

The production postimage is byte-identical to R1188. The only new delta is the cross-reference assertion block in the test.

## Test-oracle correction

R1212 identified that direct Pydantic model equality was incompatible with the intended different Core and IR reference classes. R1214 now handles matching null refs separately and, for non-null refs, compares a normalized tuple of string artifact ID, kind, media type, and manifest_profile_sha256. It retains the assertion that the Core and IR concrete ref classes differ. This measures the complete selected reference identity while respecting the layer boundary.

The corrected assertion remains in the parameterized positive conversion-and-CAS test. The test first converts the Core fixture, persists the IR result, and freshly loads it; then it verifies loaded/result equality and the Core/IR wire payload before comparing the four identity fields. The three valid status/schema cases remain. The R1188 malformed status, schema/ref mismatch, wrong kind/media, and remove-the-basis-while-retaining-the-marker controls are unchanged because the isolated delta touches only the positive assertion block.

P40 classification: SAME_CLASS test-oracle repair. The previous issue was a proxy comparison across different model classes; R1214 widens that assertion to all four identity fields rather than adding a case-specific exception. P38 divergence is corrected for this test property.

## Release-draft review

The release draft `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r1214-abm-cross-reference-test-oracle-successor-20261013/release-fragment.draft.toml` has SHA-256 `44a218dbb1bc36ae9108eb39f5e567652e67bc16e8c33d95bc6c36ba49ea48f8`. It parses as TOML and contains every root field in `release-fragments/template.toml`. The referenced migration documents exist.

Its owner and version owner are team-ir, change class is persisted-artifact-format, and the two-minor-release deprecation window matches `MODULE_COMPATIBILITY[ir]` in `tools/quality/diagnostics/gen_schema.py` and the existing IR fragment pattern. Marking impact as breaking is supported: newly serialized fields can be rejected by older strict readers; the draft correctly says forward compatibility is not claimed and sequences reader rollout before writers. Migration docs are present. Empty runbook docs are consistent with the release gate, which requires a runbook for breaking runtime-state-format changes, not persisted-artifact-format changes. The surface is classified public-stable consistently with the current ABMResult root-facade catalog row; inventory review remains false rather than being self-attested.

The draft honestly leaves the version namespace unresolved: the catalog row currently says ABMResult 1.3, the bridge preserves Core SimulationResult.schema_version (which can be 1.4), and the outer ir.abm_result CAS schema version is 1.0. Its team-ir owner decision and generated snapshot/catalog review are still required before publication. I did not run the full release gate or schema generator, and the fragment is still a draft; this review does not supply an external approval or version decision.

## Static checks and limits

Both reconstructed postimages passed AST parsing and compile checks. Product-configured Ruff passed for each reconstructed file using product-root-relative stdin filenames: exit 0, output `[]`, SHA-256 `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`. The release TOML parsed successfully. No tests, runtime imports, generator, or product-source writes were performed.

Root should run the existing focused ABM and IR tests, schema generation/check, and the actual coupled producer regressions after composition. The positive CAS matrix is a typed Core-fixture-to-IR test; it is not itself a live Foundry execution-to-CAS test.

The source change remains virtual. Closure IDs: none.
