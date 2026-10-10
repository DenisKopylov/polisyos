# Independent governance native-delta review

## Finding bucket and scope

**P40: SAME class, at a deeper shared consumer boundary.** The five earlier governance failures were manifestations of one missing Core-CAS-to-IR-store adaptation. The implementation now widens that invariant once, in the generic resolver used by all six resolver consumers. I found no second distinct escape requiring a ladder of per-pass fixes. The paired module extraction is a separate size decomposition; within this review scope I found no authority/status/order change.

Reviewed the exact 9e02 base `9e02a9f49c8b01026327a9f7c7e18711b13a96f2` (tree `881a950dccb7cdefacc636515aa7dd2bceadf928`) and the ready worktree bytes for these five modules and six tests. Shared-tree HEAD remained at that base; current peer-authored contents were read by their exact hashes below. This review did not write product code, tests, configuration, or Git state. The author’s broader closeout packet is `LOCAL/decisions/governance-native-decomposition-9e02.md`; this note is independent evidence, not formal G adjudication.

## Runtime bridge assessment

`passes/_artifact_resolution.py` now calls the established `ensure_ir_artifact_store(store)` immediately before its generic `load_model` callback. It keeps `PassContext.state["_store"]` raw and changes no resolver error classification. This is the narrow correct boundary: normative, human-review, refutation, SUTVA, cross-graph, and equity consumers all use the helper; the Core-oriented confidence, incentive-compatibility, and calibration consumers continue to receive the Core CAS.

The new `test_artifact_resolution.py` uses an actual `FileSystemCAS`, persists a typed causal graph through the adapter, and reads it back through `resolve_optional_artifact_model`. Its negative controls cover wrong kind, unavailable selected-profile digest, corrupt payload, and absent optional ref. The six helper consumers have persisted-ref positives: normative produces no invalid/missing result issue, human review emits `HUMAN_REVIEW_REQUESTED` with the graph edge, refutation emits its expected strict blocker instead of invalid-artifact, SUTVA emits its risk issue, cross-graph emits its legal-prohibition issue, and the existing equity test reads a persisted report and emits its policy findings. These exercise producer → CAS → resolver → semantic consumer rather than only checking markers.

No global `_store` replacement was made. The test-control runs include the unchanged Core-based confidence pass and incentive-compatibility pass, so the repair preserves the distinct Core API path.

## Extraction and semantic-preservation assessment

The canonical `RunGovernanceNode` and `RunNormativeArbitrationNode` remain defined at their original module paths with the same component IDs and `NodeSpec` declarations. Existing gate/artifact helper names remain imported into the canonical modules under their former names. The moved functions retain their call signatures in the canonical import surface. The governance node’s `execute` body is now split into gate-input handling, governance-outcome resolution, claim projection, and phase-2 tail helpers. Comparing the original and extracted control flow shows the same precedence: an existing human gate remains dominant; blocker findings reject; normative results can select `needs_revision` or `approve` only outside `human_gate`/`reject`; claim projection can reject publication except when already held at `human_gate`; the phase-2 tail still rejects authority promotion while retaining `human_gate`.

The normative node retains the original `_SPEC` and `RunNormativeArbitrationNode` body. The extracted calculation paths preserve the original per-channel binding mapping, zero baseline, finite-value admission, missing-binding/uncertainty warnings, and policy rules. I compared the old implementations with the new helper logic: rights/hard-constraint precedence, numeric thresholds, selected option, rationale, and metrics are the same; the change factors policy summary and per-policy evaluation into helpers without changing those decisions.

The source-size count used here excludes blank and comment-only lines. All five reviewed implementation modules are within the 1,000-logical-line limit; both explicit Ruff C901-at-12 and formatting/lint checks passed. Full physical/logical counts:

| Module | Physical | Logical |
| --- | ---: | ---: |
| `run_governance.py` | 1,018 | 930 |
| `governance_gate_requests.py` | 451 | 404 |
| `run_normative_arbitration.py` | 630 | 583 |
| `normative_arbitration_calculations.py` | 706 | 618 |
| `passes/_artifact_resolution.py` | 172 | 152 |

## Fresh independent checks

All commands ran in the assigned candidate’s `policy-engine/` with its `.venv`; complete commands, outputs, and exit files are under `LOCAL/reviews/raw/governance-baseline-9e02/`.

- Exact six-file governance baseline, after the fix: **32 passed**, exit 0. `reviewer-post-fix-baseline.log` SHA-256 `138c854d0aae5cf5cc49974d4b775b8d7477e7d3ece107fdf8a81f3f288f62cc`.
- Resolver, all six helper consumers (including existing persisted equity coverage), and Core confidence pass: **53 passed**, exit 0. `reviewer-resolver-and-core-controls.log` SHA-256 `5145e2a762b8a7f260b72e71b22ad41c9ec80b9d66c95b22e3e9542584422dbd`.
- Incentive-compatibility and calibration-leaderboard controls: **9 passed**, exit 0. `reviewer-incentive-calibration-controls.log` SHA-256 `3beb72ba5fe66943b9e36171fd1fd59f23230cf5d821d50795ae27cde3035ee6`.
- Ruff check and format check over the five modules and six tests: exit 0. C901 at threshold 12 and `py_compile` over the five modules: exit 0. Their full outputs and commands are also retained in the raw directory.

The extra author-run confidence/calibration control batch has three failures whose immediate input causes are visible, but their P41 provenance is **not established**: I did not replay that exact batch against a pre-task base. They do not establish an escape in this five-module/six-test delta; they remain unresolved test-input observations and are not classified as inherited:

- `test_loaded_noncausal_simulation_preserves_supported_confidence_profile[True]` constructs an uncertainty envelope with metadata flags and a synthetic `sha256:ffff…` identification ref, but no content-bound draw ledger or trusted verifier receipt. The actual confidence admission refuses it with `CONFIDENCE_ENVELOPE_ADMISSION_LIMITED`. The assertion that a “healthy” flag alone yields no issue is unsupported by the fixture’s evidence; resolve with an admitted evidence fixture or assert the intended limitation.
- Two calibration-validation cases pass `_artifact_ref("a")` / `_artifact_ref("b")`, synthetic IDs `sha256:aaaa…` and `sha256:bbbb…` that were never persisted to the supplied CAS. Backtest input resolution correctly fails when the manifest cannot be loaded. These tests need real persisted candidate refs before they can assert full-run outcomes.

No full suite, heavy fit, native integration, or formal G acceptance was part of this review.

## Exact reviewed source/test hashes

```text
ec9cd1b370943f564875e91ea2c62058b06e88615699ad6533d1922039a7e9ea  src/polisyos/scientist/nodes/builtins/governance/run_normative_arbitration.py
d168ec331b803fc2ce01bc089e1ece4adfb9b9647c459accb3a6480fb021b623  src/polisyos/scientist/nodes/builtins/governance/normative_arbitration_calculations.py
f0632804853a0c00747fec319b67021f635c21e5f485cea53eb2269be5efcfd9  src/polisyos/scientist/nodes/builtins/governance/run_governance.py
14fab09e4e63427db8a6a06032d44f00952fa32eda5e13200d2a1c9ce852fbc7  src/polisyos/scientist/nodes/builtins/governance/governance_gate_requests.py
c7241dd0e6333c03aaa4d102e961e11ca586db5346670bc44e778a234be6941c  src/polisyos/scientist/governance/passes/_artifact_resolution.py
5fa5cc53efa42802e8ccd46ffe40a2861a4855ccf89ccd9f12804de46119a784  tests/unit/scientist/governance/test_artifact_resolution.py
35f73f9e344b0e8f76989768ac3fc2ed46a95be104a82eaec78f97f781e66225  tests/unit/scientist/governance/test_normative_arbitration_pass.py
f1f1242f914459e341ef9ebbc52242918facd3c0bb325f76007b0b73215f002c  tests/unit/scientist/governance/test_human_review_pass.py
b6f948077fb5ac3c08f21fc30d7461ac85005eaf64e1427653598e825bedbc68  tests/unit/scientist/governance/test_refutation_pass.py
a42036725c8983cce2cf85c1ce5aca0e3ccc6efc56b29d0512807a61f23359aa  tests/unit/scientist/governance/test_sutva_check_pass.py
70366c858b1a2d5b172b5c9612047fed356a9c18e1d6b36540c18e653bf7ee12  tests/unit/scientist/governance/test_cross_graph_evidence_pass.py
```

## Independent verdict

I found **no blocking finding** in the reviewed five-module/six-test delta. The shared resolver adaptation fixes the confirmed baseline defect at the correct class boundary; semantic positives and malformed/missing-reference negatives behave as required, while Core-only store consumers remain on the Core API. The extraction preserves the original decision and authority ordering in the reviewed paths and stays within the logical-line/C901 limits. The three extra control failures remain separate, input-qualified observations with P41 not established. Formal G acceptance remains unadjudicated.

## Test-fixture delta review (read-only)

**P40: SAME class, one layer deeper at the evidence supplied by the tests.** The earlier confidence failure treated envelope labels as an admitted positive, and the two calibration failures supplied artifact IDs without CAS payloads. This delta replaces those inputs with a controlled run of the actual propagation producer and a selected candidate from `CalibrationRunRunner` persisted to CAS. I found no second escape that calls for another fixture-specific patch.

The confidence test now keeps three distinct behaviors. The no-envelope case still expects an empty result; this is the optional-input behavior, not an admitted confidence-evidence positive. The metadata-only envelope case expects a typed blocker. The new path executes `PropagateUncertaintyNode`, reads its persisted simulation result through `ConfidencePass`, and requires the `healthy` envelope to remain blocked with `draw_success_ledger_missing` and `draw_basis_verifier_missing`. The controlled input envelope still carries synthetic identification/verifier labels, but the test never treats them as authority; its expected result is refusal. This matches the current consumer, which withholds a normative value in the absence of the successful-draw ledger and trusted verifier receipt (`uncertainty.py:2322-2332`). The producer-to-consumer lineage gap documented in the G-choice packet also remains explicit. No test now claims a positive admitted route that the current source cannot produce.

The calibration helper builds its deterministic panel and eligibility input, calls `CalibrationRunRunner`, selects the returned `selected_candidate_id`, persists that candidate JSON under `scientist.calibration_candidate` in the test CAS, and returns the resulting typed ref. Both validation tests now pass that backed ref. The runner selects by validation score before its one holdout scoring pass (`blueprint_release.py:711-900`); the test does not claim that its synthetic panel is external evidence. Existing downstream assertions remain in place, including the accountability `human_gate` outcome and the missing-transport/interference eligibility blocks. The helper fixes the invalid-reference fixture without weakening those semantic assertions.

I found no blocking issue in the test-only delta by source inspection. **Independent verification is partial:** I did not run pytest, lint, or format checks because the reserved slot remains unavailable. The author-reported 62-test run is not fresh reviewer evidence, and the earlier 32/53-test receipts above do not cover these changed test bytes. No formal G acceptance or finding closure is implied. The G choice remains an unresolved authority decision; the current state is `verification_missing` for a positive propagated-confidence admission path.

Commands run in the assigned candidate, read-only: `shasum -a 256` for the listed paths, plus `sed`, `nl`, and `rg` source inspection. No Git command or test command was run.

### Exact reviewed hashes

```text
e509185c535b5574e26cf1e209f0a3b7c8ed823381dc254055c0b98124863cc8  policy-engine/tests/unit/scientist/governance/test_confidence_issue_accumulation.py
164f842b3b62c26f75c90be9284b1b8c39adcb1ae5867a0677e06ce863ca378b  policy-engine/tests/unit/scientist/governance/test_calibration_validation.py
4fb3372a657785c1a27f430122790ae34a646c8fa659308c417582be44e8262c  policy-engine/src/polisyos/scientist/governance/passes/confidence_pass.py
60a20f807e892ab374c9b2feb87ed8b1a97f2e631eff04b45b438e98c6048530  policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py
a550ae6d9523930c3b03cbc1a722f6eb50bcbc7739b1c1d046319ca1b8ab0526  policy-engine/src/polisyos/ir/analytics/uncertainty.py
18ea763e66c802ebd1f8d585926a08c85831b74308e9ab7964461e3db539f3bb  policy-engine/src/polisyos/scientist/governance/blueprint_release.py
7665ea0eb7124104260017e1449312dc2102da66dd3a5d22c6849b9c8d9137a0  policy-engine/src/polisyos/scientist/governance/calibration_validation.py
348620e0eba5caad79c5678e5555b5ad1c0b6c176a86b38b448284328905cc72  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/confidence-propagation-admission-g-choice.md
```
