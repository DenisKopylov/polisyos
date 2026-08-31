# Epoch and Decision-Validity Debt Closure Journal

Date: 2026-08-30

Branch: `codex/debt-b-epoch-decision-validity`

Slice base: `784d020148c56e9bfb3a3631909ba11232210a9f`

Plan: `docs/superpowers/plans/2026-08-30-debt-b-epoch-decision-validity.md`

## Entry state

- `git symbolic-ref -q HEAD` -> `refs/heads/codex/debt-b-epoch-decision-validity` (exit `0`).
- `git status -sb` -> attached branch, no tracked or untracked changes before task-created plan/journal (exit `0`).
- `git rev-parse HEAD` -> `784d020148c56e9bfb3a3631909ba11232210a9f` (exit `0`).
- `uv sync --frozen` completed at exit `0`; test extras are invoked explicitly with `uv run --frozen --extra test`.
- Read completely before planning: `CONTRIBUTING.md`, `docs/reference/policy-design-case-failure-patterns.md`, the eight full debt-register rows and five institutional siblings, identity §9 item 5, `docs/superpowers/specs/2026-08-20-gy-n12-epoch-chronology-design.md`, `docs/superpowers/specs/2026-08-20-gy-n12-epoch-chronology-closure-basis.md`, and all `10,727` lines of `docs/superpowers/plans/2026-08-20-gy-n12-epoch-chronology-implementation.md`.

## Baseline receipts

### GY-GAP8 live red

Command:

```bash
uv run --frozen --extra test -m pytest -q tests/repo_quality/test_claim_ledger_export_callers.py::test_all_execution_context_constructors_require_same_claim_owner_port
```

Result: exit `1`; the exact assertion is `118 == 117`.

Measured Git candidate denominator:

```text
5,710 paths = 5,705 .py + 5 .pyi
```

Independent scan composition:

```text
AST ExecutionContext constructions:   118 tests + 0 src + 0 other
token ExecutionContext constructions: 118 tests + 0 src + 0 other
AST minus token:                       0 call sites
token minus AST:                       0 call sites
```

Mapping from Task-4.5 boundary `552213d90599f392ec6c68871e5c5af12a74ed49` by stable `(path, enclosing function)`:

- added: `tests/unit/scientist/orchestration/workflows/test_builder_pinning.py::test_eval_safety_context_fields_are_keyword_only`;
- removed: none;
- current call: line `201`, column `14`;
- introduction: `f715bfdc46c59cfa70e959b99248c9543379192e` (`feat(gy-o0): gate Scientist evaluation attempts`, 2026-08-28);
- purpose: exercise base `ExecutionContext` positional compatibility and keyword-only evaluation-safety fields; it is not a production or claim-producing constructor.

P38 divergence:

- property: every non-test execution-context construction uses the claim-capable owner path;
- proxy: a scalar total of test-only base constructions;
- valid divergence: adding this test preserves the property and breaks `117`;
- unsafe divergence: a base construction in `tools/` or another non-`src/`, non-`tests/` executable partition passes the old `not src` assertion;
- repair: assert the complete base-constructor set equals its `tests/` partition, while retaining exact positive claim-capable constructor paths.

### Implemented/unorchestrated and empty-slot census

- `EpochValidityTransitionProducer` exists and has zero production constructor sites and zero production `.produce_and_persist` calls.
- The one constructor/call pair is a negative-path unit test.
- Production injects `NoEpochTransitionSigningAuthority()` at `src/polisyos/runtime/http/dependencies.py:140` on the slice base.
- `DecisionValidityService` defaults to `NoEpochTransitionVerifier`; positive verifier objects are test fixtures.
- Strict intake, durable pending freeze, completion evidence, Claim bridge, canonical N9 consumer, and offline gate-evidence re-read already exist.
- Therefore the producer row is `implemented_but_not_orchestrated`, while the positive verifier is `producer_missing`; neither is truthfully closed by a fixture.

### Lineage and recompute entry state

- Pre-N9 subject derivation fixes `current_decision_packet_ref=None` and `packet_epoch_refs=()`.
- The N9 resolver rejects the shaped `current` arm as `epoch_validity_prior_binding_unresolved`.
- Decision Validity persists raw lineage head state but exposes no content-bound lookup keyed by the derived pre-N9 lineage digest.
- Epoch staleness projection constructs `EpochDerivedRecomputeView(status="not_established")` for every dependency and always reports the engineering absence.
- `derived_observations` has exact certified derivation production/replay but no epoch-inheritance receipt/resolver.
- `TemporalService.build_epoch_staleness_projection` is refusal-only on the slice base.

### Lex ambiguity

- The tracked repository supports the historical `156,196` owner denominator statement.
- It does not contain a production Lex database or a source/test/tool/architecture artifact from which `152,636` missing `effective_from` rows can be re-derived.
- No plausible reconstruction will be used as a closure signal.

## Command receipts

Append each command once, with exact argv, semantic predicate, exit code, and relevant counts. Do not bundle one exit code across predicates.

### Task 1 reviewer correction

The required stale-caller Claim Ledger signal was run after review:

```bash
uv run --frozen --extra test -m pytest -q tests/unit/scientist/orchestration/orchestrator/test_decision_grade_compiler.py::test_stale_caller_ledger_cannot_bypass_current_head_public_export
```

Result: exit `0`; pytest output was `.                                                                        [100%]`.

## Commit receipts

Before every commit record `git symbolic-ref -q HEAD`, expected old `HEAD`, staged paths, commit ID, tree ID, and post-commit readback.

## Targeted closeout receipts

### Branch, freeze, and ancestry

- `git symbolic-ref -q HEAD` -> `refs/heads/codex/debt-b-epoch-decision-validity` (exit `0`).
- `git rev-parse HEAD` -> source-freeze commit
  `8e64b693fceb1767e8a1bc9a693612b37b6f10de` (exit `0`).
- `git status -sb` -> `## codex/debt-b-epoch-decision-validity`, clean and attached
  (exit `0`).
- `git diff 784d020148c56e9bfb3a3631909ba11232210a9f..HEAD --check` -> no output
  (exit `0`).
- `git merge-base --is-ancestor 552213d90599f392ec6c68871e5c5af12a74ed49 HEAD` ->
  no output (exit `0`), so the Task-4.5 boundary is in the source-freeze ancestry.

### Exact targeted semantic commands

GY-GAP8, exactly four nodes:

```bash
uv run --frozen --extra test -m pytest -q tests/repo_quality/test_claim_ledger_export_callers.py::test_all_execution_context_constructors_require_same_claim_owner_port tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py::test_completed_epoch_batch_is_only_authority_input_to_claim_bridge tests/unit/scientist/evidence/claims/test_head_index.py::test_crash_after_dv_completion_keeps_claim_bridge_pending_public_freeze tests/unit/scientist/orchestration/orchestrator/test_decision_grade_compiler.py::test_stale_caller_ledger_cannot_bypass_current_head_public_export
```

Result: exit `0`, `4 passed`. The lifecycle, crash/pending freeze, and stale-caller public
export predicates are distinct from the denominator predicate even though they share one focused
pytest invocation.

Decision Validity, exactly the two new atomic nodes and four named owner/readback nodes:

```bash
uv run --frozen --extra test pytest -q tests/unit/scientist/validation/test_decision_validity_service.py::test_atomic_dedupe_write_failure_cleans_only_owned_temp tests/unit/scientist/validation/test_decision_validity_service.py::test_concurrent_same_packet_persistence_has_no_fixed_temp_collision tests/unit/scientist/validation/test_decision_validity_service.py::test_decision_validity_service_records_events_dedupes_and_tracks_monitoring tests/unit/scientist/validation/test_decision_validity_service.py::test_epoch_batch_persists_complete_pending_freeze_before_first_packet_write tests/unit/scientist/validation/test_decision_validity_service.py::test_completed_batch_does_not_mask_corrupt_packet_owner_state tests/unit/scientist/validation/test_decision_validity_service.py::test_decision_validity_state_store_load_model_assertion_is_not_swallowed
```

Result: exit `0`, `6 passed`.

Existing epoch negatives, exactly six nodes:

```bash
uv run --frozen --extra test pytest -q tests/unit/runtime/quality/test_epoch_validity_cascade.py::test_unappointed_transition_signer_returns_typed_negative_before_owner_reads tests/unit/scientist/validation/test_decision_validity_service.py::test_strict_epoch_intake_fixture_does_not_establish_transition_producer tests/unit/runtime/quality/test_generation_cycle.py::test_core_generation_controller_cannot_bypass_epoch_gate tests/unit/runtime/quality/test_generation_cycle.py::test_first_decision_uses_candidate_subject_without_fabricated_prior_packet tests/unit/runtime/quality/test_generation_cycle.py::test_post_n9_packet_binds_exact_subject_and_gate_receipt tests/unit/runtime/http/test_temporal_routes.py::test_epoch_staleness_route_renders_real_declared_absences_as_usable_state
```

Result: exit `0`, `6 passed`. The post-N9 node validates a
`CanonicalPromotionReceipt` and its exact subject/gate handles. It is a canonical-receipt proxy,
not evidence that a post-N9 receipt is handed to or persisted as a Scientist DecisionPacket
lineage carrier.

### Complete-set denominators and the 118 mapping

Each product census was run separately from the `policy-engine` root:

- `git ls-files '*.py' '*.pyi' | wc -l` -> `5,710` product Python/PYI paths (exit `0`).
- `git ls-files 'src/**/*.py' 'src/**/*.pyi' | wc -l` -> `2,616` tracked src
  Python/PYI paths (exit `0`).
- `git ls-files 'src/**/*.py' | wc -l` -> `2,611` tracked src Python paths (exit `0`).
- `git ls-files | wc -l` -> `10,370` tracked product paths (exit `0`).
- `git ls-files '*.json' | wc -l` -> `1,196` product JSON paths (exit `0`).

The independent denominator walk was:

```bash
uv run --frozen --extra test python - <<'PY'
from collections import Counter
from tests.repo_quality.test_claim_ledger_export_callers import _git_candidate_files, _walk_denominator
candidates = _git_candidate_files()
print(f"git candidates: {len(candidates)} paths = {sum(path.suffix == '.py' for path in candidates)} .py + {sum(path.suffix == '.pyi' for path in candidates)} .pyi")
ast_calls, token_calls, _, _ = _walk_denominator()
ast_rows = ast_calls.get("ExecutionContext", set())
token_rows = token_calls.get("ExecutionContext", set())
for label, rows in (("AST", ast_rows), ("token", token_rows)):
    print(label, Counter("tests" if row.path.startswith("tests/") else "src" if row.path.startswith("src/") else "other" for row in rows))
print("AST/token equal:", ast_rows == token_rows)
print("AST test constructions:", len({row for row in ast_rows if row.path.startswith("tests/")}))
print("token test constructions:", len({row for row in token_rows if row.path.startswith("tests/")}))
PY
```

Result: exit `0`; `5,710 paths = 5,705 .py + 5 .pyi`; AST = `118 tests + 0 src +
0 other`; token = `118 tests + 0 src + 0 other`; AST/token sets equal. Relative to
`552213d90599f392ec6c68871e5c5af12a74ed49`, the complete stable
`(path, enclosing function)` mapping adds exactly
`tests/unit/scientist/orchestration/workflows/test_builder_pinning.py::test_eval_safety_context_fields_are_keyword_only`,
removes none, and locates the current call at line `201`, column `14`. That test was introduced by
`f715bfdc46c59cfa70e959b99248c9543379192e` to exercise base positional compatibility plus
keyword-only evaluation-safety fields; it is not a production or claim-producing constructor.

The composition invariant is the set partition, not the old scalar `117`: every base
`ExecutionContext` construction is in the complete test partition; the exact production
`ClaimCapableExecutionContext` constructor paths remain `runtime/quality/workspace/loop.py`,
`scientist/methods/backtesting/composition_bridge.py`,
`scientist/orchestration/engine/runner/_activity_worker.py`, and
`scientist/orchestration/workflows/builder.py`; the exact positive test paths remain
`tests/unit/scientist/methods/backtesting/test_composition_bridge.py` and
`tests/unit/scientist/nodes/test_build_policy_output_bundle.py`.

### Transition production, verifier, and provider census

Each predicate had its own process exit:

- `git grep -n -F 'EpochValidityTransitionProducer(' HEAD -- 'src/**/*.py'` -> no rows
  (exit `1`).
- `git grep -n -F '.produce_and_persist(' HEAD -- 'src/**/*.py'` -> no rows (exit `1`).
- `git grep -n -F 'EpochValidityTransitionProducer(' HEAD -- 'tests/**/*.py'` -> exactly one
  row, `tests/unit/runtime/quality/test_epoch_validity_cascade.py:819` (exit `0`).
- `git grep -n -F '.produce_and_persist(' HEAD -- 'tests/**/*.py'` -> exactly one row,
  `tests/unit/runtime/quality/test_epoch_validity_cascade.py:827` (exit `0`).
- `git grep -n -F 'DecisionValidityService(' HEAD -- 'src/**/*.py'` -> exactly six production
  rows: two in `run_lifecycle.py`, one each in `debug.py`, `run_index.py`, `feedback/core.py`,
  and the decision-packet builder (exit `0`).
- `git grep -n -F 'epoch_transition_verifier=' HEAD -- 'src/**/*.py'` -> no production
  injection (exit `1`).
- `git grep -n -F 'def resolve_complete_epoch_dependencies' HEAD -- 'src/**/*.py'` -> one row
  at `runtime/quality/epoch_validity_cascade.py:759` (exit `0`), inside
  `EpochDependencyDenominatorProvider(Protocol)`, not a concrete provider.
- `git grep -n -F 'def resolve_complete_owner_adjudications' HEAD -- 'src/**/*.py'` -> one row
  at `runtime/quality/epoch_validity_cascade.py:814` (exit `0`), inside
  `EpochPerturbationAdjudicationProvider(Protocol)`, not a concrete provider.
- `git grep -n -F 'def resolve_transition_manifests' HEAD -- 'src/**/*.py'` -> one row at
  `runtime/quality/epoch_validity_cascade.py:875` (exit `0`), inside
  `EpochTransitionHistoryRepository(..., Protocol)`, not a concrete history holder.
- `git grep -n -F 'test_generation_control_derives_and_admits_signed_epoch_transition' HEAD -- 'tests/**/*.py'`
  -> no exact positive orchestration test (exit `1`).

### Lineage carrier census

- `git grep -n -F 'decision_packet_lineage_key_ref' HEAD -- 'src/**/*.py'` across all `2,611`
  tracked src Python paths -> three rows: the persisted profile field name, the core contract field,
  and pre-N9 derivation in `epoch_validity_cascade.py` (exit `0`).
- `git grep -n -F 'register_decision_packet(' HEAD -- 'src/**/*.py'` -> exactly the Decision
  Validity method and its decision-packet builder caller (exit `0`).
- `git grep -n -E 'subject_ref|gate_evidence_ref|epoch_validity_projection|decision_packet_lineage_key_ref' HEAD -- 'src/polisyos/scientist/**/*.py'`
  -> no Scientist-side field among these four carrier inputs (exit `1`).

The production builder registers a Scientist packet, but no post-N9 canonical receipt-to-Scientist
packet handoff supplies those four carrier inputs. Task 3 therefore stopped at the task-A promotion
emission seam; adding only a test registration helper would have been P01/P02
`implemented_but_not_orchestrated`, not closure.

### Recompute projection and temporal-reader receipts

No generic zero was inferred. The exact present absences are:

- `git grep -n -F 'EpochDerivedRecomputeView(' HEAD -- src/polisyos/runtime/quality/epoch_staleness_projection.py`
  -> line `283` (exit `0`), hardcoded with `status="not_established"` and
  `predicate_provenance="not_established"`.
- `git grep -n -F 'derived_recompute_status_not_established' HEAD -- src/polisyos/runtime/quality/epoch_staleness_projection.py`
  -> line `491` (exit `0`).
- `git grep -n -F 'epoch_staleness_epoch_reader_not_established' HEAD -- src/polisyos/runtime/http/services/temporal.py`
  -> line `444` (exit `0`).
- `git grep -n -F 'epoch_staleness_transition_reader_not_established' HEAD -- src/polisyos/runtime/http/services/temporal.py`
  -> line `454` (exit `0`).

Task 4 stopped because an owner receipt in `derived_observations.py` alone would be orphaned from
both the synthetic projection consumer and the refusal-only temporal reader. The two consumer files
`runtime/quality/epoch_staleness_projection.py` and `runtime/http/services/temporal.py` were not
owned for source edits after the real bridge proved unavailable; no P01/P02 contract-only producer
was added.

### Lex predicates and measures

- `git ls-files src tests tools architecture | wc -l` -> `7,022` product paths (exit `0`).
- Separate searches `git grep -n -F '152,636' HEAD -- src tests tools architecture`,
  `git grep -n -F '152636' HEAD -- src tests tools architecture`, and
  `git grep -n -F '152_636' HEAD -- src tests tools architecture` each returned no match and
  exit `1` over those `7,022` paths.
- `git grep -a -l -F '"lex_amendments": 156196' HEAD -- architecture` -> exactly three
  architecture JSON paths (exit `0`): `layer3_gl_l3_legal_kg_index_coverage.json`,
  `layer3_gy_knowledge_substrate_contract.json`, and `layer3_gy_second_domain_pack.json`.
- `git ls-files 'production_data/**' | wc -l` -> `0` tracked production-data paths (exit `0`).
- `git ls-files '*.duckdb'` -> exactly four paths (exit `0`), all under
  `tests/_data/data_forge/non_lex_split/` and none a Lex production database.
- `git grep -a -l -F '"declared_amendment_count"' HEAD -- '*.json'` -> no match (exit `1`)
  over the complete `1,196` product JSON path denominator.

These receipts support the historical `156,196` architecture-owner statement but provide neither
the production Lex row set nor a current complete owner receipt. The historical `152,636` figure
was not reconstructed, so the row remains ambiguous rather than being coerced open or closed.

### Task-D overlap and remaining witness

- `git ls-files --error-unmatch tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py`
  -> path absent (exit `1`).
- A name-only search finds the closure-signal string in
  `tests/repo_quality/tools/test_trust_claim_posture.py:905`, but the body predicate
  `git grep -n -F 'def test_monitor_event_persists_claim_supersession_without_in_place_edit' HEAD -- tests`
  returns no test definition (exit `1`).

Task D still lacks precisely the row-specific persisted-supersession E2E witness that starts from a
monitor event, re-reads the persisted completed Decision Validity/Claim bindings through the runtime
consumer, appends the superseding Claim state, and proves the old claim was not edited in place.
GY-GAP8's Task-B half does not close `DS11-CLAIM-LIFECYCLE-ORCHESTRATION`.

### Institutional slots, typed ports, and the out-of-scope seam

This lane appointed or newly wired no institutional slot. The already visible empty slots are:

- predicate-policy authority: `SemanticEpochService.for_unallocated_policy_query(...)` in both
  PromotionRuntime composition (`open_world_risk.py:1262`) and temporal HTTP composition
  (`runtime/http/dependencies.py:137`);
- transition signer: `NoEpochTransitionSigningAuthority()` at
  `runtime/http/dependencies.py:140`;
- default verifier: `NoEpochTransitionVerifier` selected by
  `DecisionValidityService` at `scientist/validation/decision_validity.py:421`.

The absent or not-yet-wired typed ports are listed separately, because absence is not appointment:
producer identity (only the positive artifact field exists), independent transition-history holder
(protocol only), verifier appointment/trust registry (no production injection and the default is the
typed negative), dependency inventory (protocol only), and adjudication provider (protocol only).

`git diff --unified=0 784d020148c56e9bfb3a3631909ba11232210a9f..HEAD -- src/polisyos/runtime/http/dependencies.py`
returned no rows (exit `0`): shared `runtime/http/dependencies.py` changed lines = `0`. Line `140`
was deliberately left unchanged. `TemporalService.build_epoch_staleness_projection` calls the
signer with empty bytes solely to obtain a typed nonreceipt after its epoch reader fails; it is not
the trigger that derives a transition before strict Decision Validity intake. Replacing that object
with a factory-shaped refusal would make a constructible proxy stand in for the missing transition
property, a P38/P02 error.

The out-of-scope chain is
`GenerationCycleController -> ArtifactEpochValidityAuthorityGate -> missing transition orchestrator -> EpochValidityTransitionProducer -> DecisionValidityService.admit_epoch_validity_batch`.
Any change to the canonical promotion gate or emission sequence belongs to task A. The two
dependency denominators also diverge semantically: the producer's
`polisyos.epoch.dependency-denominator.v1` hashes certificate bindings, the complete dependency
graph, and target refs, while Decision Validity's `_resolve_epoch_target_denominator` hashes its
registered dependency key/kind/artifact plus packet-ref and lineage-key rows. Neither definition
proves equality with the other, so forwarding one ref as the other would be a P38 proxy rather than
reconciliation.

Tasks 3, 4, and 5 therefore stopped without orphan or form-only code: Task 3 found no production
post-N9 carrier producer; Task 4 found no reader/consumer path for a standalone owner receipt; Task
5 found no real transition trigger, concrete providers, producer identity, or positive verifier
appointment. The smallest correct pattern is to leave the seams named and the rows open/blocked,
not to add fixtures that would repeat P01, P02, P32, or P38.

### Required controls and source lint

The exact ledger control was:

```bash
PYTHONPATH=. uv run --frozen --extra test python tools/quality/validation/check_debt_ledger.py --check
```

Actual result: exit `1`, not the predicted `0`. Measures were `register_ids=151`, `gy_ids=38`,
`atlas_debt_rows=22`, `frontend_disposition_entries=261`,
`frontend_ds8_assignment_rows=217`, `gy_history_blocks=6`, `gy_absent_from_register=15`,
`gy_absent_from_register_closed=15`, `ds5_nonclosure_rows=27`, `ds5_planless_routes=4`,
`irregular_section_e_branch_rows=1`, `closure_signal_pytest_selections=32`,
`closure_signal_unsupported_runners=1`, `closure_signal_identities_without_commands=1`,
`closure_signal_identity_unresolvable=17`, `closure_signal_input_unresolvable=0`,
`closure_signal_selects_nothing=0`, `closure_signal_collection_failed=0`,
`closure_signal_collection_host_unknown=0`, `closure_signal_ast_collection_disagreements=0`, and
`closure_signal_count_exit_disagreements=17`. The 17 blocking findings are unresolved closure-test
identities; one is the separately measured absent DS11 E2E node above. There are also 17
informational count/exit disagreements and one unsupported Vitest runner finding. This lane does not
own the register, ledger, checker, or missing cross-row tests and did not edit them.

The exact docs lifecycle control was:

```bash
PYTHONPATH=. uv run --frozen --extra test python tools/quality/validation/check_docs_lifecycle.py
```

Actual result: exit `1` with exactly `6 findings`, not the predicted exit `0`: two
`active_plan_metadata` findings for missing `status` and `owner` front matter in
`docs/plans/active/LEDGER.md`, plus four `removed_stub_reference` findings for
the removed pre-migration dashboard stub path in
`architecture/atlas_surfaces/atlas-v15-adoption-ledger.json`,
`architecture/atlas_surfaces/atlas-v15-archive-map.json`,
`docs/reference/frontend/atlas-v15-adjudication.md`, and
`docs/research/policy-operations/audits/pao-r0/pao-r0-test-and-fixture-verification.md`.

Ruff ran through uv on exactly the three Python paths changed since the slice base:

```bash
uv run --frozen --extra lint python -m ruff check src/polisyos/scientist/validation/decision_validity.py tests/repo_quality/test_claim_ledger_export_callers.py tests/unit/scientist/validation/test_decision_validity_service.py
```

Result: exit `0`, `All checks passed!`. No full suite or directory-wide test ran.

## P41 control provenance

Both required controls were replayed literally from the clean integration worktree attached at
`main` and slice base `784d020148c56e9bfb3a3631909ba11232210a9f`; neither red was inferred
from the current branch.

At the clean base,
`PYTHONPATH=. uv run --frozen --extra test python tools/quality/validation/check_debt_ledger.py --check`
exited `1` with `18` blocking `closure_signal_identity_unresolvable` findings and `29`
informational findings: `18` count/exit disagreements, `1` unsupported Vitest runner, and `10`
missing-standing findings. Its measured selection denominator was `33 = 32 pytest + 1 Vitest`.
Task B owns exactly `1/18` of those base blockers: the then-missing
`decision-validity-fixed-temp-concurrency` selector. The branch defines that selector, so the same
literal command on the source freeze improves to `17` blockers and `17` count/exit disagreements.
The remaining branch denominator is `17 = 8 DS11 + 9 ds10`, including the separately recorded
DS11 overlap, and every one is causally disjoint from the changed mechanism paths. The added plan is
an input but supplies no DS identity or explicit non-closure and causes no finding; the journal and
Claim caller test are outside the relevant checker inputs; the Decision Validity source is
transitive only to the now-resolved Task-B-owned selector. Under P41, the remaining red is inherited
per finding and the branch strictly improves `18 -> 17`; the checker is not reported green.

At the clean base,
`PYTHONPATH=. uv run --frozen --extra test python tools/quality/validation/check_docs_lifecycle.py`
also exited `1` with exactly the same six-finding composition as the source-freeze branch: two
LEDGER metadata findings and four stale frontend-stub references. All six finding paths are
causally disjoint from Task B's changed paths. Under P41, all six are inherited, with the after
state exactly equal to the before state; the lifecycle checker is not reported green.

## Final-review correction receipt

The final review returned two buckets. The candidate-set escape is the same complete-denominator
class one level deeper (`P35`/`P38`), so the repair widens the generic mechanism instead of adding a
cache-directory exception. The lifecycle escape is a new closeout-self-reference class (`P41`), so
the correction removes only the journal's checker-triggering spelling and preserves the inherited
six-finding receipt.

At fix base `95440d0f4f4274ddaf2c176906a036de226fcd22`, the exact
`test_candidate_file_denominators_reconcile_independently` node exited `1`: independent filesystem
enumeration returned `12,037` candidates while Git returned `5,710`, with the `6,327`-path delta
entirely below a Git-ignored uv cache. Before the mechanism changed, the self-generated isolated-Git
falsifier `test_candidate_file_reconciliation_honors_git_ignores` also exited `1` because an ignored
untracked Python file appeared only in the filesystem set; its admissible untracked and force-tracked
Python witnesses remained present.

Commit `e0097e3194374196c6fe22d5a7e239007553ec41` (tree
`cc6e5565d6d15c60ca1d51d4cc75120a680eb8d5`) repairs the test-owned walker. It still discovers
Python/PYI paths independently from the filesystem, then applies Git's ignore decision generically;
Git's tracked-file semantics retain a force-tracked path below an ignored pattern. The repaired
filesystem and Git sets each contain `5,710 paths = 5,705 .py + 5 .pyi`, are set-equal, and feed
independent AST/token scans that remain equal at `118 tests + 0 src + 0 other`. The exact six-node
final-review wave exits `0` with `6 passed`; Ruff on the one changed Python file and the slice-base
diff check both exit `0`.

Before this journal correction, the exact docs-lifecycle control exited `1` with seven findings:
the base's two active-plan metadata findings, its four removed-stub references, and one additional
removed-stub reference authored by this journal. Rephrasing that one historical path receipt removes
the self-reference without changing any inherited input path. The repaired control exits `1` with
the base's exact six findings; it is intentionally not reported green. The debt control remains the
expected exit `1` with `17` inherited/disjoint unresolved closure identities.

## Register closure dossier

Pattern closeout: P01/P02 explain why Tasks 3/4/5 stopped rather than landing orphan components;
P05/P08 preserve authority and time-role boundaries; P29/P32 require behavioral resolve-bind-verify
evidence; P35 carries every set claim with its measured path and file-type denominator; P38 names
the temporal-trigger and two-denominator divergences; P40 classifies the unchanged missing bridge
class rather than repairing it one level at a time; P41 assigns the two required-control reds by
literal slice-base replay.

`8 measured rows = 2 closed + 4 open + 1 blocked + 1 ambiguous`.

### 1. `GY-DEF23`

**Verdict:** `blocked`.

**Exact deciding command or predicate + exit:**
`git grep -n -F 'EpochValidityTransitionProducer(' HEAD -- 'src/**/*.py'` and
`git grep -n -F '.produce_and_persist(' HEAD -- 'src/**/*.py'` each exit `1`; the exact six-node
epoch-negative pytest command above exits `0`, including
`test_unappointed_transition_signer_returns_typed_negative_before_owner_reads` and
`test_strict_epoch_intake_fixture_does_not_establish_transition_producer`. The deciding predicate is
that signer and producer identity remain unappointed and no real transition reaches strict intake.

**Exact append prose:** **SUPERSESSION 2026-08-31 — `blocked`:** Task B's required closeout keeps `GY-DEF23` blocked: the strict intake and typed negative paths remain correct, but the complete `2,611`-src-Python-path census finds zero production `EpochValidityTransitionProducer(` constructions and zero production `.produce_and_persist(` calls, the transition signer is still `NoEpochTransitionSigningAuthority`, producer identity has no appointed carrier, and no real signed transition is derived before `DecisionValidityService` strict intake; fixtures and signer provenance cannot appoint either missing role.

### 2. `GY-GAP8`

**Verdict:** `closed` for the Task-B half only.

**Exact deciding command or predicate + exit:** the exact six-node GY-GAP8 final-review pytest
command exits `0` with `6 passed`: the original four semantic nodes, independent candidate-set
reconciliation, and the isolated Git-ignore falsifier. Git-ignore-aware filesystem enumeration and
Git tracked/admissible-untracked enumeration each return `5,710 = 5,705 .py + 5 .pyi`, and their
independent AST/token partitions remain equal at `118 tests + 0 src + 0 other`.

**Exact append prose:** **SUPERSESSION 2026-08-31 — `closed` for Task B's half only:** the scalar `117` proxy is replaced by the complete authority partition over `5,710 = 5,705 .py + 5 .pyi` paths: Git-ignore-aware independent filesystem discovery reconciles exactly with Git's tracked-plus-admissible-untracked set, including an isolated falsifier that excludes ignored untracked Python while retaining admissible untracked and force-tracked Python below an ignored pattern; AST and token scans agree on exactly `118` base `ExecutionContext` constructions, all `118` in tests and zero in src/other, while the exact production Claim-capable constructor set remains pinned. Relative to `552213d90599f392ec6c68871e5c5af12a74ed49`, the sole addition is `tests/unit/scientist/orchestration/workflows/test_builder_pinning.py::test_eval_safety_context_fields_are_keyword_only` (current line 201, column 14; introduced by `f715bfdc46c59cfa70e959b99248c9543379192e`) and no call is removed. The denominator, completed-batch lifecycle, crash/pending freeze, and stale-caller public-export nodes all pass. This closes only GY-GAP8's Task-B denominator/bridge evidence: Task D still lacks `tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py::test_monitor_event_persists_claim_supersession_without_in_place_edit`, the row-specific persisted-supersession E2E witness proving monitor event through persisted append without in-place old-claim edit, so `DS11-CLAIM-LIFECYCLE-ORCHESTRATION` remains open.

### 3. `gy-n12-epoch-current-decision-lineage-carrier-unallocated`

**Verdict:** `open`.

**Exact deciding command or predicate + exit:**
`git grep -n -E 'subject_ref|gate_evidence_ref|epoch_validity_projection|decision_packet_lineage_key_ref' HEAD -- 'src/polisyos/scientist/**/*.py'`
exits `1` over the Scientist production partition; the exact six-node epoch-negative command exits
`0`, but its post-N9 node asserts a `CanonicalPromotionReceipt`, not a Scientist packet carrier.

**Exact append prose:** **SUPERSESSION 2026-08-31 — `open`:** the pre-N9 lineage digest and canonical post-N9 receipt exist, and the Scientist decision-packet builder calls `register_decision_packet`, but the complete `2,611`-src-Python-path census finds no post-N9 canonical-receipt handoff that supplies `subject_ref`, `gate_evidence_ref`, `epoch_validity_projection`, and `decision_packet_lineage_key_ref` to a persisted Scientist DecisionPacket carrier; the task-A promotion emission seam is therefore still the missing producer/bridge, and a test-only carrier would be `implemented_but_not_orchestrated`, not closure.

### 4. `gy-n12-lex-amendment-valid-effect-carrier`

**Verdict:** `ambiguous`.

**Exact deciding command or predicate + exit:** the three separate exact searches for `152,636`,
`152636`, and `152_636` over `7,022` tracked `src tests tools architecture` paths each exit
`1`; the `"lex_amendments": 156196` architecture search exits `0` with exactly three JSON paths;
the declared-amendment-count search over `1,196` product JSON paths exits `1`.

**Exact append prose:** **SUPERSESSION 2026-08-31 — `ambiguous`:** a complete tracked-repository census finds the historical `156,196` architecture-owner statement in exactly three architecture JSON paths, but zero tracked `production_data/**` paths, only four test-only non-Lex DuckDB paths, no `"declared_amendment_count"` in the complete `1,196`-JSON-path denominator, and no `152,636` literal in comma, plain, or underscored form across the complete `7,022`-path `src/tests/tools/architecture` denominator; because neither the production Lex row set nor a current complete owner receipt is present, no valid/effect-carrier closure predicate can be evaluated and `152,636` is not reconstructed.

### 5. `ds18-epoch-inheritance-recompute-projection-missing`

**Verdict:** `open`.

**Exact deciding command or predicate + exit:** the exact hardcoded
`EpochDerivedRecomputeView(` search exits `0` at
`runtime/quality/epoch_staleness_projection.py:283`; the derived-recompute limitation search exits
`0` at line `491`; both temporal reader-not-established code searches exit `0` at
`runtime/http/services/temporal.py:444` and `:454`.

**Exact append prose:** **SUPERSESSION 2026-08-31 — `open`:** epoch staleness still constructs every `EpochDerivedRecomputeView` as `status="not_established"` / `predicate_provenance="not_established"`, always appends `derived_recompute_status_not_established`, and the temporal service exposes both `epoch_staleness_epoch_reader_not_established` and `epoch_staleness_transition_reader_not_established`; an owner receipt alone would be orphaned because the projection and temporal reader are absent, and those consumer files were outside this lane's source ownership, so no P01/P02 contract-only producer was added.

### 6. `ds18-positive-transition-production-unorchestrated`

**Verdict:** `open`.

**Exact deciding command or predicate + exit:**
`git grep -n -F 'EpochValidityTransitionProducer(' HEAD -- 'src/**/*.py'` and
`git grep -n -F '.produce_and_persist(' HEAD -- 'src/**/*.py'` each exit `1`; their test-partition
counterparts each exit `0` with exactly one row; the exact positive-orchestration-test search exits
`1`.

**Exact append prose:** **SUPERSESSION 2026-08-31 — `open` (`implemented_but_not_orchestrated`):** `EpochValidityTransitionProducer` remains a real isolated component with exactly one negative test construction/call but zero production constructions and zero production `produce_and_persist` calls across `2,611` tracked src Python paths; the live seam remains `GenerationCycleController -> ArtifactEpochValidityAuthorityGate -> missing transition orchestrator -> producer -> Decision Validity intake`, and any promotion-gate trigger change belongs to task A.

### 7. `ds18-positive-transition-verification-producer-missing`

**Verdict:** `open`.

**Exact deciding command or predicate + exit:**
`git grep -n -F 'epoch_transition_verifier=' HEAD -- 'src/**/*.py'` exits `1`, and
`git grep -n -F 'test_generation_control_derives_and_admits_signed_epoch_transition' HEAD -- 'tests/**/*.py'`
exits `1`; `DecisionValidityService(` has six production rows but defaults to
`NoEpochTransitionVerifier`.

**Exact append prose:** **SUPERSESSION 2026-08-31 — `open` (`producer_missing`):** six production `DecisionValidityService` sites exist, but none injects `epoch_transition_verifier=`, the default remains `NoEpochTransitionVerifier`, no concrete positive verifier/default injection or verifier appointment/trust registry exists, and the exact positive generation-control transition test is absent; this is still missing engineering and therefore remains open rather than blocked on an appointment, while a shaped signed artifact or test fixture cannot establish positive trust.

### 8. `decision-validity-fixed-temp-concurrency`

**Verdict:** `closed`.

**Exact deciding command or predicate + exit:** the exact six-node Decision Validity command above
exits `0` with `6 passed`; the Task-2 behavioral history records the pre-fix named concurrency node
RED at exit `1`, the cleanup remove-the-property mutation RED at exit `1`, and the restored focused
two-node GREEN at exit `0`.

**Exact append prose:** **SUPERSESSION 2026-08-31 — `closed`:** TDD RED on `test_concurrent_same_packet_persistence_has_no_fixed_temp_collision` reproduced the shared fixed-temp race as `FileNotFoundError` at exit `1`; named GREEN followed extraction of the shared UUID-owned atomic byte-writer chokepoint, and the six-node closeout command now passes. The cleanup falsifier then removed only the exception-cleanup property while retaining the writer markers and went RED at exit `1` because the owned UUID temp survived; after byte-for-byte restoration, focused GREEN for `test_atomic_dedupe_write_failure_cleans_only_owned_temp` plus the named concurrency node passed `2/2` at exit `0`, proving cleanup removes only the writer-owned temp while preserving an unrelated sibling.

## Round 2 execution journal

### 2026-08-31 — source pin and adjudicated starting state

- Attached branch: `codex/debt-b-epoch-decision-validity` at
  `50722f7f3b547ff13988d39fa58f31762196235a`; slice base
  `784d020148c56e9bfb3a3631909ba11232210a9f`.
- The architect accepted `GY-GAP8` closed and held
  `decision-validity-fixed-temp-concurrency` open pending the two unexecuted closure
  conjuncts. Round 2 permits only `closed` or concrete `blocked` verdicts.
- Read-only transition census uses `git ls-files`: 10,370 tracked repository paths,
  including 2,821 tracked `src/` paths / 2,611 tracked source Python paths and 2,970
  tracked `tests/` paths / 2,470 tracked test Python paths.

### Fixed-temp missing conjunct attempt 1

1. `corepack pnpm install --frozen-lockfile` exited `0`; the Playwright packages and
   browser-facing workspace links are installed.
2. The exact predecessor Task-4.4 nine-file Python command exited `2` after seven
   assertion failures and an external `KeyboardInterrupt` on the OpenAPI-heavy path. A
   focused replay of the eight initially reported selectors completed normally at B
   HEAD: `7 failed, 1 passed`, exit `1`.
3. The same eight selectors at clean slice base `784d02014` produced the identical
   `7 failed, 1 passed`, exit `1`. None of B's post-base source paths intersects the two
   HTTP test modules or the route/step-up implementation under test; every failing
   request stops before the changed atomic persistence helper.
4. The failures are seven stale or contradictory shared-test expectations: the
   authorized epoch-batch and human-decision rows each contradict their own typed
   refusal status; five production-approval/OpenAPI rows retain expectations from before
   the current three-input gate, owner admission, or two live acquisition actions.
5. Tasks A, C, D, and E each report zero owned diff in the two stale HTTP tests. Task D
   identifies the concrete landable repair as one DS20/team-runtime current
   authorization-denominator reconciliation receipt derived from the complete live
   unsafe-method router and OpenAPI sets, updating both matrices together. No current
   row or commit owns that receipt; the successor owner must be appointed by the
   architect.
6. The exact zero-retry DS9 visual no-writer command exited `1` on its first attempt:
   `Timed out waiting 120000ms from config.webServer`. Debug logging localized the
   nonreceipt to the fixture runtime API health check on port 8000; it never bound while
   several sibling Python workers drove load above twenty. Standalone Storybook reached
   its iframe health URL in about seven seconds, ports were initially free, and Chromium
   was installed. This is not yet a visual pass or failure; the unchanged command must
   be retried after contention clears.

### Transition and recompute pre-implementation census

- `EpochValidityTransitionProducer(`: zero constructions across the complete 2,611
  source Python paths; `.produce_and_persist(`: zero production calls. The producer
  exists and remains `implemented_but_not_orchestrated`.
- `resolve_transition_manifests`: protocol declaration plus producer call, zero concrete
  adapters. Correction to round 1: `FileSemanticEpochHistoryRepository` is already a
  concrete exact history owner; only its transition adapter is absent.
- `resolve_complete_epoch_dependencies`: protocol declaration plus producer call, zero
  concrete providers. `resolve_complete_owner_adjudications`: the same zero. Owner target
  dispositions have zero production constructions.
- Concrete positive verifier intersection: among all 35 `def verify` rows in 27 source
  files, only the protocol and `NoEpochTransitionVerifier` share the full transition
  signature. `epoch_transition_verifier=` has zero production injections; all six
  production `DecisionValidityService` constructions take the negative default.
- Recompute is a real engineering split: `derived_observations.py` has the certified
  derivation producer/reader but no epoch recompute receipt; the staleness projection
  constructs every edge as `not_established`. Round 2 will build the completed-only
  owner receipt and exact reader, then block on the named temporal read bridge outside
  B's files.
- Scientist carrier census: each required token `subject_ref`, `gate_evidence_ref`,
  `epoch_validity_projection`, and `decision_packet_lineage_key_ref` occurs zero times in
  the complete 584-file Scientist source-Python partition. The task-A post-N9 handoff
  must land all four fields before B can build a production current-lineage reader.

### Fixed-temp missing conjunct attempt 2

- The unchanged exact zero-retry DS9 visual no-writer command progressed through both
  fixture servers but exited `1` before collection: Node rejected the transitive direct
  JSON import reached through `publicationPacket.ts -> TimeSemanticsLabel.tsx ->
  LocaleProvider.tsx -> en.json`, then Playwright reported no collected tests. The active
  Node `v22.22.2` satisfies the workspace's declared `>=22 <23` engine, so this is not a
  host-version mismatch.
- `git blame` attributes the newly reachable chain to
  `9ae4badd27a981a340007ca9f49713b4caa35425` (`feat(ds18): render universal epoch
  staleness chrome`). The predecessor journal records the exact DS9 command green before
  that source addition. Task D accepted ownership of the shared dashboard-domain repair:
  its immutable source-freeze commit must restore a pure publication-domain import and
  make this unchanged no-writer command collect and pass with retries fixed at zero.
- Consequently the fixed-temp implementation is locally verified, but its three-part
  register signal remains unmet on two concrete landing artifacts: the Task-D dashboard
  freeze commit above and one DS20/team-runtime authorization-denominator reconciliation
  receipt that makes the seven Task-4.4 HTTP nodes agree with the complete live unsafe
  router and OpenAPI sets.

## Round 2 resume after the prerequisite merges

### Source preservation and ordinary main merge

- The in-progress semantic-history adapter and its real-CAS fixture were preserved first
  as commit `6137d7516`; the prior round's journal receipt was preserved separately as
  `3a631d18c`. No uncommitted work was used as storage.
- Local `main=3681f22fa2cf4161d49451ec3f12bce4f826d8ed` was then merged normally,
  without rebase, producing `c6b3beb43`. The dashboard freeze present in that merge is
  `03c5783609271c27d6f3d212b76dda7eddef2074`, with the architect-supplied
  1,314-path digest receipt unchanged.
- A post-merge diff proves zero Task-B changes in the shared container and task-A
  corridors: `git diff --exit-code main...HEAD --
  src/polisyos/runtime/http/dependencies.py
  src/polisyos/runtime/quality/promotion_sequence.py
  src/polisyos/runtime/quality/generation_cycle.py` exits `0`. In particular,
  `dependencies.py:140` still injects `NoEpochTransitionSigningAuthority()`; no
  factory-shaped refusal replaced it.

### Fixed-temp conjunction re-run after both landings

The local atomic-writer conjunct remains green:

```bash
uv run --frozen --extra test python -m pytest -q \
  tests/unit/scientist/validation/test_decision_validity_service.py::test_concurrent_same_packet_persistence_has_no_fixed_temp_collision
```

Result: exit `0`, `1 passed`.

The exact Task-4.4 nine-file suite was then run:

```bash
uv run --frozen --extra test python -m pytest -q \
  tests/unit/scientist/validation/test_decision_validity_service.py \
  tests/unit/runtime/http/test_decision_validity_api.py \
  tests/unit/runtime/http/test_runtime_api_authz.py \
  tests/unit/runtime/http/test_runtime_step_up_authz.py \
  tests/unit/runtime/http/test_runs_api.py \
  tests/unit/runtime/http/test_control_service_di.py \
  tests/unit/runtime/quality/test_promotion_sequence.py \
  tests/unit/runtime/quality/test_generation_cycle.py \
  tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py
```

Result: exit `1`, `22 failed`. The complete failing-file partition is
`22 = 1 test_runs_api + 5 test_promotion_sequence + 14 test_generation_cycle +
2 test_recursive_generation_cycle_epoch_gate`. Both authz files now pass inside this
same run, so task I's landing is real; the remaining failures are a current Task-4.4
contract/fixture reconciliation in task-A and runtime-run corridors, not the old seven
authz failures and not Task B's atomic writer.

After `corepack pnpm install --frozen-lockfile` exited `0`, the exact zero-retry DS9
no-writer command was run:

```bash
CI=1 PLAYWRIGHT_RETRIES=0 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 \
corepack pnpm --filter @polisyos/runtime-dashboard exec playwright test \
  --config=playwright.visual.config.ts --project=chromium \
  --grep 'DS9 human decision gate' --workers=1 --timeout=90000 \
  --global-timeout=240000
```

Result: exit `1`, all four identities collected and all four failed. Three fixtures did
not render `case-workspace-page`; the fourth called `buildPublicDecisionPacket` without
the now-required exact admitted epoch semantics or typed epoch-semantics nonreceipt.
This agrees with task D's merged journal: D closed the Node-22 collection break, then
explicitly recorded these same four fixture findings as outside its freeze. Collection
success therefore does not satisfy the visual predicate. The fixed-temp row's three-part
signal is `1 green + 2 red`, so it remains unclosed despite the atomic repair itself.

### Exact semantic-history adapter

Commit `6137d7516` adds `FileSemanticEpochTransitionHistoryAdapter`. It reuses the
existing `FileSemanticEpochHistoryRepository`, exact-reads the one framed production
receipt and both manifests, recomputes and verifies the complete scope-history snapshot,
requires a sole current head and direct sole predecessor, and rejects purpose, scope,
receipt, manifest, history, head, and predecessor drift. It does not create a second
history store and does not appoint a signer.

The named pre-implementation adapter node exited `1` because the adapter class did not
exist. At final source freeze:

```bash
uv run --frozen --extra test python -m pytest -q \
  tests/unit/runtime/quality/test_epoch_validity_cascade.py \
  -k 'file_transition_history_adapter or unappointed_transition_signer_returns_typed_negative_before_owner_reads'
```

exits `0` with `10 passed`. The wave includes substituted receipt/manifest, wrong
purpose/scope, missing/ambiguous predecessor, non-head current epoch, corrupt bytes, and
the typed unappointed-signer refusal before owner reads.

### Certified inheritance-recompute producer half

Commit `f23d37487` adds a completed-only
`EpochInheritanceRecomputeReceipt`, its ref-only persisted handle, an exact recipe
artifact profile, a producer, and an exact reader in the named derived-observations
owner. The receipt binds the transition ref and byte hash, old/current epoch, query and
purpose, producer dependency denominator, exact graph edge, target disposition,
certificate binding, recipe, certified-consumption identity, and recomputed derived
output. Its authority is fixed to certified derived-series recomputation and explicitly
excludes transition issuance, observation, publication, and source-observation claims.

The first round-trip node exited `1` before implementation because
`persist_derivation_recipe_artifact` was absent. Final targeted receipts are:

```bash
uv run --frozen --extra test python -m pytest -q \
  tests/unit/runtime/quality/test_derived_observations.py \
  -k 'epoch_inheritance_recompute'
```

Result: exit `0`, `12 passed`.

```bash
uv run --frozen --extra test python -m pytest -q \
  tests/unit/runtime/quality/test_derived_observations.py::test_registered_families_share_recipe_cache_certificate_and_passport_boundary \
  tests/unit/runtime/quality/test_derived_observations.py::test_same_source_artifact_can_fill_two_recipe_roles_and_replay \
  tests/unit/runtime/quality/test_derived_observations.py::test_versioned_family_requires_exact_selection_and_replays_that_version \
  tests/unit/runtime/quality/test_derived_observations.py::test_recomputed_unregistered_family_is_refused_at_consumption
```

Result: exit `0`, `5 passed` including the parametrized first node. The new wave covers
round trip, substitution, authentic-old/head-advance expectation, corrupt bytes and
manifest, wrong disposition, absent edge, certificate drift, recipe drift, and derived
output drift. A complete AST census still finds zero production calls to the new
producer/reader; that is expected because the named temporal consumer is the remaining
registered bridge absence, not because the producer is missing.

### Final complete censuses

At final source freeze the tracked denominators are `10,410` repository paths,
`2,826` source paths, `2,616` source Python paths, `584` Scientist source Python paths,
`2,983` test paths, and `2,482` test Python paths.

A complete AST walk first derives the 2,616-path denominator with `git ls-files
'src/**/*.py'`, then parses every file selected by a complete token prefilter. It exits
`0` with:

```text
EpochValidityTransitionProducer constructor calls     0
produce_and_persist calls                              0
concrete resolve_complete_epoch_dependencies classes  0
concrete resolve_complete_owner_adjudications classes 0
transition-verifier signature matches                 2
  = EpochTransitionVerifier Protocol + NoEpochTransitionVerifier
positive transition-verifier implementations          0
DecisionValidityService production constructions      6
constructions injecting epoch_transition_verifier      0
```

The three simpler exact source searches for `EpochValidityTransitionProducer(`,
`.produce_and_persist(`, and `epoch_transition_verifier=` each exit `1`. A separate
complete AST call census exits `0` with zero source calls to
`FileSemanticEpochTransitionHistoryAdapter`,
`produce_epoch_inheritance_recompute_receipt`, and
`read_epoch_inheritance_recompute_receipt`.

The lineage carrier census walks all 584 Scientist source Python files. Each exact token
search for `subject_ref`, `gate_evidence_ref`, `epoch_validity_projection`, and
`decision_packet_lineage_key_ref` exits `1`. Across all 2,616 source Python files there
is one real Scientist `register_decision_packet` handoff, but it passes only
`packet_ref`, `envelope`, `baseline`, and `monitoring_contract_ref`; it does not consume
the four post-N9 fields.

The denominator incompatibility is structural, not a naming mismatch:

- `polisyos.epoch.dependency-denominator.v1` hashes exact certificate bindings, the
  epoch dependency graph, and the graph's target `ArtifactRef` set.
- `DecisionValidityService._resolve_epoch_target_denominator` hashes registered
  Decision-Validity rows containing dependency key/kind, owner artifact ID, packet-ref
  membership, and lineage-key membership, and separately derives
  `(packet_ref, dependency_key, decision_lineage_key)` targets.
- Strict intake requires the verifier receipt's single `dependency_denominator_ref` to
  equal the second hash. Forwarding the producer's first hash therefore fails honestly.
  Closure needs a persisted cross-owner denominator-reconciliation receipt that binds
  both refs/hashes and their exact mapping, plus a reader and appointed verifier
  provenance. None exists in the complete verifier/provider census.

The current Lex re-measurement covers `7,040` tracked paths under
`src/tests/tools/architecture`, `1,202` tracked JSON paths, and zero tracked
`production_data/**` paths. Exact searches for `152,636`, `152636`, and `152_636` each
exit `1`; `declared_amendment_count` over all 1,202 JSON paths exits `1`. The supported
`156196` denominator still appears in tracked architecture owner artifacts. The missing
production row set and current complete owner receipt are therefore concrete landable
inputs, not a number to reconstruct.

### Final controls and protected boundaries

- The bound debt checker exits `1` with `14` blocking unresolved closure identities:
  `5 DS11 + 9 ds10`. The literal slice-base replay recorded above had `18`; the current
  set is smaller, and Task B added no identity. The checker is not reported green.
- The bound docs-lifecycle checker exits `1` with exactly six inherited findings:
  two active-plan metadata findings and four removed-stub-reference findings. This
  journal adds no seventh finding.
- Ruff over all seven changed Python paths exits `0`; `git diff --check main...HEAD`
  exits `0`.
- `uv run --frozen polisyos-tools architecture guardrails check` exits `1`. Both API
  generated families are clean; the sole failure is the inherited
  `trust-claim-posture-register` generator probe, which rejects the register's current
  `DS11-CLAIM-LIFECYCLE-ORCHESTRATION` appointment/status combination. No import-policy
  edge or exception is introduced by Task B.
- No task-B row appears under an `Explicit non-closure` heading in the complete tracked
  slice-plan Markdown scan. No architect-owned register, ledger, GY plan, Atlas master
  plan, or published denominator was edited.

### Institutional slots left typed and empty

No person or body was appointed or proposed. The new history adapter supplies only the
existing engineering history port, and the recompute producer consumes already signed
evidence; neither mints an institutional act. The empty slots remain sharply visible:

- `gy-n12-epoch-predicate-policy-authority-unappointed` /
  `ds18-epoch-predicate-policy-signer-unappointed`: the runtime projection retains the
  typed `policy_admission_missing` absence.
- `gy-n12-epoch-transition-signing-authority-unappointed` /
  `ds18-epoch-transition-signer-unappointed`: `dependencies.py:140` still supplies
  `NoEpochTransitionSigningAuthority()`, producing
  `epoch_transition_signer_not_established` without reading owner inputs.
- `ds18-epoch-history-independent-holder-unappointed`: no holder is invented; the
  adapter proves only exact repository history and sole-head/direct-predecessor facts.
- The Decision-Validity verifier trust/provenance slot remains empty: all six production
  constructions take `NoEpochTransitionVerifier`, and no positive verifier exists.
- The owner-held transition producer-identity slot remains empty; exact signed bytes do
  not self-appoint their producer.

Task D's `GY-GAP8` overlap is now precise on merged `main`: Task B's denominator and
three named tests are closed. `DS11-CLAIM-LIFECYCLE-ORCHESTRATION` separately blocks on
the registered `claim-ledger-supersession-owner-event-producer-missing` row: production
has the bridge and owner port, but `append_verified_owner_event` is a nonreceipt stub and
the verified owner-event artifact/producer/resolver have not landed. Task B does not
close that row.

## Register closure dossier — resumed final

Pattern closeout: P01/P02 separate built halves from live bridges; P05/P32 preserve
institutional and verifier authority; P07/P08 bind exact chronology; P31/P38 reject
empty-byte and cross-denominator proxies; P35 carries every zero with its complete
denominator; P41 records the two red closure conjuncts and generated-freshness control
without laundering them as Task-B regressions.

`8 measured rows = 1 closed + 7 blocked`.

### 1. `GY-DEF23`

**Verdict:** `blocked`.

**Blocked by:** `gy-n12-epoch-transition-signing-authority-unappointed`: the
purpose-scoped transition signer and owner-held producer-identity appointments have not
landed. The distinct engineering orchestration remainder is carried by the DS18
production row, not bundled back into this narrowed institutional row.

**Deciding command/predicate + exit:** the 2,616-file AST census exits `0` with zero
production producer constructions/calls; the ten-node history/signer-negative wave
exits `0`; `git grep -n -F 'NoEpochTransitionSigningAuthority()' --
src/polisyos/runtime/http/dependencies.py` exits `0` at line 140. The strict intake is
built and the empty signer fails before owner reads, but the named appointments are
absent.

**Exact append prose:** **RESUME SUPERSESSION 2026-08-31 — `blocked`; `blocked_by: gy-n12-epoch-transition-signing-authority-unappointed`.** Task B has now built and verified the exact semantic-history transition adapter around the empty slot: ten targeted cases pass, including sole-head/direct-predecessor readback and the typed no-signer refusal before owner reads. The complete 2,616-source-Python AST census still finds zero production `EpochValidityTransitionProducer` constructions/calls, which remains separately owned by `ds18-positive-transition-production-unorchestrated`; this narrowed row itself cannot close until the purpose-scoped transition signer and owner-held producer-identity roles are appointed. No appointment was made or proposed.

### 2. `GY-GAP8`

**Verdict:** `closed` for Task B's half, as accepted by the architect.

**Deciding command/predicate + exit:** the exact four-node GY-GAP8 command recorded
above exits `0` with `4 passed`; independent filesystem/Git and AST/token walks agree on
`118 tests + 0 src + 0 other`; and
`git merge-base --is-ancestor 552213d90599f392ec6c68871e5c5af12a74ed49
HEAD` exits `0`. The sole mapped addition is the construction introduced by
`f715bfdc4` in `test_builder_pinning.py`; the scalar total pin was deleted in favor of
the composition invariant.

**Exact append prose:** **RESUME CONFIRMATION 2026-08-31 — `closed` for Task B's half.** The accepted closure remains intact after the ordinary main merge: the Task-4.5 boundary is an ancestor, the complete Git-ignore-aware filesystem/Git candidate sets reconcile, independent AST/token scans agree on `118 tests + 0 src + 0 other`, and the denominator plus three named Claim-lifecycle/public-export nodes pass. The 118th construction is `tests/unit/scientist/orchestration/workflows/test_builder_pinning.py::test_eval_safety_context_fields_are_keyword_only`, introduced by `f715bfdc4`; no scalar total was repinned. The overlapping DS11 row is not closed here and now blocks separately on `claim-ledger-supersession-owner-event-producer-missing`.

### 3. `gy-n12-epoch-current-decision-lineage-carrier-unallocated`

**Verdict:** `blocked`.

**Blocked by:** a task-A post-N9 canonical-receipt handoff that persists all four fields
`subject_ref`, `gate_evidence_ref`, `epoch_validity_projection`, and
`decision_packet_lineage_key_ref` into the Scientist DecisionPacket/Decision-Validity
registration path.

**Deciding command/predicate + exit:** four exact `git grep` searches over all 584
tracked Scientist source Python files each exit `1`; the 2,616-file source AST census
finds the one real `register_decision_packet` call but none of the four fields at that
handoff. The protected task-A files have zero Task-B diff, exit `0`.

**Exact append prose:** **RESUME SUPERSESSION 2026-08-31 — `blocked`; `blocked_by: task-A post-N9 canonical-receipt-to-Scientist-packet handoff`.** Across all 584 Scientist source Python files, each of `subject_ref`, `gate_evidence_ref`, `epoch_validity_projection`, and `decision_packet_lineage_key_ref` has zero occurrences; the sole real `register_decision_packet` handoff supplies only packet ref, envelope, baseline and monitoring-contract ref. The required landing is one content-bound task-A emission carrying all four fields into the persisted Scientist DecisionPacket path, after which direct, recursive, HTTP and offline readers can share the lineage-head carrier and run the authentic-old/head-advance/missing/substituted/denominator-drift falsifiers. Task B did not edit `promotion_sequence.py` or `generation_cycle.py`.

### 4. `gy-n12-lex-amendment-valid-effect-carrier`

**Verdict:** `blocked`.

**Blocked by:** the production Lex amendment row set and a current complete
owner-adjudication receipt covering every row; neither is tracked in this repository.

**Deciding command/predicate + exit:** over 7,040 tracked
`src/tests/tools/architecture` paths, the exact `152,636`, `152636`, and `152_636`
searches each exit `1`; zero `production_data/**` paths are tracked; and
`declared_amendment_count` over all 1,202 JSON paths exits `1`. The `156196` owner
denominator search exits `0`.

**Exact append prose:** **RESUME SUPERSESSION 2026-08-31 — `blocked`; `blocked_by: production Lex row set plus current complete owner receipt`.** Re-measurement is complete: all three encodings of the historical `152,636` value are absent from the 7,040 tracked source/test/tool/architecture paths, no production-data path is tracked, and no `declared_amendment_count` exists across 1,202 tracked JSON files, while the supported `156,196` denominator remains present in architecture owner artifacts. The repository therefore cannot evaluate whether every amendment now has a valid/effect coordinate. This is a landable data-and-owner-receipt block, not a standing ambiguity, and `152,636` is not reconstructed.

### 5. `ds18-epoch-inheritance-recompute-projection-missing`

**Verdict:** `blocked`.

**Blocked by:** the temporal read bridge in
`runtime/quality/epoch_staleness_projection.py` and
`runtime/http/services/temporal.py` that must exact-read the new persisted receipt and
project its status at the requested temporal coordinate.

**Deciding command/predicate + exit:** the new 12-node recompute wave and five-case
existing derivation blast radius exit `0`; a complete 2,616-file AST census exits `0`
with zero production producer/reader calls; and an exact search for the new receipt/
reader symbols in the two named consumer files exits `1`.

**Exact append prose:** **RESUME SUPERSESSION 2026-08-31 — `blocked`; capability state narrowed from `producer_missing + bridge_missing` to `bridge_missing`.** Commit `f23d37487` builds the completed-only owner producer and exact reader: the receipt binds transition, old/current epoch, query/purpose, graph edge, disposition, certificate, recipe, certified replay and derived output; twelve adversarial owner cases and five imported derivation cases pass. The landable remainder is the temporal read bridge in `epoch_staleness_projection.py` and `runtime/http/services/temporal.py`; those consumers still have zero references to the new receipt/reader and therefore still project `not_established`. The producer is not an orphan because this registered consumer absence names its destination.

### 6. `ds18-positive-transition-production-unorchestrated`

**Verdict:** `blocked`.

**Blocked by:** three concrete engineering landings plus the typed-empty authority slot:
a real task-A pre-N9 trigger, a complete `EpochDependencyDenominatorProvider`, a complete
`EpochPerturbationAdjudicationProvider`, and the purpose-scoped signer/owner-held producer
identity appointment.

**Deciding command/predicate + exit:** the complete 2,616-file AST census exits `0`
with `0` producer constructions, `0` `.produce_and_persist` calls, and `0` concrete
classes for either provider protocol. The ten-node exact-history/typed-negative wave
exits `0`; the separate adapter source-call census exits `0` with zero production calls.

**Exact append prose:** **RESUME SUPERSESSION 2026-08-31 — `blocked`; `blocked_by: task-A pre-N9 trigger + complete dependency-inventory producer + complete owner-adjudication producer + transition signer/producer-identity appointment`.** The producer was never missing, and Task B now supplies its exact semantic-history adapter; ten adapter/negative cases pass. A complete 2,616-source-Python AST census nevertheless finds zero production producer constructions/calls and zero concrete implementations of either complete owner provider. The provider contracts' positive `independently_reconciled` receipts cannot be replaced by empty denominators, and `dependencies.py:140` remains the typed no-signer slot rather than an empty-byte orchestration proxy. These named artifacts/appointments must land before a real run can persist a positive transition.

### 7. `ds18-positive-transition-verification-producer-missing`

**Verdict:** `blocked`.

**Blocked by:** a persisted cross-owner
`EpochTransitionDenominatorReconciliationReceipt` (or equivalently named admitted
artifact) with a producer and exact reader, followed by an appointed verifier
trust/provenance identity.

**Deciding command/predicate + exit:** the complete 2,616-file AST census exits `0`
with exactly two verifier-signature shapes—the Protocol and
`NoEpochTransitionVerifier`—and zero positive implementations. It finds six production
`DecisionValidityService` constructions and zero verifier injections. The two source
hash definitions above are read directly and require equality at strict intake despite
different member sets.

**Exact append prose:** **RESUME SUPERSESSION 2026-08-31 — `blocked`; `blocked_by: persisted cross-owner denominator-reconciliation receipt/producer/reader plus appointed verifier provenance`.** The complete source census finds zero positive transition verifier implementations and zero verifier injections across all six production `DecisionValidityService` constructions. More importantly, the producer's `polisyos.epoch.dependency-denominator.v1` hashes certificate bindings, dependency graph and graph targets, while strict intake recomputes dependency key/kind, owner artifact, packet and lineage membership and requires that different hash in the same field. A verifier cannot honestly forward one as the other. A content-bound mapping receipt carrying both refs/hashes and exact membership reconciliation must land before the positive verifier can be built; the default remains `NoEpochTransitionVerifier`, and no trust appointment was fabricated.

### 8. `decision-validity-fixed-temp-concurrency`

**Verdict:** `blocked`.

**Blocked by:** two exact external reconciliation landings: the current Task-4.4
nine-file contract/fixture wave must return exit `0`, and the four DS9 visual fixtures
must satisfy the unchanged zero-retry no-writer command at exit `0`.

**Deciding command/predicate + exit:** the named concurrency node exits `0`; the exact
Task-4.4 command exits `1` with `22 failed`; the exact DS9 command exits `1` with four
identities collected and `4 failed`.

**Exact append prose:** **RESUME SUPERSESSION 2026-08-31 — `blocked`; `blocked_by: current Task-4.4 suite reconciliation + DS9 four-fixture visual reconciliation`.** The UUID/O_EXCL/0600/fsync/atomic-replace writer remains green on its named concurrency node, but the row's conjunction is not met. After merging task I, the exact nine-file Task-4.4 suite exits `1` with `22 = 1 runs-API + 5 promotion-sequence + 14 generation-cycle + 2 recursive-gate` failures; the two authz files are green, so this is the current task-A/runtime contract-fixture remainder. After merging task D, the exact zero-retry no-writer command collects all four DS9 identities but exits `1`: three fixtures never render the case-workspace page and one omits the required typed epoch semantics/nonreceipt. Both external suites must land green; collection success and a locally correct atomic writer are not substitutes for the row's conjunction.
