# INT-R4 — Stage 3 Amendment Ledger

Amendment stage: `stage_3_amendment`  
Package head answered: `c3999897b5be2308513846935f1c4fb68157bcb3`  
Audit head answered: `ea2eac5575e5b8fb4a5462c068a37bb913076952`  
Amendment branch: `research/int-r4-ops-r5-amendment`  
Joint pair: `INT-R4` with `OPS-R5`  
Ledger ownership: this file owns `AUD-F01`, `AUD-F03`, `AUD-F04`, `AUD-F05`, `AUD-F07`,
`AUD-F09`, `AUD-F10`, `AUD-F12`, `AUD-F13`, and `AUD-F14`. The OPS-R5 ledger owns the other
eight findings. No finding is duplicated between ledgers.

This ledger is an append-only amendment record. Where it expressly supersedes a stage-1 statement,
the superseding rule below governs the amended package. It does not edit or reinterpret an audit
artifact, confer authority, register a type, appoint a person or institution, or lift the audit verdict.

## 1. Standing And Non-Effect

The standing vector remains:

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
audit_verdict: GO_WITH_REVISIONS
```

Stage 3 responds to findings. It does not create a capability or convert the audit's target verdict
into an observed `GO`.

## 2. `AUD-F01` — Absorbed OPS-R7 Discharge

Audit defect: `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:107`.  
Disposition: `accepted`.

A field that records a version or exposure history is not a causal-validity rule. The seven questions
identified by the audit are discharged below with an estimand, admission conditions, failure mode,
falsifier, and honest residue.

### 2.1 OPS-R7 closure matrix

| Absorbed question | Amended rule | Admission evidence and assumptions | Failure or falsifier | Unresolved residue |
|---|---|---|---|---|
| Repeated looks and stopping | Every confirmatory comparison names a prospective look schedule, information basis, stopping rule, and error-control method appropriate to the design. An unscheduled outcome-driven look cannot support a confirmatory update and is retained as exploratory evidence. Crossing a stopping boundary may change exposure or trial continuation, but does not by itself make the stopped effect-size estimate unbiased. | Immutable schedule or charter; look number and information fraction; multiplicity or always-valid error-control record; unchanged outcome, population, version and analysis definition. | A consumer reaches the same confirmatory result after deleting the schedule, changing the look after seeing outcomes, or treating an early stop as final effect-size calibration. | No universal stopping method transfers across domains. The design owner must select and justify the method before deployment. |
| Endogenous version assignment; sequential exchangeability and positivity | Causal comparison across versions is admitted only under prospective randomization, or under a declared longitudinal identification model in which sequential exchangeability, consistency and positivity are argued at every decision point using the full measured history that triggered adaptation. If a bad outcome itself changes the next version and the adaptation trigger is not fully controlled, version comparison is association-only. | Assignment mechanism; decision history `H_t`; version propensity or randomized probability; support/overlap diagnostics; complete adaptation-trigger and concurrent-intervention record; censoring model. | A version effect survives after removing the adaptation trigger, positivity evidence, or assignment record; or a deterministic high-risk route is represented as if all units could have received all versions. | Unmeasured adaptation triggers and structural non-positivity cannot be repaired by more rows from the same deployment. They remain `not_established` or require a new design. |
| Carryover and treatment history | The treatment object is the complete exposure sequence, not the current version label. Every estimand declares the relevant lag, washout, persistence and interaction assumptions. If prior versions can affect the current outcome and their effects cannot be separated, the admissible object is a sequence or dynamic-regime estimand, not a current-version effect. | Versioned exposure start/stop, dose/intensity, prior states, lagged outcomes, concurrent interventions, and a subject-matter carryover model or design-based washout. | Two units with the same current version but materially different histories are treated as exchangeable; deleting pre-current exposure history leaves the result unchanged. | Unknown long-tail carryover is a structural identification gap. The package specifies refusal or bounds; it does not invent a washout horizon. |
| Version-specific versus mixture versus dynamic-regime estimand | Use a version-specific estimand for a claim about one named `A_v`; a mixture estimand only when the target distribution `g(v)` over versions is itself declared and stable; and a dynamic-regime estimand when the intervention is a rule `π(H_t) → A_t`. Ambiguity among these objects makes the comparison unevaluable. | Exact claim object; version and rule identity; target population; exposure distribution; assignment history; intended versus realized regime; policy rule effective dates. | Changing the version distribution or decision rule leaves the claimed estimand identity unchanged; a mixture is reported as a single-version effect; or an adaptive regime is analyzed as a static treatment. | There is no domain-independent preferred estimand. Selection is claim-specific and must precede outcome inspection. |
| Pooling or equivalence across versions | Evidence for `v` never transfers to `v+1` by default. Pooling requires a predeclared equivalence claim over every causally material dimension: intervention content, eligibility, dose/exposure, decision rule, outcome definition, measurement pipeline and relevant context. The equivalence margin and test are fixed before observing comparative outcomes. | Content diff; bridge or dual-run evidence; version-by-effect interaction assessment; equivalence margin tied to the claim; exposure comparability; unchanged or explicitly bridged measurement. | Any material dimension changes without a bridge; the version-by-effect interaction exceeds the bound; the bridge fails; or removing the equivalence evidence still preserves the old claim. | Equivalence cannot be inferred from “small code change”, common name, overlapping confidence intervals, or absence of detected difference. |
| Unplanned adaptation: reset versus downgrade | Every unplanned adaptation creates a new version identity. A change to the causal object—construct, eligibility, exposure, decision rule, outcome, measurement relation or mechanism—resets confirmatory status for the changed object to `exploratory_only`. A bounded operational change may move the prior claim to `under_review` rather than reset it only when prospective equivalence evidence proves the claim object unchanged. | Classified version delta; claim dependency map; equivalence evidence; prospective decision record; affected population and exposure history. | A materially changed version retains `confirmatory_intact`; or a harmless operational change is declared equivalent solely by author assertion. | Whether a specific delta is causally material is domain evidence, not a repository-wide default. |
| Version-specific exploratory-to-confirmatory promotion and multiplicity | Promotion is a new prospective test: freeze the version or dynamic rule, estimand, endpoint, population, horizon, analysis and multiplicity family before collecting promotion evidence. Evidence generated while discovering the hypothesis or selecting the version stays exploratory. A later version does not inherit the promotion result. | Frozen promotion record; prospective sample/evidence start; version-specific analysis plan; family definition and multiplicity control; independent or design-based evidence; immutable history. | The same observations select and confirm a hypothesis; endpoints/subgroups/windows change after results; or `v+1` inherits `v`'s confirmatory status without a new test or valid equivalence bridge. | Production error rates and promotion thresholds remain domain-specific and are not selected by this amendment. |

### 2.2 Consequence for the amended package

The stage-1 statement that OPS-R7 was covered by retaining version and exposure fields is narrowed:
those fields are necessary but not sufficient. Any later architecture must implement the rules above
or continue to report the absorbed task as incomplete. No causal update may rely on a version comparison
whose estimand, assignment, history, stopping and promotion conditions are not established.

## 3. `AUD-F03` — Measurement Design For Residual Absorption

Audit defect: `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:109`.  
Disposition: `accepted_with_variation`.

The audit requested measurement design, not a fabricated prevalence. No sealed, independently
adjudicated domain holdout exists at the repository pin, so no performance result or acceptable
abstention threshold is claimed. The closure test remains unmet until the evaluation described here is
materialized and executed by a party independent of vocabulary authoring.

### 3.1 Evaluation population

The future evaluation set must be sealed before tuning and stratified at minimum across:

1. official-statistics or administrative series breaks and revisions;
2. online-experiment trust failures, including behavior-induced selection;
3. intervention delivery, eligibility and version divergence;
4. strategic and non-strategic behavioral response;
5. context, concurrent policy, spillover and control contamination;
6. delayed, censored, no-channel and zero-inclusion harm;
7. clean model-compatible and clean prediction-error controls.

Cases used to derive SMDV-1 or write decision rules are development cases, never holdout cases.
Synthetic mutations may supplement but cannot replace externally grounded cases. Oracle records need
independent case construction or blinded adjudication, explicit disagreement, and a route to
`nonidentified` where no unique class is supportable. This amendment specifies that role; it appoints no
adjudicator.

### 3.2 Required measurements

For consequence stratum `c` and substantive class `k`:

```text
coverage(c)
  = resolved_cases(c) / evaluable_cases(c)

selective_risk(c)
  = wrong_substantive_primary(c) / resolved_cases(c)

precision(k)
  = true_k / all_resolved_as_k

recall(k)
  = true_k / all_oracle_k

false_resolution(c)
  = resolved_when_oracle_nonidentified(c) / oracle_nonidentified(c)

false_abstention(c)
  = unresolved_when_oracle_unique(c) / oracle_unique(c)

blocking_contributor_recall(c)
  = detected_blocking_contributors(c) / oracle_blocking_contributors(c)
```

Report, without aggregate substitution:

- class-specific precision and recall;
- false-resolution and false-abstention rates;
- blocking-contributor recall;
- coverage and selective risk by domain and consequence;
- the full risk–coverage curve as confidence/abstention policy varies;
- unresolved reasons and missing-discriminator distribution;
- calibration of diagnosis confidence where confidence is emitted;
- time to correct routing, separately from classification accuracy.

A maximum tolerated unresolved rate is not set before these data exist.

### 3.3 Baselines and anti-degeneracy checks

The evaluator must compare SMDV-1 against at least:

- `D0_all_unresolved`: quarantine every evaluable movement;
- `D1_observation_trust_gate`: resolve only explicit observation-integrity failures and quarantine the
  remainder;
- a domain-local rule set where a mature source regime exists.

SMDV-1 must not be promoted merely because it has zero unsafe updates; `D0_all_unresolved` can obtain
that result while providing no discrimination. Promotion requires useful resolved coverage without
excess false resolution, reported by consequence class. No numbers are asserted in this amendment.

### 3.4 Registered acquisition gap

```yaml
holdout_artifact: absent/unallocated
sealed_oracle: absent/unallocated
independent_adjudication: not_established
performance_results: not_established
production_thresholds: not_established
closure_test_AUD-F03: unmet
```

What would settle it: a committed immutable case set or controlled external case store, content hashes,
sealed expected records, independent adjudication provenance, an evaluator, and a published
risk–coverage report.

## 4. `AUD-F04` — Admission Order And Mandatory Contributor Routing

Audit defect: `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:110`.  
Disposition: `accepted`.

The stage-1 0–6 sequence is superseded as a claim of global causal precedence. Observation validity
retains priority as an admission gate for substantive learning. Intervention/version,
context/interference and behavior are peer diagnostic gates after observation validity; no universal
order among those three is asserted.

### 4.1 Five-field amended shape

```yaml
admission_gate_order:
  - comparison_identity_and_maturity
  - observation_process_validity
  - peer_substantive_gates:
      - intervention_delivery_or_version
      - context_or_interference
      - behavioral_paths
  - predictive_compatibility
  - unresolved_if_no_supported_unique_routing_disposition

primary_routing_disposition: <the disposition controlling the requested consumer operation>
contributing_classes: [<all supported non-primary classes>]
blocking_contributors: [<contributors that deny the requested operation>]
mandatory_contributor_lane_obligations:
  - class: <supported class>
    required_lane: <measurement | delivery | behavior | context | model | acquisition>
    obligation_status: <open | satisfied | superseded | explicitly_not_applicable>
    evidence_refs: [...]
    route_or_missing_owner: <route | no_owner_exists>
```

`primary_routing_disposition` is not a declaration that one physical cause “wins.” It identifies the
disposition controlling a particular requested operation. The same diagnosis may therefore have a
different controlling disposition for causal learning and for protective response.

### 4.2 Consumer invariants

For every supported contributor:

```text
retain contributor
AND create or link its mandatory lane obligation
AND record route/owner or explicit absence
AND prevent closure until obligation is satisfied, superseded, or proven not applicable
```

A consumer that reads only `primary_routing_disposition` is non-conforming. A blocking contributor
blocks the named learning or write operation even when it is not primary. Conflicting supported routes
that cannot be separated produce `diagnosis_unresolved`.

### 4.3 Mixed behavior–observation divergent case

```yaml
observed_path:
  - policy_variant
  - genuine_behavioral_response
  - changed_inclusion_or_filtering_probability
  - biased_observed_sample

primary_routing_disposition_for_effect_update: observation_process_change
contributing_classes:
  - behavioral_response
blocking_contributors:
  - observation_process_change
mandatory_contributor_lane_obligations:
  - measurement_or_selection_repair
  - behavior_or_mechanism_review
effect_posterior_mutation: forbidden
```

The observation lane blocks causal learning until a valid independent bridge exists. The behavior lane
is nevertheless mandatory because the policy changed a substantive mechanism as well as the
observation path. An implementation that refreshes measurement but silently drops mechanism review
fails this case.

### 4.4 Consequence for prior package text

The former fixed precedence among intervention/version, context/interference and behavior is withdrawn.
The class meanings, contributor retention, unresolved terminal, and observation-first validity gate are
preserved. Later architecture must encode lane obligations as an enforceable consumer property, not as
an optional field.
