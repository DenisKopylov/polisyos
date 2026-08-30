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
