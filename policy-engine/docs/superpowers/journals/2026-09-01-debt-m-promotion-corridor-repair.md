# Task M — promotion and generation corridor repair

Date: 2026-09-01
Branch: `codex/debt-m-promotion-corridor-repair`
Base: `113b71aecc1f90fea91ef42b6378939725b176d2`
Owned register row: `main-red-in-promotion-and-generation-corridor`

## Outcome

The raw four-file corridor started at exit 1 with 23 failures and 228 passes. Every
one of those 23 nodes is classified below before its repair is credited. Sixteen
were class C test/harness prerequisite defects: twelve silently depended on an
ignored owner-data tree, and four silently depended on the CP-SAT solver extra.
Seven were class B migrations to behavior already ratified in named commits and
documents. There are no class A or class D rows and no failures left unclassified.

The final, source-frozen four-file run exits 0 with 252 passes. The increase from
the original 251-node denominator is one new semantic test which executes the lazy
N8 wrapper through the real `FoundryValuePort`; no failing node was deleted or
skipped. The other five files named by the task were measured together before any
repair and all 295 tests passed. They were not touched.

No governed contract, frozen receipt epoch, OpenAPI source, generated client or
schema was edited. No file under `docs/plans/active/` was edited. The authentic
historical promotion receipt remains readable as history and rejected as current
authority.

## Environment and denominator binding

The worktree-local environment was created with:

```text
uv sync --frozen --extra test
```

The required binding probe was:

```text
uv run --frozen --extra test python -c "import polisyos, sys; print(sys.prefix)"
```

and printed:

```text
/Users/deniskopylov/polisyos/.worktrees/debt-m-promotion-corridor-repair/policy-engine/.venv
```

The ignored `production_data` owner tree was then bound read-only as prescribed by
the repository worktree toolchain notes. It is not a tracked change. The solver
proof profile was provisioned with:

```text
uv sync --frozen --extra test --extra solvers --extra analytics --extra lint
```

`ortools==9.15.6755` was importable under that bound interpreter. The tracked
source denominator remained 2,617 Python files.

The raw four-file measurement used only the test extra and no worktree owner-data
binding:

```text
uv run --frozen --extra test pytest -o addopts='' -q tests/unit/runtime/quality/test_generation_cycle.py tests/unit/runtime/quality/test_promotion_sequence.py tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py tests/unit/runtime/http/test_runs_api.py
```

Result: exit 1, 23 failed and 228 passed.

After binding the declared owner-data and solver prerequisites but before source
repair, the remaining product/test reconciliation denominator was seven failures:

| File | Raw result | Prerequisite-bound, pre-repair result | Why the delta is not a repair |
|---|---:|---:|---|
| `tests/unit/runtime/quality/test_generation_cycle.py` | 70 passed, 13 failed | 82 passed, 1 failed | Twelve nodes passed unchanged when the ignored owner catalog existed. |
| `tests/unit/runtime/quality/test_promotion_sequence.py` | 108 passed, 7 failed | 112 passed, 3 failed | Four nodes passed unchanged when the recorded solver extra was installed. |
| `tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py` | 5 passed, 2 failed | 5 passed, 2 failed | No prerequisite delta. |
| `tests/unit/runtime/http/test_runs_api.py` | 45 passed, 1 failed | 45 passed, 1 failed | No prerequisite delta. |

## Classification table — all 23 starting failures

Evidence keys are expanded immediately after the table. A node has exactly one
class even when repairing it exposed an ancillary defect in the same harness.

| Failing node id | Class | Evidence and correct assertion |
|---|:---:|---|
| `tests/unit/runtime/quality/test_generation_cycle.py::test_joint_port_reuses_exact_cycle_context_wmr` | C | C-GEN. The target assertion is unchanged; the test must bind its owner catalog before claiming an N5 semantic failure. |
| `tests/unit/runtime/quality/test_generation_cycle.py::test_joint_port_accepts_label_drift_after_atom_world_resolution` | C | C-GEN. The target assertion is unchanged; the test must bind its owner catalog before claiming label/world-resolution behavior. |
| `tests/unit/runtime/quality/test_generation_cycle.py::test_joint_port_rejects_candidate_ref_mismatched_to_context_wmr` | C | C-GEN. The mismatch assertion was correct; the ambient prerequisite was not declared. |
| `tests/unit/runtime/quality/test_generation_cycle.py::test_cycle_world_identity_rejects_shaped_atom_even_when_strings_match` | C | C-GEN. The shaped-atom refusal assertion was correct; the ambient prerequisite was not declared. |
| `tests/unit/runtime/quality/test_generation_cycle.py::test_cycle_world_identity_rejects_atom_from_another_problem` | C | C-GEN. The foreign-problem refusal assertion was correct; the ambient prerequisite was not declared. |
| `tests/unit/runtime/quality/test_generation_cycle.py::test_joint_port_rejects_empty_atom_slots_as_unresolved_world_identity` | C | C-GEN. The unresolved-world assertion was correct; the ambient prerequisite was not declared. |
| `tests/unit/runtime/quality/test_generation_cycle.py::test_joint_port_types_tampered_strict_atom_as_unresolved_world_identity` | C | C-GEN. The tamper refusal assertion was correct; the ambient prerequisite was not declared. |
| `tests/unit/runtime/quality/test_generation_cycle.py::test_explicit_joint_request_cannot_bypass_context_wmr` | C | C-GEN. The no-bypass assertion was correct; the ambient prerequisite was not declared. |
| `tests/unit/runtime/quality/test_generation_cycle.py::test_explicit_joint_request_atom_refs_bind_before_injected_controller` | C | C-GEN. The pre-controller binding assertion was correct; the ambient prerequisite was not declared. |
| `tests/unit/runtime/quality/test_generation_cycle.py::test_explicit_request_nested_atom_missing_slot_fails_world_identity` | C | C-GEN. The nested-slot refusal assertion was correct; the ambient prerequisite was not declared. |
| `tests/unit/runtime/quality/test_generation_cycle.py::test_shaped_wmr_ref_without_resolved_object_is_rejected` | C | C-GEN. The resolved-object requirement was correct; the ambient prerequisite was not declared. |
| `tests/unit/runtime/quality/test_generation_cycle.py::test_acquisition_required_derives_n7_inputs_without_test_hints_and_reenters` | C | C-GEN. The reentry assertion was correct; the test had silently relied on the ignored production owner catalog. |
| `tests/unit/runtime/quality/test_generation_cycle.py::test_active_overlay_reentry_is_exact_direct_and_read_only` | B | B-CTX. Commit `08332b724d3b988fed99d16b23d0f76398a839c2` made evaluation context explicit; the stale direct `FoundryValuePort` expectation was replaced by a lazy actual-N5-bound wrapper and the production caller was migrated. |
| `tests/unit/runtime/quality/test_promotion_sequence.py::test_fixed_time_n8_calibration_is_ledger_refused_and_stays_shadow` | B | B-EFFECT. Commit `5c6b5f948c44a6a07142b96120ed8ebf6998639b` ratified missing EFFECT evidence as real-scope `UNKNOWN`, not `SCOPE_INSUFFICIENT`; the test now asserts that exact distinction. |
| `tests/unit/runtime/quality/test_promotion_sequence.py::test_legacy_v3_history_is_exactly_readable_but_not_current_authority` | B | B-HISTORY. Commit `cbee85fea19d68405cd3a973328c30d9a71fc736` advanced the governing epoch; the test now reads authentic historical v3 bytes rather than treating the current v6 canonical pointer as v3. Current-authority rejection remains asserted. |
| `tests/unit/runtime/quality/test_promotion_sequence.py::test_supported_owner_bound_offer_round_trips_through_generic_validator` | B | B-RESOLVER. Commit `c8a9e5e0c4a7798c23ea9d696efe00ae76af6969` made evidence resolution explicit and fail-closed; the private generic-validator probe now supplies the explicit resolver argument instead of relying on its pre-change call shape. |
| `tests/unit/runtime/quality/test_promotion_sequence.py::test_effect_exact_or_bounded_entailment_satisfies_without_minting[False-effect_claim_entailed]` | C | C-SOLVER. It passed unchanged once CP-SAT was installed; without that declared proof dependency the runtime honestly returned `UNKNOWN / ortools_cp_sat_unavailable`. |
| `tests/unit/runtime/quality/test_promotion_sequence.py::test_effect_exact_or_bounded_entailment_satisfies_without_minting[True-effect_claim_bounded]` | C | C-SOLVER. Same evidence; the correct test asserts entailment only under the solver-bearing proof profile. |
| `tests/unit/runtime/quality/test_promotion_sequence.py::test_production_n9_port_persists_effect_but_refuses_contract_only_cg2` | C | C-SOLVER. Same evidence; the missing solver prevented the node from reaching its intended later CG2 authority refusal. The expectation was not weakened. |
| `tests/unit/runtime/quality/test_promotion_sequence.py::test_promotion_history_remains_readable_after_exact_v3_to_v6_reissue` | C | C-SOLVER. Same evidence; missing CP-SAT changed current recomputation to `unknown` and correctly caused governing-projection drift. The frozen artifact was not rewritten. |
| `tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py::test_recursive_constructor_denominator_has_no_unwrapped_n9_call` | B | B-EPOCH. Commit `f44032ade3890309665733f94ef1a77480957cf2` deliberately added two real epoch-chronology controller callers. Their stale absence is the decisive class. The same node also exposed a class-C harness defect: it walked ignored `.venv`/cache trees and treated an inline constructor `.run` as ambiguous. Those ancillary defects were repaired generically and falsified. |
| `tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py::test_task_44_public_export_denominator_is_exact` | B | B-EXPORT. Commit `552213d90599f392ec6c68871e5c5af12a74ed49` deliberately made `EpochValidityCompletedBatchEvidenceDenominator` public. The owner `__all__` and stale Task-4.4 denominator were aligned with that ratified facade; unrelated API hashes were removed from this task-owned semantic denominator. |
| `tests/unit/runtime/http/test_runs_api.py::test_reissue_endpoint_fails_closed_without_durable_control_plane` | B | B-CUSTODY. Commit `7733a092affa8c83f06716a0f523fb5d82128ff9` made production startup invoke custody maintenance. The test snapshot now starts after lifespan startup and still proves that the endpoint request itself performs no prohibited write. |

### C-GEN — undeclared owner-data prerequisite

The twelve C-GEN nodes all failed before their named semantic boundary because a
fresh linked worktree does not contain the ignored `production_data` owner tree.
After the prescribed read-only owner-data bind, all twelve passed without a source
or expectation change. They were wrong when written because they treated ambient,
ignored workstation state as a fixture. The correct assertion is the existing
world-identity/reentry assertion after an explicit owner-catalog fixture or declared
worktree prerequisite; an owner-catalog nonreceipt must not be mislabeled as failure
of the later semantic property.

### C-SOLVER — undeclared proof-profile prerequisite

Direct import under `--extra test` raised `ModuleNotFoundError` for `ortools`.
`grounding_relation._solve_joint_cross_modal()` correctly converted that to
`UNKNOWN / ortools_cp_sat_unavailable`; downstream EFFECT and current-governing
projection checks then failed closed. All four nodes passed unchanged under
`--extra solvers`. They were wrong when written because the test profile did not
bind the proof engine on which their positive entailment depended. The correct
assertions are the existing assertions under the solver-bearing profile. An
optimistic SAT fallback, skip or frozen-receipt rewrite would have laundered the
authority proof and was not used.

### B-CTX — explicit evaluation context

Ratifying commit: `08332b724d3b988fed99d16b23d0f76398a839c2`
(`fix(runtime): bind evaluation safety admission`).

Ratifying decision, `docs/superpowers/plans/2026-08-27-gy-o0-attempted-evaluation-safety-gate.md`:

> “Make `FoundryValuePort` require an explicit `EvaluationExecutionContext`.
> `simulate_only` proceeds without a certificate; all other modes call the
> single verifier before the value-owner gateway. A missing real service or
> certificate blocks before gateway work.”

The reentry bridge now waits for the actual new N5 observation, derives its exact
candidate/problem/WMR/input context, and installs only the active read-only overlay
gateway. A non-simulation stale context refuses before `_run_cycle` or owner access.

### B-EFFECT — real-scope UNKNOWN

Ratifying commit: `5c6b5f948c44a6a07142b96120ed8ebf6998639b`
(`fix: resolve governed EFFECT obligation`).

Ratifying decision, `docs/superpowers/plans/2026-08-30-debt-a-promotion-gate.md`:

> “missing bridge evidence: EFFECT is `UNKNOWN`, has real semantic scope, and
> is visibly not `SCOPE_INSUFFICIENT`;”

### B-HISTORY — v6 governs; older epochs remain history

Ratifying commit: `cbee85fea19d68405cd3a973328c30d9a71fc736`
(`fix: reissue N9 promotion comparison epoch`).

Ratifying decision, `docs/superpowers/plans/2026-08-30-debt-a-promotion-gate.md`:

> “Authentic v5/v3/v2 bytes remain exact readable history and are rejected at
> every current-authority entry point.”

The register's closed `promotion-comparison-admission-manifest-drift` row further
records:

> “The N9 companion now carries **three `n9_promotion.v6` receipts** at the
> three canonical pointers under the
> `canonical_promotion_receipt_verification_projection.v5` owner rule,
> verified by the architect in the generated artifact.”

### B-RESOLVER — producer evidence, not caller assertion

Ratifying commit: `c8a9e5e0c4a7798c23ea9d696efe00ae76af6969`
(`fix: bind promotion obligations to producer evidence`).

Ratifying decision, the closed `gy-n9-caller-asserted-gate-predicates` register row:

> “The resolver performs exact CAS readback, source recomputation,
> candidate/problem binding and fixed verifier-provenance checking; an empty
> independence graph, a foreign candidate binding and a non-appointed verifier
> all fail closed.”

### B-EPOCH — epoch chronology added real callers

Ratifying commit: `f44032ade3890309665733f94ef1a77480957cf2`
(`test(gy-n12): freeze epoch and artifact-transition validators`).

Ratifying decision, `docs/superpowers/plans/2026-08-20-gy-n12-epoch-chronology-implementation.md`:

> “The validator imports and runs the real epoch resolver, full-prefix verifier,
> Decision Validity typed path, Claim bridge and actual N9/public OpenWorldRisk
> consumer.”

The repaired scanner derives independent Git and filesystem denominators, prunes
ignored directory roots, retains the final per-file ignore check, resolves inline
constructor calls, and treats direct, aliased and literal-`getattr`
`_promotion_port` calls as governed calls. Its falsifiers prove a dropped path,
duplicate constructor, missing runtime, unscoped verification caller, shaped
promotion call, alias, star import, shadow, and dynamic `getattr` escape are red.

### B-EXPORT — completed epoch evidence became public

Ratifying commit: `552213d90599f392ec6c68871e5c5af12a74ed49`
(`feat(claims): consume completed epoch validity batches`).

Ratifying decision, `docs/superpowers/plans/2026-08-20-gy-n12-epoch-chronology-implementation.md`:

> “`feat(claims): consume completed epoch validity batches` — Task 4.5; closes
> GY-GAP8 only when ledger persistence and real public export pass.”

### B-CUSTODY — startup maintenance is production behavior

Ratifying commit: `7733a092affa8c83f06716a0f523fb5d82128ff9`
(`feat(runtime): watch published signature custody`).

Ratifying decision, `docs/superpowers/plans/2026-08-30-debt-d-ds11-trust-posture.md`:

> “`ControlWorker` receives a bounded periodic maintenance callback, so
> production startup invokes the watcher without a human/API trigger. The
> callback records nonreceipt rather than treating an empty population as an
> all-clear.”

## Repairs and commits

The source/test repair groups, each committed after verifying branch attachment,
are:

| Commit | Coherent repair group |
|---|---|
| `aa4e0f12c` | Lazy actual-N5 evaluation context and read-only active-overlay reentry; refuses stale non-simulation context. |
| `26ff5bc9d` | Independent ignored-tree-safe recursive denominator, inline constructor handling, ratified epoch callers, and exact public export. |
| `40acc4fe5` | Ratified EFFECT/history/resolver expectations plus request-scoped HTTP write snapshot. |
| `b6de70859` | Independent-review hardening for dynamic promotion calls and actual wrapper execution/fresh-context semantics. |

An independent source review initially found two Important P38/P40 gaps: a literal
`getattr(..., "_promotion_port")` escape and a wrapper test that inspected shape
without executing the wrapper. Commit `b6de70859` closed both. Delta review replayed
both mutations and returned no Critical, Important or Minor findings; ready to merge.

## Exact repair replays

Before each class-B repair, its exact node was replayed and failed. After the
repair, the same node was replayed, followed by its named file. The substantive
commands were:

```text
uv run --frozen --extra test --extra solvers --extra analytics pytest -o addopts='' -q tests/unit/runtime/quality/test_generation_cycle.py::test_active_overlay_reentry_is_exact_direct_and_read_only
uv run --frozen --extra test --extra solvers --extra analytics pytest -o addopts='' -q tests/unit/runtime/quality/test_promotion_sequence.py::test_fixed_time_n8_calibration_is_ledger_refused_and_stays_shadow
uv run --frozen --extra test --extra solvers --extra analytics pytest -o addopts='' -q tests/unit/runtime/quality/test_promotion_sequence.py::test_legacy_v3_history_is_exactly_readable_but_not_current_authority
uv run --frozen --extra test --extra solvers --extra analytics pytest -o addopts='' -q tests/unit/runtime/quality/test_promotion_sequence.py::test_supported_owner_bound_offer_round_trips_through_generic_validator
uv run --frozen --extra test --extra solvers --extra analytics pytest -o addopts='' -q tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py::test_recursive_constructor_denominator_has_no_unwrapped_n9_call
uv run --frozen --extra test --extra solvers --extra analytics pytest -o addopts='' -q tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py::test_task_44_public_export_denominator_is_exact
uv run --frozen --extra test --extra solvers --extra analytics pytest -o addopts='' -q tests/unit/runtime/http/test_runs_api.py::test_reissue_endpoint_fails_closed_without_durable_control_plane
```

The review-hardening exact nodes also passed:

```text
uv run --frozen --extra test --extra solvers --extra analytics pytest -o addopts='' -q tests/unit/runtime/quality/test_generation_cycle.py::test_default_value_port_binds_the_actual_n5_context
uv run --frozen --extra test --extra solvers --extra analytics pytest -o addopts='' -q tests/unit/runtime/quality/test_generation_cycle.py::test_active_overlay_reentry_is_exact_direct_and_read_only
uv run --frozen --extra test --extra solvers --extra analytics pytest -o addopts='' -q tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py::test_recursive_constructor_denominator_has_no_unwrapped_n9_call
```

Post-repair named-file results from real runs:

| File | Exact command | Final result |
|---|---|---:|
| `test_generation_cycle.py` | `uv run --frozen --extra test --extra solvers --extra analytics pytest -o addopts='' -q tests/unit/runtime/quality/test_generation_cycle.py` | 84 passed |
| `test_promotion_sequence.py` | `uv run --frozen --extra test --extra solvers --extra analytics pytest -o addopts='' -q tests/unit/runtime/quality/test_promotion_sequence.py` | 115 passed |
| `test_recursive_generation_cycle_epoch_gate.py` | `uv run --frozen --extra test --extra solvers --extra analytics pytest -o addopts='' -q tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py` | 7 passed |
| `test_runs_api.py` | `uv run --frozen --extra test --extra solvers --extra analytics pytest -o addopts='' -q tests/unit/runtime/http/test_runs_api.py` | 46 passed |

The final required combined command was:

```text
uv run --frozen --extra test --extra solvers --extra analytics pytest -o addopts='' -q tests/unit/runtime/quality/test_generation_cycle.py tests/unit/runtime/quality/test_promotion_sequence.py tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py tests/unit/runtime/http/test_runs_api.py
```

Verbatim summary:

```text
252 passed in 2580.62s (0:43:00)
```

## The other five Task-4.4 files

They were measured together before repair with this exact command:

```text
uv run --frozen --extra test pytest -o addopts='' -q tests/unit/scientist/validation/test_decision_validity_service.py tests/unit/runtime/http/test_decision_validity_api.py tests/unit/runtime/http/test_runtime_api_authz.py tests/unit/runtime/http/test_runtime_step_up_authz.py tests/unit/runtime/http/test_control_service_di.py
```

Result: exit 0, 295 passed. Per-file denominators were:

| File | Passed | Failed | Touched by Task M |
|---|---:|---:|:---:|
| `tests/unit/scientist/validation/test_decision_validity_service.py` | 25 | 0 | no |
| `tests/unit/runtime/http/test_decision_validity_api.py` | 11 | 0 | no |
| `tests/unit/runtime/http/test_runtime_api_authz.py` | 169 | 0 | no |
| `tests/unit/runtime/http/test_runtime_step_up_authz.py` | 65 | 0 | no |
| `tests/unit/runtime/http/test_control_service_di.py` | 25 | 0 | no |

The current collection check independently still totals 295. Because none of these
five files or their source denominator was touched, the final command correctly
remained the four owned corridor files as the task instructed.

## Remaining failures and verdict-change rules

None. There are no class-D rows and no named prerequisite whose absence leaves a
failure hidden. If the read-only owner-data binding is removed, the twelve C-GEN
tests fail before their target semantics and retain class C until their fixtures
explicitly own that setup. If the solver extra is removed, the four C-SOLVER tests
must return honest `UNKNOWN` and retain class C; they become a production defect
only if an independently ratified equivalent proof engine or a contract requiring
solver-free entailment lands. A recurrence must not be silenced, skipped or used to
rewrite a frozen receipt.

No stop rule fired. In particular, the repairs did not change a governed contract,
receipt epoch, OpenAPI source, generated client or schema; no cited closure was
invalidated; and no row exhausted class-B ratification evidence.

## Exact append-only prose for the register row

The architect can append the following to
`main-red-in-promotion-and-generation-corridor` without editing this lane's plan
files:

> **TASK M 2026-09-01 — `open` -> `closed`.** Replayed and classified all 23
> starting failures before repair: **16 class C test/harness prerequisite defects
> + 7 class B ratified behavior migrations + 0 class A + 0 class D**. The sixteen
> are twelve generation/world-identity tests that silently depended on the ignored
> owner-data tree and four promotion/EFFECT proofs that silently omitted the
> recorded CP-SAT solver extra; all sixteen pass with their authority assertions
> unchanged once those prerequisites are bound. The seven class-B rows each carry
> a ratifying commit and quoted decision in the Task M dossier: explicit
> actual-N5 evaluation context, real-scope EFFECT `UNKNOWN`, v6-current/v3-history
> semantics, explicit producer-evidence resolution, epoch-chronology callers,
> completed-batch public export, and startup custody maintenance. Production
> reentry now derives context only after the new N5 observation, uses the active
> overlay read-only, and refuses stale non-simulation context before owner access;
> the recursive denominator independently enumerates the complete production set
> and detects direct, aliased and literal-`getattr` promotion calls. Independent
> review replayed both prior escapes and returned no findings. Final targeted wave:
> **252 passed** across the four owned files; the untouched companion five remain
> **295 passed**. No governed contract, frozen epoch, OpenAPI source, generated
> client or schema changed; historical receipts remain readable but non-authoritative.
> Under the required bound interpreter the debt ledger exposes **12 unresolved
> closure-signal identities**, all outside the Task M diff; their provenance is
> `not_established` because this lane did not replay that long check on the base.
> Docs lifecycle retains exactly the carried six findings, Ruff passes every
> changed Python file, and tracked `src/**/*.py` remains **2,617**.

## Boundary note

One read-only, path-scoped history query during diagnosis used `git log --all`
before the branch-reading boundary was reasserted. It did not visit another
worktree path, move a ref, change a checkout or contribute evidence to a verdict.
Every classification citation above was subsequently reread from this worktree and
the current branch's reachable history. No further all-ref query was used.

## Final validation receipts

The shell was first activated with `source .venv/bin/activate`, after which the
required commands were entered verbatim. A repeat binding probe still printed the
worktree-local `.venv` prefix shown above.

### Debt ledger — bound interpreter

Command:

```text
PYTHONPATH=. python3 tools/quality/validation/check_debt_ledger.py --check
```

Exit: 1. Verbatim output:

```text
register_ids=175
gy_ids=38
atlas_debt_rows=22
frontend_disposition_entries=261
frontend_ds8_assignment_rows=217
gy_history_blocks=6
gy_absent_from_register=15
gy_absent_from_register_closed=15
ds5_nonclosure_rows=27
ds5_planless_routes=4
irregular_section_e_branch_rows=1
closure_signal_pytest_selections=41
closure_signal_unsupported_runners=1
closure_signal_identities_without_commands=4
closure_signal_identity_unresolvable=12
closure_signal_input_unresolvable=0
closure_signal_selects_nothing=0
closure_signal_collection_failed=0
closure_signal_collection_host_unknown=0
closure_signal_ast_collection_disagreements=0
closure_signal_count_exit_disagreements=12
Blocking findings:
closure_signal_identity_unresolvable: DS11-EXTERNAL-A11Y-COUNTERSIGN: tests/repo_quality/docs/test_accessibility_evidence.py::test_external_countersign_is_content_bound_current_and_scope_exact; ast=False; collected=0; exit=4; ERROR: not found: /Users/deniskopylov/polisyos/.worktrees/debt-m-promotion-corridor-repair/policy-engine/tests/repo_quality/docs/test_accessibility_evidence.py::test_external_countersign_is_content_bound_current_and_scope_exact | (no match in any of [<Module test_accessibility_evidence.py>])
closure_signal_identity_unresolvable: DS11-FULL-TRUST-CENTER-AND-DOCS-IA: tests/repo_quality/frontend/test_public_surface_claim_ownership.py::test_every_retained_trust_docs_route_has_an_approved_owner_and_evidence_contract; ast=False; collected=0; exit=4; no tests collected in 0.00s | ERROR: file or directory not found: tests/repo_quality/frontend/test_public_surface_claim_ownership.py::test_every_retained_trust_docs_route_has_an_approved_owner_and_evidence_contract
closure_signal_identity_unresolvable: DS11-GROUNDED-PERFORMANCE: tests/integration/runtime_quality/test_first_governed_promotion.py::test_promoted_design_supplies_content_bound_public_performance_evidence; ast=False; collected=0; exit=4; no tests collected in 0.00s | ERROR: file or directory not found: tests/integration/runtime_quality/test_first_governed_promotion.py::test_promoted_design_supplies_content_bound_public_performance_evidence
closure_signal_identity_unresolvable: DS11-PUBLIC-SIGNATURE-POPULATION: tests/unit/runtime/http/test_public_export.py::test_first_governed_public_signature_is_custody_bound; ast=False; collected=0; exit=4; no tests collected in 0.00s | ERROR: file or directory not found: tests/unit/runtime/http/test_public_export.py::test_first_governed_public_signature_is_custody_bound
closure_signal_identity_unresolvable: DS11-SCOPE-ADJUDICATION-RECORD: tests/unit/core/contracts/test_scope_adjudication.py::test_four_way_ruling_is_produced_consumed_and_plane_specific; ast=False; collected=0; exit=4; ERROR: not found: /Users/deniskopylov/polisyos/.worktrees/debt-m-promotion-corridor-repair/policy-engine/tests/unit/core/contracts/test_scope_adjudication.py::test_four_way_ruling_is_produced_consumed_and_plane_specific | (no match in any of [<Module test_scope_adjudication.py>])
closure_signal_identity_unresolvable: ds10-connector-acquisition-content: tests/unit/runtime/http/test_control_api.py::test_list_connectors_and_profiles_are_producer_backed; ast=False; collected=0; exit=4; ERROR: not found: /Users/deniskopylov/polisyos/.worktrees/debt-m-promotion-corridor-repair/policy-engine/tests/unit/runtime/http/test_control_api.py::test_list_connectors_and_profiles_are_producer_backed | (no match in any of [<Module test_control_api.py>])
closure_signal_identity_unresolvable: ds10-global-case-index-producer-allocation: tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index; ast=False; collected=0; exit=4; ERROR: not found: /Users/deniskopylov/polisyos/.worktrees/debt-m-promotion-corridor-repair/policy-engine/tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index | (no match in any of [<Module test_capability_discovery_api.py>])
closure_signal_identity_unresolvable: ds10-public-decision-rendering: tests/unit/runtime/http/test_public_export.py::test_public_decision_projection_is_custody_bound; ast=False; collected=0; exit=4; no tests collected in 0.00s | ERROR: file or directory not found: tests/unit/runtime/http/test_public_export.py::test_public_decision_projection_is_custody_bound
closure_signal_identity_unresolvable: epoch-dependency-denominator-defined-twice-incompatibly: tests/unit/scientist/validation/test_decision_validity_service.py::test_epoch_denominator_reconciliation_receipt_bridges_both_owner_definitions; ast=False; collected=0; exit=4; ERROR: not found: /Users/deniskopylov/polisyos/.worktrees/debt-m-promotion-corridor-repair/policy-engine/tests/unit/scientist/validation/test_decision_validity_service.py::test_epoch_denominator_reconciliation_receipt_bridges_both_owner_definitions | (no match in any of [<Module test_decision_validity_service.py>])
closure_signal_identity_unresolvable: explicit-nonclosure-check-blind-to-table-shaped-lists: tests/repo_quality/tools/test_debt_ledger_checker.py::test_explicit_nonclosure_parser_reads_every_populated_section; ast=False; collected=0; exit=4; ERROR: not found: /Users/deniskopylov/polisyos/.worktrees/debt-m-promotion-corridor-repair/policy-engine/tests/repo_quality/tools/test_debt_ledger_checker.py::test_explicit_nonclosure_parser_reads_every_populated_section | (no match in any of [<Module test_debt_ledger_checker.py>])
closure_signal_identity_unresolvable: global-case-index-producer-missing: tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index; ast=False; collected=0; exit=4; ERROR: not found: /Users/deniskopylov/polisyos/.worktrees/debt-m-promotion-corridor-repair/policy-engine/tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index | (no match in any of [<Module test_capability_discovery_api.py>])
closure_signal_identity_unresolvable: register-status-parsed-from-prose-not-from-the-status-cell: tests/repo_quality/tools/test_debt_ledger_checker.py::test_row_status_comes_from_the_status_cell_not_from_prose; ast=False; collected=0; exit=4; ERROR: not found: /Users/deniskopylov/polisyos/.worktrees/debt-m-promotion-corridor-repair/policy-engine/tests/repo_quality/tools/test_debt_ledger_checker.py::test_row_status_comes_from_the_status_cell_not_from_prose | (no match in any of [<Module test_debt_ledger_checker.py>])
Informational findings (do not block):
closure_signal_count_exit_disagreement: DS11-EXTERNAL-A11Y-COUNTERSIGN: tests/repo_quality/docs/test_accessibility_evidence.py::test_external_countersign_is_content_bound_current_and_scope_exact; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: DS11-FULL-TRUST-CENTER-AND-DOCS-IA: tests/repo_quality/frontend/test_public_surface_claim_ownership.py::test_every_retained_trust_docs_route_has_an_approved_owner_and_evidence_contract; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: DS11-GROUNDED-PERFORMANCE: tests/integration/runtime_quality/test_first_governed_promotion.py::test_promoted_design_supplies_content_bound_public_performance_evidence; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: DS11-PUBLIC-SIGNATURE-POPULATION: tests/unit/runtime/http/test_public_export.py::test_first_governed_public_signature_is_custody_bound; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: DS11-SCOPE-ADJUDICATION-RECORD: tests/unit/core/contracts/test_scope_adjudication.py::test_four_way_ruling_is_produced_consumed_and_plane_specific; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: ds10-connector-acquisition-content: tests/unit/runtime/http/test_control_api.py::test_list_connectors_and_profiles_are_producer_backed; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: ds10-global-case-index-producer-allocation: tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: ds10-public-decision-rendering: tests/unit/runtime/http/test_public_export.py::test_public_decision_projection_is_custody_bound; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: epoch-dependency-denominator-defined-twice-incompatibly: tests/unit/scientist/validation/test_decision_validity_service.py::test_epoch_denominator_reconciliation_receipt_bridges_both_owner_definitions; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: explicit-nonclosure-check-blind-to-table-shaped-lists: tests/repo_quality/tools/test_debt_ledger_checker.py::test_explicit_nonclosure_parser_reads_every_populated_section; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: global-case-index-producer-missing: tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: register-status-parsed-from-prose-not-from-the-status-cell: tests/repo_quality/tools/test_debt_ledger_checker.py::test_row_status_comes_from_the_status_cell_not_from_prose; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_runner_unsupported: ds10-lex-pipeline-mutation-boundary: src/features/lex/routes/LexKnowledgeGraphPage.test.tsx; Vitest selection is unsupported by design; resolve this row manually
register_supplies_missing_standing: GY:GY-DEF14: register=closed, source=ambiguous
register_supplies_missing_standing: GY:GY-DEF15: register=closed, source=ambiguous
register_supplies_missing_standing: GY:GY-DEF19: register=closed, source=prose_only
register_supplies_missing_standing: GY:GY-DEF22: register=open, source=ambiguous
register_supplies_missing_standing: GY:GY-DEF23: register=blocked, source=ambiguous
register_supplies_missing_standing: GY:GY-DEFC-1: register=closed, source=ambiguous
register_supplies_missing_standing: GY:GY-GAP5: register=blocked, source=ambiguous
register_supplies_missing_standing: GY:GY-GAP6: register=blocked, source=ambiguous
register_supplies_missing_standing: GY:GY-GAP7: register=folded, source=ambiguous
register_supplies_missing_standing: GY:GY-GAP8: register=closed, source=ambiguous
```

Every blocking identity names either an absent node or absent file outside the Task
M diff. A path-complete diff over the checker, active register and all named target
files returned no paths. That proves disjointness from Task M, but not inheritance:
P41 requires replaying the same bound command on the base, which this lane did not
do. The finding provenance is therefore `not_established`, not “inherited.” The
unbound carried exit-0 baseline is deliberately not used because it downgrades
these failures.

### Docs lifecycle

Command:

```text
PYTHONPATH=. python3 tools/quality/validation/check_docs_lifecycle.py
```

Exit: 1. Verbatim output:

<pre>
Docs lifecycle gate FAILED:
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `status` front matter.
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `owner` front matter.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-adoption-ledger.json: stale direct reference `frontend&#47;runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-archive-map.json: stale direct reference `frontend&#47;runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/reference/frontend/atlas-v15-adjudication.md: stale direct reference `frontend&#47;runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/research/policy-operations/audits/pao-r0/pao-r0-test-and-fixture-verification.md: stale direct reference `frontend&#47;runtime-dashboard`; use `apps/runtime-dashboard`.
</pre>

This exactly matches the carried six-finding baseline. None of the six paths is in
Task M's diff. The four legacy-path slashes are HTML-entity encoded only in the raw
journal source so the lifecycle scanner does not recursively treat quoted output as
a seventh live reference; the rendered `<pre>` receipt reproduces the original text.

### Ruff

Command:

```text
.venv/bin/python -m ruff check src/polisyos/core/contracts/decision_validity.py src/polisyos/runtime/quality/generation_cycle.py tests/unit/runtime/http/test_runs_api.py tests/unit/runtime/quality/test_generation_cycle.py tests/unit/runtime/quality/test_promotion_sequence.py tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py
```

Exit: 0. Verbatim output:

```text
All checks passed!
```

### Additional repository guardrail

After the repository-required `corepack pnpm install --frozen-lockfile`, both
generated-client freshness probes were clean. The architecture guardrail still
exited 1 for three deep imports in the unchanged
`src/polisyos/runtime/http/services/acquisition_admission_bundle.py` and a trust
appointment/register mismatch in unchanged inputs. Task M did not sync the
baseline or change those governed surfaces. Because the exact guardrail was not
replayed on the base, their provenance is also `not_established`, not inherited.

`git diff --check` is clean, `git diff -- docs/plans/active` is empty, and
`git ls-files 'src/**/*.py' | wc -l` prints `2617`.
