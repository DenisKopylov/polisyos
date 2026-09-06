# Task Q — re-measure what went stale, and type what was left undecided

Date: 2026-09-01
Branch: `codex/debt-q-remeasure-and-typing`
Base and measurement HEAD: `f6c465648d0b55b316452e982c62f6db6a0e051e`
Worktree: `/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine`

## Scope, preservation, and method

This lane owns five debt rows plus one nine-row institutional audit. It does not own the
architect-maintained register, ledger, or active plans, so no path under `docs/plans/active/` was
edited. Measurements are pinned to the attached branch and base above. The only intended tracked
deliverable is this append-only journal; the attempted DS9 fixture repair was reverted after it
exposed a producer/consumer contract mismatch that cannot honestly be repaired in a fixture.

Pattern pass:

- `P35`/`P36`: every set claim below carries its complete path/file-type or row denominator;
  historical and current counts are not mixed.
- `P37`/`P38`: a declared field, a green schema checker, or a consumer-authored fixture is not a
  decisive-property measurement. `GY-C2` is therefore explicitly `not_measured`, and `GY-S3` is
  a direct false-green finding.
- `P40`: the second DS9 fixture finding is bucketed as the same integrity class one level deeper.
  Repair stopped when the next move required changing another lane's production producer/consumer
  contract.
- `P41`: the DS9 expected red was preceded by a passing positive control. Its red is evidence about
  the instrument only, never evidence that crash recovery is broken.
- Capability labels remain precise: `absent/unallocated`, `producer_missing`,
  `implemented_but_not_orchestrated`, `bridge_missing`, `surface_missing`, and
  `not_measured` are not collapsed into “built” or “blocked.”

Environment receipt, executed once before measurement:

```sh
uv run --directory /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine --frozen --extra test python -c "import polisyos, sys; print(sys.prefix)"
```

```text
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv
```

The prefix is the bound worktree `.venv`; measurement continued.

## Complete tracked-path denominator

Executing party: `/root/census_calibration_runner`.

```sh
git -C /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine ls-files --full-name -- ':/' |
PYTHONDONTWRITEBYTECODE=1 python3 -c 'import collections,pathlib,sys; p=sys.stdin.read().splitlines(); c=collections.Counter(pathlib.PurePosixPath(x).suffix or "<no_ext>" for x in p); print(len(p), sorted(c.items()))'
```

Exact output:

```text
DENOMINATOR full_current_tracked_paths 10478
FILE_TYPES .blob=11 .cfg=1 .cjs=9 .css=17 .csv=15 .cypher=2 .duckdb=4
.example=3 .html=3 .ini=11 .js=5 .json=1210 .jsonc=1 .jsonl=5 .lock=1
.md=1635 .mdc=1 .mjs=36 .pkl=2 .png=36 .py=5737 .pyi=5 .rego=23
.reproducible=1 .sh=45 .sql=6 .svg=18 .tf=1 .tmpl=7 .toml=217 .tpl=1
.ts=507 .tsx=716 .txt=5 .typed=2 .webm=3 .yaml=85 .yml=69 .zip=4
<no_ext>=18
FILE_TYPE_SUM 10478
```

The Git root contains 22 tracked companions outside `policy-engine/`; the current product-subtree
denominator is 10,456. Both scopes are reported below wherever the older runner row mixed them.

## 1. `calibration-report-fixture-blanket-fields`

### Verdict

**Reproduced at an exact coordinate; `ambiguous` -> `open`.** No production repair is warranted in
Task Q. The defect is in the runtime HTTP fixture shape.

History denominator: two row-bearing commits. `b1a2e63f136908b5c283701daa9ccb1eb62e98b8`
registered the ambiguous row on 2026-08-26; `d1680bd0d26d86c98a97229523253af44c942017`
only allocated Task Q on 2026-09-01. The alleged origin `7615c002a` changed `_put_json` to
`_put_json_raw` for a monitoring-contract fixture and supplied no calibration coordinate.

Complete marker census over all 10,478 tracked paths:

```text
CalibrationReport files=58 types=.json=6,.md=13,.tsx=2,.py=37
calibration_report files=132 types=.ini=2,.ts=6,.json=18,.toml=5,.md=18,.tsx=2,.py=81
calibration-report files=7 types=.json=1,.md=3,.py=3
```

All 37 Python `CalibrationReport` candidates parsed with zero AST errors:

```text
CALIBRATION_REPORT_CLASS_COUNT 2
CALIBRATION_REPORT_POPULATION_CALL_COUNT 9
```

Both exact classes are strict `extra="forbid"`. The nine populations are two production
constructors, one dynamic strict `model_validate`, and six test fixtures; none uses `**` unpacking.

Deciding exact-kind command:

```sh
git -C /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine grep -I -n -F 'kind="foundry.calibration_report"' HEAD -- ':(top)**'
```

Exact output:

```text
HEAD:src/polisyos/foundry/calibration/report.py:138: kind="foundry.calibration_report"
HEAD:tests/_helpers/runtime_http.py:360: kind="foundry.calibration_report"
```

Across the full 10,478-path tree, `foundry.calibration_report` occurs in seven files
(`.py=4, .ts=2, .tsx=1`); only the two lines above construct the artifact. The exact defect chain
is:

1. `tests/_helpers/runtime_http.py:344-360` constructs the fixture and calls `_put_json`.
2. `_put_json` at lines 80-86 routes every mapping through `_with_runtime_fixture_authority`.
3. That wrapper at lines 68-76 blanket-adds exactly three keys.
4. `src/polisyos/foundry/calibration/report.py:72-106` defines the strict production model and
   `Calibrator.run` at `calibrator.py:1406-1427` emits none of those keys.
5. `put_calibration_report` at `report.py:128-145` persists the typed model, so those extras cannot
   cross the production path.

AST comparison output:

```text
RAW_FIXTURE_FIELDS calibrated_params,diagnostics,execution_context,fit_quality,
grad_norm_history,loss_history,per_target_loss,schema_version,series_comparison,
target_weights,total_loss,uncertainties
BLANKET_WRAPPER_FIELDS authority_boundary,authority_result,legacy_path_disposition
OUTSIDE_STRICT_MODEL authority_boundary,authority_result,legacy_path_disposition
BLANKET_FIELDS_NOT_PRODUCED authority_boundary,authority_result,legacy_path_disposition
```

The raw fixture also retains `fit_quality=None` and `uncertainties=None`, whereas typed production
canonicalization uses `exclude_none=True`. Those are valid schema fields and are recorded only as a
secondary shape drift, not as the blanket-field defect.

### Deciding rule

The verdict remains reproduced while the exact-kind fixture passes through blanket `_put_json`
and persists keys outside `CalibrationReport.model_fields`. It changes only when the fixture uses
the typed production serializer or a non-blanketing raw helper and a behavioral persisted-key-set
parity test proves zero fixture-only keys. An explicit production-contract change admitting the
three fields would also change the verdict. If a serializer prerequisite lands without the parity
test, the row stays `open` as `semantic_test_missing`.

### Exact append-only register prose

> **TASK Q RE-MEASUREMENT 2026-09-01 — `reproduced_at_f6c465648`; status `open`, not `ambiguous`.** Executed by `/root/census_calibration_runner` over the complete 10,478 tracked-path denominator and its recorded file-type denominator. The exact `foundry.calibration_report` census found two construction sites: production `src/polisyos/foundry/calibration/report.py:128-145` and fixture `tests/_helpers/runtime_http.py:344-360`. The fixture calls `_put_json`, whose mapping wrapper at `:68-86` blanket-adds `authority_result`, `legacy_path_disposition`, and `authority_boundary`. All three lie outside the strict `CalibrationReport` model at `src/polisyos/foundry/calibration/report.py:72-106`, are absent from `Calibrator.run` at `src/polisyos/foundry/calibration/calibrator.py:1406-1427`, and cannot be emitted by typed `put_calibration_report`. This is a fixture-contract drift; no production change is required. Close only when the fixture persists through the production-typed shape or a non-blanketing raw path and a semantic parity test proves zero fixture-only keys.

LEDGER disposition: move the authoritative source from the ambiguous section to the open section.

## 2. `transitive-runner-closure-unbound`

### Verdict

**The falsifier still holds.** No out-of-band identity binds the local Vite/Vitest transitive
module closure before C10 admission. The row remains `open`, `absent/unallocated`; a fresh bounded
residual is the successful outcome.

The original falsifier, recovered from `DS6-evidence-workflow.md:642-662` and the concrete mutation
at `DS6-evidence-workflow-journal.md:3978-3986`, is:

- modify a transitively loaded Vite `dist/node/chunks/*` or Vitest `dist/chunks/*` file;
- preserve the recorded entry path, package version, and entry SHA-256;
- observe that the substituted loader can forge the reconciler module or passing JSON while current
  admission remains green;
- close only with an identity produced outside the repository that signs the runner's transitive
  module closure and is independently verified before C10 admission.

The historical lexical vocabulary behind “386 supply-chain candidates” was never recorded, so
that scalar cannot honestly be replayed. The semantic falsifier was replayed using explicit
producer, verifier, identity, target, and admission families.

Current searches over all 10,478 tracked paths:

```text
producer primitives: 6 files
  file types: .json=1 .md=1 .py=1 .toml=1 .yml=2

independent-verifier primitives: 6 files
  file types: .json=1 .md=1 .py=4

direct runner/module-closure identity: 11 files
  file types: .md=9 .ts=2

producer ∩ verifier ∩ identity ∩ Vite/Vitest ∩ admission:
  1 file, .md=1
  docs/plans/active/atlas-slices/DS6-evidence-workflow-journal.md
```

The searches used `git grep -I -i -l -F` over `HEAD -- ':(top)**'` with these exact vocabularies:

```text
producer: attest-build-provenance, sign-blob, slsa-github-generator
verifier: gh attestation verify, verify-blob, slsa-verifier, verify_attestation,
          verify attestation, AttestationVerifier, _verify_slsa
identity: runner_identity / runner identity / runner-identity,
          module_closure / module closure / module-closure,
          transitive_runner / transitive runner / transitive-runner,
          signed runner, signed build
```

The complete production-candidate review denominator is 11 paths, with file types
`.mjs=1,.py=6,.toml=1,.ts=1,.yml=2`:

```text
.github/workflows/release.yml
architecture/control_plane_supply_chain.toml
ops/ci/templates/workflows/build-and-push.yml
tools/ops_runners/release/check_operability_release_gates.py
src/polisyos/core/audit/standalone_verifier_template.py
src/polisyos/core/audit/verifier.py
src/polisyos/core/security/tee.py
src/polisyos/core/security/tee_middleware.py
src/polisyos/core/artifacts/signed_evidence.py
apps/runtime-dashboard/src/test/evidence/atlasAutomatedEvidenceCapture.ts
apps/runtime-dashboard/scripts/reconcile_atlas_surface_readiness.mjs
```

Release attestations bind release assets; the audit verifier binds package-root/dependency SLSA
subjects; TEE verification binds platform measurements; `signed_evidence.py` signs generic
in-repository artifacts; and dashboard `runner_identity: "independently_reconciled"` compares a
report to in-repository literal profiles and commands. None binds the C10 local Vite/Vitest
transitive closure. The C10 script imports Vite and calls `ssrLoadModule` without resolving or
verifying a transitive-chunk identity. Actual external execution is `not_established`.

### Cause of every denominator movement

The original 9,870 statement is pinned by `git log -S` to
`c1354ec7a9664ae86275b025fb2a0c4dc0726d79`, 2026-08-18 17:11:19 +03. At the
subject-sweep parent `50b08b00527c241ac3bb9cb5eac10b7201529981`, the full tree was 10,361,
the `policy-engine/` subtree was 10,339, and the 22 outer companions were unchanged. Thus the old
displayed `9,870 -> 10,339` mixed scopes.

Exact movement:

```text
original full tree:          9870
real full-tree growth:       +491 = 509 added - 18 deleted
sweep full tree:            10361
scope change full→subtree:    -22
sweep displayed subtree:    10339
displayed movement:          +469
9870 + 491 - 22 = 10339

sweep→current full tree:    10361 → 10478 = +117
sweep→current subtree:      10339 → 10456 = +117
membership:                                  118 added - 1 deleted
```

Deciding membership commands and exact output:

```sh
git -C /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine diff --name-status --no-renames c1354ec7a9664ae86275b025fb2a0c4dc0726d79 50b08b00527c241ac3bb9cb5eac10b7201529981 -- ':/'
```

```text
c135..50b A=509 D=18 M=802 NET=+491
527 A/D lines
sha256=b4ea8bb7d7c92e208f7ffb1a3cefa9fa241f5c31437e5e312e1ba6a9acd38da
```

```sh
git -C /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine diff --name-status --no-renames 50b08b00527c241ac3bb9cb5eac10b7201529981 f6c465648d0b55b316452e982c62f6db6a0e051e -- ':/'
```

```text
50b..f6c A=118 D=1 M=361 NET=+117
119 A/D lines
sha256=a509a55aee3ef60318fc8fb4e1b3f6c09f3e977f83b51d0b73079b5a09cffe3a
```

The second interval's sole deletion is
`src/polisyos/core/observability/truthfulness.py`. Added-path buckets are
`apps=23, architecture=4, docs=53, release-fragments=1, src=11, tests=25, tools=1`, totaling 118.
The first interval's added-path buckets are
`apps=160, architecture=21, docs=174, packages=1, release-fragments=14, schemas=1, src=54,
tests=76, tools=8`, totaling 509; its 18 deleted paths are the superseded dashboard image/hooks,
offline-queue files, split CLI modules, old claim/embedder/failure-card files, and their replaced
calibration/embedder tests. Direct parent-to-commit A/D attribution sums exactly to the two interval
totals; no unexplained movement remains.

### Deciding rule

Close only when an out-of-band signed identity binds the exact Vite/Vitest entry plus transitive
module closure, an independently sourced verifier executes before C10 admission, and changing a
transitive chunk while preserving entry path/version/hash makes admission fail. If an attestation
producer lands without the independent pre-admission verifier and mutation negative, the row stays
open as `bridge_missing + semantic_test_missing`.

### Exact append-only register prose

> **TASK Q RE-MEASUREMENT 2026-09-01 — bounded residual confirmed at `f6c465648`; denominator corrected.** Executed by `/root/census_calibration_runner` over the complete 10,478 tracked-path denominator and recorded file-type denominator. The recovered falsifier is the DS6 scenario in which a modified transitive Vite/Vitest chunk forges module loading or passing JSON while the entry path, version and SHA-256 remain green. Current producer, verifier, runner-identity, target and admission searches, followed by inspection of the complete 11-path production-candidate set, find no out-of-band identity binding that closure and no independent verifier executed before C10 admission. Release attestations bind release assets; package SLSA verification binds audit-package subjects; TEE verification binds platform measurements; the dashboard `runner_identity` remains reconciliation against an in-repository declared profile. Actual external execution is `not_established`. The old `9,870 -> 10,339` statement mixed scopes: at original pin `c1354ec7a` the full tree was 9,870; at sweep pin `50b08b005` it was 10,361 while the `policy-engine/` subtree was 10,339. The real growth was `+491 = 509 added - 18 deleted`, followed by `+117 = 118 added - 1 deleted` to current full-tree 10,478/current subtree 10,456; the 22 outer paths remained constant. Keep `open`, `absent/unallocated`. Close only on an externally produced signed runner/module-closure identity, independent pre-admission verification, and a modified-transitive-chunk negative that turns admission red.

## 3. `gy-census-decisive-property-unmeasured`

### Historical denominator and cause

Commit `73d930f8284682fafc283c2b78c54d64bbecf1dd` (2026-08-30 17:10:45 +03)
introduced the debt row and one contiguous 24-row table block. The exact complete-set command was:

```sh
git -C /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine show 73d930f8284682fafc283c2b78c54d64bbecf1dd:./docs/plans/active/layer3-slices/GY-engine-subordination.md |
sed -n '/^| `GY-M1` /,/^| `GY-S3` /p' |
awk -F'|' 'BEGIN{n=0} /^\| `GY-/ {gsub(/`/,"",$2); gsub(/^ +| +$/,"",$2); print ++n "\t" $2}'
```

Exact output:

```text
1 GY-M1
2 GY-B
3 GY-H
4 GY-D1
5 GY-D2
6 GY-D3
7 GY-E
8 GY-C1
9 GY-C2
10 GY-C3
11 GY-I
12 GY-F1
13 GY-F2
14 GY-F3
15 GY-G
16 GY-M2
17 GY-J
18 GY-K
19 GY-L
20 GY-S0
21 GY-S1
22 GY-N-V
23 GY-S2
24 GY-S3
```

The exact historically measured set was `GY-D1`, `GY-M2`, `GY-K`; subtraction produced the 21-row
measurement denominator:

```text
GY-M1 GY-B GY-H GY-D2 GY-D3 GY-E GY-C1 GY-C2 GY-C3 GY-I
GY-F1 GY-F2 GY-F3 GY-G GY-J GY-L GY-S0 GY-S1 GY-N-V GY-S2 GY-S3
unmeasured_count=21
```

This is arithmetic over a single historical block, not repository growth: `24 - 3 = 21`.
`GY-D1` had failed real catalog wiring at `1/3`; `GY-M2` had failed because tourism produced zero
validator hits; `GY-K` was historically ambiguous because two owner meanings collided. Commit
`7408df9f` later resolved the K collision and moved the plan distribution from 47 executed / 3
ambiguous to 48 / 2. That later semantic correction does not change the 21-row denominator.

Measurement denominator: 21 exact row selectors across 12 distinct Python test files. Material
readback denominator: nine committed JSON reports, used only beside live recomputation and never as
a replacement for it. Documentary denominator: exactly three Markdown files (GY plan, register,
ledger).

Positive control, run before expected reds:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -m pytest /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/core/contracts/test_value_outer_set.py::test_value_outer_set_interval_box_derives_width_and_l5_identification_status -q -x --lf -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-gy/pytest-cache
```

```text
. [100%]
exit 0
```

All discovery measurements used this exact envelope (with the listed absolute node substituted):

```sh
/usr/bin/perl -e 'my $s=shift @ARGV; alarm $s; exec @ARGV or die $!;' 1800 \
/usr/bin/env PYTHONDONTWRITEBYTECODE=1 \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python \
-m pytest ABSOLUTE_EXACT_NODE -vv -x --lf \
-o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-gy/pytest-cache
```

`GY-M1` was rerun with the required solver environment:

```sh
uv run --directory /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine --frozen --extra test --extra solvers python -m pytest ABSOLUTE_EXACT_NODE -vv -x --lf -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-gy/pytest-cache
```

The initial no-solver environmental failure is excluded from evidence.

### Per-row decisive-property results

1. **`GY-M1` — fail.** Property: a new GY artifact cannot be committed without a registered
   lifecycle entry and the generic validator is green. Node:
   `tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_generated_artifact_lifecycle_is_scan_based`.
   Exact material output: `assert report["status"] == "pass"` ->
   `AssertionError: assert 'fail' == 'pass'`; `1 failed in 163.38s`. This is the solver-enabled
   generic scan, not a missing-extra result.

2. **`GY-B` — pass for the selected property.** Property: a non-active operation cannot execute.
   Node: `tests/unit/runtime/quality/test_workspace_loop.py::test_slice0_rejects_non_active_operation_execution`.
   Exact output: `PASSED`; it was one of `5 passed in 579.96s`. The real registry/invariant path ran.

3. **`GY-H` — pass for the selected property.** Property: terminal precedence routes poor recall
   to repair before acquisition. Node:
   `tests/unit/runtime/quality/test_workspace_loop.py::test_loop_terminal_precedence_blocks_acquisition_when_ceiling_is_unrepaired`.
   Exact output: `PASSED`; the loop observed `search_ceiling_repair_required`.

4. **`GY-D2` — pass for the selected property.** Property: connector/source-contract admission
   fails closed. Node:
   `tests/unit/runtime/quality/test_workspace_loop.py::test_connector_and_source_contract_admission_fail_closed`.
   Exact output: `PASSED`; non-ready connectors and missing facets returned repair-required.

5. **`GY-D3` — pass, bounded to `closure_scope=slice0_gate_only`.** Property: the semantic
   adequacy negative control is rejected and recall is recorded. Node:
   `tests/unit/runtime/quality/test_workspace_loop.py::test_semantic_adequacy_benchmark_rejects_negative_control_and_records_recall`.
   Exact output: `PASSED`; `tourism_attraction_reviews` was rejected, recall was `0.0`, and poor
   recall routed red. This does not establish the wider F4/F7 corpus claim.

6. **`GY-E` — pass for the selected property.** Property: the real loop emits a costed
   `acquisition_required` terminal and typed need. Node:
   `tests/unit/runtime/quality/test_workspace_loop.py::test_slice0_acquire_continuation_emits_costed_acquisition_required_terminal`.
   Exact output: `PASSED`; missing distribution `local_tourism_site_traffic`, a selected VOI plan,
   and `money_usd=3640.0` were observed.

7. **`GY-C1` — fail.** Property: the Phase-2 playbook runs to a permitted deviation. Node:
   `tests/unit/runtime/quality/test_workspace_workflow_playbook_projection.py::test_workspace_loop_phase2_playbook_can_deviate_to_refine_blocker`.
   Exact output: `UnknownNodeError: Unknown node_id: scientist.node_build_literature_prior@1.0.0`;
   `1 failed in 218.71s`. The playbook cannot reach its deviation point.

8. **`GY-C2` — explicit `not_measured`.** Property: every named judge produces a valid verdict on
   real input. Node:
   `tests/unit/runtime/quality/test_workspace_spine_repair_gates.py::test_governance_tail_verifier_delegates_to_governance_node_owner`.
   Exact output: `PASSED`. The test delegates over constructed dictionaries containing
   `model_completeness="declared_complete"` and six named judges. It proves delegation, not valid
   real-input verdicts; the decisive predicate is `consumer_asserted` under P37.

9. **`GY-C3` — fail.** Property: Phase-2 estimate consumes real Foundry output with measurement
   authority. Node:
   `tests/integration/runtime_quality/test_workspace_foundry_consumption.py::test_phase2_estimate_consumes_real_foundry_method_output_with_measurement_authority`.
   Exact output: `assert outcome.status == "ok"` -> `AssertionError: assert 'fail' == 'ok'`.
   `RunCausalEvaluationNode` was invoked on real observational input.

10. **`GY-I` — pass for the selected property.** Property: the agent-event bridge persists an
    unmocked tool-loop event bundle. Node:
    `tests/unit/runtime/quality/test_workspace_agent_proposal_bridge.py::test_agent_event_bridge_persists_unmocked_tool_loop_event_bundle`.
    Exact output: `PASSED`.

11. **`GY-F1` — fail.** Property: the workflow-failure authority validator recomputes proofs on the
    live production surface. Node:
    `tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_workflow_failure_authority_validator_recomputes_proofs`.
    Exact output: production NL launch raises `RuntimeHTTPError` code `llm_model_unconfigured`, then
    exception handling raises `FrozenInstanceError`; `1 failed in 328.85s`. A stale committed
    artifact is not substituted.

12. **`GY-F2` — pass for the selected property.** Property: artifact surface safety is recomputed
    behaviorally. Node:
    `tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_artifact_surface_safety_validator_recomputes_proofs`.
    Exact output: `PASSED`; dedup `same_digest=true`, tamper `rejected:sha256 mismatch`, GC
    `authority_missing=[]` and `not_retained=[]`, and raw/download/export/manifest secret probes all
    produced `blocked=true`, `leaked_secret=false`, HTTP 409.

13. **`GY-F3` — pass for the selected property.** Property: time-source authority is recomputed.
    Node:
    `tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_time_source_authority_validator_recomputes_proofs`.
    Exact output: `PASSED`; dispositions were `consistent`, `inconsistent`,
    `blocked_for_owner_review`; real S12 refs were `authority_admitted`; inventory row count and
    expected/actual candidate-positive were all 406, with zero false-exclusion tickets.

14. **`GY-G` — pass for the selected property.** Property: feedback composition is invalid without
    joint grounding. Node:
    `tests/unit/runtime/quality/test_workspace_composition.py::test_feedback_composition_is_invalid_and_requires_joint_grounding`.
    Exact output: `PASSED`; real composition returned
    `composition_invalid:feedback_requires_joint_grounding`.

15. **`GY-J` — fail.** Property: graded outcome routing moves the useful-design rate honestly off
    zero. Node:
    `tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_loop_validator_recomputes_graded_outcome_routing_report`.
    Exact output: fresh recomputation raises `ValueError: claim_ledger_owner_store_mismatch`.
    Independent committed-material readback is also contrary:
    `graded_outcomes=[]`, `grounded_partial_admissible_count=0`, `useful_design_rate=0.0`.

16. **`GY-L` — fail.** Property: the GY outcome run is HTTP-triggered and honestly blocked through
    the current production app. Node:
    `tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_outcome_run_is_http_triggered_and_honestly_blocked`.
    Exact output: fresh recomputation raises `ValueError: claim_ledger_owner_store_mismatch`.
    The older committed blocker artifact cannot replace the current failed rerun. J/L are one
    underlying failure class, not two repair classes.

17. **`GY-S0` — pass for registration/versioning only.** Property: novel substrate registration is
    free-grow and changes version identity. Node:
    `tests/unit/runtime/quality/test_substrate_registry.py::test_substrate_registry_registration_is_free_grow_and_changes_version`.
    Exact output: `PASSED`; a novel source/family was registered and resolved with changed
    content/version hashes. It does not prove every named consumer.

18. **`GY-S1` — pass for the selected property.** Property: real L4 data state builds a populated
    world-model record and executes simulation. Node:
    `tests/integration/runtime_quality/test_data_state_substrate.py::test_real_l4_data_state_builds_populated_world_model_record_and_executes_sim`.
    Exact output: `PASSED`; `1 passed in 151.70s`. The source exceeded 8,000,000 agents, 128 were
    bound, `GlobalState` was populated, the S0 registry ref was present, Foundry execution was `ok`,
    and the simulation ref was non-null.

19. **`GY-N-V` — pass for timeout discipline.** Property: comparison timeout becomes unknown, never
    fabricated dominance. Node:
    `tests/unit/core/contracts/test_value_outer_set.py::test_value_outer_set_compare_is_conservative_and_unknown_on_timeout`.
    Exact output: `PASSED`.

20. **`GY-S2` — pass for the selected property.** Property: real L2 transport and contested edges
    lower to bounded, non-point value sets. Node:
    `tests/integration/runtime_quality/test_gy_s2_knowledge_substrate_lift.py::test_l2_transport_and_contested_edges_lower_to_bounded_nonpoint_sets`.
    Exact output: `PASSED`.

21. **`GY-S3` — fail.** Property: the real intervention-substrate behavior report covers every
    manifest route. Node:
    `tests/unit/runtime/quality/test_intervention_substrate.py::test_intervention_substrate_behavior_report_exercises_real_space_and_mutations`.
    Isolated exact output: the top-level `report["status"] == "pass"` and world/law coverage
    assertions pass, then method routing fails `assert 3 == 4`; `1 failed in 194.97s`. This is a
    direct P38 false green. Isolation rules out batch contamination.

Exact final distribution over the 21-row denominator:

```text
pass = 13:
GY-B GY-H GY-D2 GY-D3 GY-E GY-I GY-F2 GY-F3 GY-G GY-S0 GY-S1 GY-N-V GY-S2

fail = 7:
GY-M1 GY-C1 GY-C3 GY-F1 GY-J GY-L GY-S3

explicit not_measured = 1:
GY-C2
```

No unnamed remainder exists.

### Verdict and moved-number cause

A direct failure of any quoted `Done when` predicate overrides third-rank delivered-artifact
presence and retypes that task `executed -> ambiguous`. A selected-property pass proves only that
predicate; it does not prove the other `Done when` conjuncts or the implicit plan gate. A proxy or
declared-premise instrument is `not_measured`.

The seven direct failures are the entire cause of the distribution movement:

```text
before: 48 executed + 0 in_flight + 1 not_executable + 21 not_started + 2 ambiguous = 72
change:  -7 executed                                                   +7 ambiguous
after:  41 executed + 0 in_flight + 1 not_executable + 21 not_started + 9 ambiguous = 72
```

The seven new ambiguous rows are exactly `GY-M1`, `GY-C1`, `GY-C3`, `GY-F1`, `GY-J`, `GY-L`,
`GY-S3`. `GY-C2` remains explicitly unmeasured. If any direct failure is later repaired, its row
changes only after the same decisive property is rerun green; a weaker artifact/checker landing
without that rerun leaves it ambiguous. `GY-C2` changes only when a real-input instrument establishes
the judge verdicts independently rather than consuming declared dictionaries.

### Exact append-only register prose

> **TASK Q DECISIVE-PROPERTY RECENSUS 2026-09-01 — denominator discharged; authoritative-plan transcription remains.** At branch `codex/debt-q-remeasure-and-typing`, head `f6c465648d0b55b316452e982c62f6db6a0e051e`, the executor re-derived the 2026-08-30 census from introducing commit `73d930f8284682fafc283c2b78c54d64bbecf1dd`: exactly 24 contiguous delivered-artifact rows (`GY-M1` through `GY-S3`) in the authoritative GY task table. Subtracting the three historically measured rows (`GY-D1`, `GY-M2`, `GY-K`) yields exactly 21 rows. Exact-node, `-x --lf` measurements with an isolated cache and a prior positive control produced 13 direct selected-property passes (`GY-B`, `GY-H`, `GY-D2`, `GY-D3`, `GY-E`, `GY-I`, `GY-F2`, `GY-F3`, `GY-G`, `GY-S0`, `GY-S1`, `GY-N-V`, `GY-S2`), seven direct failures (`GY-M1`, `GY-C1`, `GY-C3`, `GY-F1`, `GY-J`, `GY-L`, `GY-S3`), and one explicit `not_measured` (`GY-C2`, because the available green instrument delegates over consumer-asserted dictionaries and does not exercise “real input”). The verdict rule is binding: a direct failure of any quoted `Done when` predicate overrides delivered-artifact presence and retypes the row `executed -> ambiguous`; a selected-property pass proves only that predicate and never the task’s remaining conjuncts or implicit §3.5.5 gate; a proxy or preflight-only result is `not_measured`. Applying the rule yields `72 = 41 executed + 0 in_flight + 1 not_executable + 21 not_started + 9 ambiguous`; the seven new ambiguous rows are exactly the seven failures above. This debt row closes only when those 21 append-only notes, the seven task-standing changes, and the recomputed distribution are present in the authoritative GY plan and its generated ledger projection.

## 4. `DS11-SCOPE-ADJUDICATION-RECORD`

### Decision

**Alternative (b): authority-band promotion is genuinely owed, but it is not Task Q work.** The
candidate artifact is correct and must remain candidate-only; it is not the terminal capability.
The named production test should exist only with a real end-to-end authority chain.

Deciding exact-node command:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --directory /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine --frozen --extra test python -m pytest -x --lf -q -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-root/pytest-cache /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/core/contracts/test_scope_adjudication.py::test_candidate_derives_ordered_four_way_proposals_without_authority
```

Exact output:

```text
....                                                                     [100%]
exit 0
```

The four parameter cases prove the ordered `own` / `integrate` / `observe` / `out_of_scope`
proposal derivation without authority. Complete test-function census:

```sh
rg -n '^def test_' /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/core/contracts/test_scope_adjudication.py
rg -n '^def test_four_way_ruling_is_produced_consumed_and_plane_specific' /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/core/contracts/test_scope_adjudication.py
```

Exact output:

```text
106:def test_candidate_derives_ordered_four_way_proposals_without_authority(
125:def test_candidate_rejects_mixed_planes_and_content_substitution() -> None:
155:def test_unestablished_predicate_is_preserved_as_a_typed_limitation() -> None:
169:def test_candidate_verifier_rejects_digest_and_semantic_substitution() -> None:
184:def test_scope_candidate_is_exported_from_the_contract_facade() -> None:
named_test_rg_exit=1
```

Denominator: five test functions / eight collected parameter cases in one test file. The named
production identity has zero definitions in that denominator. Source readback is explicit:

```text
status="candidate_only"
authority_effect="none"
closure_effect="none"
authoritative_for=()
limitations include scope_predicate_resolver_unappointed
limitations include scope_adjudication_claim_lifecycle_consumer_unappointed
```

The candidate also prohibits use for a scope ruling, claim-lifecycle mutation, head advance,
publication, or institutional execution. That is not metadata decoration; it makes candidate-only
terminal closure self-contradictory. The ratified four-way rule supplies the policy vocabulary, but
the authority-band act still needs purpose-scoped, independently established predicate evidence and
an accountable minting boundary. Carrying a ratified rule is not authority to assert its predicates
for a particular function/plane.

The owed successor must produce all of:

1. a production `ScopePredicateEvidenceResolver` that resolves, content-binds, and records
   non-producer verifier provenance and the frozen P37 establishment class for each predicate;
2. a purpose-scoped authority that applies the ratified ordered rule and mints a typed
   `ScopeAdjudicationRecord`, with one-plane identity, rule/schema version, validity/knowledge times,
   provenance, authority purpose, and exact candidate lineage;
3. CAS persistence and replay/revalidation of the ruling artifact;
4. a `ScopeAdjudicationClaimLifecycleConsumer` wired through the real scientist governance
   lifecycle/container path, without allowing the consumer to self-attest the predicates;
5. an audit/API projection and negative semantic tests for mixed planes, unknown predicates,
   digest/semantic substitution, untrusted provenance, and a sibling-consumer bypass;
6. only then, the named identity
   `test_four_way_ruling_is_produced_consumed_and_plane_specific` exercising producer -> persisted
   record -> orchestration bridge -> lifecycle consumer -> governed surface.

Ownership: `team-architecture` owns the ratified rule and purpose/producer boundary; the runtime /
scientist governance successor owns persistence, orchestration, lifecycle consumption, and surface.
This is executable engineering, not an appointment-only block.

### Rejected alternative

Alternative (a), “candidate-only is terminal and the closure signal is wrong,” is rejected because
the candidate explicitly has no authority or closure effect and forbids the uses the row exists to
enable. Changing the signal to one of the five candidate tests would close a contract-only
capability (`P01`) and preserve the absent producer/bridge/consumer. Writing the named test now is
also rejected: it would either select nothing or fake production objects to satisfy a signal.

### Deciding rule

The row stays `open` until the complete authority chain above exists and the named test executes it.
If only a resolver, artifact class, or test identity lands, classify the row with the remaining
`producer_missing`, `bridge_missing`, `consumer_missing`, `surface_missing`, or
`semantic_test_missing` labels; do not close it. If an institutional minting appointment is later
required, the typed-empty slot may be `blocked` on appointment only after the mechanism exists.

### Exact append-only register prose

> **TASK Q ARCHITECT DECISION 2026-09-01 — alternative (b); status stays `open`.** The candidate-band artifact is correct but not terminal. Its strict contract says `status=candidate_only`, `authority_effect=none`, `closure_effect=none`, `authoritative_for=()`, forbids use for scope rulings and claim-lifecycle mutation, and carries typed `scope_predicate_resolver_unappointed` plus `scope_adjudication_claim_lifecycle_consumer_unappointed` limitations. The five candidate tests (eight parameter cases) pass, while the named production identity remains absent by design. The ratified document owns the ordered four-way rule, but applying it to a particular function/plane still requires independently established, content-bound predicate evidence and a purpose-scoped minting boundary; a consumer may carry the ratified rule but may not self-attest its premises. Closure therefore requires a production `ScopePredicateEvidenceResolver`, typed persisted `ScopeAdjudicationRecord` with rule/time/provenance/authority lineage, real scientist lifecycle orchestration and consumer, governed audit/API projection, and negative mixed-plane/substitution/provenance/sibling-bypass tests. Only that chain may introduce `test_four_way_ruling_is_produced_consumed_and_plane_specific`. Rejected: candidate-only terminal closure, because it would close a P01 contract while the artifact itself prohibits the claimed authority effect. Owner split: `team-architecture` for rule/purpose/producer boundary; runtime/scientist successor for persistence, bridge, consumer, and surface.

## 5. `ds9-human-decision-crash-test-fixture-blocked`

### Positive control and base red

The positive control ran first:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --directory /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine --frozen --extra test python -m pytest -x --lf -q -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-root/pytest-cache /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/http/test_control_plane_store.py::test_human_decision_crash_reservation_requires_reconciliation_before_reuse
```

```text
.                                                                        [100%]
exit 0
```

Then the exact higher-level node:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --directory /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine --frozen --extra test python -m pytest -x --lf -q -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-root/pytest-cache /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/http/test_human_decision_service.py::test_human_decision_hard_crash_reconciles_null_ref_signed_orphan_before_v2
```

Exact material output:

```text
__ test_human_decision_hard_crash_reconciles_null_ref_signed_orphan_before_v2 __
...
with pytest.raises(_SimulatedProcessDeath):
>   fixture.service.create_record(...)
...
if resolved.projection.status != "available":
>   raise HumanDecisionUnavailableError(resolved.projection)
E   polisyos.runtime.http.services.human_decisions.HumanDecisionUnavailableError: blocked
...
FAILED tests/unit/runtime/http/test_human_decision_service.py::test_human_decision_hard_crash_reconciles_null_ref_signed_orphan_before_v2
stopping after 1 failures
exit 1
```

The patched `HumanDecisionWriteFence.commit` was never reached, so the red says nothing about the
reserved-to-committed crash property.

### Root-cause ladder

The original fixture imports `_prepare_gateway` from
`tests/unit/runtime/quality/test_agent_action_authority.py`. Commit
`b633ea7b75af4d07feaf0690926712353022d21f` added two coupled producer facts:

1. current mandate-owner evidence, whose helper defaults are relative to that module's fixed
   `NOW=2026-08-19`; and
2. unconditional `human_decision_missing` when an out-of-envelope source has no current human
   resolution.

The consuming DS9 fixture evaluates at `NOW=2026-08-24`. Its imported mandate evidence is already
expired, so delegation-contract resolution fails, no envelope is selected, and the generated
request has a zero-length TTL. The typed base reasons were:

```text
status=blocked
DS9-DECISION-TTL-EXPIRED
DS9-MANDATE-NOT-SHOWN
DS9-PRESENTATION-CONTRACT-INVALID
DS9-EXPOSURE-SESSION-INVALID
DS9-MANDATE-NOT-SHOWN
DS9-EVIDENCE-NOT-OPENED
DS9-RUBBER-STAMP
```

A temporary test-only clock binding was tried after the base red. It correctly changed the result
from `blocked` to `invalid_source`, but did not reach `commit`:

```text
E   polisyos.runtime.http.services.human_decisions.HumanDecisionUnavailableError: invalid_source
FAILED tests/unit/runtime/http/test_human_decision_service.py::test_human_decision_hard_crash_reconciles_null_ref_signed_orphan_before_v2
exit 1
```

An existing baseline assertion independently printed the exact consumer reason:

```text
AssertionError: (HumanDecisionGateReason(code='DS9-DECISION-SOURCE-INVALID',
message='The signed source/request/contract packet join is invalid.',
status='invalid_source'),)
assert 'invalid_source' == 'available'
```

Direct execution of `_pa2_packet_join_issues` on the current, clock-corrected producer packet gave:

```text
issues=principal_authority,source
envelope=envelope.search.agent-search
outcome=refused
refusals=('operation_out_of_envelope', 'human_decision_missing')
checks=(('verified_identity', True, 'recomputed'), ('explicit_permission', True, 'recomputed'), ('mandate_bounded_delegation', True, 'independently_reconciled'), ('operation_in_envelope', False, 'recomputed'), ('live_accountability', True, 'recomputed'))
contract_ref=sha256:17415be17328c19b52c42389d07863ecaf60c8656863dcb72418879787acd845
contract_hash=sha256:17415be17328c19b52c42389d07863ecaf60c8656863dcb72418879787acd845
basis=sha256:17415be17328c19b52c42389d07863ecaf60c8656863dcb72418879787acd845
request_reasons=['out_of_envelope']
source_envelope_id=envelope.search.agent-search
request_interval=2026-08-24T12:00:00+00:00|2026-08-24 13:00:00+00:00|2026-08-24 13:00:00+00:00
```

The diagnostic's `principal_authority` token came from a hand-entered permission spelling and is
excluded; the `source` finding is independently decisive. The current producer necessarily emits
`('operation_out_of_envelope', 'human_decision_missing')`, while
`_pa2_packet_join_issues` accepts only the singleton `('operation_out_of_envelope',)`.
`git blame` attributes the consumer singleton to `3b1a87fd04` and the producer's appended
`human_decision_missing` to later commit `b633ea7b75`.

### Verdict and rejected repair

**The row remains `open`, re-typed from “fixture blocked” to a PA2 producer/consumer compatibility
gap owned by `team-runtime` across the agent-action-authority producer and DS9 human-decision
consumer.** The local clock mismatch is repairable in the fixture, but that repair exposes a second
same-class incompatibility. Per P40, repair stopped at the second finding and the temporary edit was
reverted; no test or production source change remains.

Rejected alternative: strip `human_decision_missing` from the fixture's signed source or construct
a singleton-reason DTO by hand. No current producer emits that packet, so the test would prove a
fiction. Also rejected: changing either production side in Task Q, because that crosses into the
DS9/agent-authority runtime lane without adjudicating whether the new reason belongs in the accepted
PA2 protocol.

### Deciding rule

The verdict changes only when the owning runtime lane defines one current, producer-emittable PA2
source protocol and the consumer independently accepts that exact protocol, with mandate evidence
bound to the consuming fixture's clock. The exact crash node must then reach the monkeypatched
`HumanDecisionWriteFence.commit`, raise `_SimulatedProcessDeath`, restart, reconcile the null-ref
signed orphan, and pass; the lower reservation-pair positive control must remain green. If only the
clock fix or only one side of the protocol lands, keep the row open. A new prerequisite without an
end-to-end rerun does not close it.

### Exact append-only register prose

> **TASK Q REPRODUCTION AND RE-TYPING 2026-09-01 — status stays `open`; no production change.** A passing write-fence crash-reservation control ran first. The named higher-level node then reproduced the base red: `HumanDecisionUnavailableError: blocked` occurs before the patched `HumanDecisionWriteFence.commit`, so the test still cannot witness the crash transition. Root cause is two-layer fixture drift introduced by `b633ea7b75`: the imported mandate-authority helper is effective around its own `2026-08-19` clock while this fixture evaluates at `2026-08-24`, producing expired evidence and a zero-TTL request; rebinding that evidence to the fixture clock advances the gate but exposes `invalid_source`. Direct packet recomputation then shows the current producer emits refusal reasons `('operation_out_of_envelope', 'human_decision_missing')`, while the DS9 PA2 consumer accepts only `('operation_out_of_envelope',)`. A fixture-only singleton would be unproducible and was rejected; the temporary diagnostic edit was reverted. Retype the remaining owner to `team-runtime` across `runtime/quality/agent_action_authority` and the DS9 human-decision PA2 consumer. Close only when a current producer-emittable packet is accepted end to end, the exact crash node reaches the patched commit and passes restart reconciliation, and the lower reservation-pair control remains green. A one-sided protocol or clock change leaves the row open.

## 6. Institutional audit — nine rows

### Denominators and deciding commands

Executing party: `/root/institutional_audit`. The source/test denominator is exact and tracked:

```text
src tracked files=2827; src Python files=2617
tests tracked files=2990; tests Python files=2490
combined tracked files=5817; combined Python files=5107
```

These are current denominators only; no historical movement is claimed. The only corrected inherited
scalar is the W5 route count, explained below.

The required positive control ran first:

```sh
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -m pytest /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/http/test_temporal_routes.py::test_epoch_staleness_route_renders_real_declared_absences_as_usable_state -x --lf -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-institutional/pytest-cache
```

```text
.                                                                        [100%]
1 passed in 6.04s
```

Then six exact production/refusal witnesses:

```sh
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -m pytest \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_chronology_custody.py::test_production_provider_reports_both_unappointed_roles \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_epoch_validity_cascade.py::test_unappointed_transition_signer_returns_typed_negative_before_owner_reads \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/data_forge/domains/catalog/knowledge/test_acquisition_authority.py::test_acquisition_authority_supplies_epoch_service_and_query \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_agent_action_authority.py::test_matching_contract_signer_without_current_mandate_evidence_refuses \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/integration/core_runtime/test_acquisition_admission_bundle.py::test_empty_signer_slot_blocks_before_authority_artifact_write \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_promotion_sequence.py::test_eval_safety_names_the_missing_promotion_authority_without_reusing_o0 \
-x --lf -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-institutional/pytest-cache
```

Exact output:

```text
......                                                                   [100%]
6 passed in 301.97s (0:05:01)
```

Complete key-call census over the 2,617 source-Python / 2,490 test-Python denominators:

```text
EpochValidityTransitionProducer(
matching_src_files=0/2617 matching_test_files=1/2490
tests/unit/runtime/quality/test_epoch_validity_cascade.py:1273

\.produce_and_persist\(
matching_src_files=0/2617 matching_test_files=1/2490
tests/unit/runtime/quality/test_epoch_validity_cascade.py:1281

AgentActionAuthorityGateway(
matching_src_files=0/2617 matching_test_files=2/2490
tests/integration/core_runtime/test_acquisition_admission_bundle.py:411
tests/unit/runtime/quality/test_agent_action_authority.py:586

admit_acquisition_with_production_semantic_epoch(
matching_src_files=1/2617 matching_test_files=1/2490
src/polisyos/runtime/quality/acquisition_executor.py:1829:def ...
tests/unit/data_forge/domains/catalog/knowledge/test_acquisition_authority.py:549
```

### Audit verdicts

| Row | Surrounding mechanism built? | Slot typed and empty by construction? | Precise state |
| --- | --- | --- | --- |
| `ds15-semantic-epoch-qualification-authority` | **No, incomplete.** Typed refusal and persisted negative receipt exist, but the production-composition symbol has only its definition in source and one test call. | **Yes.** `EpochChronologyPolicyOwner \| None`, with explicit unallocated factory. | `absent/unallocated + bridge_missing` |
| `ds15-signed-v2-delegation-mandate-owner-authority` | **No.** The gateway is constructed zero times in source and twice in tests. | **No.** `CurrentMandateOwnerEvidence` is an evidence DTO, not an empty authority slot; a plain mapping simply lacks a key. | institutional `absent/unallocated`; evidence `producer_missing`; gateway `implemented_but_not_orchestrated`; drop `artifact_missing` |
| `ds18-epoch-history-independent-holder-unappointed` | **No, incomplete.** Provider is injected, but no source consumer reads the container field and no persistence/audit/API surface exists. | **Yes.** `HolderAppointmentResult` is discriminated and `NoEpochAnchorAppointmentResolver` produces the unavailable arm. | `implemented_but_not_orchestrated + surface_missing` plus institutional absence |
| `ds18-epoch-predicate-policy-signer-unappointed` | **Yes, for the declared absence.** Production factory -> typed refusal -> temporal consumer -> audit -> HTTP semantic test. | **Yes.** Explicit unallocated policy-owner state. | institutional `absent/unallocated` only |
| `ds18-epoch-transition-signer-unappointed` | **Yes for the refusal surface; no for positive production.** Positive `EpochValidityTransitionProducer` has zero source constructions/calls. | **Yes.** `NoEpochTransitionSigningAuthority` fills the typed slot. | institutional `absent/unallocated`; positive engineering gap stays in its separate row |
| `gy-n12-epoch-predicate-policy-authority-unappointed` | **Yes, for the declared absence.** The production temporal refusal chain is real. | **Yes.** Factory constructs explicit unallocated state and returns before index access. | institutional `absent/unallocated` only |
| `gy-n12-epoch-transition-signing-authority-unappointed` | **Yes for the refusal surface; positive production remains elsewhere.** | **Yes.** Explicit `NoEpochTransitionSigningAuthority`. | institutional `absent/unallocated` only; LEDGER `producer_missing` is stale |
| `w5-institutional-authority-slots` | **No.** All four named builder tasks are `not_started`; all mandatory symbol families are absent. | **No.** There are no 18 purpose-specific typed-empty slots. | `blocked -> open`, `absent/unallocated`; split by plane/purpose and build first |
| `eval-safety-promotion-authority-producer-missing` | **No.** Existing certificate is for attempted-evaluation admission and must deny promotion; no promotion-specific mechanism exists. | **No.** A hard-coded `owner_ref="absent/unallocated"` obligation is not a slot. | `blocked -> open`, precise `absent/unallocated` |

The standing blanket statement “only institutional prerequisites remain” is therefore false for
five rows in a material sense: three have no typed-empty slot at all, and two more have incomplete
bridges/surfaces around a real slot. Four rows have a real typed refusal surface, though the two
transition rows intentionally leave positive production in a separate engineering row.

### W5 exact set and moved-number cause

Complete unique-ID output:

```text
W5-O5-Q04
W5-O5-Q05
W5-O5-Q10
W5-R2-Q04
W5-R2-Q05
W5-R2-Q06
W5-R2-Q13
W5-R3-Q06
W5-R3-Q08
W5-R4-Q08
W5-R4-Q09
W5-R5-Q02
W5-R5-Q04
W5-R5-Q08
W5-R5-Q09
W5-R5-Q10
W5-R6-Q04
W5-R6-Q05
unique_route_ids=18
```

The inherited “17” did not grow by merge; it was a miscount of the row's existing complete set.
The corrected set contains 18 exact unique identifiers, so the movement cause is arithmetic/census
error, not a newly added route.

Mandatory-symbol census over all 5,107 tracked source/test Python files:

```text
AdaptationTransitionRequest|AdaptationDecisionRecord|RestartEvidenceRecord|KPIControlStateSnapshot
rg_exit=1
GapAcquisitionCase|NonDataAcquisition|non_data_acquisition
rg_exit=1
human_comprehension_established|OperatorComprehension
rg_exit=1
MAEP|MultilingualAuthority|AuthorityEquivalence|CoAuthentic|co_authentic
rg_exit=1
```

### Per-row deciding rules and exact append-only register prose

#### `ds15-semantic-epoch-qualification-authority`

The verdict changes to appointment-only only after a non-test composition root invokes the existing
producer, persists the typed refusal, and an audit/API surface consumes it. Appointment evidence
without that bridge leaves the row `bridge_missing`.

> **TASK Q INSTITUTIONAL AUDIT 2026-09-01 — basis narrowed; status stays `open`.** `EpochChronologyPolicyOwner` and `SemanticEpochQualificationAdapter._policy_owner: EpochChronologyPolicyOwner | None` form a real typed slot; the unallocated factories construct `None` / `_policy_authority_unallocated=True`, and the consumer returns typed `PolicyAdmissionMissingFailure`. The isolated composition persists `PersistedSemanticEpochProductionReceipt(status="not_established", failure_codes=("policy_admission_missing",))`. But across all 2,617 tracked source Python files `admit_acquisition_with_production_semantic_epoch` occurs only as its definition, and its only call is in one test. The surrounding DS15 capability therefore remains `bridge_missing`; the allocation-pass statement that it is already built is superseded. This becomes appointment-only only after a non-test composition root invokes it and an audit/API surface consumes the persisted refusal; appointment evidence then changes the institutional result.

#### `ds15-signed-v2-delegation-mandate-owner-authority`

The verdict changes only when a purpose-specific typed-empty slot, external producer/admission
artifact, production gateway bridge, persisted refusal, and semantic surface test all exist.
Appointment alone changes nothing.

> **TASK Q INSTITUTIONAL AUDIT 2026-09-01 — appointment-only basis refuted; status stays `open`.** `CurrentMandateOwnerEvidence` is a typed external evidence DTO, not a typed-empty mandate-owner slot. `AgentActionAuthorityGateway` requires `mandate_authority_evidence_refs_by_owner_ref: Mapping[str, str]`; a missing key is simply absent and raises `current_mandate_authority_not_established`. Across 2,617 source Python files there are zero gateway constructions, while two tests construct it. `AcquisitionAdmissionSigningSlot.empty()` is purpose-bound to the deterministic admission bundle and cannot stand in for mandate-owner authority. Retype the chain as institutional `absent/unallocated` + mandate-evidence `producer_missing` + gateway `implemented_but_not_orchestrated`; drop `artifact_missing`, which presupposes producer logic that does not exist. The verdict changes only when a purpose-specific typed-empty mandate-owner slot, external producer/admission artifact, production gateway bridge, persisted refusal and semantic surface test all exist; appointment may then remain as the sole residual.

#### `ds18-epoch-history-independent-holder-unappointed`

The verdict changes to appointment-only only when a production lifecycle calls the provider,
persists or audits its typed result, exposes it, and a negative end-to-end test proves the no-holder
arm. A holder appointment without those consumers leaves the capability incomplete.

> **TASK Q INSTITUTIONAL AUDIT 2026-09-01 — basis refuted; status stays `open`.** The holder slot is explicit and typed: `EpochAnchorAppointmentResolution.holder: HolderAppointmentResult`, and `NoEpochAnchorAppointmentResolver` constructs the `UnavailableHolderAppointment` arm with `anchor_holder_not_established`. The production provider is built and injected into `RuntimeContainer`, but the complete 2,617-source-Python census finds no consumer read of `epoch_anchor_custody_provider` after construction and no audit/API/dashboard projection. The surrounding capability is `implemented_but_not_orchestrated + surface_missing`, not appointment-only. That verdict changes only when a production lifecycle calls the provider, persists or audits the typed result, exposes it on a governed surface, and a negative end-to-end test proves the no-holder result; only then does independent-holder appointment remain.

#### `ds18-epoch-predicate-policy-signer-unappointed`

The verdict changes when a purpose-scoped institution supplies independently verified exact
policy/admission/provenance/relation artifacts and the same production call stops returning
`policy_admission_missing`.

> **TASK Q INSTITUTIONAL AUDIT 2026-09-01 — basis holds.** The predicate-policy slot is explicit through `EpochChronologyPolicyOwner` and `_policy_owner: EpochChronologyPolicyOwner | None`; production constructs the unallocated arm, the generic consumer emits `policy_admission_missing`, the temporal bridge consumes it, the access audit records status/provenance, and the HTTP surface renders it under an exact semantic test. Capability state remains institutional `absent/unallocated` only. This verdict changes when a purpose-scoped institution is appointed and its exact content-bound policy/admission/provenance/relation artifacts are independently verified so the same production call no longer returns `policy_admission_missing`.

#### `ds18-epoch-transition-signer-unappointed`

The engineering fact changes only when a real trigger drives and persists a transition; this row's
institutional fact changes only on distinct signer appointment and admitted exact signature. One
without the other does not close both rows.

> **TASK Q INSTITUTIONAL AUDIT 2026-09-01 — basis split, not wholly affirmed.** `EpochTransitionSigningAuthority` and `NoEpochTransitionSigningAuthority` are a real typed-empty-by-construction slot, and the production temporal route renders and audits `epoch_transition_signer_not_established`. The positive transition mechanism is not orchestrated: across 2,617 source Python files there are zero `EpochValidityTransitionProducer(...)` constructions and zero `.produce_and_persist(...)` calls, against one of each in tests. Keep this row `absent/unallocated` because `ds18-positive-transition-production-unorchestrated` separately owns `implemented_but_not_orchestrated`; do not repeat `producer_missing` here. The engineering fact changes when a real trigger and complete owner providers drive and persist a transition; this row’s institutional verdict changes only on distinct signer appointment and admitted exact signature.

#### `gy-n12-epoch-predicate-policy-authority-unappointed`

The verdict changes only when the named institution supplies independently verified exact artifacts
and the same production call succeeds without self-admission.

> **TASK Q INSTITUTIONAL AUDIT 2026-09-01 — basis holds with the 2026-08-30 correction preserved.** The production path does not consult a canonical empty admission index: `from_unallocated_policy_authority()` explicitly constructs the typed empty owner state and `QualificationConsumer.qualify()` directly returns `policy_admission_missing`. That refusal flows through the temporal consumer, audit event and HTTP semantic test. State remains `absent/unallocated`; the mechanism is real independently of the appointment ruling. The verdict changes only when the named institution supplies independently verified exact policy/admission/owner-provenance/owner-relation artifacts and the same production call succeeds without self-admission.

#### `gy-n12-epoch-transition-signing-authority-unappointed`

The institutional verdict changes on appointment/admission of purpose-scoped signing and producer
identity evidence. Producer orchestration changes only the separate DS18 engineering row.

> **TASK Q INSTITUTIONAL AUDIT 2026-09-01 — register narrowing holds; LEDGER is stale.** The typed `EpochTransitionSigningAuthority` slot is explicitly filled by `NoEpochTransitionSigningAuthority`, and the production temporal route renders the typed non-receipt. Positive transition production remains `implemented_but_not_orchestrated`, but the 2026-08-31 register history deliberately moved that engineering conjunct to `ds18-positive-transition-production-unorchestrated`. Therefore this institutional row is `absent/unallocated` only and LEDGER must drop `producer_missing`. Its verdict changes on appointment and admission of both purpose-scoped signing and producer-identity evidence; producer orchestration changes only the separate engineering row.

#### `w5-institutional-authority-slots`

The verdict changes only after all 18 purposes are decomposed by plane/purpose and each has an
explicit typed-empty slot plus complete producer/artifact/bridge/consumer/verification/persistence/
surface/semantic-test chain. Appointing any subset without that mechanism leaves it open.

> **TASK Q INSTITUTIONAL AUDIT 2026-09-01 — basis refuted; `blocked` -> `open` until decomposition and build.** The row contains 18 distinct route IDs, not seventeen: `W5-O5-Q04`, `W5-O5-Q05`, `W5-O5-Q10`, `W5-R2-Q04`, `W5-R2-Q05`, `W5-R2-Q06`, `W5-R2-Q13`, `W5-R3-Q06`, `W5-R3-Q08`, `W5-R4-Q08`, `W5-R4-Q09`, `W5-R5-Q02`, `W5-R5-Q04`, `W5-R5-Q08`, `W5-R5-Q09`, `W5-R5-Q10`, `W5-R6-Q04`, `W5-R6-Q05`. `GY-AQ1`, `GY-CB1`, `GY-ML1` and `GY-CR1` are all `not_started`; their plan-specified mandatory runtime symbols have zero occurrences across all 5,107 tracked source/test Python files. No stronger capability label than `absent/unallocated` is warranted, and the grouped row must be split by purpose/plane before it can be appointment-only. The verdict changes only when every one of the 18 purposes maps to an explicit typed-empty slot and a complete producer/artifact/bridge/consumer/verification/persistence/surface/semantic-test chain; appointment then closes each purpose independently.

#### `eval-safety-promotion-authority-producer-missing`

The verdict changes only after a neutral promotion-purpose contract, typed-empty authority slot,
producer, verifier, persistence bridge, fail-closed N9 consumer, governed surface, and negative
semantic test exist. Appointment may block only the remaining minting act.

> **TASK Q INSTITUTIONAL AUDIT 2026-09-01 — basis refuted; `blocked` -> `open` for the mechanism.** The existing `EvalSafetyCertificate` is authority only for `attempted_evaluation_admission` and is type-constrained to deny `promotion`; it is not a promotion-authority slot. `_eval_safety_obligation` hardcodes `owner_ref="absent/unallocated"` and a prose `producer_missing` diagnosis, while the complete 5,107-file source/test Python census finds no EvalSafety promotion-authority contract or slot. The precise maturity is `absent/unallocated`, weaker than `producer_missing`. The verdict changes only after a neutral purpose-scoped contract, typed-empty signer/authority slot, producer, verifier, persistence bridge, fail-closed N9 consumer, governed surface and negative semantic test land; only the resulting appointment residual may then be blocked.

## Consolidated verdict arithmetic before closeout verification

Primary five-row denominator:

```text
calibration-report-fixture-blanket-fields: reproduced, ambiguous -> open
transitive-runner-closure-unbound: bounded residual confirmed, stays open
gy-census-decisive-property-unmeasured: measurement denominator discharged; row closes after architect transcription
DS11-SCOPE-ADJUDICATION-RECORD: alternative (b), stays open
ds9-human-decision-crash-test-fixture-blocked: reproduced and retyped, stays open
```

Institutional nine-row denominator:

```text
basis fully holds for declared absence: 4
  ds18 predicate; ds18 transition refusal; GY predicate; GY transition refusal

basis materially refuted/narrowed: 5
  ds15 semantic epoch; ds15 mandate owner; ds18 independent holder; W5; EvalSafety promotion

typed-empty slot exists: 6
  ds15 semantic epoch; ds18 independent holder; ds18 predicate; ds18 transition;
  GY predicate; GY transition

typed-empty slot absent: 3
  ds15 mandate owner; W5; EvalSafety promotion
```

No active plan, register, ledger, runtime source, or test source is changed by this journal.

## Closeout verification before final bound reconciliation

The closeout loop used whole-file selectors, without `-x` or `--lf`.

DS11 candidate-contract file:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --directory /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine --frozen --extra test python -m pytest -q -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-root/scope-file-cache /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/core/contracts/test_scope_adjudication.py
```

```text
........                                                                 [100%]
exit 0
collected=8 passed=8 failed=0
```

DS9 human-decision file:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --directory /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine --frozen --extra test python -m pytest -q -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-root/ds9-file-cache /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/http/test_human_decision_service.py
```

```text
exit 1
collected_nodeids=71
failed_nodeids=42
passed_nodeids=29
failure_list_complete=True
```

The exact counts are read from that isolated run's pytest `nodeids` and `lastfailed` cache; the
failure list is a subset of the complete collected set. The two dominant pre-property shapes are
the zero-length `ProductionHumanDecisionBasis` interval and
`HumanDecisionUnavailableError: blocked` before record creation. The named hard-crash node is one
of the 42. This whole-file result corroborates that the imported fixture family is stale; it is not
used as evidence against crash recovery.

Docs lifecycle comparison:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine uv run --directory /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine --frozen --extra test python /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tools/quality/validation/check_docs_lifecycle.py
```

Exact output from that pre-marker run (superseded by the review correction below):

<!-- docs-lifecycle-evidence:start -->
```text
Docs lifecycle gate FAILED:
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `status` front matter.
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `owner` front matter.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-adoption-ledger.json: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-archive-map.json: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/reference/frontend/atlas-v15-adjudication.md: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/research/policy-operations/audits/pao-r0/pao-r0-test-and-fixture-verification.md: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
```
<!-- docs-lifecycle-evidence:end -->

`git diff --check` exited 0 before this receipt was appended. There is no changed Python file, so
Ruff has an empty applicable denominator (`0`) rather than a synthetic path invocation. The failure
pattern register was reopened at closeout; the operative findings remain P35, P37, P38, P40, and
P41 as stated in the opening pattern pass.

## Independent-review corrections and reproducibility supplement

This section is an append-only supersession. Where it conflicts with an earlier verdict, command
description, output label, owner statement, or closeout characterization, this section controls.
The independent review found no critical defect, but found five important evidence defects: the
runner mutation had not yet been behaviorally replayed; `GY-C2` was truthfully `not_measured` but
the row was incorrectly called discharged; several derived summaries were labelled literal output;
the GY test batching was not recorded; and authority decisions lacked finding-level citations.

### Literal current-tree and movement receipts

The opening tracked-path output was a formatted rendering, not literal output of its displayed
one-line command. The following executable command and output supersede that label:

```sh
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python - <<'PY'
import collections
import pathlib
import subprocess

root = "/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine"
paths = subprocess.check_output(
    ["git", "-C", root, "ls-files", "--full-name", "--", ":/"],
    text=True,
).splitlines()
counts = collections.Counter(
    pathlib.PurePosixPath(path).suffix or "<no_ext>" for path in paths
)
print(f"DENOMINATOR full_current_tracked_paths {len(paths)}")
print("FILE_TYPES " + " ".join(f"{key}={counts[key]}" for key in sorted(counts)))
print(f"FILE_TYPE_SUM {sum(counts.values())}")
PY
```

```text
DENOMINATOR full_current_tracked_paths 10478
FILE_TYPES .blob=11 .cfg=1 .cjs=9 .css=17 .csv=15 .cypher=2 .duckdb=4 .example=3 .html=3 .ini=11 .js=5 .json=1210 .jsonc=1 .jsonl=5 .lock=1 .md=1635 .mdc=1 .mjs=36 .pkl=2 .png=36 .py=5737 .pyi=5 .rego=23 .reproducible=1 .sh=45 .sql=6 .svg=18 .tf=1 .tmpl=7 .toml=217 .tpl=1 .ts=507 .tsx=716 .txt=5 .typed=2 .webm=3 .yaml=85 .yml=69 .zip=4 <no_ext>=18
FILE_TYPE_SUM 10478
```

Likewise, the earlier movement blocks were derived summaries rather than literal output of bare
`git diff --name-status`. Their counts remain correct; their manifest hash strings are superseded
by this exact serializer and are not used by any verdict:

```sh
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python - <<'PY'
import collections
import hashlib
import subprocess

root = "/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine"
pairs = (
    ("c1354ec7a9664ae86275b025fb2a0c4dc0726d79", "50b08b00527c241ac3bb9cb5eac10b7201529981", "c135..50b"),
    ("50b08b00527c241ac3bb9cb5eac10b7201529981", "f6c465648d0b55b316452e982c62f6db6a0e051e", "50b..f6c"),
)
for old, new, label in pairs:
    raw = subprocess.check_output(
        ["git", "-C", root, "diff", "--name-status", "--no-renames", old, new, "--", ":/"],
        text=True,
    )
    rows = raw.splitlines()
    counts = collections.Counter(row.split("\t", 1)[0] for row in rows)
    membership = "\n".join(
        row for row in rows if row.startswith(("A\t", "D\t"))
    ) + "\n"
    print(
        f"{label} A={counts['A']} D={counts['D']} M={counts['M']} "
        f"NET={counts['A'] - counts['D']:+d}"
    )
    print(f"{counts['A'] + counts['D']} A/D lines")
    print(f"sha256={hashlib.sha256(membership.encode()).hexdigest()}")
PY
```

```text
c135..50b A=509 D=18 M=802 NET=+491
527 A/D lines
sha256=76a78d8c96c026cc802fcd74d56ed78d7b87311164e9971dab7117dd0145ba2d
50b..f6c A=118 D=1 M=361 NET=+117
119 A/D lines
sha256=c5597906b94495591d3cbc656fbafc5239af97ca26799b9eba805948e3cb9ed4
```

The causal account is unchanged: `+491 = 509 added - 18 deleted`, then
`+117 = 118 added - 1 deleted`; the historical displayed `+469` additionally subtracts the 22
outer paths because the older statement changed scope from full tree to product subtree.

### GY verdict correction

The phrases “denominator discharged” and “row closes after architect transcription” above are
withdrawn. The correct result is a defensible partial census:

```text
13 pass + 7 fail + 1 not_measured = 21
```

`GY-C2` is the exact named remainder. Its green delegation test consumes caller-constructed
dictionaries, including `model_completeness="declared_complete"`, and does not exercise the quoted
“valid verdict on real input” property. The debt row therefore remains `open`. The seven direct
failures imply a *conditional*, not yet authoritative, distribution change:

```text
current:     48 executed + 1 not_executable + 21 not_started + 2 ambiguous = 72
if applied: 41 executed + 1 not_executable + 21 not_started + 9 ambiguous = 72
```

The seven required `executed -> ambiguous` rows are exactly `GY-M1`, `GY-C1`, `GY-C3`, `GY-F1`,
`GY-J`, `GY-L`, and `GY-S3`. None of those plan edits is made in Task Q.

Corrected exact register prose, superseding the earlier GY block in full:

> **TASK Q DECISIVE-PROPERTY RE-MEASUREMENT 2026-09-01 — remains `open`.** At branch `codex/debt-q-remeasure-and-typing`, head `f6c465648d0b55b316452e982c62f6db6a0e051e`, the historical 2026-08-30 census denominator was re-derived from introducing commit `73d930f8284682fafc283c2b78c54d64bbecf1dd`: exactly 24 contiguous delivered-artifact rows (`GY-M1` through `GY-S3`) in the authoritative GY task table, minus the three historically measured rows (`GY-D1`, `GY-M2`, `GY-K`), leaves exactly 21 rows. Exact-node pytest with `-x --lf`, an isolated cache and a prior positive control produced 13 direct selected-property passes (`GY-B`, `GY-H`, `GY-D2`, `GY-D3`, `GY-E`, `GY-I`, `GY-F2`, `GY-F3`, `GY-G`, `GY-S0`, `GY-S1`, `GY-N-V`, `GY-S2`), seven direct failures (`GY-M1`, `GY-C1`, `GY-C3`, `GY-F1`, `GY-J`, `GY-L`, `GY-S3`), and one `not_measured` row (`GY-C2`). `GY-C2` remains `not_measured` because its available green test delegates over caller-constructed, consumer-asserted dictionaries and does not exercise the quoted “valid verdict on real input” property. The verdict rule is: a direct failure of any quoted `Done when` predicate overrides delivered-artifact presence and requires `executed -> ambiguous`; a selected-property pass establishes only that conjunct, never the task’s other `Done when` clauses or implicit §3.5.5 gate; a declared-premise or proxy instrument is not a decisive measurement. If the seven direct failures are accepted and transcribed by the GY plan owner, the conditional distribution would be `72 = 41 executed + 0 in_flight + 1 not_executable + 21 not_started + 9 ambiguous`, but that distribution is not authoritative yet. This debt row remains open because `GY-C2` lacks a direct real-input measurement, the 21 row-level notes and seven status changes have not been appended to the authoritative GY plan, and `LEDGER.md` has not been regenerated and diffed from those authoritative changes.

### GY actual command grouping and exact material output

The earlier statement that every discovery run used one substituted exact node is inaccurate.
Every selector was exact, but several invocations batched exact node IDs and stopped at the first
red under `-x`. These are the actual deciding batches; the solver-less `GY-M1` non-receipt is
excluded, and the solver-enabled isolated rerun below is binding.

Five-row loop batch (`GY-B`, `GY-H`, `GY-D2`, `GY-D3`, `GY-E`):

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -m pytest \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_workspace_loop.py::test_slice0_rejects_non_active_operation_execution \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_workspace_loop.py::test_loop_terminal_precedence_blocks_acquisition_when_ceiling_is_unrepaired \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_workspace_loop.py::test_connector_and_source_contract_admission_fail_closed \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_workspace_loop.py::test_semantic_adequacy_benchmark_rejects_negative_control_and_records_recall \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_workspace_loop.py::test_slice0_acquire_continuation_emits_costed_acquisition_required_terminal \
-vv -x --lf -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-gy/pytest-cache
```

```text
test_slice0_rejects_non_active_operation_execution PASSED
test_loop_terminal_precedence_blocks_acquisition_when_ceiling_is_unrepaired PASSED
test_connector_and_source_contract_admission_fail_closed PASSED
test_semantic_adequacy_benchmark_rejects_negative_control_and_records_recall PASSED
test_slice0_acquire_continuation_emits_costed_acquisition_required_terminal PASSED
======================== 5 passed in 579.96s ========================
exit 0
```

The next actual retries used this exact prefix and suffix around the selector lists shown below:

```text
prefix=/usr/bin/perl -e 'my $s=shift @ARGV; alarm $s; exec @ARGV or die $!;' 1800 /usr/bin/env PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -m pytest
suffix=-vv -x --lf -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-gy/pytest-cache
```

`GY-C1` first-red batch, exact selector order:

```text
tests/unit/runtime/quality/test_workspace_workflow_playbook_projection.py::test_workspace_loop_phase2_playbook_can_deviate_to_refine_blocker
tests/unit/runtime/quality/test_workspace_spine_repair_gates.py::test_governance_tail_verifier_delegates_to_governance_node_owner
tests/integration/runtime_quality/test_workspace_foundry_consumption.py::test_phase2_estimate_consumes_real_foundry_method_output_with_measurement_authority
tests/unit/runtime/quality/test_workspace_agent_proposal_bridge.py::test_agent_event_bridge_persists_unmocked_tool_loop_event_bundle
tests/unit/runtime/quality/test_workspace_composition.py::test_feedback_composition_is_invalid_and_requires_joint_grounding
tests/unit/runtime/quality/test_substrate_registry.py::test_substrate_registry_registration_is_free_grow_and_changes_version
tests/unit/core/contracts/test_value_outer_set.py::test_value_outer_set_compare_is_conservative_and_unknown_on_timeout
tests/integration/runtime_quality/test_gy_s2_knowledge_substrate_lift.py::test_l2_transport_and_contested_edges_lower_to_bounded_nonpoint_sets
tests/unit/runtime/quality/test_intervention_substrate.py::test_intervention_substrate_behavior_report_exercises_real_space_and_mutations
```

Each selector above was passed with the absolute worktree prefix
`/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/` between the exact
prefix and suffix. Literal material output:

```text
GY-C1 FAILED
UnknownNodeError:
Unknown node_id: scientist.node_build_literature_prior@1.0.0
======================== 1 failed in 218.71s ========================
exit 1
```

`GY-C2` / `GY-C3` retry used the same list minus `GY-C1`. Literal material output before `-x`:

```text
GY-C2 PASSED
GY-C3 FAILED
assert outcome.status == "ok"
AssertionError: assert 'fail' == 'ok'
=================== 1 failed, 1 passed in 133.24s ====================
exit 1
```

Six-row `GY-I`, `GY-G`, `GY-S0`, `GY-N-V`, `GY-S2`, `GY-S3` batch used these exact absolute-node
suffixes in that order:

```text
tests/unit/runtime/quality/test_workspace_agent_proposal_bridge.py::test_agent_event_bridge_persists_unmocked_tool_loop_event_bundle
tests/unit/runtime/quality/test_workspace_composition.py::test_feedback_composition_is_invalid_and_requires_joint_grounding
tests/unit/runtime/quality/test_substrate_registry.py::test_substrate_registry_registration_is_free_grow_and_changes_version
tests/unit/core/contracts/test_value_outer_set.py::test_value_outer_set_compare_is_conservative_and_unknown_on_timeout
tests/integration/runtime_quality/test_gy_s2_knowledge_substrate_lift.py::test_l2_transport_and_contested_edges_lower_to_bounded_nonpoint_sets
tests/unit/runtime/quality/test_intervention_substrate.py::test_intervention_substrate_behavior_report_exercises_real_space_and_mutations
```

```text
GY-I PASSED
GY-G PASSED
GY-S0 PASSED
GY-N-V PASSED
GY-S2 PASSED
GY-S3 FAILED
assert report["coverage"]["method_route"]["available"] == report["coverage"]["method_route"]["total"]
E assert 3 == 4
=================== 1 failed, 5 passed in 227.22s ====================
exit 1
```

The authority/artifact retry first ran exact nodes `GY-S1`, `GY-F1`, `GY-F2`, `GY-F3`, `GY-J`,
`GY-L` under the same prefix/suffix and stopped at `GY-F1`:

```text
GY-F1 FAILED
RuntimeHTTPError: Natural-language production runs require a configured LLM model.
code="llm_model_unconfigured"
FrozenInstanceError: cannot assign to field '__traceback__'
======================== 1 failed in 328.85s ========================
exit 1
```

The five-node retry `GY-S1`, `GY-F2`, `GY-F3`, `GY-J`, `GY-L` produced:

```text
GY-F2 PASSED
GY-F3 PASSED
GY-J FAILED
ValueError: claim_ledger_owner_store_mismatch
=================== 1 failed, 2 passed in 231.14s ====================
exit 1
```

The two-node retry `GY-S1`, `GY-L` produced:

```text
GY-L FAILED
ValueError: claim_ledger_owner_store_mismatch
======================== 1 failed in 166.19s ========================
exit 1
```

The isolated `GY-S1` exact command was:

```sh
/usr/bin/perl -e 'my $s=shift @ARGV; alarm $s; exec @ARGV or die $!;' 1800 /usr/bin/env PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -m pytest /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/integration/runtime_quality/test_data_state_substrate.py::test_real_l4_data_state_builds_populated_world_model_record_and_executes_sim -vv -x --lf -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-gy/pytest-cache
```

```text
PASSED [100%]
======================== 1 passed in 151.70s ========================
exit 0
```

The binding solver-enabled `GY-M1` command was:

```sh
/usr/bin/perl -e 'my $s=shift @ARGV; alarm $s; exec @ARGV or die $!;' 1800 /usr/bin/env PYTHONDONTWRITEBYTECODE=1 uv run --frozen --extra test --extra solvers python -m pytest /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_generated_artifact_lifecycle_is_scan_based -vv -x --lf -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-gy/pytest-cache
```

The tool workdir for that exact invocation was
`/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine`.

```text
assert report["status"] == "pass"
AssertionError: assert 'fail' == 'pass'
======================== 1 failed in 163.38s ========================
exit 1
```

The isolated `GY-S3` instrument check repeated the exact node already named above and produced:

```text
assert report["status"] == "pass"                         # passed
assert world_slot.bound == world_slot.total              # passed
assert law_trace.traced == law_trace.total                # passed
assert method_route.available == method_route.total
E assert 3 == 4
======================== 1 failed in 194.97s ========================
exit 1
```

The complete committed-material/documentary set named earlier is now enumerated by an executable
tracked-membership census:

```sh
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python - <<'PY'
import pathlib
import subprocess

root = pathlib.Path("/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine")
json_paths = (
    "architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_generated_public_lifecycle_audit.json",
    "architecture/policy_design_case/layer3_gy_workflow_failure_authority_proofs.json",
    "architecture/policy_design_case/layer3_gy_cas_integrity_reports.json",
    "architecture/policy_design_case/layer3_gy_secret_pii_scan_reports.json",
    "architecture/policy_design_case/layer3_gy_time_source_envelope_audit.json",
    "architecture/policy_design_case/layer3_gy_authority_candidate_inventory.json",
    "architecture/policy_design_case/layer3_gy_graded_outcome_routing_report.json",
    "architecture/policy_design_case/layer3_gy_outcome_run.json",
    "architecture/policy_design_case/layer3_gy_data_state_substrate_contract.json",
)
markdown_paths = (
    "docs/plans/active/layer3-slices/GY-engine-subordination.md",
    "docs/plans/active/DEBT-REGISTER.md",
    "docs/plans/active/LEDGER.md",
)
for kind, paths in (("json", json_paths), ("markdown", markdown_paths)):
    for path in paths:
        subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", path],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        print(f"{kind}\ttracked\t{path}")
    print(f"{kind}_denominator={len(paths)}")
PY
```

```text
json tracked architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_generated_public_lifecycle_audit.json
json tracked architecture/policy_design_case/layer3_gy_workflow_failure_authority_proofs.json
json tracked architecture/policy_design_case/layer3_gy_cas_integrity_reports.json
json tracked architecture/policy_design_case/layer3_gy_secret_pii_scan_reports.json
json tracked architecture/policy_design_case/layer3_gy_time_source_envelope_audit.json
json tracked architecture/policy_design_case/layer3_gy_authority_candidate_inventory.json
json tracked architecture/policy_design_case/layer3_gy_graded_outcome_routing_report.json
json tracked architecture/policy_design_case/layer3_gy_outcome_run.json
json tracked architecture/policy_design_case/layer3_gy_data_state_substrate_contract.json
json_denominator=9
markdown tracked docs/plans/active/layer3-slices/GY-engine-subordination.md
markdown tracked docs/plans/active/DEBT-REGISTER.md
markdown tracked docs/plans/active/LEDGER.md
markdown_denominator=3
```

Generator ownership is also explicit: workflow-failure authority uses
`check_layer3_workflow_failure_authority.py`; CAS/secret reports use
`check_layer3_artifact_surface_safety.py`; time-source/inventory reports use
`check_layer3_time_source_authority.py`; graded-outcome/outcome-run reports use
`check_layer3_gy_loop_artifacts.py`; data-state uses
`check_layer3_gy_data_state_substrate_contract.py`. The Task-0 audit exposes validation only, not a
writer. The GY plan and register are authoritative hand-maintained documents; `LEDGER.md` is
generated by `check_debt_ledger.py --write`.

### Authority findings controlling DS11 and the institutional audit

- `S0-K03` is ratified at
  `docs/system-design-decisions/stage0-custody-kernel-ratification.md:96`; its exact one-plane chain
  and mixed-row decomposition rule are at
  `docs/research/policy-operations/consolidation/stage0/stage0-consensus-kernel.md:86-108`.
- `S0-K06` is ratified at `stage0-custody-kernel-ratification.md:99`; the authority closure tuple
  and fail-closed rule are at `stage0-consensus-kernel.md:143-157`; the binding candidate/authority
  band application note is at `stage0-custody-kernel-ratification.md:155-171`.
- The ordered four-way rule and PolicyOS ownership of typed INTEGRATE/OBSERVE contracts are at
  `docs/system-design-decisions/policyos-identity-and-custody-boundary.md:100-122`.
- Identity decision §9 item 5, at that document's lines 180-199, says institutional absence binds
  the claim rather than capability and requires the mechanism to remain fully built with a typed
  empty signature slot. Item 6, lines 201-225, says appointment binds the minting act rather than
  vocabulary or pure verification.

Those findings produce one shared institutional deciding rule: an incomplete typed mechanism is
`open` and executable regardless of institutional absence; a complete mechanism with a
purpose-specific typed-empty slot may leave only the authority-band appointment
`absent/unallocated`. Appointment may block the minting act, never construction of the contract,
verifier, persistence bridge, consumer, or governed refusal surface.

For DS11 specifically, the authoritative owner remains `team-architecture` at
`docs/plans/active/atlas-slices/DS11-trust-docs-posture.md:1300-1303` and
`docs/plans/active/DEBT-REGISTER.md:287`. The earlier journal wording presented a runtime/scientist
successor split as an allocation; that is too strong. Task Q recommends that routing as the
smallest architecture-compatible implementation split, but it is not a ratified appointment.
This ownership precision does not change decision (b): candidate-only cannot close an
authority-effect capability, and the row stays executable and `open` under its authoritative
owner.

Corrected DS11 exact register prose, superseding the ownership sentence in the earlier block:

> **TASK Q ARCHITECT DECISION 2026-09-01 — alternative (b); status stays `open`.** Ratified `S0-K03` requires one-plane adjudication; ratified `S0-K06` and its binding application note permit the candidate band to carry typed unknowns but require subject/purpose/tenant/jurisdiction/producer/time/use closure before authority-bearing use. The candidate artifact is therefore correct but not terminal: its strict contract says `status=candidate_only`, `authority_effect=none`, `closure_effect=none`, `authoritative_for=()`, forbids use for scope rulings and claim-lifecycle mutation, and carries typed resolver/consumer limitations. Five candidate tests (eight cases) pass; the named production identity remains absent by design. Closure requires independently established predicate evidence, a purpose-scoped minting boundary, typed persisted `ScopeAdjudicationRecord`, real lifecycle orchestration/consumer, governed audit/API projection, and negative mixed-plane/substitution/provenance/sibling-bypass tests. Only that chain may introduce `test_four_way_ruling_is_produced_consumed_and_plane_specific`. Rejected: candidate-only terminal closure, because it would close a P01 contract while the artifact prohibits the claimed authority effect. Authoritative owner remains `team-architecture` (`DS11-trust-docs-posture.md:1300-1303`; `DEBT-REGISTER.md:287`). Runtime/scientist routing for persistence, bridge, consumer and surface is a Task Q recommendation, not an already-ratified allocation.

### Institutional and DS9 extraction commands

The exact source/test denominator was produced by this command, not by an omitted census:

```sh
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -c 'import pathlib,subprocess; root="/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine";
def tracked(scope): return subprocess.check_output(["git","-C",root,"ls-files","--",scope],text=True).splitlines()
src=tracked("src"); tests=tracked("tests"); print("src tracked files={}; src Python files={}".format(len(src),sum(pathlib.PurePosixPath(path).suffix==".py" for path in src))); print("tests tracked files={}; tests Python files={}".format(len(tests),sum(pathlib.PurePosixPath(path).suffix==".py" for path in tests))); print("combined tracked files={}; combined Python files={}".format(len(src)+len(tests),sum(pathlib.PurePosixPath(path).suffix==".py" for path in src+tests)))'
```

```text
src tracked files=2827; src Python files=2617
tests tracked files=2990; tests Python files=2490
combined tracked files=5817; combined Python files=5107
```

Exact key-call commands:

```sh
git -C /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine grep -n -F 'EpochValidityTransitionProducer(' -- 'src/**/*.py' 'tests/**/*.py'
git -C /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine grep -n -F '.produce_and_persist(' -- 'src/**/*.py' 'tests/**/*.py'
git -C /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine grep -n -F 'AgentActionAuthorityGateway(' -- 'src/**/*.py' 'tests/**/*.py'
git -C /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine grep -n -F 'admit_acquisition_with_production_semantic_epoch(' -- 'src/**/*.py' 'tests/**/*.py'
```

Literal concatenated output:

```text
tests/unit/runtime/quality/test_epoch_validity_cascade.py:1273:    producer = EpochValidityTransitionProducer(
tests/unit/runtime/quality/test_epoch_validity_cascade.py:1281:    result = producer.produce_and_persist(
tests/integration/core_runtime/test_acquisition_admission_bundle.py:411:    return AgentActionAuthorityGateway(
tests/unit/runtime/quality/test_agent_action_authority.py:586:    gateway = authority.AgentActionAuthorityGateway(
src/polisyos/runtime/quality/acquisition_executor.py:1829:def admit_acquisition_with_production_semantic_epoch(
tests/unit/data_forge/domains/catalog/knowledge/test_acquisition_authority.py:549:    receipt = admit_acquisition_with_production_semantic_epoch(
```

The W5 route count was generated directly from the one authoritative row:

```sh
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -c 'import pathlib,re; path=pathlib.Path("/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/docs/plans/active/DEBT-REGISTER.md"); row=next(line for line in path.read_text().splitlines() if line.startswith("| `w5-institutional-authority-slots` |")); ids=sorted(set(re.findall(r"W5-(?:O5|R[2-6])-Q[0-9]{2}",row))); print(chr(10).join(ids)); print(f"unique_route_ids={len(ids)}")'
```

```text
W5-O5-Q04
W5-O5-Q05
W5-O5-Q10
W5-R2-Q04
W5-R2-Q05
W5-R2-Q06
W5-R2-Q13
W5-R3-Q06
W5-R3-Q08
W5-R4-Q08
W5-R4-Q09
W5-R5-Q02
W5-R5-Q04
W5-R5-Q08
W5-R5-Q09
W5-R5-Q10
W5-R6-Q04
W5-R6-Q05
unique_route_ids=18
```

No merge added the eighteenth identifier: all 18 are in the one inherited row at this base. The
moved-number cause is the older row's arithmetic/census error, not repository growth.

The four W5 mandatory-symbol families were checked over the exact 5,107 tracked Python inputs:

```sh
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -c 'import pathlib,re,subprocess; root=pathlib.Path("/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine"); tracked=[]
for scope in ("src","tests"): tracked.extend(subprocess.check_output(["git","-C",str(root),"ls-files","--",scope],text=True).splitlines())
files=[root/path for path in tracked if pathlib.PurePosixPath(path).suffix==".py"]; patterns=("AdaptationTransitionRequest|AdaptationDecisionRecord|RestartEvidenceRecord|KPIControlStateSnapshot","GapAcquisitionCase|NonDataAcquisition|non_data_acquisition","human_comprehension_established|OperatorComprehension","MAEP|MultilingualAuthority|AuthorityEquivalence|CoAuthentic|co_authentic"); print(f"tracked_python_denominator={len(files)}")
for pattern in patterns: hits=[str(path.relative_to(root)) for path in files if re.search(pattern,path.read_text(errors="replace"))]; print(pattern); print(f"matching_files={len(hits)}"); print(chr(10).join(hits) if hits else "<none>")'
```

```text
tracked_python_denominator=5107
AdaptationTransitionRequest|AdaptationDecisionRecord|RestartEvidenceRecord|KPIControlStateSnapshot
matching_files=0
<none>
GapAcquisitionCase|NonDataAcquisition|non_data_acquisition
matching_files=0
<none>
human_comprehension_established|OperatorComprehension
matching_files=0
<none>
MAEP|MultilingualAuthority|AuthorityEquivalence|CoAuthentic|co_authentic
matching_files=0
<none>
```

The DS9 whole-file counts were extracted from the isolated cache by this exact command:

```sh
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -c 'import json,pathlib; cache=pathlib.Path("/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-root/ds9-file-cache/v/cache"); nodeids=json.loads((cache/"nodeids").read_text()); failed=json.loads((cache/"lastfailed").read_text()); target="tests/unit/runtime/http/test_human_decision_service.py"; collected=sorted(node for node in nodeids if node.startswith(target+"::")); failed_nodes=sorted(node for node in failed if node.startswith(target+"::")); passed=sorted(set(collected)-set(failed_nodes)); print(f"collected_nodeids={len(collected)}"); print(f"failed_nodeids={len(failed_nodes)}"); print(f"passed_nodeids={len(passed)}"); print(f"failure_keys_subset_of_collected={set(failed_nodes).issubset(collected)}")'
```

```text
collected_nodeids=71
failed_nodeids=42
passed_nodeids=29
failure_keys_subset_of_collected=True
```

This supersedes the looser label `failure_list_complete`; it proves only that all 42 cache failure
keys belong to the 71-node collected denominator.

### Runner behavioral falsifier replay

The earlier runner section's lexical/source census did **not** by itself rerun the behavioral
falsifier. It remains useful as a complete candidate census, but the claim “falsifier replayed” is
superseded by the actual mutation replay below.

Executing party: `/root/census_calibration_runner`. Every shell call had tool workdir
`/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine`; the deciding
launcher and persistence paths and the mutation target were absolute. Missing workspace dependency
links were provisioned first with `corepack pnpm install --frozen-lockfile --offline`; it exited 0,
left only ignored dependencies, and its existing `prepare` lifecycle installed Git hooks in the
shared Git directory.

The required clean positive control ran first through the actual C10 persistence/admission script:

```sh
printf '%s\n' '{"operation":"persist_atlas_surface_readiness_claims"}' |
POLISYOS_CAS_BACKEND=filesystem \
POLISYOS_CAS_ROOT=/tmp/polisyos-c10-replay.emdhHd/cas-positive \
PYTHONDONTWRITEBYTECODE=1 \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/apps/runtime-dashboard/scripts/persist_atlas_evidence.py
```

Exact material output:

```text
operation=persist_atlas_surface_readiness_claims
report_claim_count=5
projection_claim_count=5
claim_report_artifact_id=sha256:6a997e23c952faeb48f064b46a633c4bc1ea89c6569199f438d79b881e4f1f7e
projection_artifact_id=sha256:666f49fbec10991c6846083ac5dcccbe7089d841604241b3c029ae14ba5683fa
POSITIVE_EXIT_CODE=0
```

Pre-mutation identity:

```text
Vite entry path=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/node_modules/.pnpm/vite@7.3.2_@types+node@24.12.2_jiti@2.6.1_lightningcss@1.32.0_terser@5.46.2/node_modules/vite/dist/node/index.js
Vite version=7.3.2
Vite entry sha256=8b142bd1231a46bf2cad4c05b3f76de5b183064ee771b9934fbaffb70b914652
Vitest entry path=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/node_modules/.pnpm/vitest@4.1.5_@types+node@24.12.2_@vitest+browser-playwright@4.1.5_@vitest+coverage-v8@4_5a0df7f6c822d847e3d5462c0680e92f/node_modules/vitest/vitest.mjs
Vitest version=4.1.5
Vitest entry sha256=39db22f579acf5639bbb17a261408debbde03f4692c0c439e77e7f13aeba74d6
transitive config.js sha256=7b2e8f85ebe8e6c903dec7dc426a2459776a99e63b7db1659be28b0a81597aec
```

The transitive chunk was backed up, compared, and changed with this absolute-path patch. Its one
empty context line is rendered with a visible label so the journal itself carries no trailing space:

```diff
*** Begin Patch
*** Update File: /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/apps/runtime-dashboard/node_modules/vite/dist/node/chunks/config.js
@@
 import zlib from "zlib";
 import * as qs from "node:querystring";
[blank context line: one unified-diff context-prefix space]
+process$1.stderr.write("C10_TRANSITIVE_VITE_CHUNK_MUTATION_ACTIVE\n");
+
 //#region src/shared/constants.ts
*** End Patch
```

Its SHA-256 changed from
`7b2e8f85ebe8e6c903dec7dc426a2459776a99e63b7db1659be28b0a81597aec` to
`bbce760e7b11236504dc1badd7a1263177e12ef9c5d3a1edb9987df277c30bdf`; both entry paths,
versions and entry hashes above remained unchanged.

The fixed launcher witness command was:

```sh
set +e
mutated_launcher_output=$(env -i HOME=/var/empty LANG=C LC_ALL=C PATH=/usr/bin:/bin TZ=UTC /opt/homebrew/Cellar/node@22/22.22.2_1/bin/node /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/apps/runtime-dashboard/scripts/reconcile_atlas_surface_readiness.mjs 2>/tmp/polisyos-c10-replay.emdhHd/mutated-launcher.stderr)
mutated_launcher_status=$?
printf '%s' "$mutated_launcher_output" | /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -c 'import json,sys; x=json.load(sys.stdin); print(json.dumps({"report_schema":x.get("report_schema"),"claim_count":len(x.get("claims",[])),"claim_ids":[c.get("claim_id") for c in x.get("claims",[])],"vite_loader":x.get("producer",{}).get("vite_loader")},sort_keys=True,separators=(",",":")))'
printf 'MUTATED_LAUNCHER_STDERR='; tr -d '\r' </tmp/polisyos-c10-replay.emdhHd/mutated-launcher.stderr
printf 'MUTATED_LAUNCHER_EXIT_CODE=%d\n' "$mutated_launcher_status"
```

Literal output:

```text
{"claim_count":5,"claim_ids":["route-redirect-launch:readiness_state:implemented","route-redirect-sources:readiness_state:implemented","route-redirect-data:readiness_state:implemented","route-redirect-lex:readiness_state:implemented","route-redirect-health:readiness_state:implemented"],"report_schema":{"id":"polisyos.atlas.surface-readiness-claim-report","version":"2.0.0"},"vite_loader":{"path":"/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/node_modules/.pnpm/vite@7.3.2_@types+node@24.12.2_jiti@2.6.1_lightningcss@1.32.0_terser@5.46.2/node_modules/vite/dist/node/index.js","sha256":"8b142bd1231a46bf2cad4c05b3f76de5b183064ee771b9934fbaffb70b914652","version":"7.3.2"}}
MUTATED_LAUNCHER_STDERR=C10_TRANSITIVE_VITE_CHUNK_MUTATION_ACTIVE
MUTATED_LAUNCHER_EXIT_CODE=0
```

This proves the changed transitive chunk actually executed. The actual C10 admission then ran under
the mutation:

```sh
mkdir -p /tmp/polisyos-c10-replay.emdhHd/cas-mutated
set +e
mutated_admission_output=$(printf '%s\n' '{"operation":"persist_atlas_surface_readiness_claims"}' | POLISYOS_CAS_BACKEND=filesystem POLISYOS_CAS_ROOT=/tmp/polisyos-c10-replay.emdhHd/cas-mutated PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/apps/runtime-dashboard/scripts/persist_atlas_evidence.py 2>&1)
mutated_admission_status=$?
printf '%s' "$mutated_admission_output" | /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -c 'import json,sys; x=json.load(sys.stdin); r=x.get("resolved_claim_report",{}).get("report",{}); p=x.get("resolved_projection",{}).get("projection",{}); print(json.dumps({"operation":x.get("operation"),"error":x.get("error"),"claim_report_artifact_id":x.get("claim_report_ref",{}).get("artifact_id"),"projection_artifact_id":x.get("projection_ref",{}).get("artifact_id"),"report_claim_count":len(r.get("claims",[])),"projection_claim_count":len(p.get("claims",[])),"claim_ids":[c.get("claim_id") for c in p.get("claims",[])],"vite_loader":r.get("producer",{}).get("vite_loader"),"observation_statuses":[c.get("basis",{}).get("observation",{}).get("status") for c in p.get("claims",[])]},sort_keys=True,separators=(",",":")))'
printf 'MUTATED_ADMISSION_EXIT_CODE=%d\n' "$mutated_admission_status"
```

Literal output:

```text
{"claim_ids":["route-redirect-launch:readiness_state:implemented","route-redirect-sources:readiness_state:implemented","route-redirect-data:readiness_state:implemented","route-redirect-lex:readiness_state:implemented","route-redirect-health:readiness_state:implemented"],"claim_report_artifact_id":"sha256:df9491ff42c3a45cd1d97436f503577e874c26a23b78f3f3dcb41d60b0c16767","error":null,"observation_statuses":["observed","observed","observed","observed","observed"],"operation":"persist_atlas_surface_readiness_claims","projection_artifact_id":"sha256:dcfba32e685cd6704fd1b375f66e3fb7aecc704e806ca56093634b4c51e553b6","projection_claim_count":5,"report_claim_count":5,"vite_loader":{"path":"/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/node_modules/.pnpm/vite@7.3.2_@types+node@24.12.2_jiti@2.6.1_lightningcss@1.32.0_terser@5.46.2/node_modules/vite/dist/node/index.js","sha256":"8b142bd1231a46bf2cad4c05b3f76de5b183064ee771b9934fbaffb70b914652","version":"7.3.2"}}
MUTATED_ADMISSION_EXIT_CODE=0
```

The changed chunk was restored from its byte-preserving backup. Absolute final readback:

```sh
git -C /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine symbolic-ref --short HEAD
git -C /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine rev-parse HEAD
shasum -a 256 /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/apps/runtime-dashboard/node_modules/vite/dist/node/index.js /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/apps/runtime-dashboard/node_modules/vite/dist/node/chunks/config.js /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/apps/runtime-dashboard/node_modules/vitest/vitest.mjs
printf 'TRACKED_DIFF_EXIT='; git -C /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine diff --quiet; printf '%d\n' "$?"
git -C /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine status --short
```

```text
codex/debt-q-remeasure-and-typing
f6c465648d0b55b316452e982c62f6db6a0e051e
8b142bd1231a46bf2cad4c05b3f76de5b183064ee771b9934fbaffb70b914652  /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/apps/runtime-dashboard/node_modules/vite/dist/node/index.js
7b2e8f85ebe8e6c903dec7dc426a2459776a99e63b7db1659be28b0a81597aec  /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/apps/runtime-dashboard/node_modules/vite/dist/node/chunks/config.js
39db22f579acf5639bbb17a261408debbde03f4692c0c439e77e7f13aeba74d6  /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/apps/runtime-dashboard/node_modules/vitest/vitest.mjs
TRACKED_DIFF_EXIT=0
?? docs/superpowers/journals/2026-09-01-debt-q-remeasure-and-typing.md
```

Additional restoration receipts were `RESTORE_CMP_EXIT=0`, `MARKER_SEARCH_EXIT=1`, and
`SCRATCH_REMOVED_EXIT=0`. No source or test file remains changed.

The divergence is at `persist_atlas_evidence.py:1582-1597` and `:2070-2086`: admission identifies
and rechecks only Vite's entry path/version/bytes. Child stderr is consulted only on nonzero return
at `:2088-2093`. The launcher imports Vite at
`reconcile_atlas_surface_readiness.mjs:4`; Vite's entry imports `./chunks/config.js` at `index.js:2`.

Corrected exact register prose, superseding the earlier static-only runner block:

> **TASK Q BEHAVIORAL FALSIFIER REPLAY 2026-09-01 — `reproduced_at_f6c465648`; status stays `open`, `absent/unallocated`.** Executed by `/root/census_calibration_runner` through the actual C10 persistence/admission path. A clean positive control exited 0 and admitted five observed claims. The transitively loaded Vite `dist/node/chunks/config.js` was then changed from SHA-256 `7b2e8f85…` to `bbce760e…` while the Vite entry remained path-identical, version `7.3.2`, SHA-256 `8b142bd…`, and the Vitest entry remained version `4.1.5`, SHA-256 `39db22f…`. The fixed launcher emitted the mutation marker from that chunk and exited 0; the enclosing C10 admission also exited 0, persisted five claims, and classified all five observations as `observed`. The chunk was restored byte-for-byte and no tracked diff remains. Thus the transitive-runner closure is behaviorally unbound; external identity/verification remains `not_established`. Close only when an out-of-band signed identity binds the exact entry plus transitive module closure, an independent verifier executes before admission, and this changed-transitive-chunk replay makes admission fail closed.

### P41 docs-lifecycle comparison

The earlier “carried six” label is withdrawn. An extracted exact-base replay proves the same six
messages existed at `f6c465648`, but the aggregate gate cannot be labelled inherited under P41
because this changed journal belongs to the checker's complete input denominator.

The base was materialized as ordinary harness scratch, not as another worktree:

```sh
git -C /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine archive f6c465648d0b55b316452e982c62f6db6a0e051e | tar -x -C /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-p41-base-f6c465648
```

Exact base command:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-p41-base-f6c465648 /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-p41-base-f6c465648/tools/quality/validation/check_docs_lifecycle.py --repo-root /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-p41-base-f6c465648
```

Base output was exit 1 with exactly six findings. The current journal initially introduced a
seventh by quoting the stale dashboard token in an ordinary fenced block. That is a real
task-caused checker finding, so the quotation was wrapped in the checker's supported journal
evidence markers rather than ignored. The current complete reference-scan membership is:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -c 'from pathlib import Path; from tools.quality.validation.check_docs_lifecycle import _iter_reference_scan_files; root=Path("/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine"); target=(root/"docs/superpowers/journals/2026-09-01-debt-q-remeasure-and-typing.md").resolve(); members=tuple(_iter_reference_scan_files(root)); print(f"reference_scan_files={len(members)}"); print(f"changed_journal_in_reference_scan={target in members}")'
```

```text
reference_scan_files=10292
changed_journal_in_reference_scan=True
```

Current command after the evidence-marker correction:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine uv run --directory /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine --frozen --extra test python /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tools/quality/validation/check_docs_lifecycle.py
```

<!-- docs-lifecycle-evidence:start -->
```text
Docs lifecycle gate FAILED:
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `status` front matter.
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `owner` front matter.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-adoption-ledger.json: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-archive-map.json: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/reference/frontend/atlas-v15-adjudication.md: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/research/policy-operations/audits/pao-r0/pao-r0-test-and-fixture-verification.md: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
exit 1
```
<!-- docs-lifecycle-evidence:end -->

P41 verdict: the six individual messages reproduce at the exact base and again at current state,
but aggregate provenance remains `not_established`, not inherited, because changed-path/input-set
intersection is nonzero (`1` journal in 10,292 inputs). The evidence markers prevent Task Q from
adding a seventh; they do not make the aggregate disjoint.

### Literal-receipt correction after delta review

The GY result blocks above that use labels such as `GY-C1 FAILED` are normalized material excerpts,
not literal pytest stdout. The prefix/suffix rendering is replayable but is not itself the recorded
shell command. Those labels are withdrawn. The following full commands are the actual recorded
invocations for every previously abbreviated batch.

`GY-C1` first-red batch:

```sh
/usr/bin/perl -e 'my $s=shift @ARGV; alarm $s; exec @ARGV or die $!;' 1800 /usr/bin/env PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -m pytest \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_workspace_workflow_playbook_projection.py::test_workspace_loop_phase2_playbook_can_deviate_to_refine_blocker \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_workspace_spine_repair_gates.py::test_governance_tail_verifier_delegates_to_governance_node_owner \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/integration/runtime_quality/test_workspace_foundry_consumption.py::test_phase2_estimate_consumes_real_foundry_method_output_with_measurement_authority \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_workspace_agent_proposal_bridge.py::test_agent_event_bridge_persists_unmocked_tool_loop_event_bundle \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_workspace_composition.py::test_feedback_composition_is_invalid_and_requires_joint_grounding \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_substrate_registry.py::test_substrate_registry_registration_is_free_grow_and_changes_version \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/core/contracts/test_value_outer_set.py::test_value_outer_set_compare_is_conservative_and_unknown_on_timeout \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/integration/runtime_quality/test_gy_s2_knowledge_substrate_lift.py::test_l2_transport_and_contested_edges_lower_to_bounded_nonpoint_sets \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_intervention_substrate.py::test_intervention_substrate_behavior_report_exercises_real_space_and_mutations \
-vv -x --lf -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-gy/pytest-cache
```

`GY-C2` / `GY-C3` retry:

```sh
/usr/bin/perl -e 'my $s=shift @ARGV; alarm $s; exec @ARGV or die $!;' 1800 /usr/bin/env PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -m pytest \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_workspace_spine_repair_gates.py::test_governance_tail_verifier_delegates_to_governance_node_owner \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/integration/runtime_quality/test_workspace_foundry_consumption.py::test_phase2_estimate_consumes_real_foundry_method_output_with_measurement_authority \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_workspace_agent_proposal_bridge.py::test_agent_event_bridge_persists_unmocked_tool_loop_event_bundle \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_workspace_composition.py::test_feedback_composition_is_invalid_and_requires_joint_grounding \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_substrate_registry.py::test_substrate_registry_registration_is_free_grow_and_changes_version \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/core/contracts/test_value_outer_set.py::test_value_outer_set_compare_is_conservative_and_unknown_on_timeout \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/integration/runtime_quality/test_gy_s2_knowledge_substrate_lift.py::test_l2_transport_and_contested_edges_lower_to_bounded_nonpoint_sets \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_intervention_substrate.py::test_intervention_substrate_behavior_report_exercises_real_space_and_mutations \
-vv -x --lf -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-gy/pytest-cache
```

`GY-I` / `GY-G` / `GY-S0` / `GY-N-V` / `GY-S2` / `GY-S3` batch:

```sh
/usr/bin/perl -e 'my $s=shift @ARGV; alarm $s; exec @ARGV or die $!;' 1800 /usr/bin/env PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -m pytest \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_workspace_agent_proposal_bridge.py::test_agent_event_bridge_persists_unmocked_tool_loop_event_bundle \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_workspace_composition.py::test_feedback_composition_is_invalid_and_requires_joint_grounding \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_substrate_registry.py::test_substrate_registry_registration_is_free_grow_and_changes_version \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/core/contracts/test_value_outer_set.py::test_value_outer_set_compare_is_conservative_and_unknown_on_timeout \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/integration/runtime_quality/test_gy_s2_knowledge_substrate_lift.py::test_l2_transport_and_contested_edges_lower_to_bounded_nonpoint_sets \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_intervention_substrate.py::test_intervention_substrate_behavior_report_exercises_real_space_and_mutations \
-vv -x --lf -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-gy/pytest-cache
```

Authority/artifact batch through `GY-F1`:

```sh
/usr/bin/perl -e 'my $s=shift @ARGV; alarm $s; exec @ARGV or die $!;' 1800 /usr/bin/env PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -m pytest \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/integration/runtime_quality/test_data_state_substrate.py::test_real_l4_data_state_builds_populated_world_model_record_and_executes_sim \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_workflow_failure_authority_validator_recomputes_proofs \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_artifact_surface_safety_validator_recomputes_proofs \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_time_source_authority_validator_recomputes_proofs \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_loop_validator_recomputes_graded_outcome_routing_report \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_outcome_run_is_http_triggered_and_honestly_blocked \
-vv -x --lf -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-gy/pytest-cache
```

`GY-F2` / `GY-F3` / `GY-J` retry:

```sh
/usr/bin/perl -e 'my $s=shift @ARGV; alarm $s; exec @ARGV or die $!;' 1800 /usr/bin/env PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -m pytest \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/integration/runtime_quality/test_data_state_substrate.py::test_real_l4_data_state_builds_populated_world_model_record_and_executes_sim \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_artifact_surface_safety_validator_recomputes_proofs \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_time_source_authority_validator_recomputes_proofs \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_loop_validator_recomputes_graded_outcome_routing_report \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_outcome_run_is_http_triggered_and_honestly_blocked \
-vv -x --lf -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-gy/pytest-cache
```

`GY-L` retry:

```sh
/usr/bin/perl -e 'my $s=shift @ARGV; alarm $s; exec @ARGV or die $!;' 1800 /usr/bin/env PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -m pytest \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/integration/runtime_quality/test_data_state_substrate.py::test_real_l4_data_state_builds_populated_world_model_record_and_executes_sim \
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_outcome_run_is_http_triggered_and_honestly_blocked \
-vv -x --lf -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-gy/pytest-cache
```

Isolated `GY-S3`:

```sh
/usr/bin/perl -e 'my $s=shift @ARGV; alarm $s; exec @ARGV or die $!;' 1800 /usr/bin/env PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -m pytest /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/tests/unit/runtime/quality/test_intervention_substrate.py::test_intervention_substrate_behavior_report_exercises_real_space_and_mutations -vv -x --lf -o cache_dir=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-gy/pytest-cache
```

The literal outcome receipt is the isolated cache readback below. It is not substituted for the
behavioral test commands; it records their resulting exact node identities without normalized
pytest aliases:

```sh
/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python - <<'PY'
import json
from pathlib import Path

cache = Path("/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-gy/pytest-cache/v/cache/lastfailed")
failed = json.loads(cache.read_text())
pairs = (
    ("GY-M1", "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_generated_artifact_lifecycle_is_scan_based"),
    ("GY-B", "tests/unit/runtime/quality/test_workspace_loop.py::test_slice0_rejects_non_active_operation_execution"),
    ("GY-H", "tests/unit/runtime/quality/test_workspace_loop.py::test_loop_terminal_precedence_blocks_acquisition_when_ceiling_is_unrepaired"),
    ("GY-D2", "tests/unit/runtime/quality/test_workspace_loop.py::test_connector_and_source_contract_admission_fail_closed"),
    ("GY-D3", "tests/unit/runtime/quality/test_workspace_loop.py::test_semantic_adequacy_benchmark_rejects_negative_control_and_records_recall"),
    ("GY-E", "tests/unit/runtime/quality/test_workspace_loop.py::test_slice0_acquire_continuation_emits_costed_acquisition_required_terminal"),
    ("GY-C1", "tests/unit/runtime/quality/test_workspace_workflow_playbook_projection.py::test_workspace_loop_phase2_playbook_can_deviate_to_refine_blocker"),
    ("GY-C2", "tests/unit/runtime/quality/test_workspace_spine_repair_gates.py::test_governance_tail_verifier_delegates_to_governance_node_owner"),
    ("GY-C3", "tests/integration/runtime_quality/test_workspace_foundry_consumption.py::test_phase2_estimate_consumes_real_foundry_method_output_with_measurement_authority"),
    ("GY-I", "tests/unit/runtime/quality/test_workspace_agent_proposal_bridge.py::test_agent_event_bridge_persists_unmocked_tool_loop_event_bundle"),
    ("GY-F1", "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_workflow_failure_authority_validator_recomputes_proofs"),
    ("GY-F2", "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_artifact_surface_safety_validator_recomputes_proofs"),
    ("GY-F3", "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_time_source_authority_validator_recomputes_proofs"),
    ("GY-G", "tests/unit/runtime/quality/test_workspace_composition.py::test_feedback_composition_is_invalid_and_requires_joint_grounding"),
    ("GY-J", "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_loop_validator_recomputes_graded_outcome_routing_report"),
    ("GY-L", "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_outcome_run_is_http_triggered_and_honestly_blocked"),
    ("GY-S0", "tests/unit/runtime/quality/test_substrate_registry.py::test_substrate_registry_registration_is_free_grow_and_changes_version"),
    ("GY-S1", "tests/integration/runtime_quality/test_data_state_substrate.py::test_real_l4_data_state_builds_populated_world_model_record_and_executes_sim"),
    ("GY-N-V", "tests/unit/core/contracts/test_value_outer_set.py::test_value_outer_set_compare_is_conservative_and_unknown_on_timeout"),
    ("GY-S2", "tests/integration/runtime_quality/test_gy_s2_knowledge_substrate_lift.py::test_l2_transport_and_contested_edges_lower_to_bounded_nonpoint_sets"),
    ("GY-S3", "tests/unit/runtime/quality/test_intervention_substrate.py::test_intervention_substrate_behavior_report_exercises_real_space_and_mutations"),
)
counts = {"pass": 0, "fail": 0, "not_measured": 0}
for row, node in pairs:
    verdict = "not_measured" if row == "GY-C2" else "fail" if node in failed else "pass"
    counts[verdict] += 1
    print(f"{row}\t{verdict}\t{node}")
print(f"pass={counts['pass']} fail={counts['fail']} not_measured={counts['not_measured']} total={sum(counts.values())}")
print("lastfailed=" + json.dumps(failed, sort_keys=True, separators=(",", ":")))
PY
```

```text
GY-M1 fail tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_generated_artifact_lifecycle_is_scan_based
GY-B pass tests/unit/runtime/quality/test_workspace_loop.py::test_slice0_rejects_non_active_operation_execution
GY-H pass tests/unit/runtime/quality/test_workspace_loop.py::test_loop_terminal_precedence_blocks_acquisition_when_ceiling_is_unrepaired
GY-D2 pass tests/unit/runtime/quality/test_workspace_loop.py::test_connector_and_source_contract_admission_fail_closed
GY-D3 pass tests/unit/runtime/quality/test_workspace_loop.py::test_semantic_adequacy_benchmark_rejects_negative_control_and_records_recall
GY-E pass tests/unit/runtime/quality/test_workspace_loop.py::test_slice0_acquire_continuation_emits_costed_acquisition_required_terminal
GY-C1 fail tests/unit/runtime/quality/test_workspace_workflow_playbook_projection.py::test_workspace_loop_phase2_playbook_can_deviate_to_refine_blocker
GY-C2 not_measured tests/unit/runtime/quality/test_workspace_spine_repair_gates.py::test_governance_tail_verifier_delegates_to_governance_node_owner
GY-C3 fail tests/integration/runtime_quality/test_workspace_foundry_consumption.py::test_phase2_estimate_consumes_real_foundry_method_output_with_measurement_authority
GY-I pass tests/unit/runtime/quality/test_workspace_agent_proposal_bridge.py::test_agent_event_bridge_persists_unmocked_tool_loop_event_bundle
GY-F1 fail tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_workflow_failure_authority_validator_recomputes_proofs
GY-F2 pass tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_artifact_surface_safety_validator_recomputes_proofs
GY-F3 pass tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_time_source_authority_validator_recomputes_proofs
GY-G pass tests/unit/runtime/quality/test_workspace_composition.py::test_feedback_composition_is_invalid_and_requires_joint_grounding
GY-J fail tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_loop_validator_recomputes_graded_outcome_routing_report
GY-L fail tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_outcome_run_is_http_triggered_and_honestly_blocked
GY-S0 pass tests/unit/runtime/quality/test_substrate_registry.py::test_substrate_registry_registration_is_free_grow_and_changes_version
GY-S1 pass tests/integration/runtime_quality/test_data_state_substrate.py::test_real_l4_data_state_builds_populated_world_model_record_and_executes_sim
GY-N-V pass tests/unit/core/contracts/test_value_outer_set.py::test_value_outer_set_compare_is_conservative_and_unknown_on_timeout
GY-S2 pass tests/integration/runtime_quality/test_gy_s2_knowledge_substrate_lift.py::test_l2_transport_and_contested_edges_lower_to_bounded_nonpoint_sets
GY-S3 fail tests/unit/runtime/quality/test_intervention_substrate.py::test_intervention_substrate_behavior_report_exercises_real_space_and_mutations
pass=13 fail=7 not_measured=1 total=21
lastfailed={"tests/integration/runtime_quality/test_workspace_foundry_consumption.py::test_phase2_estimate_consumes_real_foundry_method_output_with_measurement_authority":true,"tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_generated_artifact_lifecycle_is_scan_based":true,"tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_loop_validator_recomputes_graded_outcome_routing_report":true,"tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_outcome_run_is_http_triggered_and_honestly_blocked":true,"tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_workflow_failure_authority_validator_recomputes_proofs":true,"tests/unit/runtime/quality/test_intervention_substrate.py::test_intervention_substrate_behavior_report_exercises_real_space_and_mutations":true,"tests/unit/runtime/quality/test_workspace_workflow_playbook_projection.py::test_workspace_loop_phase2_playbook_can_deviate_to_refine_blocker":true}
```

The spaces in this Markdown rendering delimit the three fields; the command's literal separators
were tabs.

The runner positive-control summary at the start of the behavioral section was also a normalized
field rendering rather than direct stdout. This final restored-path control used a command that
emits exactly the receipt shown:

```sh
test ! -e /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-runner-final-positive && mkdir -p /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-runner-final-positive/cas
set +e
positive_output=$(printf '%s\n' '{"operation":"persist_atlas_surface_readiness_claims"}' | POLISYOS_CAS_BACKEND=filesystem POLISYOS_CAS_ROOT=/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/_build/task-q-runner-final-positive/cas PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/apps/runtime-dashboard/scripts/persist_atlas_evidence.py)
positive_status=$?
printf '%s' "$positive_output" | /Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing/policy-engine/.venv/bin/python -c 'import json,sys; x=json.load(sys.stdin); r=x.get("resolved_claim_report",{}).get("report",{}); p=x.get("resolved_projection",{}).get("projection",{}); print(json.dumps({"operation":x.get("operation"),"error":x.get("error"),"claim_report_artifact_id":x.get("claim_report_ref",{}).get("artifact_id"),"projection_artifact_id":x.get("projection_ref",{}).get("artifact_id"),"report_claim_count":len(r.get("claims",[])),"projection_claim_count":len(p.get("claims",[])),"claim_ids":[c.get("claim_id") for c in p.get("claims",[])],"observation_statuses":[c.get("basis",{}).get("observation",{}).get("status") for c in p.get("claims",[])]},sort_keys=True,separators=(",",":")))'
printf 'POSITIVE_EXIT_CODE=%d\n' "$positive_status"
```

Literal output:

```text
{"claim_ids":["route-redirect-launch:readiness_state:implemented","route-redirect-sources:readiness_state:implemented","route-redirect-data:readiness_state:implemented","route-redirect-lex:readiness_state:implemented","route-redirect-health:readiness_state:implemented"],"claim_report_artifact_id":"sha256:7334e481c35ac1954e36ccc9c0304cc3b6fafc0abb5e7d616e983572b659e062","error":null,"observation_statuses":["observed","observed","observed","observed","observed"],"operation":"persist_atlas_surface_readiness_claims","projection_artifact_id":"sha256:2092499f5052738097c7dd0c7d4ae520f1f72b500c2222643acf8a5b8d0e0692","projection_claim_count":5,"report_claim_count":5}
POSITIVE_EXIT_CODE=0
```

The original ordering requirement remains satisfied by the pre-mutation positive control; this
second control exists only to make the output receipt literal after restoration.

Finally, the P41 base command's exact output was the following, not merely the six-count summary:

<!-- docs-lifecycle-evidence:start -->
```text
Docs lifecycle gate FAILED:
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `status` front matter.
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `owner` front matter.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-adoption-ledger.json: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-archive-map.json: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/reference/frontend/atlas-v15-adjudication.md: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/research/policy-operations/audits/pao-r0/pao-r0-test-and-fixture-verification.md: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
exit 1
```
<!-- docs-lifecycle-evidence:end -->
