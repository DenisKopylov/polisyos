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

## Repair checkpoint — C1 canonical volatile-field ownership

RED: setting `content_hash_excluded_fields=[]`, recomputing the outer contract hash, and validating
the frozen payload passed. The declaration was decorative.

`polisyos.pdc` now exports one immutable GY excluded-field vocabulary and its predicate. Recursive
hash stripping, the capstone declaration, contract hashing, volatile mutation, and writer carry all
consume that owner. The writer source mutation now inverts the equal-hash comparison itself. A
separate semantic-delta probe proves changed semantics take the full-rewrite branch and retain the
new clocks.

```text
declaration RED before repair: exit 1, expected issue absent
declaration/equal-hash/full-rewrite/nested-clock probes after repair:
  4 passed (26.910 s)
```

The frozen capstone intentionally remains stale until the structural evidence and corrupt-drift
repairs are complete; one writer rebaseline will update its canonical declaration and hashes.

## Repair checkpoint — A/B/D/H structural recomputation and static mutation denominator

The first structural rewrite exposed two further real P31/P32 gaps under adversarial review before
the artifact was frozen:

- a content-valid advisor observation could be transplanted to another selected candidate because
  the capstone witness did not bind `ValuePortObservation.candidate_id`;
- a real grounding planner route could classify a run even if the value observation claimed
  positive authority, and education's higher-precedence refusal did not independently recompute
  the earlier grounding route.

The single evidence projector now validates and content-binds the complete typed grounding and
value observations, selected candidate, DesignProblem ref, value-data profile, live advisor
denominator, selection-context hash, and the exact acquisition gap. Every acquisition terminal is
regenerated through `plan_requirement_gap_acquisition` from that gap. Education keeps the deeper
advisor refusal as its class only after the earlier grounding route also verifies; L1 and grounding
routes share the same canonical route verifier. Distinctness is counted from the resulting witness
types, not labels or report strings.

The no-pack vocabulary denominator now derives from both resolved owner contexts: candidate levers,
transport covariates/contexts, WMR policy slots, and intervention knob/LEX vocabulary, plus semantic
N4 proposal fields. Focused negatives cover `tax_relief_rate`, the education-only
`school_quality`, and the first-world WMR-only `household_cells.disposable_income`.

The static proof-recording verifier now validates the real embedded
`CompiledRecursiveGenerationCycleRun` objects. Only the already-audited single historical recursive
hash drift may enter the historical envelope verifier; any other schema error is fatal. In-memory
real-recording probes that previously survived now fail for both a nested cycle terminal mutation
and a fully rehashed extra compiled authority field.

The corrupt lane is fail-closed on a missing or invalid base and expands to eleven frozen-only
cases: top-level stale hash, evidence relabel, witness forgery, planner semantic drift, route hash,
compiler bytes, N4 bytes, recursive compiled bytes, fully rehashed compiled schema drift, terminal
distribution projection, and fabricated terminal. A baseline is validated before mutations so a
pre-existing RED cannot masquerade as mutation evidence.

Decisive live replay under repository runtime:

```text
education cached owner replay: exit 0 (657.616 s)
terminal=acquisition_required
evidence_kind=estimand_binding_refusal
selected_candidate=gy_n4.active_learning_pedagogy_reform
selected_method=bayesian.gp.gp_regression@1.0.0
advisor_receipt=sha256:79fe8e60f1970f08fee2e4e060c631a091e06b0cd658a2220e790fe862325a9a
selection_context=sha256:54a3a19ad298575a7244701c00ec6ed3ceb8c675c7e4f71c2909c83e94a1c7a2
value_profile=sha256:eb5faeaffbb5507ba9ceed7c69ed3a892d5c106eb6a6336ed62c4d68f1db3566
grounding_route=sha256:ac388789680a2c15b3ffa489061043533acb3a51d197f79249e362d8a9a0dc9e
```

Focused verification before the artifact rebaseline:

```text
historical envelope + no-context fence/recording + live education unbound owner:
  6 passed, exit 0
N10 local source-flip denominator declaration: 1 passed, exit 0
all 16 local source guards: exact occurrence count 1
.venv/bin/ruff check validator + focused tests: exit 0
```

The behavioral source flips are declared now but intentionally execute only after the new capstone
is written green; otherwise a stale artifact could create false REDs. The current two-class truth is
also explicit: first-vertical and unseen both carry independently recomputed grounding-coverage
routes, while education carries the deeper estimand-binding refusal. The historical unseen L1 gap
was produced only after contaminated fixed-vertical generation and is not retained as a third class.

## Provenance ripple checkpoint

The canonical dependency ladder was replayed after all owner/source fixes:

```text
N4 --check: exit 0
Fork-B CG1/L2 census --check: exit 0
  rows=13,092; false-analog=1,076; unknown=12,016
N8 --check: exit 0
N10a pack --check: exit 0
composition --check: exit 1, layer3_gy_composition_certificate_drift
```

Only composition moved. N4 bytes and both census hashes were unchanged, so the 56-minute census
rederive and the N8/N10a writers were correctly skipped. The composition writer regenerated the
live recursive receipt after the WorkspaceLoop authority repair; two measured writes produced the
same file SHA-256:

```text
before: c86810b84c5a8e85d1237972b8f2ae2f4d6b4324c4038a492ffe7a9766da64fe
after:  6d94790328eee38dbdae6c551ec71ef30edb9789f1467341d506d2eae0b1d06b
repeat: 6d94790328eee38dbdae6c551ec71ef30edb9789f1467341d506d2eae0b1d06b
writer exits: 0; wall times 47.835 s, 47.735 s, 47.783 s
```

## Capstone rebaseline checkpoint

After committed provenance stability passed, the canonical capstone writer replayed all three
embedded recordings through current owners and emitted only after the strengthened static and
semantic gates passed.

```text
first --write: exit 0; 1473.399346 s
second --write: exit 0; 1291.923042 s
contract_content_hash:
  sha256:38b61d274df4ff48bb6cebaf0c40907ebd2754d2477c88cef5db2cf812f95845
file SHA-256 after both writes:
  97e5ea0d39ecfb7f429b357998692861ccca13a460f40ecbc8d77ba046f65a0e
frozen --check: exit 0; 107.272672 s
```

Measured distributions:

```text
first_vertical: acquisition_required / owner_acquisition_route / blocked
education:      acquisition_required / estimand_binding_refusal / blocked
unseen:         acquisition_required / owner_acquisition_route / blocked
```

The unseen proof recording now contains the typed no-context N4 owner refusal, no model responses
or owner projection, and grammar-derived levers exactly equal to its compiled DesignProblem:
`demand_reduction_instrument`, `emission_reduction_instrument`, and
`equity_protection_instrument`. Static compiled/response verification reports no issue.

## Continued closure audit — F3 shaped advisor problem sibling

The final codebase-wide caller census found one surviving instance of the same P31/P32 class fixed
for Workspace Phase 2. `FoundryValuePort` starts with a validated `DesignProblem`, but
`_selector_problem_with_owner_context` projects it to an untyped mapping before the
authority-bearing `select_value_method_for_problem` call. The mapping is content-bound later by the
advisor receipt, so no observed receipt was forged, but shape is still standing in for typed problem
authority at the owner boundary. The direct caller denominator is exactly two: Workspace Phase 2
now passes its original typed object, while the generation-cycle value lane passes this mapping.

Classification: **must-fix / real sibling defect (P31, P32)**. The bounded fix preserves the
original `DesignProblem` and replaces only its runtime-only advisor context with the owner-derived
`ValueDataProfile` projection. A focused RED must observe a real `DesignProblem` plus the exact
profile hash at the Foundry boundary. This does not widen selection and must leave the advisor
selection-context hash unchanged.

The pre-fix committed capstone behavioral replay remained green and is retained as the base control:

```text
check_layer3_gy_depth_n_universality_contract.py --rederive-audit
exit 0; status=pass; issues=[]; wall_time_seconds=758.257067
```

Independent subagents were requested for the final F/G/H source census but the workspace reported
exhausted subagent credits. This continuation is therefore explicitly local/non-independent; the
evidence is recomputed from source and focused behavioral probes rather than accepted from prior
journal claims.

RED-first and bounded repair evidence:

```text
typed advisor projection probe before repair:
  exit 1; projected value was dict, not DesignProblem
typed advisor projection + Workspace sibling after repair:
  2 passed; exit 0; 10.941414 s
typed projection + real selection + cross-profile replay negatives:
  3 passed; exit 0; 33.177 s
.venv/bin/ruff check generation_cycle.py test_value_gate.py:
  exit 0; All checks passed
```

The owner projection now returns a `DesignProblem` and changes only its runtime-only advisor
context to the content-bound `ValueDataProfile` fields. No method family, domain, candidate, or
selection default was added. The final caller census has two authority-bearing advisor calls and
both now receive typed `DesignProblem` objects.

## Continued closure audit — P29 canonical-route mutation survived

The first full N10 mutation replay restored all source bytes but exited 1 after 408.729319 seconds:
15 local/delegated properties went RED, while `canonical_route_recompute_removed` survived. The
owner comparison is present; the negative did not isolate it. The test added a nonexistent
`requirement_gap_id` field to `AcquisitionActionRecord`, so `extra="forbid"` rejected the report
even when canonical regeneration was removed. That is trust in an incidental schema error, not
proof of the route-recompute property.

Classification: **must-fix / real P29 test defect**. The strengthened negative mutates the existing
typed `requirement_gap_ref`, recomputes the planner hash, and rebinds the stored witness and all
outer hashes. On the normal owner path the regenerated report must still reject the transplant; with
only the `report != expected_report` comparison removed, the mutation must become an otherwise
coherent payload and the focused probe must turn RED.

Repair evidence:

```text
strengthened schema-valid transplant against normal owner:
  1 passed; exit 0; 20.603541 s
canonical_route_recompute_removed isolated source flip:
  RED; exit 0 harness; probe exit 1; signal observed; 20.348491 s
  restored validator sha256=f39684559f90ce956c176d5bdaee869268a3c22c9d66e3316aade359fd789b7c
.venv/bin/ruff check test_depth_n_universality.py:
  exit 0; All checks passed
```

## Fresh-state finding — I1 absolute Lex store path in CG certificate identity

The required detached checkout began at `0c9cfb78c` with no `.tmp`, mounted only the repository
runtime and read-only owner data, and passed the frozen `--check` plus all three wrong-checkout
precedence/byte-preservation probes. Its first behavioral rederive then failed after 217.22 seconds
with `proof_n4_owner_projection_replay_drift`. The warmed audit worktree continued to pass the same
embedded recording, so the failure was not accepted as an artifact expectation or retried away.

A full-body differential over the identical first-vertical recording localized every changed
CG1 input to the Lex provision URI prefix. The read-only database rows and all dispositions were
identical, but `LegalKnowledgeStore` emitted its physical checkout path into owner evidence:

```text
cold: duckdb:///.../.worktrees/gy-n10-audit-clean/policy-engine/production_data/...#lex_provisions/...
warm: duckdb:///.../.worktrees/gy-n10/policy-engine/production_data/...#lex_provisions/...
reference_versions.L6:
  cold sha256:a68fa9da17bcb83f46bc21dc7e1361fb0d1dc19ad97bdf1dc74a3eda0270f09e
  warm sha256:f1813b5e4b5374c2393d49bdf39c2aab362e573a42f13d742b2db9da2237903c
```

That path leak changed the CG1 content hash and therefore every linked CG2, CG3, CG5, and ticket
identity despite identical owner knowledge. Classification: **blocker / real P30 content-addressing
defect**. The bounded owner-first repair is to separate the Lex store's physical read path from its
canonical repository-relative evidence reference. Repository-bound callers supply the canonical
relative DB ref; external/default callers retain their existing physical ref. Every DuckDB evidence
URI emitted by the store consumes that one reference owner. A RED must prove that two physical
checkouts over the same DB bytes produce identical provision/threshold refs and hence identical L6
reference content. Replay equality and every CG gate remain unchanged.
