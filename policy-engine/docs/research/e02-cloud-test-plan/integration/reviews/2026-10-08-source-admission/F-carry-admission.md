# F carried-source admission — 2026-10-07

**Disposition: bounded code GO for F candidate 852 in the proposed composition tree; whole-package/global quality remains a separate, unresolved gate.** This is source admission guidance, not a finding-closure decision.

## Identity and preservation

- Current G: `dac9d700fe684d5b4c0ae3fbcff66f5d05b2f6f2`, tree `9ae98d6f3ff63daff3a4ecf9f4e556de2ed3c1e0`.
- F candidate: `852cc3707bfc7dee132ec07a9ed5adcb5911fdf2`, tree `52fb13e9e12d80e4b1af5580f61d15310535e5e8`.
- The committed `merge-feasibility.json` records exit 0/no conflicts and composed tree `a1faa2717458f9bd330b566404ec1555c47817ac`.
- Read-only Git comparison found **zero product, tests, worker, or package-configuration differences between candidate 852 and the proposed composed tree**. Thus the candidate’s exact source/test blobs carry into that tree without an integration-side source delta.
- The accepted G/V11 executor is preserved by content as well as ancestry: `policy-engine/src/polisyos/scientist/orchestration/engine/executor.py` is blob `fe0aadf975873aa54d35008d5020b66c6c6778fa` in accepted commit `cb4c6b82ec55f131caa5604125fd04502f264a05`, current G, F candidate 852, and composed tree. The accepted V11 commit is an ancestor of current G and candidate 852.

## What is covered

The F35 carry is not just the latest nine-path patch. Source 519 is an ancestor of candidate 852 and is the indexed F35 product baseline; 8236 is an ancestor of 519. The committed independent F35 review set covers 35 original IDs / 17 bundles: 11 estimator criteria, 11 GCM/graph criteria, 11 migration criteria, and separate B214/B56 decisions. The source-bound wheel and rebuilt-sdist receipt at 519 reports 91/91 PASS for each, over the selected graph and installed-catalog consumers. The 8236 and 4ee receipts are narrower historical consumer evidence and transfer only where their exact source blobs remain unchanged.

Candidate 852’s later delta has its own independent exact-source review in `R/next-intake-20261007-2018/F-delta.md`. It records 38 native PASS, 17 installed-wheel PASS, real Method/Node/CAS/readback behavior, and property-removal controls. This supersedes the old 4ee MGraph-as-ADMG positive: that earlier positive is not evidence for the corrected reserved-`mgraph` profile. Candidate 852’s rebuilt-sdist profile is UNRUN.

The new bounded mechanism admits only an explicit, consistent DAG/ADMG profile and refuses a contradictory reserved MGraph contract before reconciliation side effects. The helper is shared by the method, Node, and fragment-composition paths. Requested reconciliation that cannot be applied to a PAG is retained as an explicit warning/limitation in the persisted report. The existing `report` output remains; `discovery_pipeline_report` is additive and tested through the real method/CAS reader. No DTO field or graph wire-schema version changes in this delta, and no package dependency/lock change is carried after source 519.

The 852 source-to-composition equality means these exact-source receipts remain applicable to the bounded graph mechanism in the proposed tree. No material consumer break was found in the carry comparison.

## Specific holds and non-blocking follow-ups

- **B214 remains limited:** the bounded refusal/profile gate does not define general PAG/CPDAG identification or authority semantics.
- **B56 remains limited/UNRUN:** the shared admitted-study budget still needs a real canonical Runtime/Scientist admission input and workload witness.
- **B212 test-body evidence is narrower than source evidence:** `tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py` has a changed producer/report/fresh-reader case that the F35 estimator review says was not established by the 91-case installed profile. Run that focused test under the supported Python 3.12 DoWhy profile before claiming that test body green. This is not a graph-profile blocker.
- `tests/unit/remediation/test_req_01_installed.py` was added by commit `5650b7aed7991606d62cd8510b377698a778ce39` after source 519. It is a test-only installed compiler consumer, not a causal runtime change, and it is outside the retained 91-case package profile and the 852 graph selectors. If G adopts its REQ-01 test claim, run that exact selector on the composed source; it does not block the bounded F graph code.
- The F35 source-519 audit records scanner `ERROR/-9` twice (5,957 configured paths, incomplete output), Ruff `FAIL103`, public-surface `FAIL38`, and a merge diff-check failure on two preserved raw-output whitespace lines. P41 remains `not_established`: do not label these inherited, and do not turn them into proof that every F unit is defective. They remain unresolved aggregate checks before claiming whole-package/global green. Run or reconcile them once against the frozen composed tree with the complete input denominator.
- A complete installed sdist witness for exact 852 and optional backend/production-data claims are not established. They are outside this bounded synthetic graph-property GO. Any generated public companion that is actually required can be reconciled by G after the accepted source freeze; this delta changes no typed DTO or graph schema.

## Actionable G path

1. Admit the exact 852 product tree into the append-only integration history using the recorded conflict-free composition; preserve the V11 executor blob above.
2. Record code acceptance for the bounded graph-profile/report behavior separately from B214/B56 and from all 35 finding dispositions. Carry the exact 38-native/17-installed-wheel receipts by their 852 source identity; do not reuse the superseded MGraph positive.
3. At the final composed-source freeze, run the one planned global quality/consumer wave and attribute its complete denominator under P41. Add the exact-source sdist or separate test follow-ups only where their claimed surface requires them; do not rerun the 519 unchanged 91-case profile absent an affected source/dependency delta.

Pattern boundary: P01/P02/P10/P29/P32/P37/P38/P40/P41. The property is typed unsupported-profile refusal plus honest report preservation; a marker-only graph-type check is not sufficient. The exact native and installed receipts exercise the method/Node/CAS consumers, while broad partial-graph semantics and global quality remain explicitly limited.
