# GY-N10 Final Closure Audit Journal

## Status

`GO-CONFIRMED`

The provisional GO declared at `36942a1a8` was withdrawn for this independent audit. Every blocker
and must-fix finding was repaired owner-first, and the complete A--I denominator was recomputed at
the audited capstone commit `6fcbd2c11b817745d266a73be247d7d59ebad04c`. Evidence in this
journal comes from source inspection, direct frozen-payload probes, and recomputation; the earlier
stage journals are context only. Read-only reconnaissance ran in parallel. Every validator,
source flip, writer, and repair remained serial under the repository runtime. No merge to `main`
was performed.

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

### I1 owner repair checkpoint

`LegalKnowledgeStore` now separates its physical read path from one optional canonical evidence
path and routes every provision, threshold, obligation, temporal-subject, and amendment DuckDB ref
through the same helper. The standalone API keeps its existing physical-path default; the two
repository-bound L6 owners explicitly provide the repo-relative canonical path. No row, threshold,
relation, or grounding gate changed.

```text
RED before repair:
  test_legal_store_evidence_refs_ignore_physical_checkout_path
  TypeError: canonical_db_ref_path unsupported; exit 1
focused Lex owner file: 4 passed; exit 0; 2.28 s
real L6 law resolution/behavior probes: 3 passed; exit 0; 40.72 s
two-root full CredalReference proof: exit 0; 413.68 s
  reference_hashes=[sha256:706f49e7...90b74, sha256:706f49e7...90b74]
  reference_epochs=[kref:706f49e73924a725, kref:706f49e73924a725]
  L6 versions=[sha256:3f167b68...da81b, sha256:3f167b68...da81b]
source flip lex_reference_mount_path_independence_removed:
  RED; probe exit 1; signal observed; exact source restoration
Ruff over owner/callers/validator/tests: All checks passed
```

The canonical repo-relative identity intentionally changes the prior absolute-path-derived L6 and
CG certificate hashes. The canonical provenance ladder and capstone remain pending a single writer
rebaseline; accepting the warmed historical hashes would preserve the defect.

### I1 N4 provenance rebaseline

The historical N4 frozen receipt remained valid under `--check`, while the live rederive correctly
reported only certificate-bearing drift from the canonicalized L6 owner identity:

```text
check_layer3_gy_design_generation_contract.py --rederive-audit
exit 1; wall_time_seconds=1329.57
issue=frozen_payoff_live_receipt_drift
recorded=sha256:f40decc86a4212389b4bf92a5eb656028065c61f1006e4a1d1091a26ececa36b
computed=sha256:cfb821d480fe6c2e4f5318d6a789839f43ce4b36dc78537b7f929e993120fd63
changed keys:
  frozen_payoff_receipt
  generation_results
  grounding_payoff
  positive_gate
  synthetic_cg3_handoff_probe
```

The canonical writer then replayed the current owners twice. Both writes produced identical bytes;
the diff is confined to relation certificates, tickets, atom identities, and enclosing content
hashes. Candidate dispositions, generator paths, grounding states, and gate outcomes are unchanged.

```text
first --write:  exit 0; wall_time_seconds=1536.67
second --write: exit 0; wall_time_seconds=1384.97
artifact SHA-256 after both writes:
  665cdea7b0f83c1b6c0630e1e9ce94f38a9709b04482960017bd01d8d557a2fe
frozen --check: exit 0; wall_time_seconds=58.08
```

This rebaseline is the required downstream consequence of fixing evidence identity; it does not
change any acceptance, binding, or promotion authority.

### I1 Fork-B census provenance rebaseline

The next canonical dependency failed closed on the changed N4 receipt before inspecting relation
outcomes:

```text
check_layer3_gy_n10_cg1_l2_relation_census.py --check
exit 1; design_generation_artifact_ref_drift
```

The full CG1/L2 denominator was then recomputed twice: first through the audit lane and again through
the canonical standalone owner that persists the writer input. Both runs produced exactly the same
content result and the same Fork-B conclusion; only the N4 evidence reference changed.

```text
audit --rederive-audit: exit 1 (expected drift); wall_time_seconds=4104.242354
canonical standalone rederive: exit 0; wall_time_seconds=2484.361342
raw content hash, both runs:
  sha256:415e73219df496e86f9b199885a7458bf9ea9818ab2d989e82f9c6c992e16247
denominator/results, both runs:
  atom_x_numeric_edge_pairs_evaluated=13092
  SAT:false-analog=1076
  UNKNOWN:unknown=12016
  fork_a_evidence_candidate_rows=0
```

The compact writer remained byte-stable and the frozen checker accepted the new receipt:

```text
first --write:  exit 0; 1.795683 s
second --write: exit 0; 1.679039 s
compact content hash:
  sha256:f511626547c17ff010b1ee26d9157c753a6f13fe8be18f96c17ee9f1ca31e605
artifact SHA-256 after both writes:
  1c004559fe41cc84296ebb05edcfd4f5f95ade9542b2992aa52543ccb0c3bca4
--check: exit 0; 0.869115 s
```

The 1,076 false-analog vetoes remain the firewall's honest result; no positive relation was invented
to avoid the provenance ripple.

### I1 N8 value-gate provenance rebaseline

N8 first refused the superseded Fork-B constants with
`fork_b_census_content_hash_drift`. The two verifier constants were repointed only to the two
independently recomputed Fork-B hashes above. Live rederive then reported drift exclusively in
content-bound receipt sections:

```text
--rederive-audit: exit 1; wall_time_ms=59282.964
issues:
  fork_b_census_receipt_drift
  fork_b_census_receipt
  production_refusal
  acquisition_routing
  transport_component_proofs
unchanged decisive semantics:
  catalog_method_count=390
  value_capable_method_count=55
  native_contract_families=6
  education selected=bayesian.gp.gp_regression@1.0.0
  education blocker=method_estimand_binding_mismatch
  production blocker=acquire_data:value_panel_data_missing
```

The first source-flip attempt stopped before mutating because one focused test duplicated the old
content-derived candidate id as a string. The RED was
`candidate_b5d5d03eee11c6a6 != candidate_ea26e1ad2b9926a5`. The assertion now compares the cycle
candidate with the candidate selected by the canonical frozen N4 owner lane. It still proves exact
identity continuity, while removing the second non-owner identity source. Classification:
**stronger / stale literal replaced by owner-bound expectation**.

```text
focused owner-bound N8 route test: 1 passed; exit 0; 46.79 s
```

The canonical writer remained byte-stable and the complete mutation denominator passed against the
new receipt:

```text
first --write:  exit 0; ~61.04 s
second --write: exit 0; ~61.93 s
artifact SHA-256 after both writes:
  b941c0b947a6c3e0c269c0974f76cb6c169e7e72607777b95ef87cefa0f21b69
--check: exit 0; ~45.29 s
--source-flip-mutations: exit 0; ~762.57 s
  every mutation RED
  every touched owner/verifier restored to its suite-base SHA-256
Ruff (validator + focused test): All checks passed
```

No N9 consumer or promotion receipt shape was changed.

### I1 N10a historical N4 boundary and five-artifact rebaseline

After N8 moved, the frozen pack check first failed only on
`n8_transport_gap_receipt_drift`. The initial live rederive then exposed a real frozen-receipt lane
defect instead of being absorbed by the writer:

```text
--rederive-audit: exit 1; 6.257 s
education_n4_owner_capture_invalid:
  n4_owner_capture_input_binding_mismatch
  n4_owner_lever_context_binding_mismatch
```

The frozen capture still validated exactly against its frozen context. Against current owners, the
only input-binding deltas were `design_problem_ref` and
`cycle_substrate_context_content_hash`; the old and current DesignProblems differed solely in
`nl_provenance.source_context.census_content_hash`. No world, registry, pack, substrate-input, WMR,
policy field, or raw response changed.

The canonical live-bundle lane now applies the frozen-receipt doctrine narrowly:

- the complete old capture must validate against its historical problem/context;
- current and historical DesignProblems must match after removing only the typed census checksum;
- the current issue set must be exactly the two issues above;
- the changed binding fields must be exactly the two fields above;
- every raw response hash/alias, journal row, effective config, call role/model/status, and call
  denominator remains exact;
- old and current prompt hashes are both preserved in a content-hashed historical replay receipt.

The first implementation attempt correctly went RED because four current prompt hashes differ from
their original live-journal hashes. The repair does not relabel those calls: it preserves the live
journal rows, records the current replay prompt rows separately, and binds both to the same five raw
response hashes plus the full provenance-stripped problem projection. Ordinary live captures still
require byte-equal journal/current prompt rows.

```text
historical replay + non-identity drift + raw tamper witnesses:
  3 passed; exit 0; ~193.0 s
rehashed non-identity projection drift:
  fatal n4_owner_status_not_generated
raw bytes changed + outer capture rehashed:
  fatal n4_owner_capture_raw_response_hash_mismatch
whole-bundle --rederive-audit after repair:
  exit 1; wall_time_seconds=182.929801
  drift artifacts=census,pack,smoke_problem,cycle_trace,gaps
```

The five canonical outputs are byte-stable across two successful writers:

```text
first --write:  exit 0; wall_time_seconds=183.660994
second --write: exit 0; wall_time_seconds=183.795551
file SHA-256 after both writes:
  census       82ae8c00ca45ab910d5f4547f8965dd142768f06aeca5e44fd2d7096e67fa347
  pack         a710bd4bc44fe6f665913b61890b0a5376f3dd120dbf4f8262d9873c68bc1f30
  smoke        46e9b2dc0813bfa69ce43fef5ebf7bb8ea823b73bc2c301511bec8b3d4cc8911
  cycle trace  3a2a4563e02debccffaa2f4dea8f63fea571a8d409d2c6f67718c01f134201a3
  gaps         eed7d5d9cfa91e11b10d595ac11a44cd48c3f5269402952ab1d4b679d0e7843b
--check: exit 0; wall_time_seconds=0.646577
```

The corruption lane initially exited 2 because `terminal_kind="crash"` was schema-invalid and
therefore never exercised `smoke_terminal_not_honest`. The adversary now keeps the typed N6 run
coherent and changes only the outer execution status to `crashed`. That direct property witness is
RED-capable:

```text
--corrupt-field-drift-check: expected exit 1; 8.462 s
  smoke_terminal_not_honest observed
  no corrupt_field_drift_not_detected
focused crash/honesty witness: 1 passed; exit 0; ~193.1 s
Ruff (checker + focused tests): All checks passed
```

The complete focused module then found one pre-existing form-based seam-hash test: its hardcoded
replacement string no longer existed, so the purported seam mutation changed zero bytes. The probe
now resolves the witnessed function by AST, appends an in-function no-op, and proves that unrelated
out-of-function text remains hash-neutral while the real segment changes.

```text
AST-local seam witness: 1 passed; exit 0; 8.653 s
tests/unit/runtime/quality/test_second_domain_pack.py:
  62 passed; exit 0; ~230.0 s
```

The rebaselined N10a education trace remains `acquisition_required`; no provider call was made and
no unbound lever was promoted.

### I1 composition provenance rebaseline

The live composition check then reported only
`layer3_gy_composition_certificate_drift`, caused by the rebaselined N10a smoke DesignProblem. Its
canonical writer recomputed the recursive receipt twice with identical bytes:

```text
first --write:  exit 0; ~30.00 s
second --write: exit 0; 29.154 s
artifact SHA-256 after both writes:
  003a5f0fa8851629832dc5b38d7387bd3b8085a7c0544f9f96f819ef513582da
final --check: exit 0; 29.338 s
```

No coupling observation, recursion result, or composition authority changed.

### I1 aggregate-ladder convergence: N8 post-N10a provenance carry

The first aggregate pass on committed composition base `0dd6f1108` was green for N4 and the
Fork-B census, then N8 correctly reported drift:

```text
N4 --check: exit 0; 58.98 s
Fork-B --check: exit 0; 1.511 s
  content_hash=sha256:f511626547c17ff010b1ee26d9157c753a6f13fe8be18f96c17ee9f1ca31e605
  relation_rows=13092; false-analog=1076; unknown=12016
N8 --check: exit 1; ~143 s; artifact_drift
N8 --rederive-audit: exit 1; wall_time_ms=113949.662
  live_rederive_section_drift: transport_component_proofs
```

The frozen/live field comparison localized the movement to the education proof's
`design_problem_ref`, `cycle_substrate_context_content_hash`, `context_binding_hash`, and derived
`proof_content_hash`. The candidate identity and content, lever binding, WMR, selection diagram,
two transport covariates and values, transport receipt/status, first-vertical refusal, and unseen
transport proof were byte-identical. Cause: the N8 artifact was frozen before the final N10a
historical-problem rebind, so its education component still named the pre-rebind N10a smoke
problem. This is provenance-only convergence, not a semantic rebaseline. The canonical writer is
permitted only if the artifact diff preserves that exact classification.

The canonical N8 diff met that condition exactly: the four classified education hashes and the
enclosing `contract_content_hash` were the only changed fields. Two writes were byte-identical at
file SHA-256
`755d67837fd74b7e7fb35aff6ae3b355f5b1fafd9381b8964d1a02a18ae937cb`;
the final live `--check` passed.

```text
first --write:  exit 0; ~109.92 s
second --write: exit 0; ~115.15 s
--check:         exit 0; ~114.12 s
```

On committed N8 base `bae0dbb1c`, N10a then reported the single expected downstream binding:

```text
N10a --check: exit 1; wall_time_seconds=1.0703
  n8_transport_gap_receipt_drift
```

No smoke-problem, pack, registry, lever, WMR, or cycle-trace issue was reported. The N10a writer is
therefore restricted to the gap receipt's N8 provenance and its enclosing hashes.

The writer diff preserved that boundary. The census and smoke DesignProblem did not move. The gap
receipt records the new N8 contract/proof hashes; the trace and pack carry the resulting gap/trace
hashes. The full-rewrite-only `generated_at` and `runtime_metrics` values changed but remain
excluded operational fields, and the second writer preserved their bytes exactly.

```text
first --write:  exit 0; wall_time_seconds=386.019850
second --write: exit 0; wall_time_seconds=387.509877
--check:         exit 0; wall_time_seconds=1.047132
stable file SHA-256:
  census       82ae8c00ca45ab910d5f4547f8965dd142768f06aeca5e44fd2d7096e67fa347
  pack         dbec9d3513e7f7fd53724a36c8a747e07233affc03cc371ff6c26a1777c3ea28
  smoke        46e9b2dc0813bfa69ce43fef5ebf7bb8ea823b73bc2c301511bec8b3d4cc8911
  cycle trace  eae69c1f4d04c608b8f566d3f2a4dc3e983e29352dc29e02aa49abff281c9a3e
  gaps         3282aebafd21747863bc566c3ca742d6cfa30d94ee33877630c97adf697ab930
```

The complete owner-local ladder was then green, but its dedicated cross-owner witness exposed one
stale assertion:

```text
N4 --check:         exit 0; 55.74 s
Fork-B --check:     exit 0; 1.469 s
N8 --check:         exit 0; ~91.76 s
N10a --check:       exit 0; wall_time_seconds=1.007486
composition --check: exit 0; ~44.38 s
provenance-stability focused witness: exit 1; education_prompt_hash_binding_drift
```

The aggregate witness still required historical journal prompt hashes to equal today's replay
prompts. That expectation would erase the already-verified historical boundary. The repaired
witness retains exact equality for live captures; for a historical capture it accepts journal/current
inequality only when the N10a owner recomputes a clean content-hashed replay receipt and the
receipt's historical/replay sequences exactly match the journal and owner projection respectively.
Response prompt hashes must always equal the current owner projection. The permanent raw-byte
tamper and non-identity-drift negatives remain on the N10a owner.

```text
provenance-stability focused witness after reconciliation: 1 passed; exit 0; ~94.53 s
Ruff (capstone validator + focused test): All checks passed
```

The frozen capstone remained internally coherent before rewriting:

```text
capstone --check: exit 0; wall_time_seconds=103.778853
superseded contract_content_hash:
  sha256:38b61d274df4ff48bb6cebaf0c40907ebd2754d2477c88cef5db2cf812f95845
superseded file SHA-256:
  97e5ea0d39ecfb7f429b357998692861ccca13a460f40ecbc8d77ba046f65a0e
```

The canonical writer now runs against the stable committed owner graph. Its first diff is admitted
only if terminals, structural evidence classes, dispositions, denominators, and domain roles are
unchanged.

The first canonical write refused before touching the artifact:

```text
capstone --write: exit 1; wall_time_seconds=364.102762
  proof_n4_owner_projection_replay_drift
```

A single read-only replay localized the first-vertical delta to CG1/CG2/CG3/CG5 certificate
IDs/content hashes and their bridge-ticket IDs/content hashes across the same three grounding
dispositions. Candidate identities, disposition kinds/reasons, counts, prompts, raw responses,
world binding, and every non-provenance field were unchanged. This is the direct downstream effect
of the audited Lex evidence-reference canonicalization. The repair is a narrow, named historical
projection-rebind receipt: it verifies the original recording hash and raw bytes, permits exactly
those certificate/ticket paths once, retains the complete historical projection, binds the live
projection and exact changed-path set, and rejects any non-identity field movement.

```text
historical N4 projection rebind focused battery: 2 passed; exit 0; ~12.17 s
  certificate/ticket-only delta: accepted through content-bound receipt
  raw-response tamper: RED
  disposition change: RED
Ruff (capstone validator + focused test): All checks passed
```

The committed-base provenance witness remained green (`1 passed`, ~90.68 s). The retried writer
then completed:

```text
capstone first --write: exit 0; wall_time_seconds=1265.261875
contract_content_hash:
  sha256:fb1194882178801f0d08835e7c6683433ace055bcbd3ea44e6ecd6ba99a742a6
file SHA-256:
  29bb35048575ccc4fd61124875569d90c4cf843f5dac4f42b6f1ad768b22e9c6
```

The old/new semantic audit observed 752 status/kind/reason/method/candidate leaves on each side and
found exact equality. All three role names, terminal distributions, terminal kinds, structural
evidence kinds, decision grades, candidate IDs, proposal IDs, selected-candidate refs, N4
dispositions, depth semantics, non-panel semantics, capability reality, and the universality
expectation were unchanged. The first-vertical and education domain-run hashes moved only because
their certificate/ticket provenance and content-bound historical receipts moved; unseen semantic
bytes remained unchanged. Excluded operational clocks were rewritten once with the new contract
identity and must be carried byte-for-byte by the second writer.

The second writer preserved every byte:

```text
capstone second --write: exit 0; wall_time_seconds=1354.788064
contract_content_hash:
  sha256:fb1194882178801f0d08835e7c6683433ace055bcbd3ea44e6ecd6ba99a742a6
file SHA-256:
  29bb35048575ccc4fd61124875569d90c4cf843f5dac4f42b6f1ad768b22e9c6
byte-stable: true
```

The complete final-byte gate battery then passed against those exact bytes:

```text
capstone --check: exit 0; validator_wall_time_seconds=111.365562
capstone --corrupt-field-drift-check: expected exit 1; wall_time_seconds=77.320249
capstone --rederive-audit: exit 0; wall_time_seconds=1468.433073; issues=[]
```

The static corrupt lane rejected all 11 decisive nested mutations:
`stale_contract_hash`, `evidence_kind_relabel`, `evidence_witness_forgery`,
`planner_report_semantic_drift`, `forged_route_hash`, `compiler_response_bytes`,
`n4_response_bytes`, `compiled_recursive_bytes`, `compiled_schema_rehashed`,
`terminal_distribution_projection`, and `fabricated_terminal`.

The source-flip lane was rerun with a retained transcript after the desktop session dropped the
first oversized terminal payload. Both executions restored the same source base; the retained run
is the auditable denominator:

```text
capstone --source-flip-mutations: exit 0; wall_time_seconds=527.351959
status=pass; issues=[]
local mutations: 17/17 RED with signal_observed=true and source restoration receipts
delegated composition mutations: 5/5 RED with signal_observed=true and source restoration receipts
non-RED results: 0
missing restoration receipts: 0
```

The 17 local mutation IDs were `domain_pinned_in_engine`,
`cycle_driven_by_pinned_fixture`, `unseen_domain_honesty_removed`,
`no_context_generation_authority_fence_removed`, `acquisition_route_verification_removed`,
`canonical_route_recompute_removed`, `degradation_class_relabel_accepted`,
`fabricated_terminal_accepted`, `degradation_class_denominator_weakened`,
`education_refusal_precedence_removed`, `live_advisor_denominator_verification_removed`,
`value_owner_candidate_binding_removed`, `historical_receipt_verification_removed`,
`operational_clock_preservation_removed`, `unbound_estimand_authority_fence_removed`,
`n7_design_problem_authority_removed`, and `lex_reference_mount_path_independence_removed`.
The five delegated IDs were `gy_g_fixture_caller_reintroduced`,
`empty_coupling_assumed_independent`, `n5_joint_simulation_owner_bypassed`,
`unsupported_n5_relabelled_joint_simulated`, and `gy_g_production_default_route_removed`.
Every probe exited 1 on its expected RED signal. Post-harness `git status --short` showed no source
movement: only this journal and the canonical capstone artifact remained modified.

## Final independent verdict — A--I

`GO-CONFIRMED`

The capstone artifact was committed as the isolated checkpoint `6fcbd2c11b817745d266a73be247d7d59ebad04c`
before the decisive cold-checkout replay. The final contract identity is:

```text
contract_content_hash:
  sha256:fb1194882178801f0d08835e7c6683433ace055bcbd3ea44e6ecd6ba99a742a6
file SHA-256:
  29bb35048575ccc4fd61124875569d90c4cf843f5dac4f42b6f1ad768b22e9c6
```

Hash lineage:

- provisional GO: `sha256:8d4b2f69f35d989206cc9304d6ccb76759800b386406654085a55fcb671cbb16`
  at `ce847b9f2`;
- pre-Lex audit rewrite: `sha256:38b61d274df4ff48bb6cebaf0c40907ebd2754d2477c88cef5db2cf812f95845`
  with file SHA `97e5ea0d39ecfb7f429b357998692861ccca13a460f40ecbc8d77ba046f65a0e`;
- final path-independent capstone: `sha256:fb119488...99a742a6` with file SHA
  `29bb3504...b22e9c6`.

The two canonical writers took `1265.261875 s` and `1354.788064 s` and produced identical bytes.
The old/new semantic comparison observed 752 status/kind/reason/method/candidate leaves on each
side with exact equality. Only content-bound provenance moved.

### Final domain evidence

| Domain | Terminal | Structural evidence | Grade | Domain-run content hash |
| --- | --- | --- | --- | --- |
| first vertical | `acquisition_required` | `owner_acquisition_route` | `blocked` | `sha256:2c43f86b73110915f3cc5462d0fbe3a1308faf9d7837fe121cd3bdbe6d559b0d` |
| education | `acquisition_required` | `estimand_binding_refusal` | `blocked` | `sha256:68152e96cb0590f9d276b093b17c3f62e763361a1f221bba1ed12a97f5adc85d` |
| unseen | `acquisition_required` | `owner_acquisition_route` | `blocked` | `sha256:b4226d20e9659abc389d56d2090509809dd89cc76ecb555c33aeb9cea40af1de` |

Education's deeper value evidence binds a live 55-method capability denominator, selected
`bayesian.gp.gp_regression@1.0.0`, advisor receipt
`sha256:79fe8e60f1970f08fee2e4e060c631a091e06b0cd658a2220e790fe862325a9a`,
selection-context hash
`sha256:54a3a19ad298575a7244701c00ec6ed3ceb8c675c7e4f71c2909c83e94a1c7a2`,
and owner-data-profile hash
`sha256:eb5faeaffbb5507ba9ceed7c69ed3a892d5c106eb6a6336ed62c4d68f1db3566`.
The real advisor route therefore reaches `method_estimand_binding_mismatch`; the verified earlier
grounding route cannot mask it. Education correctly does not promote.

### A--I recomputation matrix

| Item | Verdict | Recomputed evidence |
| --- | --- | --- |
| A — structural universality | PASS | Evidence classes derive from validated typed owner witnesses. Relabel, fabricated-terminal, forged-route, canonical-route, and weakened-denominator mutations all went RED. Two superficial strings over one witness type cannot increase the structural class count. |
| B — education precedence | PASS | The 55-method advisor receipt and owner-data profile recompute; the selected Bayesian GP is advisor-ranked, not code-pinned. The early-route-versus-downstream-refusal negative and `education_refusal_precedence_removed` mutation went RED. |
| C — volatile carry | PASS | `polisyos.pdc` is the single owner of the excluded-field vocabulary. A semantic nested mutation takes the full-rewrite branch and changes the hash; inversion of the equal-hash condition went RED. |
| D — corrupt drift | PASS | All 11 decisive nested corruptions went RED; both warm and cold commands exited 1 with an empty harness-issue list. |
| E — historical boundary | PASS | Only the named, single nested content-hash projection delta is eligible. Raw compiler/N4 bytes and non-hash validation drift remain fatal; the permanent tamper negatives and historical-receipt source flip are RED-capable. |
| F — shared surfaces | PASS | The authority-caller census found no dict-shaped pseudo-`DesignProblem` reaching Foundry; the two surviving callers pass typed owner objects. Operational N6/N7 clocks are hash-neutral while semantic cost remains hash-decisive. |
| G — assertion sweep | PASS | Seven replacement groups were stronger or neutral; zero weakened assertions. The N4 closure assertion now requires three `novel_cg3` dispositions and zero bind-authorized candidates/rankings. |
| H — U1--U4 | PASS | No domain/role/model branch controls generation, context resolution, recursion, value projection, advisor selection, or capstone authority. The unseen recording carries no first-vertical or education vocabulary. L6 intake is registry/data-derived; proof roles are expectations only. |
| I — fresh state and coherence | PASS | Detached commit `6fcbd2c11` passed frozen check, behavioral rederive, wrong-checkout fences, and corrupt drift. Final owner checks, censuses, registration, guardrails, Ruff, and merge-tree all passed. |

### Assertion-change classification

| Commit | Surface | Classification | Evidence |
| --- | --- | --- | --- |
| `739f15b82` | depth-N proof lifecycle | neutral/stronger | Replaces `proof_runs_pending` with exactly three completed proof roles and implemented capability labels. |
| `d575f86f9` | compiler characterization | stronger | Adds seed preservation and expands the frozen denominator to 21 with repeatability controls. |
| `d1093bec3` | compiler token ceiling | neutral | Rebaselines observed completion/headroom while preserving the same derived 8192 ceiling. |
| `6bbb9b482` | N7 grounding route | stronger | Replaces a dead-end label with a verified acquisition requirement and canonical planner report. |
| `13a1103db` | terminal evidence | stronger/neutral | Requires an exact acquisition terminal and planner-report hash; changes the evidence label only to the recomputed owner-route class. |
| `f34b87ee0` | wrong-checkout and frozen lifecycle | stronger/neutral | Requires byte preservation of the real artifact; updates the CLI expectation after artifact admission. |
| `6ff1e7986` | N4 closure | strictly stronger | Requires exactly three `novel_cg3` dispositions, real owner calls, and zero candidates, rankings, candidate IDs, or atom authority. |

No other Task-13--15 assertion was weakened.

### Decisive cold checkout

The detached checkout was created at
`/Users/deniskopylov/polisyos/.worktrees/gy-n10-audit-final-clean`, HEAD
`6fcbd2c11b817745d266a73be247d7d59ebad04c`. Before validation it had no `.tmp` and only local
links for `.venv`, `production_data`, and `.env`. The validator then created its own isolated
temporary world; no warmed-checkout source path appeared.

```text
capstone --check: exit 0; wall_time_seconds=71.849248
capstone --rederive-audit: exit 0; issues=[]; wall_time_seconds=880.937063
three wrong-checkout focused probes: 3 passed; exit 0; tool wall=11.073074 s
capstone --corrupt-field-drift-check: expected exit 1;
  all 11 cases red; harness issues=[]; wall_time_seconds=47.412417
artifact SHA after all cold probes:
  29bb35048575ccc4fd61124875569d90c4cf843f5dac4f42b6f1ad768b22e9c6
git diff --exit-code: exit 0
```

This behavioral replay is the decisive closure of the cold-environment Lex defect: it derives from
the embedded proof recordings in a different checkout and preserves the same structural terminals.

### Final committed-base coherence

| Gate | Result |
| --- | --- |
| N4 design generation | PASS; exit 0; issues=[] |
| Fork-B CG1/L2 census | PASS; 13,092 rows = 1,076 false-analog vetoes + 12,016 unknowns; zero usable relations |
| N8 value gate | PASS; exit 0 |
| N10a second-domain pack | PASS; validator wall `0.651772 s` |
| composition | PASS; validator wall `28.187470 s` |
| N5 joint simulation | PASS; validator wall `2.294039 s` |
| N6 generation cycle | PASS; validator wall `0.003976 s` |
| N7 acquisition | PASS; validator wall `0.251882 s`; `network_calls=0` |
| N9 promotion | PASS; validator wall `0.003957 s` |
| canonical disposition ledger | PASS; the already-known CVXPY/OR-Tools version warnings remain non-authoritative noise |
| engine census | PASS; 69 rows; 0 violations |
| validator import/help census | PASS; 37/37; 0 failures; `51.848 s` |
| current capstone registration | PASS; exactly one `generated_committed` family with the canonical output and checker workflow |
| architecture guardrails | PASS; exit 0 |
| Ruff over every Python path changed from `main` | PASS; `All checks passed!` |
| `git merge-tree --write-tree --name-only --messages main HEAD` | PASS; exit 0; no conflict messages |

One extra broad probe,
`check_layer3_gy_generated_public_lifecycle_audit.py --check --json`, returned its frozen Task-0
inventory drift (352 violations spanning hundreds of pre-existing output-root files and all post-N0
validators). It is classified **stale expectation / non-applicable to the requested current-family
registration check**. It was neither weakened nor regenerated. The capstone's exact current family,
output, lifecycle, check command, and workflow were instead parsed directly from
`architecture/generated_artifacts.toml`, and architecture guardrails passed.

### Audit delta from the provisional GO

The independent audit added or strengthened: the cold-checkout contamination fence; structural
owner-witness classification; nested corrupt-field depth; one canonical volatile-field source;
advisor authority binding at both sibling consumers; repository-relative Lex evidence addressing;
the narrow historical prompt-rebind receipt; the narrow historical N4 certificate/ticket rebind;
and the path-independence source flip. The historical-replay exception remains deliberately narrow:
verified byte-identical raw responses, a provenance-only problem delta, the exact eligible issue
set, one rebind, and permanent raw-tamper/non-identity-drift negatives. It is not permission to
reuse responses under changed prompts.

### Carried typed debt

- `owner_registration_derivation_missing` — `artifact_missing`
- `journal_raw_evidence_persistence_missing` — `artifact_missing`

Both remain explicit N7 infrastructure residuals. Neither is hidden, treated as acquired, or
counted as a successful value/promotion result.

## Verdict

**GO-CONFIRMED** — GY-N10 proves that the existing cycle is domain-generic and degrades honestly.
Education correctly terminates without promotion. No merge to `main` was performed.
