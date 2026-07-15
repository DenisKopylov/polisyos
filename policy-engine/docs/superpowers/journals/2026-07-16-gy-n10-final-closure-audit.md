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

## Pending audit items

Historical-receipt boundaries, shared N7/N6 surfaces, the complete Task-13–15 test-diff sweep,
generated-artifact registration, and fresh-state reproducibility remain under read-only audit.
No owner repair begins until those findings are classified here.
