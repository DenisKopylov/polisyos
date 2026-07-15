# GY-N10 Final Closure Audit Journal

## Status

`findings_repair_pending`

The GO declared at `36942a1a8` is withdrawn pending this independent audit. Evidence in this
journal comes from source inspection, direct frozen-payload probes, and recomputation; the earlier
stage journals are context only. Read-only reconnaissance ran in parallel. Every validator,
source flip, writer, and repair remains serial under the repository runtime.

## Audit baseline

- branch: `codex/gy-n10-depth-n-universality`
- declared capstone commit: `ce847b9f2`
- declared contract hash:
  `sha256:8d4b2f69f35d989206cc9304d6ccb76759800b386406654085a55fcb671cbb16`
- audit start: clean worktree at `36942a1a8`
- local review posture: independent subagents were available for read-only source reconnaissance;
  their conclusions are accepted only where the primary process reproduced the source/artifact
  evidence.

## Initial findings — journaled before repair

### Blocker A1 — degradation-class authority trusts recognized strings

Source evidence:

- `tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py:2779`
  classifies evidence from literal `authority_blockers`, terminal kind, and a role fallback;
- the same validator at the terminal-honesty gate adds those returned strings to a set and treats
  the set cardinality as structural class diversity;
- the compact education trace carries only an advisor receipt hash, and the compact unseen trace
  carries only an acquisition-requirement id. Neither typed owner receipt body is validated by the
  static gate.

Recomputed-hash probes against the frozen payload showed:

1. adding `method_estimand_binding_mismatch` to the first-vertical value blockers and changing its
   recorded class to `estimand_binding_refusal` passed validation;
2. the same transplant on unseen also passed;
3. replacing education's advisor receipt hash with `sha256:` plus 64 zeroes passed;
4. changing a run to the allowlisted `grounded_abstention` terminal with a matching recomputed
   evidence label passed;
5. setting a terminal distribution grade to `publishable` passed.

The existing simple relabel negative and forged planner-hash negative do go RED, but they do not
close the class. Classification: **blocker / real defect (P29, P31, P32)**. Bounded owner-first
shape: project and validate typed owner witness bodies (`MethodSelectionReceipt`, canonical L1
availability `AcquisitionRequirementGap`, or verified grounding-coverage planner report), bind
terminal kind and decision grade to the witness, remove the role-derived class fallback, and count
structural witness kinds rather than blocker strings.

### Blocker D1 — static corrupt drift has a one-field denominator

`corrupt_field_drift_check` changes only top-level `proof_status`. Static validation does not
cross-bind the top-level `terminal_distributions` map to domain runs and only verifies that the
three proof-recording role keys exist. Recomputed-hash probes showed that a mutated top-level
education distribution and stale embedded compiler raw-request bytes both pass.

Classification: **blocker / real defect (P29, P33)**. The repair must add a static corruption
denominator covering nested evidence kinds, planner/report hashes, embedded compiler/N4/compiled
recordings, terminal kind/grade, and top-level distributions. Semantic cases recompute outer hashes
so they exercise the property; stale nested hashes must be rejected by their own content bindings.

### Blocker H1 — unseen/no-pack proof contains first-vertical vocabulary

Direct artifact evidence:

```text
domain_runs.unseen.stage_trace.generation.proposed_lever_ids =
  ["tax_subsidy", "tax_subsidy", "tax_subsidy"]
proof_recordings.unseen.n4_recording.owner_result_projection
  .proposed_interventions[*].operator_kind = "tax_subsidy"
```

The embedded N4 projection also contains `avg_income`, `avg_price`, `inflation_rate`, and
`wartime_budget_feasibility`. The compiler-owned unseen `DesignProblem`, by contrast, carries
`demand_reduction_instrument`, `emission_reduction_instrument`, and
`equity_protection_instrument`. The contamination is therefore introduced downstream.

Source archaeology localizes the cause to the canonical Scientist formalizer path:

- `src/polisyos/scientist/agent/formalizer.py` maps many unrelated mechanism aliases to
  `tax_subsidy`, defaults missing kinds to `tax_subsidy`, injects `avg_income`, and adds the wartime
  budget constraint;
- the capstone validator's unseen check scans only the projected domain run and uses a five-token
  hand list that omits these values; it does not inspect embedded proof recordings.

Classification: **blocker / real defect (U2-U4, P29, P31-P33)**. The bounded fix is not to rebuild
the Scientist schema. Where no owner substrate context can bind the compiled domain vocabulary,
the cycle must take an existing typed U4 refusal/problem-derived fallback before the fixed vertical
formalizer can become authority. The capstone must supersede the contaminated N4 recording with a
content-bound owner refusal and validate the entire embedded unseen denominator, not a hand-picked
token list.

### Must-fix C1 — volatile exclusion ownership is duplicated and decorative

Positive control: a normal nested semantic mutation changes the contract hash, and the current
carry helper did not copy the mutated semantic value. The masking bug is not presently observed.
However:

- `_CONTENT_HASH_EXCLUDED_TOP_LEVEL` is a writer-local list;
- `runtime_metrics` is repeated as writer-local special cases in hash, mutation, and carry helpers;
- the artifact's `content_hash_excluded_fields` declaration is neither validated nor consumed;
- changing that declaration to `[]` and recomputing the hash passes;
- the source flip removes preservation rather than flipping the equal-hash condition, and there is
  no semantic-difference/full-rewrite negative.

Classification: **must-fix / real single-source and RED-capability gap (P29, P31)**. The canonical
GY hash owner must expose the exclusion vocabulary; declaration, hash, carry, and mutation helpers
must all consume it. A nested semantic mutation must change hash and perform a full rewrite, and an
`equal` to `not-equal` branch flip must go RED.

## Positive controls retained

- forged acquisition planner hashes are rejected;
- a simple recorded `evidence_kind` relabel is rejected;
- ordinary semantic changes do not currently enter the equal-hash carry branch;
- the worktree remained clean throughout read-only reconnaissance.

### Must-fix F1 — N7 receipt hashes include operational clocks

`AcquisitionReceipt.generated_at` is operational, but `_receipt_content_hash` serializes the whole
receipt except `content_hash`, including both the receipt clock and the nested planner-report clock.
Recomputing real positive and no-result receipts with only a one-second clock change changed their
hashes (`03ced0... -> 5d65e6...` and `2d1b97... -> 5b5961...`). The N6 injected-clock change
therefore moved operational time into semantic identity.

Classification: **must-fix / real defect (P07, P29)**. The N7 owner must define one semantic
receipt projection that excludes operational clocks recursively, add a same-semantics/different-
clock RED, and rebaseline every affected N7/N10a/capstone witness through canonical writers.

### Must-fix F2 — Workspace Phase 2 sends a dict pseudo-problem to Foundry

`WorkspaceLoop.run_intent` receives and validates a real `DesignProblem`, then projects it to a
workspace-intent dict and drops the owner object before `_phase2_state`. `_phase2_value_method_selection`
constructs a smaller shaped dict and passes it to authority-bearing
`select_value_method_for_problem`. The N7 caller census is clean, but this sibling advisor consumer
reopens the same P31/P32 class.

Classification: **must-fix / real defect (P31, P32)**. Propagate the already-owned
`DesignProblem` through `_phase2_state` and the selector; retain the projected intent for mechanics
only. A caller census and focused WorkspaceLoop negative must prove no shaped pseudo-problem reaches
the Foundry owner.

### Item E — historical boundary passes read-only audit

The rederive eligibility predicate accepts exactly one nested recursive content-hash validation
error. Education and unseen embedded receipts produce that one historical drift; first vertical
validates under the current DTO. `_verify_historical_compiled_envelope` passes all three real
recordings. Raw compiler/N4 byte mutations fail their inner/outer hashes, and adding a non-hash
validation error makes the predicate false and remains fatal. Classification: **pass**, pending the
serial focused replay in the affected gate.

### Item G — Task-13–15 assertion sweep

The commit-by-commit assertion sweep found seven replacement groups and no weakened assertion.
`6ff1e7986` is strictly stronger: it requires three `novel_cg3` dispositions, real organ calls, and
zero candidates, rankings, atom hashes, or candidate-id authority. Other changes were stronger or
neutral lifecycle/evidence rebaselines. Classification: **pass**, pending the serial focused test
denominator after repairs.

## Pending audit items

Generated-artifact registration and source-level fresh-state prerequisites passed read-only
inspection. The actual clean-checkout rederive and final coherence gates remain pending. Owner
repairs begin only after this classification commit.

## Repair checkpoint — F2 typed DesignProblem propagation

The RED-first WorkspaceLoop probe failed because `_phase2_state` could not receive the already-owned
`DesignProblem`. The owner path now propagates that exact typed object through Phase 2 and deletes
the reconstructed dict. The focused probe observes object identity at
`select_value_method_for_problem`; the AST census finds no surviving `problem = { ... }` sibling in
the production module. Landed separately as `02c606a52`.

## Repair checkpoint — F1 N7 semantic receipt projection

RED evidence:

```text
env ... .venv/bin/python -m pytest \
  tests/unit/runtime/quality/test_acquisition_planner.py::test_n7_closed_loop_compiles_all_specs_and_reenters_same_cycle -q
exit 1: clock-shifted hash d31c5988... != original 57624c6c...
```

The canonical N7 receipt owner now routes receipt hashing through the existing recursive GY
volatile-field projection. The live boundary still validates the recorded hash, so only operational
clocks are removed from identity. A one-dollar semantic cost change remains hash-decisive.

Verification:

```text
focused receipt test: exit 0 (12.013 s)
check_layer3_gy_acquisition_contract.py --rederive-audit:
  exit 1 only on expected frozen content-hash drift
check_layer3_gy_acquisition_contract.py --write: exit 0 (5.108 s)
second --write: exit 0 (5.080 s)
check_layer3_gy_acquisition_contract.py --check: exit 0 (0.438 s)
artifact sha256 before/after second write:
  23ebac67c73963be8bd64fb3052d785904d1b7a7bcbea6ee79fecea9c5539bdd
.venv/bin/ruff check acquisition_planner.py test_acquisition_planner.py: exit 0
```

The writer emitted pre-existing unclosed-client warnings after a successful offline result; no
network authority or semantic output depended on those warnings. Downstream N10a/capstone witness
hashes remain intentionally pending the single canonical ripple rebaseline after all owner fixes.

## Repair checkpoint — H1 no-pack U4 fence and recording supersession

RED evidence was the frozen no-pack proof itself: the embedded N4 recording proposed three
`tax_subsidy` interventions and carried first-vertical outcome/constraint vocabulary even though
the compiled DesignProblem declared only demand-reduction, emission-reduction, and renter-equity
instruments. A focused N4-port RED also proved the Scientist owner was called when the resolved
cycle context was absent (`scientist_generation_reached_without_owner_context`, exit 1).

The production cycle port now emits `cycle_substrate_context_unavailable` before entering the
fixed Scientist formalizer. The existing grammar fallback then derives its entire candidate
denominator from the compiled DesignProblem. The capstone replay path no longer bypasses this port:
it verifies every legacy raw response/hash as superseded history, replaces both the contaminated
N4 projection and compiled run with a typed no-context recording/current recursive run, and stores
that normalized recording. Context-present N4 replay is unchanged.

Focused evidence:

```text
N4 no-context RED: exit 1, Scientist owner reached
N4 no-context + existing grammar fallback probes after repair: 2 passed (37.7 s)
validator no-context capture/legacy-hash/normalized-writer probes: 3 passed (12.8 s)
real embedded unseen replay: exit 0 (~54.6 s)
  generation_channel=grammar_fallback
  proposed_lever_ids=[demand_reduction_instrument,
    emission_reduction_instrument,equity_protection_instrument]
  normalized N4 schema=policyos.layer3.gy.n10.no_context_generation_recording.v1
  responses/owner_result_projection absent
```

The honest no-pack replay now stops on the grounding-coverage acquisition route rather than the
previous L1-data-gap class: without an owner WMR, entering the later value-data owner would itself
be fabricated authority. This still leaves the frozen minimum of two structurally distinct
degradation classes once evidence classification is repaired; no terminal label is transplanted.
