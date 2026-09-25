# R14 — promotion-contract checker verdict

**Discrepancy.** A completed canonical owner replay can reject the frozen
promotion comparison epoch with `promotion_comparison_admission_manifest_drift`.
The old `--check` let that `ValueError` escape instead of returning a verdict.
The current frozen v5 owner-rule manifest/v6 receipts and live v7 manifest/v8
receipts do not satisfy either registered reissue predicate. This is an
unauthorized transition to report, not a reason to rewrite the governed
contract. The frozen artifact remains
`policy-engine/architecture/policy_design_case/layer3_gy_promotion_contract.json@sha256:0d159ddcf3a2174d4cf6bf32859cd93e70eacb6b2852ea000e636b5f1ecf8484`.

**Property and owner.** The canonical promotion owner decides whether the
frozen comparison can be reconciled with its live replay. The checker reports
`PASS`, `FAIL`, or `UNRUN` with the deciding inputs and limits of its
inspection. A typed owner refusal is `FAIL`; unavailable input or unexpected
replay failure is `UNRUN` (exit 2). A malformed frozen JSON file is `FAIL`
only for its parseability predicate. The `--write` and reissue predicates are
unchanged. The production caller is the governed GY promotion-contract
validation command; this repair makes its completed refusal observable.

| Check | Result | Receipt |
| --- | --- | --- |
| New focused verdict file | 7/7 pass, including missing input, parse-only failure, real v6→v8 owner refusal, replay UNRUN and byte-equal control | `/Users/deniskopylov/.codex/scratch/e02-r2-r14-integration-focused-20260925.junit.xml@sha256:fba8e2ced7a1c7f31b23221f90e9ce1a19dbc4a028786efbb2c98cb0e45988e1` |
| Standalone current `--check --output-format json` | exit 1, `FAIL`; `proof_input_strangle_drift` and typed `promotion_comparison_admission_manifest_drift` at `unauthorized_manifest_epoch_transition` | `/Users/deniskopylov/.codex/scratch/e02-r2-r14-integration-direct-20260925.json@sha256:e8688a0b84532ed78ceb2f5ee9041fc72f2a28b285fc3dc549156ca96f0aacdc` |
| Existing promotion-contract test file | 42 tests: 37 pass, 5 fail | `/Users/deniskopylov/.codex/scratch/e02-r2-r14-integration-existing-20260925.junit.xml@sha256:1977bdf3fb851de4c13157cec47d0e63c7769839dc6239a0eb1cceebaea92340` |
| Exact-parent replay of those five reds | 5/5 fail with the same issue codes on the unchanged checker at `f76231d1d1b48da2eada6ffd8f9fc4eee8d720f141782f4f3c200c76cc460d4d`; no new R14 pass→fail among the 42 current tests | `/Users/deniskopylov/.codex/scratch/e02-r2-r14-exact-parent-five-20260925.junit.xml@sha256:2b0bd513dec0c0dcc6ce4cd6318a44cef88369852af6d1705b523144e4b54c52` |
| Marker-preserving removal of the typed owner-refusal handler | the distinguishing test turns red: actual `UNRUN`/2 instead of `FAIL`/1; the exception type and issue-code markers remain | `/Users/deniskopylov/.codex/scratch/e02-r2-r14-removal-probe-20260925.junit.xml@sha256:01ab82cb4a5bd634c09228b2b5d8cd2b96fca555f7d2592a78400b961850a613`; mutant `/Users/deniskopylov/.codex/scratch/e02-r2-r14-removal-mutant-20260925.py@sha256:61e624989e3df318dc92e1b41742b70bc6686930f93a44e0ea1bd15ac259e417` |

The five inherited reds have two owners. The historical receipt test expects
`promotion_reissue_historical_receipt_incomplete`, while R3's stricter parser
returns `promotion_history_payload_not_lossless`; the promotion-history owner
must reconcile that diagnostic contract. Four frozen/live comparison tests
still expect an authorized epoch transition or a different refusal reason;
the promotion comparison owner must resolve those through its registered
reissue predicates and any required principal decision. This checker repair
does not restamp them. The standalone verdict's measured frozen-file SHA
matches the tracked artifact. Its scope says that full loaded-code, imports
and data-input coverage is not established. The four-base post-repair replay
of this pre-existing test file remains open.
After the removal probe, the checker was restored byte-exactly to
`policy-engine/tools/quality/validation/check_layer3_gy_promotion_contract.py@sha256:0e32259d5aef6d6ebf34cc23676c98a7716953a6e9b01c184043ce3fb30618a8`.

**P37/P38.** Frozen bytes and digest are measured; payload predicates and the
canonical owner's registered transition predicates are recomputed. The
complete loaded-code/import/data denominator is `not_established`, explicitly
reported. The intended gate is frozen-payload validity plus reconciliation
against one canonical owner replay in this checkout. The implementation
tests exactly those selected bytes and predicates. An unselected imported
module can change deployment identity without changing this selected result;
the checker makes no deployment-currentness claim.

Independent review was GO for the bounded `--check` path only:
`/Users/deniskopylov/.codex/scratch/e02-r2-r14-promotion-checker-v3-review-20260925.md@sha256:94b49dece6cc78654442226a553ba6bf5d576422bd63bc268eebb03b024ebfb1`.
Applied-delta review was also GO:
`/Users/deniskopylov/.codex/scratch/e02-r2-r14-applied-delta-review-20260925.md@sha256:03fac384378b7fcb9c7481c0a07c8a66cbb68f4cab70e7623a9ede023ba1d5cf`.
The review did not cover `--write`, rederive, corrupt, or mutation CLI modes.
